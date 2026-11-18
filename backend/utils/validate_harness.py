"""Host-safe Phase 0 structural validation: parse/hash source, never import it."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
HARNESS = BACKEND / "test_harness"
REPO = HARNESS / "payflow-core"
CONTRACT = HARNESS / "contracts" / "verify_signature.v1.json"
EXPECTED_FILES = {
    "app.py", "routes/stripe.py", "routes/checkout.py", "routes/users.py",
    "routes/refunds.py", "services/auth.py", "services/webhook_listener.py",
    "services/dispatcher.py", "services/checkout.py", "services/users.py",
    "services/refunds.py", "services/payments.py", "models/payment.py",
    "models/user.py", "utils/retry.py", "utils/audit.py", "utils/money.py",
    "tests/test_payflow.py",
}


def source_snapshot(repo: Path = REPO) -> dict:
    """Hash sorted relative paths plus exact bytes, independent of absolute paths."""
    entries = []
    for path in sorted(repo.rglob("*.py")):
        if path.is_symlink():
            raise ValueError(f"Fixture source must not be a symlink: {path}")
        relative = path.relative_to(repo).as_posix()
        content = path.read_bytes()
        entries.append({"path": relative, "sha256": hashlib.sha256(content).hexdigest()})
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"algorithm": "sha256-sorted-path-and-file-sha256-json-v1", "sha256": hashlib.sha256(canonical).hexdigest(), "files": entries}


def function_symbols(tree: ast.AST, prefix: str) -> list[str]:
    result = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            qualified = prefix + "." + node.name
            if not isinstance(node, ast.ClassDef):
                result.append(qualified)
            result.extend(function_symbols(node, qualified))
    return result


def validate() -> dict:
    snapshot = source_snapshot()
    found = {entry["path"] for entry in snapshot["files"]}
    if found != EXPECTED_FILES:
        raise ValueError(f"Unexpected source inventory: missing={EXPECTED_FILES-found}, extra={found-EXPECTED_FILES}")
    symbols = []
    trees = {}
    for relative in sorted(found):
        source = (REPO / relative).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative, feature_version=(3, 11))
        compile(tree, relative, "exec")  # No target code is executed.
        trees[relative] = tree
        symbols.extend(function_symbols(tree, relative[:-3].replace("/", ".")))
    if len(symbols) != 54:
        raise ValueError(f"Expected 54 functions/methods including four tests, got {len(symbols)}")
    tests = [n.name for n in trees["tests/test_payflow.py"].body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    if len(tests) != 4:
        raise ValueError(f"Expected exactly four baseline tests, got {tests}")
    manifest = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if manifest["source_snapshot"] != snapshot:
        raise ValueError("Reviewed fixture source hash is stale; review changes before rebinding")
    oracle = CONTRACT.parent / manifest["oracle_file"]
    if hashlib.sha256(oracle.read_bytes()).hexdigest() != manifest["oracle_sha256"]:
        raise ValueError("Oracle hash does not match the reviewed manifest")
    ast.parse(oracle.read_text(encoding="utf-8"), feature_version=(3, 11))
    truth = json.loads((HARNESS / "ground_truth.json").read_text(encoding="utf-8"))
    if sorted(truth["function_symbols"]) != sorted(symbols):
        raise ValueError("Ground-truth symbol inventory is stale")
    routes = []
    for relative, tree in trees.items():
        module = relative[:-3].replace("/", ".")
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.args and isinstance(decorator.args[0], ast.Constant):
                        routes.append({"symbol": module + "." + node.name, "method": decorator.func.attr.upper(), "path": decorator.args[0].value})
    if sorted(routes, key=lambda entry: entry["path"]) != truth["route_entrypoints"]:
        raise ValueError("Ground-truth route inventory is stale")
    # Validate curated expressions without pretending to implement the Phase 2 resolver.
    for edge in truth["selected_call_sites"]:
        relative = edge["source_file"]
        calls = [ast.unparse(n) for n in ast.walk(trees[relative]) if isinstance(n, ast.Call)]
        if edge["expression"] not in calls:
            raise ValueError(f"Missing curated call-site expression: {edge}")
    return {"validation": "passed", "python_files": len(found), "functions_including_tests": len(symbols), "baseline_test_definitions": tests, "source_sha256": snapshot["sha256"], "contract_id": manifest["contract_id"], "runtime_tests": "not executed by static validator"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        print(json.dumps(validate(), indent=2))
    except (OSError, ValueError, KeyError, SyntaxError) as error:
        parser.exit(1, f"Structural validation failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
