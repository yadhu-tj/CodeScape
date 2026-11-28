import hashlib
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

if importlib.util.find_spec("tree_sitter_python") is None:
    raise unittest.SkipTest("Phase 2 tests require the backend dependencies.")

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from tree_sitter import Parser

from backend.main import create_app
from backend.models import Node, Repo
from backend.services import repository_snapshot
from backend.services.python_graph import LANGUAGE, PythonGraph, analyze_snapshot
from backend.services.repository_snapshot import RepositoryInputError, SHOWCASE, acquire_snapshot


def parse(sources: dict[str, str]) -> PythonGraph:
    graph = PythonGraph()
    parser = Parser(LANGUAGE)
    for relative, source in sources.items():
        graph.add_file(relative, source.encode(), parser)
    graph.collect_symbols()
    graph.resolve_references()
    return graph


def edges(graph: PythonGraph):
    return {
        (graph.symbols[edge.source].qualified_name, edge.expression): (
            graph.symbols[edge.destination].qualified_name if edge.destination is not None else None,
            edge.confidence,
        )
        for edge in graph.references if edge.kind == "calls"
    }


class ParserTests(unittest.TestCase):
    def test_showcase_matches_manifest(self):
        manifest = json.loads((SHOWCASE.parent / "ground_truth.json").read_text(encoding="utf-8"))
        graph = analyze_snapshot(SHOWCASE)
        graph.resolve_references()
        self.assertEqual(sum(symbol.kind == "file" for symbol in graph.symbols), manifest["python_files"])
        self.assertEqual(
            sorted(symbol.qualified_name for symbol in graph.symbols if symbol.kind == "function"),
            sorted(manifest["function_symbols"]),
        )
        self.assertEqual(
            {symbol.qualified_name: symbol.route_path for symbol in graph.symbols if symbol.route_path is not None},
            {route["symbol"]: route["path"] for route in manifest["route_entrypoints"]},
        )
        calls = edges(graph)
        for site in manifest["selected_call_sites"]:
            self.assertEqual(calls[site["source_symbol"], site["expression"]],
                             (site["target_symbol"], site["confidence"]))
        self.assertTrue(all(edge.line > 0 for edge in graph.references))

    def test_complexity_constructs_and_nested_scope(self):
        sources = {
            "branch": "if x: pass\n    elif y: pass\n    else: pass",
            "loops": "for x in xs: pass\n    async for x in xs: pass\n    while x: pass",
            "handlers": "try: pass\n    except ValueError: pass\n    except TypeError: pass",
            "boolean": "return (a and b and c) or d",
            "ternary": "return a if b else c",
            "comprehension": "return [x for x in xs if x if y]",
            "match_subject": "match x:\n        case 1: pass\n        case _: pass",
            "nested": "def inner():\n        if x: pass",
        }
        graph = parse({
            "example.py": "\n".join(f"async def {name}():\n    {body}\n" for name, body in sources.items())
        })
        self.assertEqual(
            {symbol.qualified_name.removeprefix("example."): symbol.complexity
             for symbol in graph.symbols if symbol.kind == "function"},
            {"branch": 3, "loops": 4, "handlers": 3, "boolean": 4, "ternary": 2, "comprehension": 3,
             "match_subject": 1, "nested": 1, "nested.inner": 2},
        )

    def test_relative_aliases_shadowing_inheritance_and_dynamic_calls(self):
        graph = parse({
            "package/base.py": "def work(): pass\nclass Base:\n    def check(self): pass\n",
            "package/deep/other.py": "def work(): pass\n",
            "package/deep/task.py": (
                "from ..base import Base, work as run\n"
                "from . import other as alias\n"
                "from external import missing\n"
                "class Task(Base):\n"
                "    def handle(self):\n"
                "        return self.check()\n"
                "def call():\n"
                "    run()\n"
                "    alias.work()\n"
                "    missing()\n"
                "    task_registry[0]()\n"
                "    getattr(alias, 'work')()\n"
                "def shadow(run):\n"
                "    run()\n"
                "def comp():\n"
                "    return [run() for run in run()]\n"
                "def local():\n"
                "    from ..base import work as run_local\n"
                "    run_local()\n"
                "def guessed(receiver):\n"
                "    receiver.check()\n"
            ),
        })
        calls = edges(graph)
        label = "package.deep.task"
        self.assertEqual(calls[f"{label}.call", "run()"], ("package.base.work", "confirmed"))
        self.assertEqual(calls[f"{label}.call", "alias.work()"], ("package.deep.other.work", "confirmed"))
        self.assertEqual(calls[f"{label}.local", "run_local()"], ("package.base.work", "confirmed"))
        self.assertEqual(calls[f"{label}.Task.handle", "self.check()"], ("package.base.Base.check", "probable"))
        self.assertEqual(calls[f"{label}.guessed", "receiver.check()"], (None, "unresolved"))
        self.assertEqual(calls[f"{label}.shadow", "run()"], (None, "unresolved"))
        for expression in ("missing()", "task_registry[0]()", "getattr(alias, 'work')()"):
            self.assertEqual(calls[f"{label}.call", expression], (None, "unresolved"))
        self.assertEqual(
            {edge.confidence for edge in graph.references
             if graph.symbols[edge.source].qualified_name == f"{label}.comp" and edge.expression == "run()"},
            {"confirmed", "unresolved"},
        )
        inheritance = [edge for edge in graph.references if edge.kind == "inherits"]
        self.assertEqual(len(inheritance), 1)
        self.assertEqual(graph.symbols[inheritance[0].destination].qualified_name, "package.base.Base")

    def test_decorated_symbol_preserves_exact_span(self):
        source = '# first\n@router.get(path="/item")\nasync def route(x: int = 2) -> str:\n    """Doc."""\n    return str(x)\n'
        graph = parse({"api.py": source})
        symbol = graph.symbols[1]
        self.assertEqual((symbol.start_line, symbol.end_line), (2, 5))
        self.assertEqual(symbol.signature, "async def route(x: int = 2) -> str:")
        self.assertEqual(symbol.docstring, "Doc.")
        self.assertEqual(symbol.body_text, source.split("\n", 1)[1].rstrip("\n"))
        self.assertEqual(symbol.route_path, "/item")

    def test_function_locals_do_not_become_attributes_or_bind_early(self):
        graph = parse({
            "helpers.py": "def run(): pass\n",
            "main.py": (
                "def outer():\n"
                "    run()\n"
                "    from helpers import run\n"
                "    run()\n"
                "    def inner(): pass\n"
                "outer.inner()\n"
            ),
        })
        self.assertEqual(edges(graph)["main", "outer.inner()"], (None, "unresolved"))
        self.assertEqual(
            [(edge.line, edge.confidence) for edge in graph.references if edge.expression == "run()"],
            [(2, "unresolved"), (4, "confirmed")],
        )

    def test_dotted_imports_expose_only_loaded_submodules(self):
        graph = parse({
            "pkg/__init__.py": "from . import exported\n",
            "pkg/a.py": "def run(): pass\n",
            "pkg/b.py": "def run(): pass\n",
            "pkg/exported.py": "def run(): pass\n",
            "main.py": (
                "import pkg.a\n"
                "pkg.a.run()\n"
                "pkg.b.run()\n"
                "pkg.exported.run()\n"
                "import pkg.b\n"
                "pkg.b.run()\n"
            ),
            "aliased.py": "import pkg as alias\nalias.a.run()\nalias.exported.run()\n",
        })
        self.assertEqual(
            [(graph.symbols[edge.source].file_path, edge.line, edge.confidence)
             for edge in graph.references if edge.kind == "calls"],
            [("main.py", 2, "confirmed"), ("main.py", 3, "unresolved"),
             ("main.py", 4, "confirmed"), ("main.py", 6, "confirmed"),
             ("aliased.py", 2, "unresolved"), ("aliased.py", 3, "confirmed")],
        )

    def test_ambiguous_module_and_package_member_stays_unresolved(self):
        graph = parse({
            "pkg/__init__.py": "def worker(): pass\n",
            "pkg/worker.py": "def run(): pass\n",
            "main.py": "from pkg import worker\nworker()\nworker.run()\n",
        })
        calls = edges(graph)
        self.assertEqual(calls["main", "worker()"], (None, "unresolved"))
        self.assertEqual(calls["main", "worker.run()"], (None, "unresolved"))

    def test_module_shadowing_blocks_imports_through_namespace_directory(self):
        for package_file, confidence in (
            ("pkg.py", "unresolved"), ("pkg/__init__.py", "confirmed"), (None, "confirmed"),
        ):
            with self.subTest(package_file=package_file):
                sources = {
                    "pkg/sub.py": "def run(): pass\n",
                    "direct.py": "import pkg.sub\npkg.sub.run()\n",
                    "aliased.py": "import pkg.sub as sub\nsub.run()\n",
                    "from_member.py": "from pkg.sub import run\nrun()\n",
                    "from_module.py": "from pkg import sub\nsub.run()\n",
                }
                if package_file:
                    sources[package_file] = "pass\n"
                graph = parse(sources)
                target = "pkg.sub.run" if confidence == "confirmed" else None
                self.assertEqual(edges(graph), {
                    ("direct", "pkg.sub.run()"): (target, confidence),
                    ("aliased", "sub.run()"): (target, confidence),
                    ("from_member", "run()"): (target, confidence),
                    ("from_module", "sub.run()"): (target, confidence),
                })
                imports = [edge for edge in graph.references if edge.kind == "imports"]
                self.assertEqual(len(imports), 4)
                self.assertTrue(all(edge.confidence == confidence for edge in imports))

    def test_attribute_writes_invalidate_the_original_target_through_import_aliases(self):
        graph = parse({
            "helpers.py": "def run(): pass\ndef intact(): pass\n",
            "main.py": (
                "import helpers\n"
                "import helpers as alias\n"
                "from helpers import run as saved\n"
                "def replacement(): pass\n"
                "helpers.run()\n"
                "helpers.run = replacement\n"
                "helpers.run()\n"
                "alias.run()\n"
                "alias.intact()\n"
                "del alias.intact\n"
                "helpers.intact()\n"
                "saved()\n"
                "from helpers import run as saved\n"
                "saved()\n"
            ),
        })
        calls = [
            (edge.line, graph.symbols[edge.destination].qualified_name if edge.destination is not None else None,
             edge.confidence)
            for edge in graph.references if edge.kind == "calls"
        ]
        self.assertEqual(calls, [
            (5, "helpers.run", "confirmed"), (7, None, "unresolved"),
            (8, None, "unresolved"), (9, "helpers.intact", "confirmed"), (11, None, "unresolved"),
            (12, "helpers.run", "confirmed"), (14, None, "unresolved"),
        ])

    def test_multiple_inheritance_follows_python_method_resolution_order(self):
        graph = parse({
            "example.py": (
                "from external import Unknown\n"
                "class Root(object):\n"
                "    def run(self): pass\n"
                "class Left(Root): pass\n"
                "class Right:\n"
                "    def run(self): pass\n"
                "class Child(Left, Right):\n"
                "    def call(self): return self.run()\n"
                "class Reverse(Right, Left):\n"
                "    def call(self): return self.run()\n"
                "class Partial(Unknown, Left):\n"
                "    def call(self): return self.run()\n"
            ),
        })
        self.assertEqual(edges(graph), {
            ("example.Child.call", "self.run()"): ("example.Root.run", "probable"),
            ("example.Reverse.call", "self.run()"): ("example.Right.run", "probable"),
            ("example.Partial.call", "self.run()"): (None, "unresolved"),
        })

    def test_explicit_static_import_root_keeps_snapshot_paths(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for path, body in {
                "src/pkg/auth.py": "def verify(): pass",
                "src/pkg/service.py": "from pkg.auth import verify\nverify()",
                "pkg/auth.py": "def verify(): pass",
                "tests/test_service.py": "from pkg.auth import verify\nverify()",
            }.items():
                file = root / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(body, encoding="utf-8")
            graph = analyze_snapshot(root, "src")
            with self.assertRaisesRegex(RepositoryInputError, "repository-relative"):
                analyze_snapshot(root, "../src")
            with self.assertRaisesRegex(RepositoryInputError, "does not exist"):
                analyze_snapshot(root, "missing")
        graph.resolve_references()
        targets = {
            graph.symbols[edge.source].file_path: graph.symbols[edge.destination].file_path
            for edge in graph.references if edge.kind == "calls" and edge.destination is not None
        }
        self.assertEqual(targets, {
            "src/pkg/service.py": "src/pkg/auth.py",
            "tests/test_service.py": "src/pkg/auth.py",
        })
        self.assertIn("pkg.auth.verify", {symbol.qualified_name for symbol in graph.symbols
                                          if symbol.file_path == "src/pkg/auth.py"})


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.storage = self.root / "storage"
        self.source = self.root / "input"
        self.source.mkdir()
        (self.source / "app.py").write_bytes(b"def hello(): pass\r\n")

    def acquire(self, source="input"):
        return acquire_snapshot(source, self.storage, self.root, "github.com")

    def test_snapshot_filters_and_hashes_exact_bytes(self):
        (self.source / ".env.local").write_text("ignored", encoding="utf-8")
        (self.source / "secret.key").write_text("ignored", encoding="utf-8")
        (self.source / "__pycache__").mkdir()
        (self.source / "__pycache__" / "ignored.py").touch()
        first = self.acquire()
        second = self.acquire()
        self.assertNotEqual(first.path, second.path)
        self.assertEqual(first.source_sha256, second.source_sha256)
        original = b"def hello(): pass\r\n"
        expected = hashlib.sha256(b"\0\0\0\x06app.py" + len(original).to_bytes(8, "big") + original)
        self.assertEqual(first.source_sha256, expected.hexdigest())
        self.assertEqual([file.name for file in first.path.iterdir()], ["app.py"])
        self.assertEqual((first.path / "app.py").read_bytes(), original)
        (self.source / "app.py").write_bytes(b"def changed(): pass\n")
        self.assertNotEqual(first.source_sha256, self.acquire().source_sha256)
        self.assertEqual((first.path / "app.py").read_bytes(), original)

    def test_rejects_traversal_and_unsafe_clone_before_acquisition(self):
        for source in ("input/../input", str(self.root.parent), "file:///temp/test",
                       "https://user:token@github.com/owner/repo", "https://github.com/owner/../repo",
                       "https://github.com.evil.invalid/owner/repo"):
            with self.subTest(source=source), self.assertRaises(RepositoryInputError):
                self.acquire(source)
        self.assertFalse(self.storage.exists())

    def test_rejects_large_snapshot_and_cleans_up(self):
        with patch.object(repository_snapshot, "MAX_FILE_BYTES", 5):
            with self.assertRaisesRegex(RepositoryInputError, "limit"):
                self.acquire()
        self.assertEqual(list(self.storage.iterdir()), [])

    def test_rejects_included_symlink(self):
        try:
            (self.source / "alias.py").symlink_to(self.source / "app.py")
        except OSError:
            self.skipTest("Symlink creation is unavailable.")
        with self.assertRaisesRegex(RepositoryInputError, "link"):
            self.acquire()
        self.assertEqual(list(self.storage.iterdir()), [])


@unittest.skipUnless(os.environ.get("CODESCAPE_PHASE2_TEST_DATABASE_URL"), "Requires a migrated PostgreSQL test database.")
class RepositoryAPITests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        settings = patch.dict(os.environ, {
            "DATABASE_URL": os.environ["CODESCAPE_PHASE2_TEST_DATABASE_URL"],
            "REPOS_STORAGE_PATH": str(Path(temporary.name) / "snapshots"),
            "REPOS_IMPORT_ROOT": temporary.name,
            "AI_PROVIDER": "gemini",
            "GEMINI_API_KEY": "unit-test-placeholder",
        })
        self.addCleanup(settings.stop)
        settings.start()
        self.app = create_app(demo_mode=False)
        client = TestClient(self.app)
        self.client = client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)
        self.repo_ids = []
        self.addCleanup(self.client.portal.call, self.delete_repos)

    async def delete_repos(self):
        if self.repo_ids:
            async with self.app.state.database.sessions.begin() as db:
                await db.execute(delete(Repo).where(Repo.id.in_(self.repo_ids)))

    async def stored_embeddings(self, repo_id: int) -> int:
        async with self.app.state.database.sessions() as db:
            return await db.scalar(select(func.count(Node.embedding)).where(Node.repo_id == repo_id))

    def post_repo(self, payload=None):
        response = self.client.post("/api/v1/repos", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        repo = response.json()["data"]
        self.repo_ids.append(repo["id"])
        return repo

    def test_showcase_graph_roundtrip_and_local_search(self):
        repo = self.post_repo()
        self.assertEqual(len(repo["source_sha256"]), 64)
        self.assertEqual(repo["embedding_status"], "disabled")
        self.assertIn(repo, self.client.get("/api/v1/repos").json()["data"])
        graph = self.client.get(f"/api/v1/repos/{repo['id']}/graph").json()["data"]
        self.assertEqual(graph["summary"]["nodes_by_kind"], {"file": 18, "class": 2, "function": 54})
        self.assertEqual(graph["summary"]["route_count"], 11)
        self.assertEqual(set(graph["summary"]["calls_by_confidence"]), {"confirmed", "probable", "unresolved"})
        self.assertTrue(all("embedding" not in node for node in graph["nodes"]))
        search = self.client.post(f"/api/v1/repos/{repo['id']}/search", json={"query": "verify_signature"})
        self.assertEqual(search.json()["data"]["search_mode"], "lexical_fallback")
        self.assertEqual(search.json()["data"]["anchor_node"]["qualified_name"], "services.auth.verify_signature")
        self.assertEqual(self.client.get("/api/v1/repos/0/graph").status_code, 404)
        self.assertEqual(self.client.post("/api/v1/repos", json={"source": "../outside"}).status_code, 400)

    def test_embeddings_batch_and_fail_without_losing_graph(self):
        mock = AsyncMock()
        mock.embed_texts.side_effect = lambda batch: [[1.0] * 768 for _ in batch]
        with patch("backend.services.ingestion_service.GeminiProvider", return_value=mock):
            enriched = self.post_repo({"embed": True})
            self.assertEqual(enriched["embedding_status"], "ready")
            self.assertEqual([len(call.args[0]) for call in mock.embed_texts.await_args_list], [32, 24])
            self.assertEqual(self.client.portal.call(self.stored_embeddings, enriched["id"]), 56)
            mock.embed_texts.side_effect = [[[1.0] * 768] * 32, [[1.0]] * 24]
            failed = self.post_repo({"embed": True})
            self.assertEqual(failed["embedding_status"], "failed")
            self.assertEqual(self.client.portal.call(self.stored_embeddings, failed["id"]), 0)
        self.assertEqual(self.client.get(f"/api/v1/repos/{failed['id']}/graph").status_code, 200)

    def test_no_key_and_invalid_snapshot(self):
        with patch.object(self.app.state.settings, "GEMINI_API_KEY", None):
            unavailable = self.post_repo({"embed": True})
        self.assertEqual(unavailable["embedding_status"], "unavailable")
        self.assertEqual(self.client.portal.call(self.stored_embeddings, unavailable["id"]), 0)

        source = self.app.state.settings.REPOS_IMPORT_ROOT / "invalid"
        source.mkdir()
        (source / "broken.py").write_text("def (): ?", encoding="utf-8")
        snapshots = self.app.state.settings.REPOS_STORAGE_PATH
        original_paths = set(snapshots.iterdir())
        response = self.client.post("/api/v1/repos", json={"source": "invalid"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(snapshots.iterdir()), original_paths)

    def test_static_import_root_is_used_by_ingestion_api(self):
        source = self.app.state.settings.REPOS_IMPORT_ROOT / "project"
        package = source / "src" / "pkg"
        package.mkdir(parents=True)
        (package / "auth.py").write_text("def verify(): pass\n", encoding="utf-8")
        (package / "service.py").write_text("from pkg.auth import verify\nverify()\n", encoding="utf-8")
        repo = self.post_repo({"source": "project", "import_root": "src"})
        graph = self.client.get(f"/api/v1/repos/{repo['id']}/graph").json()["data"]
        nodes = {node["id"]: node for node in graph["nodes"]}
        call, = [edge for edge in graph["edges"] if edge["kind"] == "calls"]
        self.assertEqual(call["confidence"], "confirmed")
        self.assertEqual(nodes[call["dst_node_id"]]["qualified_name"], "pkg.auth.verify")
        self.assertEqual(nodes[call["dst_node_id"]]["file_path"], "src/pkg/auth.py")
        invalid = self.client.post("/api/v1/repos", json={"source": "project", "import_root": "../src"})
        self.assertEqual(invalid.status_code, 400)

    def test_cli_fixture_matches_reviewed_calls(self):
        harness = SHOWCASE.parent
        expected = json.loads((harness / "report_cli_ground_truth.json").read_text(encoding="utf-8"))
        with patch.object(self.app.state.settings, "REPOS_IMPORT_ROOT", harness):
            repo = self.post_repo({"source": expected["repository"], "import_root": expected["import_root"]})
        response = self.client.get(f"/api/v1/repos/{repo['id']}/graph")
        self.assertEqual(response.status_code, 200, response.text)
        graph = response.json()["data"]
        self.assertEqual(graph["summary"]["nodes_by_kind"], {
            "file": expected["python_files"], "function": expected["function_count"],
        })
        self.assertEqual(graph["summary"]["route_count"], expected["http_route_count"])
        names = {node["id"]: node["qualified_name"] for node in graph["nodes"]}
        for site in expected["selected_call_sites"]:
            with self.subTest(source=site["source_symbol"], expression=site["expression"]):
                observed = [
                    (names.get(edge["dst_node_id"]), edge["confidence"])
                    for edge in graph["edges"]
                    if edge["kind"] == "calls"
                    and names[edge["src_node_id"]] == site["source_symbol"]
                    and edge["raw_callee_expr"] == site["expression"]
                ]
                self.assertEqual(observed, [(site["target_symbol"], site["confidence"])])
