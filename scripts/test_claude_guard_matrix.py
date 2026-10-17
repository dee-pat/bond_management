"""Executable acceptance matrix for docs/specs/claude-guard-shell-policy.md."""

import json
import subprocess
import sys
import unittest
from itertools import product
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
MATRIX = json.loads((SCRIPTS / "claude_guard_cases.json").read_text())["cases"]


def invoke(payload):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "claude_guard.py")],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )


class ClaudeGuardMatrixTests(unittest.TestCase):
    def check_command(self, command, allowed):
        result = invoke(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))
        self.assertEqual(result.returncode, 0 if allowed else 2, command)
        self.assertEqual(result.stdout, "")
        if not allowed:
            self.assertIn("Blocked by scripts/claude_guard.py:", result.stderr)

    def test_documented_matrix(self):
        self.assertEqual(len({case["id"] for case in MATRIX}), len(MATRIX))
        for case in MATRIX:
            with self.subTest(case=case["id"], group=case["group"]):
                self.check_command(case["command"], case["allow"])

    def test_quotes_wrappers_and_site_cross_product(self):
        programs = ("bench", "'bench'", '"bench"', "$'bench'", "be'n'ch")
        verbs = ("reinstall", "re'install'", "re$''install")
        wrappers = ("", "command -- ", "sudo -u root ", "timeout 60 ")
        temporary = "bond-management-lifecycle-0123456789abcdef0123456789abcdef.localhost"
        for program, verb, wrapper, site in product(
            programs, verbs, wrappers, (temporary, "bond-management-dev.localhost")
        ):
            with self.subTest(program=program, verb=verb, wrapper=wrapper, site=site):
                self.check_command(f"{wrapper}{program} --site {site} {verb} --yes", site == temporary)

    def test_invalid_payloads_fail_closed_without_echoing_contents(self):
        canary = "synthetic-private-canary"
        payloads = (
            "not JSON " + canary,
            "[]",
            "null",
            json.dumps({"tool_name": "Bash", "tool_input": {"command": [canary]}}),
            json.dumps({"tool_name": "Bash", "tool_input": {"command": None}}),
            json.dumps({"tool_name": "Read", "tool_input": {"file_path": {"x": canary}}}),
            json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo '\x00" + canary}}),
            json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo " + "x" * 65537}}),
            json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo " * 4097}}),
        )
        for payload in payloads:
            with self.subTest(payload_length=len(payload)):
                result = invoke(payload)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertNotIn(canary, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_every_destructive_verb_and_site_boundary(self):
        temporary = "bond-management-race-0123456789abcdef0123456789abcdef.localhost"
        sites = (
            temporary,
            "bond-management-dev.localhost",
            "bond-management-test.localhost",
            "foreign.localhost",
        )
        verbs = (
            "drop-site",
            "new-site",
            "reinstall",
            "restore",
            "partial-restore",
            "trim-database",
            "trim-tables",
        )
        for verb, site in product(verbs, sites):
            if verb in ("drop-site", "new-site"):
                command = f"bench {verb} {site} --force"
            else:
                command = f"bench --site {site} {verb}"
            with self.subTest(verb=verb, site=site):
                self.check_command(command, site == temporary)

    def test_word_provenance_and_descriptor_boundaries(self):
        from claude_guard_shell import commands

        command = commands("FLAG='literal value' echo \"a b\" '2'>output.txt 2>&1")[0]
        self.assertEqual([word.value for word in command.words], ["FLAG=literal value", "echo", "a b", "2"])
        self.assertEqual([word.assignment for word in command.words], [True, False, False, False])
        self.assertEqual([word.value for word in command.targets], ["output.txt"])
        quoted = commands("'FLAG=value' echo '*.py' *.py")[0]
        self.assertFalse(quoted.words[0].assignment)
        self.assertEqual([word.glob for word in quoted.words], [False, False, False, True])
        source = commands('source "${HOME}/.config/bond_management/test-browser.env"')[0]
        self.assertEqual(source.words[1].references, ("HOME",))

    def test_read_input_boundaries_and_private_diagnostics(self):
        canary = "synthetic-private-canary"
        for path in ("", canary + "\x7f", canary + "\x00", canary + "\t", canary + "\n", "x" * 65537):
            with self.subTest(path_length=len(path)):
                result = invoke(json.dumps({"tool_name": "Read", "tool_input": {"file_path": path}}))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertNotIn(canary, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
        at_limit = invoke(json.dumps({"tool_name": "Read", "tool_input": {"file_path": "x" * 65536}}))
        self.assertEqual(at_limit.returncode, 0)
        self.assertEqual(at_limit.stdout + at_limit.stderr, "")


if __name__ == "__main__":
    unittest.main()
