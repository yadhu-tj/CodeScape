"""Host-safe tests of build/report orchestration; never import the target/oracle."""

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "utils"))
import build_sandbox
import validate_harness

NAMES = ["test_valid_signature", "test_wrong_well_formed_signature", "test_checkout_calculation", "test_user_profile_lookup"]


def report(extra: str = "", names: list[str] = NAMES) -> str:
    return '<testsuites><testsuite tests="4" failures="0" errors="0" skipped="0">' + ''.join(f'<testcase name="{name}">{extra if index == 0 else ""}</testcase>' for index, name in enumerate(names)) + '</testsuite></testsuites>'


class BaselineEvidenceTests(unittest.TestCase):
    def test_only_four_executed_expected_tests_are_accepted(self):
        self.assertEqual(build_sandbox.verify_baseline_xml(report())["passed"], 4)
        for names in ([], NAMES[:3], NAMES + ["extra"], [NAMES[0]] * 4):
            with self.subTest(names=names), self.assertRaises(ValueError):
                build_sandbox.verify_baseline_xml(report(names=names))

    def test_skipped_failed_and_teardown_errors_are_rejected(self):
        for outcome in ("skipped", "failure", "error"):
            with self.subTest(outcome=outcome), self.assertRaises(ValueError):
                build_sandbox.verify_baseline_xml(report(f"<{outcome}/>"))

    def test_contract_requires_expected_exceptions_and_passing_controls(self):
        malformed = [("", "IndexError"), ("v1=not-hex", "ValueError"), ("v1=0", "ValueError")]
        xml = '<testsuites><testsuite errors="0" skipped="0">'
        for parameter, exception in malformed:
            xml += f'<testcase name="test_malformed_signatures_return_false[{parameter}]"><failure message="{exception}: seeded"/></testcase>'
        for control in ("valid_signature", "wrong_signature", "empty_hex_signature", "out_of_contract_input"):
            xml += f'<testcase name="test_{control}_control"/>'
        xml += '</testsuite></testsuites>'
        self.assertEqual(build_sandbox.verify_contract_xml(xml)["passing_controls"], 4)
        with self.assertRaises(ValueError):
            build_sandbox.verify_contract_xml(xml.replace("IndexError:", "AssertionError:"))
        with self.assertRaises(ValueError):
            build_sandbox.verify_contract_xml(xml.replace('<testcase name="test_valid_signature_control"/>', '<testcase name="test_valid_signature_control"><failure/></testcase>'))

    def test_timeout_removes_surviving_container(self):
        with patch.object(build_sandbox, "run", side_effect=subprocess.TimeoutExpired("docker", 1)), patch.object(build_sandbox.subprocess, "run") as cleanup:
            with self.assertRaises(subprocess.TimeoutExpired):
                build_sandbox.baseline("docker", "sha256:fixture", 1)
            command = cleanup.call_args.args[0]
            self.assertEqual(command[:3], ["docker", "rm", "--force"])
            self.assertTrue(command[3].startswith("codescape-phase0-"))

    def test_run_uses_readonly_source_and_bounded_storage(self):
        command = build_sandbox.hardened_run("docker", "sha256:fixture", "fixture", Path("source with spaces"))
        self.assertEqual(command[command.index("--network") + 1], "none")
        self.assertIn("--read-only", command)
        self.assertIn("1000:1000", command)
        self.assertIn("ALL", command)
        mount = command[command.index("--mount") + 1]
        self.assertTrue(mount.endswith("target=/workspace/repo,readonly"))
        self.assertIn("source with spaces", mount)
        self.assertEqual(command.count("--tmpfs"), 2)
        self.assertNotIn("/var/run/docker.sock", " ".join(command))


class StructuralFixtureTests(unittest.TestCase):
    def test_reviewed_inventory_and_hashes_match_without_importing_target(self):
        result = validate_harness.validate()
        self.assertEqual(result["python_files"], 18)
        self.assertEqual(result["functions_including_tests"], 54)
        self.assertEqual(len(result["baseline_test_definitions"]), 4)
        self.assertNotIn("services.auth", sys.modules)


if __name__ == "__main__":
    unittest.main()
