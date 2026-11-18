"""Build the reviewed showcase image and run a hardened four-test baseline.

No target repository code runs on the host. Run from any working directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

from validate_harness import REPO, source_snapshot, validate

BACKEND = Path(__file__).resolve().parents[1]


def run(command: list[str], *, timeout: float, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=check, timeout=timeout, text=True, encoding="utf-8", errors="replace", capture_output=capture)


def hardened_run(docker: str, image: str, name: str, repo: Path = REPO) -> list[str]:
    return [
        docker, "run", "--rm", "--name", name, "--pull", "never",
        "--network", "none", "--read-only", "--user", "1000:1000",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
        "--memory", "256m", "--cpus", "1", "--pids-limit", "64",
        "--ulimit", "nofile=256:256", "--ulimit", "fsize=16777216:16777216",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m,uid=1000,gid=1000,mode=1777",
        "--tmpfs", "/workspace/test_run:rw,noexec,nosuid,size=16m,uid=1000,gid=1000,mode=0700",
        "--mount", f"type=bind,source={repo.resolve()},target=/workspace/repo,readonly",
        "--env", "PYTHONPATH=/workspace/repo:/workspace/test_run",
        "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
        image,
    ]


def verify_baseline_xml(xml: str) -> dict:
    root = ElementTree.fromstring(xml)
    cases = root.findall(".//testcase")
    expected = {"test_valid_signature", "test_wrong_well_formed_signature", "test_checkout_calculation", "test_user_profile_lookup"}
    if len(cases) != 4 or {case.get("name") for case in cases} != expected:
        raise ValueError("Baseline report must contain exactly the four expected test IDs")
    if any(case.find(tag) is not None for case in cases for tag in ("failure", "error", "skipped")):
        raise ValueError("Baseline contains failed, errored or skipped tests")
    for suite in root.iter("testsuite"):
        if any(int(suite.get(attr, "0")) for attr in ("errors", "failures", "skipped")):
            raise ValueError("Baseline suite contains failures/errors/skips")
    return {"passed": 4, "test_names": sorted(expected)}


def verify_contract_xml(xml: str) -> dict:
    """Expect three seeded failures and four passing controls, not a clean suite."""
    root = ElementTree.fromstring(xml)
    cases = root.findall(".//testcase")
    expected_failures = {
        "test_malformed_signatures_return_false[]": "IndexError",
        "test_malformed_signatures_return_false[v1=not-hex]": "ValueError",
        "test_malformed_signatures_return_false[v1=0]": "ValueError",
    }
    controls = {"test_valid_signature_control", "test_wrong_signature_control", "test_empty_hex_signature_control", "test_out_of_contract_input_control"}
    if len(cases) != 7 or {case.get("name") for case in cases} != set(expected_failures) | controls:
        raise ValueError("Contract report must contain all three reproduction cases and four controls")
    for case in cases:
        if case.find("skipped") is not None or case.find("error") is not None:
            raise ValueError("Contract reproduction cannot contain skips or lifecycle errors")
        name = case.get("name")
        failure = case.find("failure")
        if name in controls and failure is not None:
            raise ValueError(f"Contract control failed: {name}")
        if name in expected_failures and (failure is None or not failure.get("message", "").startswith(expected_failures[name] + ":")):
            raise ValueError(f"Seeded exception did not reproduce: {name}")
    for suite in root.iter("testsuite"):
        if int(suite.get("errors", "0")) or int(suite.get("skipped", "0")):
            raise ValueError("Contract suite has lifecycle errors or skips")
    return {"expected_seeded_failures": 3, "passing_controls": 4, "runtime_classification": "Phase 4 triage not implemented"}


def baseline(docker: str, image: str, timeout: float, *, contract: bool = False) -> dict:
    name = "codescape-phase0-" + uuid.uuid4().hex[:12]
    # JUnit stays in bounded tmpfs and is printed after successful pytest. No RW
    # host bind is needed. The global JSON reporter belongs to Phase 4.
    test_path = "/workspace/contracts/test_verify_signature_contract.py" if contract else "/workspace/repo/tests/"
    program = (
        "import os,subprocess,sys; from pathlib import Path; "
        "assert os.getuid()==1000 and os.getgid()==1000; "
        "Path('/tmp/write_probe').write_text('ok'); "
        "p=subprocess.run([sys.executable,'-m','pytest','-o','cache_dir=/tmp/.pytest_cache',"
        f"'--junitxml=/workspace/test_run/baseline.xml',{test_path!r}]); "
        "print('CODESCAPE_BASELINE_XML_BEGIN',flush=True); "
        "print(Path('/workspace/test_run/baseline.xml').read_text(),flush=True); "
        "sys.exit(p.returncode)"
    )
    command = hardened_run(docker, image, name)
    if contract:
        index = command.index(image)
        command[index:index] = ["--mount", f"type=bind,source={BACKEND / 'test_harness/contracts'},target=/workspace/contracts,readonly"]
    try:
        result = run(command + ["python", "-c", program], timeout=timeout, capture=True, check=not contract)
        if contract and result.returncode != 1:
            raise ValueError(f"Seeded contract suite must exit 1, received {result.returncode}: {result.stderr}")
        print(result.stdout)
        marker = "CODESCAPE_BASELINE_XML_BEGIN\n"
        if marker not in result.stdout:
            raise ValueError("Container did not emit the baseline report")
        xml = result.stdout.split(marker, 1)[1].strip()
        summary = verify_contract_xml(xml) if contract else verify_baseline_xml(xml)
        return {**summary, "junit_xml": xml, "container_exit_code": result.returncode}
    finally:
        # Also remove a surviving container after a client-side timeout.
        subprocess.run([docker, "rm", "--force", name], capture_output=True, timeout=15)


def smoke_runtime(docker: str, image: str, timeout: float) -> dict:
    name = "codescape-phase0-smoke-" + uuid.uuid4().hex[:12]
    command = hardened_run(docker, image, name)
    index = command.index(image)
    command[index:index] = ["--mount", f"type=bind,source={BACKEND / 'test_harness/verify_showcase_runtime.py'},target=/opt/codescape/verify_showcase_runtime.py,readonly"]
    try:
        result = run(command + ["python", "/opt/codescape/verify_showcase_runtime.py"], timeout=timeout, capture=True)
        return json.loads(result.stdout)
    finally:
        subprocess.run([docker, "rm", "--force", name], capture_output=True, timeout=15)


def pytest_version(docker: str, image: str) -> str:
    # Even --version initializes pytest capture, which needs writable temp space.
    name = "codescape-phase0-version-" + uuid.uuid4().hex[:12]
    try:
        return run(hardened_run(docker, image, name) + ["python", "-m", "pytest", "--version"], timeout=20, capture=True).stdout.strip()
    finally:
        subprocess.run([docker, "rm", "--force", name], capture_output=True, timeout=15)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="codescape-sandbox:latest")
    parser.add_argument("--skip-build", action="store_true", help="Verify an already prepared local image")
    parser.add_argument("--timeout", type=float, default=30, help="Baseline smoke deadline in seconds (live chaos default remains 8)")
    parser.add_argument("--evidence", type=Path, default=BACKEND.parent / "data/evidence/phase0-baseline.json")
    args = parser.parse_args(argv)
    if args.timeout <= 0 or args.tag.startswith("-"):
        parser.error("Use a positive timeout and a valid image tag")
    docker = shutil.which("docker")
    evidence = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "status": "failed", "requested_image": args.tag}
    try:
        evidence["static_validation"] = validate()
        if docker is None:
            raise RuntimeError("Docker CLI not found. Install/start a Linux-container Docker engine, then rerun this script. No target tests were run on the host.")
        evidence["docker_version"] = run([docker, "version"], timeout=20, capture=True).stdout
        contract_manifest = json.loads((BACKEND / "test_harness/contracts/verify_signature.v1.json").read_text(encoding="utf-8"))
        evidence["contract_version"] = contract_manifest["version"]
        evidence["oracle_sha256"] = contract_manifest["oracle_sha256"]
        if not args.skip_build:
            run([docker, "build", "--file", str(BACKEND / "Dockerfile.sandbox"), "--tag", args.tag, str(BACKEND)], timeout=900)
        image = json.loads(run([docker, "image", "inspect", args.tag], timeout=20, capture=True).stdout)[0]
        evidence["image_id"] = image["Id"]
        evidence["repo_digests"] = image.get("RepoDigests", [])
        evidence["dependency_manifest_sha256"] = hashlib.sha256((BACKEND / "sandbox-requirements.txt").read_bytes()).hexdigest()
        evidence["python_version"] = run([docker, "run", "--rm", "--pull", "never", "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", image["Id"], "python", "--version"], timeout=20, capture=True).stdout.strip()
        evidence["pytest_version"] = pytest_version(docker, image["Id"])
        original = source_snapshot()
        evidence["baseline"] = baseline(docker, image["Id"], args.timeout)
        evidence["showcase_integration"] = smoke_runtime(docker, image["Id"], args.timeout)
        evidence["contract_reproductions"] = [baseline(docker, image["Id"], args.timeout, contract=True) for _ in range(2)]
        if source_snapshot() != original:
            raise ValueError("Showcase source changed during the baseline run")
        evidence["source_unchanged"] = True
        evidence["status"] = "passed"
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError, ElementTree.ParseError) as error:
        evidence["error"] = str(error)
        if isinstance(error, subprocess.CalledProcessError):
            evidence["stdout"] = error.stdout
            evidence["stderr"] = error.stderr
        print(f"Phase 0 sandbox check failed: {error}", file=sys.stderr)
        return 1
    finally:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(f"Evidence: {args.evidence}")


if __name__ == "__main__":
    raise SystemExit(main())
