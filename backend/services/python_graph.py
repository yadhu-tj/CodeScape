"""Build a static, confidence-tagged graph from cached Python syntax trees."""

from ast import literal_eval
from collections import defaultdict
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path, PurePosixPath
import tokenize

from tree_sitter import Language, Node, Parser
import tree_sitter_python

from .repository_snapshot import RepositoryInputError


LANGUAGE = Language(tree_sitter_python.language())
DEFINITIONS = {"function_definition", "class_definition"}
COMPOUND_BLOCKS = {
    "if_statement", "for_statement", "while_statement", "try_statement", "match_statement",
    "with_statement",
}
DECISIONS = {
    "if_statement", "elif_clause", "for_statement", "while_statement", "except_clause",
    "boolean_operator", "conditional_expression", "if_clause",
}
ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace", "api_route"}
COMPREHENSIONS = {"list_comprehension", "dictionary_comprehension", "set_comprehension", "generator_expression"}
MAX_GRAPH_NODES = 25_000
MAX_GRAPH_EDGES = 100_000
MAX_SYMBOL_TEXT = 64 * 1024 * 1024
MAX_REFERENCE_TEXT = 32 * 1024 * 1024


def text(node: Node) -> str:
    return node.text.decode("utf-8")


def named(node: Node, field_name: str) -> Node | None:
    return node.child_by_field_name(field_name)


def _literal(node: Node | None) -> str | None:
    if node is not None and node.type in {"string", "concatenated_string"}:
        try:
            value = literal_eval(text(node))
        except (SyntaxError, ValueError):
            return None
        if isinstance(value, str):
            return value.replace("\0", "\\x00")
    return None


def _docstring(body: Node) -> str | None:
    first = next((child for child in body.named_children if child.type != "comment"), None)
    if first is not None and first.type == "expression_statement":
        return _literal(first.named_child(0))
    return None


def _route(wrapper: Node) -> str | None:
    if wrapper.type != "decorated_definition":
        return None
    for decorator in wrapper.named_children:
        if decorator.type != "decorator":
            continue
        call = decorator.named_child(0)
        if call.type != "call":
            continue
        receiver = _dotted(named(call, "function"))
        if len(receiver) != 2 or receiver[0] not in {"app", "router"} or receiver[1] not in ROUTE_METHODS:
            continue
        for argument in named(call, "arguments").named_children:
            if argument.type == "comment":
                continue
            if argument.type == "keyword_argument":
                if text(named(argument, "name")) != "path":
                    continue
                argument = named(argument, "value")
            path = _literal(argument)
            if path is not None and len(path) <= 250:
                return path
            break
    return None


def _dotted(node: Node | None) -> tuple[str, ...]:
    parts = []
    while node is not None and node.type == "attribute":
        parts.append(text(named(node, "attribute")))
        node = named(node, "object")
    if node is not None and node.type == "identifier":
        return (text(node), *reversed(parts))
    return ()


def _walk(root: Node, stop: set[str] | None = None):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        if stop is None or node.type not in stop:
            stack.extend(reversed(node.named_children))


def _complexity(body: Node) -> int:
    return 1 + sum(
        node.type in DECISIONS
        for node in _walk(body, DEFINITIONS | {"decorated_definition", "lambda"})
    )


@dataclass(frozen=True)
class Symbol:
    kind: str
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int
    body_text: str
    signature: str | None = None
    docstring: str | None = None
    route_path: str | None = None
    complexity: int = 1


@dataclass(frozen=True)
class Reference:
    source: int
    destination: int | None
    kind: str
    confidence: str
    line: int
    expression: str


@dataclass(frozen=True)
class ImportTarget:
    name: str
    package: str | None = None
    binds_root: bool = False
    offset: int = field(default=0, compare=False)
    scope_symbol: int | None = field(default=None, compare=False)


Binding = int | ImportTarget | None
MemberTrail = frozenset[tuple[int, tuple[str, ...]]]
LookupSite = tuple[int, int]


@dataclass
class Scope:
    symbol: int
    package: str
    parent: int | None
    body: Node
    bindings: dict[str, list[Binding]] = field(default_factory=lambda: defaultdict(list))
    binding_offsets: dict[str, int] = field(default_factory=dict)
    receiver: str | None = None
    base_expressions: list[Node] = field(default_factory=list)
    bases: list[int | None] = field(default_factory=list)


def _static_root(value: str) -> PurePosixPath:
    if value != "." and (
        any(part in {"", ".", ".."} for part in value.split("/"))
        or any(character in value for character in "\\:\0")
    ):
        raise RepositoryInputError("Static import root must be a repository-relative directory; use '/' between folders.")
    return PurePosixPath(value)


def _module_name(relative: PurePosixPath) -> tuple[str, str]:
    parts = relative.with_suffix("").parts
    package = ".".join(parts[:-1])
    module = package if parts[-1] == "__init__" and package else ".".join(parts)
    return module, package


def _end_line(node: Node) -> int:
    row, column = node.end_point
    return max(node.start_point.row + 1, row + bool(column))


def _parameter_name(node: Node) -> str | None:
    target = named(node, "name")
    if target is not None:
        return text(target)
    if node.type in {"typed_parameter", "list_splat_pattern", "dictionary_splat_pattern"}:
        return _parameter_name(node.named_child(0))
    return text(node) if node.type == "identifier" else None


def _assignment_targets(node: Node | None):
    stack = [node] if node is not None else []
    while stack:
        target = stack.pop()
        if target.type in {"identifier", "attribute"}:
            yield target
        elif target.type in {
            "pattern_list", "tuple_pattern", "list_pattern", "list_splat_pattern", "as_pattern_target",
            "tuple", "list", "list_splat", "expression_list", "parenthesized_expression",
        }:
            stack.extend(target.named_children)


def _binding_names(node: Node | None):
    return (text(target) for target in _assignment_targets(node) if target.type == "identifier")


class PythonGraph:
    def __init__(self, import_root: str = ".") -> None:
        self.import_root = _static_root(import_root)
        self.symbols: list[Symbol] = []
        self.references: list[Reference] = []
        self.scopes: list[Scope] = []
        self.modules: dict[str, list[int]] = defaultdict(list)
        self.imports: list[tuple[Scope, Node, ImportTarget, str]] = []
        self.calls: list[tuple[Scope, Node, frozenset[str]]] = []
        self.attribute_writes: list[tuple[Scope, tuple[str, ...], int, bool]] = []
        self.mutated_members: dict[tuple[int, str], list[LookupSite]] = {}
        self.method_orders: dict[int, tuple[int, ...] | None] = {}
        self.symbol_text_size = 0
        self.reference_text_size = 0

    def _add_scope(self, symbol: Symbol, body: Node, package: str, parent: int | None) -> Scope:
        self.symbol_text_size += len(symbol.body_text.encode("utf-8"))
        if (len(self.symbols) >= MAX_GRAPH_NODES or self.symbol_text_size > MAX_SYMBOL_TEXT
                or len(symbol.qualified_name) > 350):
            raise RepositoryInputError("Repository exceeds the supported graph or symbol limit.")
        scope = Scope(len(self.symbols), package, parent, body)
        self.symbols.append(symbol)
        self.scopes.append(scope)
        return scope

    def _definition(self, wrapper: Node, owner: Scope, conditional: bool) -> None:
        node = named(wrapper, "definition") if wrapper.type == "decorated_definition" else wrapper
        name = text(named(node, "name"))
        body = named(node, "body")
        colon = next(child for child in reversed(node.children) if child.type == ":")
        kind = "function" if node.type == "function_definition" else "class"
        parent = self.symbols[owner.symbol]
        scope = self._add_scope(
            Symbol(
                kind, f"{parent.qualified_name}.{name}", parent.file_path,
                wrapper.start_point.row + 1, _end_line(wrapper), text(wrapper),
                node.text[:colon.end_byte - node.start_byte].decode("utf-8"),
                _docstring(body), _route(wrapper) if kind == "function" else None,
                _complexity(body) if kind == "function" else 1,
            ),
            body, owner.package, owner.symbol,
        )
        owner.bindings[name].append(scope.symbol)
        owner.binding_offsets.setdefault(name, wrapper.end_byte)
        if conditional:
            owner.bindings[name].append(None)
        if kind == "function":
            parameters = [
                parameter for child in named(node, "parameters").named_children
                if (parameter := _parameter_name(child)) is not None
            ]
            for parameter in parameters:
                scope.bindings[parameter].append(None)
            if parent.kind == "class":
                decorators = {text(child).split("(", 1)[0].strip() for child in wrapper.named_children
                              if child.type == "decorator"}
                if parameters and "@staticmethod" not in decorators:
                    scope.receiver = parameters[0]
        else:
            bases = named(node, "superclasses")
            if bases is not None:
                scope.base_expressions = [
                    child for child in bases.named_children if child.type not in {"keyword_argument", "comment"}
                ]

    def _imports(self, scope: Scope, node: Node, conditional: bool) -> None:
        module_node = named(node, "module_name")
        module = "".join(text(module_node).split()) if module_node is not None else ""
        if node.type == "future_import_statement":
            module = "__future__"
        if module.startswith("."):
            level = len(module) - len(module.lstrip("."))
            package = scope.package.split(".") if scope.package else []
            if level > len(package):
                module = "<outside-package>"
            else:
                module = ".".join([*package[:len(package) - level + 1], module[level:]]).rstrip(".")
        for name_node in node.children_by_field_name("name"):
            alias = named(name_node, "alias")
            original = named(name_node, "name") if alias is not None else name_node
            imported = "".join(text(original).split())
            target = f"{module}.{imported}" if module else imported
            binding = imported.split(".", 1)[0] if alias is None else text(alias)
            imported_target = ImportTarget(
                target, package=module or None, binds_root=not module and alias is None, offset=node.end_byte,
                scope_symbol=scope.symbol,
            )
            scope.bindings[binding].append(imported_target)
            if conditional:
                scope.bindings[binding].append(None)
            self.imports.append((scope, node, imported_target, text(name_node)))
        if any(child.type == "wildcard_import" for child in node.named_children):
            scope.bindings["*"].append(None)
            self.imports.append((scope, node, ImportTarget(module), text(node)))

    def _record_assignment(self, scope: Scope, target: Node | None, offset: int, conditional: bool) -> None:
        for item in _assignment_targets(target):
            if item.type == "identifier":
                scope.bindings[text(item)].append(None)
            elif parts := _dotted(item):
                self.attribute_writes.append((scope, parts, offset, conditional))

    def _collect_references(self, scope: Scope) -> None:
        stack = [(scope.body, False, frozenset())]
        while stack:
            node, conditional, hidden = stack.pop()
            kind = node.type
            if kind in DEFINITIONS or kind == "decorated_definition":
                definition = named(node, "definition") if kind == "decorated_definition" else node
                body = named(definition, "body")
                name = named(definition, "name")
                headers = [child for child in definition.named_children if child != body and child != name]
                if kind == "decorated_definition":
                    headers = [child for child in node.named_children if child.type == "decorator"] + headers
                stack.extend((child, conditional, hidden) for child in reversed(headers))
                continue
            if kind in {"import_statement", "import_from_statement", "future_import_statement"}:
                self._imports(scope, node, conditional)
                continue
            if kind in {"global_statement", "nonlocal_statement", "delete_statement"}:
                for child in node.named_children:
                    self._record_assignment(scope, child, node.end_byte, conditional)
            if kind in {"assignment", "augmented_assignment", "named_expression", "for_statement", "as_pattern"}:
                target_fields = {"named_expression": "name", "as_pattern": "alias"}
                write_is_conditional = conditional or kind in {"for_statement", "as_pattern"}
                self._record_assignment(
                    scope, named(node, target_fields.get(kind, "left")), node.end_byte, write_is_conditional,
                )
            if kind == "case_clause":
                # Match captures may shadow any same-named callable in this scope.
                pattern = next((child for child in node.named_children if child.type == "case_pattern"), None)
                if pattern is not None:
                    for child in _walk(pattern):
                        if child.type == "identifier":
                            scope.bindings[text(child)].append(None)
            if kind == "call":
                self.calls.append((scope, node, hidden))
            if len(self.calls) + len(self.imports) > MAX_GRAPH_EDGES:
                raise RepositoryInputError("Repository exceeds the supported graph edge limit.")
            if kind in COMPREHENSIONS:
                first_for = next(child for child in node.named_children if child.type == "for_in_clause")
                first_iterable = named(first_for, "right")
                outer_hidden = hidden
                hidden |= frozenset(
                    name for child in node.named_children if child.type == "for_in_clause"
                    for name in _binding_names(named(child, "left"))
                )
                stack.extend((child, conditional, hidden) for child in reversed(node.named_children)
                             if child != first_for)
                stack.extend(
                    (child, conditional, hidden) for child in reversed(first_for.named_children)
                    if child != first_iterable
                )
                # The first iterator runs before the comprehension binds its names.
                stack.append((first_iterable, conditional, outer_hidden))
                continue
            if kind == "lambda":
                parameters = named(node, "parameters")
                if parameters is not None:
                    hidden |= frozenset(filter(None, map(_parameter_name, parameters.named_children)))
            conditional |= kind in COMPOUND_BLOCKS
            stack.extend((child, conditional, hidden) for child in reversed(node.named_children))

    def add_file(self, relative: str, source: bytes, parser: Parser) -> None:
        try:
            encoding, _ = tokenize.detect_encoding(BytesIO(source).readline)
            source = source.decode(encoding).encode("utf-8")
        except (SyntaxError, UnicodeError, LookupError):
            raise RepositoryInputError(f"Unable to decode Python source: {relative}") from None
        root = parser.parse(source).root_node
        if root.has_error or b"\0" in source:
            raise RepositoryInputError(f"Invalid or unsupported Python syntax: {relative}")
        file_path = PurePosixPath(relative)
        importable = file_path.is_relative_to(self.import_root)
        module, package = _module_name(file_path.relative_to(self.import_root) if importable else file_path)
        scope = self._add_scope(
            Symbol("file", module, relative, 1, _end_line(root), source.decode("utf-8"),
                   docstring=_docstring(root)),
            root, package if importable else "", None,
        )
        if importable:
            self.modules[module].append(scope.symbol)

    @staticmethod
    def _unique(values):
        values = set(values)
        return next(iter(values)) if len(values) == 1 else None

    def _module_candidates(self, name: str) -> list[int]:
        parts = name.split(".")
        for depth in range(1, len(parts)):
            ancestor = self.modules.get(".".join(parts[:depth]), [])
            if ancestor and (
                len(ancestor) != 1
                or PurePosixPath(self.symbols[ancestor[0]].file_path).name != "__init__.py"
            ):
                # A regular module blocks submodule lookup. An unindexed ancestor can be a namespace package.
                return []
        return self.modules.get(name, [])

    def _member_changed(self, owner: int, member: str, site: LookupSite | None) -> bool:
        return any(
            site is None or origin != site[0] or position <= site[1]
            for origin, position in self.mutated_members.get((owner, member), ())
        )

    def _module_path_changed(self, path: tuple[str, ...], site: LookupSite | None) -> bool:
        if not self.mutated_members:
            return False
        for depth, member in enumerate(path[1:], 1):
            parent = self._unique(self._module_candidates(".".join(path[:depth])))
            if parent is not None and self._member_changed(parent, member, site):
                return True
        return False

    def _import_target(
        self, target: ImportTarget, seen: MemberTrail, site: LookupSite | None = None,
    ) -> int | None:
        if self._module_path_changed(tuple(target.name.split(".")), site):
            return None
        modules = self._module_candidates(target.name)
        if len(modules) > 1:
            return None
        module = modules[0] if modules else None
        if target.package is None:
            return module

        packages = self._module_candidates(target.package)
        if len(packages) > 1:
            return None
        if not packages:
            return module
        member = target.name.rsplit(".", 1)[-1]
        scope = self.scopes[packages[0]]
        bindings = set(scope.bindings.get(member, []))
        if "*" in scope.bindings and not bindings:
            return None
        # A package can expose its submodule with "from . import submodule".
        if not bindings or bindings == {target}:
            return module
        value = self._members(scope.symbol, (member,), seen, site)
        return value if module is None or value == module else None

    def _follow_binding(
        self, bindings: list[Binding], parts: tuple[str, ...], seen: MemberTrail, site: LookupSite | None,
    ) -> int | None:
        if not bindings or None in bindings:
            return None
        target = self._unique(bindings)
        if isinstance(target, int):
            return self._members(target, parts, seen, site)
        if isinstance(target, ImportTarget) and not target.binds_root:
            index = self._unique(
                self._import_target(binding, seen, (binding.scope_symbol, binding.offset))
                for binding in bindings
            )
            return self._members(index, parts, seen, site) if index is not None else None
        if not all(isinstance(binding, ImportTarget) and binding.binds_root for binding in bindings):
            return None

        # An unaliased dotted import exposes its module and ancestors, not siblings.
        root = bindings[0].name.split(".", 1)[0]
        requested = (root, *parts)
        max_depth = max(binding.name.count(".") + 1 for binding in bindings)
        for length in range(min(max_depth, len(requested)), 0, -1):
            name = ".".join(requested[:length])
            if name in self.modules and any(
                binding.name == name or binding.name.startswith(name + ".") for binding in bindings
            ):
                index = self._unique(self._module_candidates(name))
                if index is not None and not self._module_path_changed(requested[:length], site):
                    return self._members(index, requested[length:], seen, site)
                return None
        return None

    def _members(
        self, index: int, parts: tuple[str, ...], seen: MemberTrail, site: LookupSite | None,
    ) -> int | None:
        if not parts:
            return index
        key = index, parts
        if (key in seen or len(seen) >= 64 or self.symbols[index].kind == "function"
                or self._member_changed(index, parts[0], site)):
            return None
        bindings = self.scopes[index].bindings.get(parts[0], [])
        return self._follow_binding(bindings, parts[1:], seen | {key}, site)

    def _bindings(self, scope: Scope, name: str, offset: int | None) -> list[Binding]:
        while True:
            if name in scope.bindings or "*" in scope.bindings:
                if offset is not None and offset < scope.binding_offsets.get(name, 0):
                    return []
                return [
                    binding for binding in scope.bindings.get(name, [])
                    if not isinstance(binding, ImportTarget) or offset is None or binding.offset <= offset
                ]
            parent = scope.parent
            while parent is not None and self.symbols[parent].kind == "class":
                parent = self.scopes[parent].parent
            if parent is None:
                return []
            scope = self.scopes[parent]
            offset = None

    def _resolve(self, scope: Scope, parts: tuple[str, ...], offset: int) -> int | None:
        return self._follow_binding(
            self._bindings(scope, parts[0], offset), parts[1:], frozenset(), (scope.symbol, offset),
        )

    def _index_attribute_writes(self) -> None:
        writes: dict[tuple[int, str], list[LookupSite]] = defaultdict(list)
        for scope, parts, offset, conditional in self.attribute_writes:
            owner = self._resolve(scope, parts[:-1], offset)
            if (owner is None and parts[:-1] == (scope.receiver,)
                    and len(scope.bindings[scope.receiver]) == 1):
                owner = scope.parent
            if owner is not None:
                # A conditional write may run before a lexically earlier call on a later loop iteration.
                writes[owner, parts[-1]].append((scope.symbol, 0 if conditional else offset))
        self.mutated_members = writes

    def _add_reference(self, scope: Scope, node: Node, target: int | None, kind: str,
                       expression: str, confidence: str = "confirmed") -> None:
        self.reference_text_size += len(expression.encode("utf-8"))
        if len(self.references) >= MAX_GRAPH_EDGES or self.reference_text_size > MAX_REFERENCE_TEXT:
            raise RepositoryInputError("Repository exceeds the supported graph edge limit.")
        self.references.append(Reference(
            scope.symbol, target, kind, confidence if target is not None else "unresolved",
            node.start_point.row + 1, expression,
        ))

    def _linearized_bases(self, owner: int, seen: frozenset[int] = frozenset()) -> tuple[int, ...] | None:
        if owner in self.method_orders:
            return self.method_orders[owner]
        if owner in seen or len(seen) >= 64:
            return None
        bases = self.scopes[owner].bases
        if None in bases or len(bases) != len(set(bases)):
            return None
        pending = []
        for base in bases:
            order = self._linearized_bases(base, seen | {owner})
            if order is None:
                return None
            pending.append(list(order))
        if bases:
            pending.append(list(bases))

        # C3 chooses the first head that does not occur in any remaining tail.
        order = [owner]
        while pending:
            tails = {item for chain in pending for item in chain[1:]}
            head = next((chain[0] for chain in pending if chain[0] not in tails), None)
            if head is None or len(order) >= 256:
                return None
            order.append(head)
            for chain in pending:
                if chain[0] == head:
                    chain.pop(0)
            pending = [chain for chain in pending if chain]
        result = tuple(order)
        self.method_orders[owner] = result
        return result

    def _method(self, owner: int, name: str, site: LookupSite) -> int | None:
        if name in self.scopes[owner].bindings:
            order = (owner,)
        else:
            order = self._linearized_bases(owner)
            self.method_orders[owner] = order
        for index in order or (owner,):
            if self._member_changed(index, name, site):
                return None
            bindings = self.scopes[index].bindings
            if name in bindings:
                target = self._unique(bindings[name])
                return target if isinstance(target, int) and self.symbols[target].kind == "function" else None
        return None

    def collect_symbols(self) -> None:
        for scope in self.scopes:
            # The list grows as definitions are found. Their cached bodies are visited once each.
            stack = [(scope.body, False)]
            while stack:
                node, conditional = stack.pop()
                if node.type in DEFINITIONS or node.type == "decorated_definition":
                    self._definition(node, scope, conditional)
                    continue
                conditional |= node.type in COMPOUND_BLOCKS
                stack.extend((child, conditional) for child in reversed(node.named_children))

    def resolve_references(self) -> None:
        for scope in self.scopes:
            self._collect_references(scope)
        self._index_attribute_writes()
        for scope, node, target, expression in self.imports:
            site = (scope.symbol, node.start_byte)
            self._add_reference(scope, node, self._import_target(target, frozenset(), site), "imports", expression)
        for scope in self.scopes:
            for base in scope.base_expressions:
                expression = base.named_child(0) if base.type == "subscript" else base
                parts = _dotted(expression)
                target = None
                if parts:
                    target = self._resolve(self.scopes[scope.parent], parts, base.start_byte)
                if target is not None and self.symbols[target].kind != "class":
                    target = None
                explicit_object = (
                    len(scope.base_expressions) == 1 and base.type == "identifier" and parts == ("object",)
                    and not self._bindings(self.scopes[scope.parent], "object", base.start_byte)
                )
                if not explicit_object:
                    scope.bases.append(target)
                self._add_reference(scope, base, target, "inherits", text(base))
        for scope, call, hidden in self.calls:
            parts = _dotted(named(call, "function"))
            target = None
            confidence = "confirmed"
            if parts and parts[0] not in hidden:
                target = self._resolve(scope, parts, call.start_byte)
                if target is not None and self.symbols[target].kind == "file":
                    target = None
                if (len(parts) == 2 and target is None and parts[0] == scope.receiver
                        and len(scope.bindings[scope.receiver]) == 1):
                    confidence = "probable"
                    target = self._method(scope.parent, parts[1], (scope.symbol, call.start_byte))
            self._add_reference(scope, call, target, "calls", text(call), confidence)


def analyze_snapshot(path: Path, import_root: str = ".") -> PythonGraph:
    parser = Parser(LANGUAGE)
    graph = PythonGraph(import_root)
    if not (path / graph.import_root).is_dir():
        raise RepositoryInputError("Static import root does not exist in the repository snapshot.")
    for file in sorted(path.rglob("*")):
        if file.is_file() and file.suffix.lower() == ".py":
            graph.add_file(file.relative_to(path).as_posix(), file.read_bytes(), parser)
    if not graph.modules:
        raise RepositoryInputError("Static import root contains no included Python files.")
    try:
        graph.collect_symbols()
    except RecursionError:
        raise RepositoryInputError("Repository exceeds the supported scope nesting limit.") from None
    return graph
