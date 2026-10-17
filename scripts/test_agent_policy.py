"""Cases for the stdlib-only policy core, bond_management/agent_policy.py."""

import ast
import fnmatch
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from claude_guard import agent_policy

APP_ROOT = Path(__file__).resolve().parent.parent
CORE = APP_ROOT / "bond_management" / "agent_policy.py"
CLAUDE_SETTINGS = APP_ROOT / ".claude" / "settings.json"
CODEX_DIR = APP_ROOT / ".codex"
CODEX_RULES = CODEX_DIR / "rules" / "bond_management.rules"
CODEX_CONFIG = CODEX_DIR / "config.toml"
CODEX_HOOK_COMMAND = 'python3 "$(git rev-parse --show-toplevel)/scripts/claude_guard.py"'
CONSUMERS = (
    APP_ROOT / "scripts" / "claude_guard.py",
    APP_ROOT / "bond_management" / "bond_management" / "tests" / "temporary_site_guard.py",
)
PERSISTENT_REASON = "Never destroy or overwrite the persistent Bond Management sites."
FOREIGN_REASON = "Destructive bench commands require one literal temporary Bond Management site."
HEX = "0123456789abcdef" * 2
TEMPORARY = f"bond-management-lifecycle-{HEX}.localhost"
FOREIGN = (
    "",
    "example.localhost",
    "bond-management.localhost",
    f"bond-management-{HEX}.localhost",
    f"bond-management-lifecycle-{HEX[:31]}.localhost",
    f"bond-management-lifecycle-{HEX}0.localhost",
    f"bond-management-lifecycle-{HEX.upper()}.localhost",
    f"Bond-Management-lifecycle-{HEX}.localhost",
    f"bond-management-lifecycle-{HEX}.localhost.evil",
    "BOND-MANAGEMENT-DEV.LOCALHOST",
)
DESTRUCTIVE = (*sorted(agent_policy.DESTRUCTIVE_VERBS), "new-site")


def spellings(verb, site):
    """Every canonical bench spelling that names one site for verb."""
    force = ["--force"] if verb == "new-site" else []
    if verb in agent_policy.POSITIONAL_SITE_VERBS:
        return (["bench", verb, site, *force],)
    return (
        ["bench", "--site", site, verb],
        ["bench", f"--site={site}", verb],
        ["bench", verb, "--site", site],
    )


class AgentPolicyTests(unittest.TestCase):
    def assert_violation(self, argv, expected):
        self.assertEqual(agent_policy.destructive_site_violation(argv), expected, argv)

    def test_core_imports_only_the_standard_library(self):
        tree = ast.parse(CORE.read_text())
        modules = {
            alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
        }
        modules |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertTrue(modules)
        for module in modules:
            self.assertIn(module.partition(".")[0], sys.stdlib_module_names, module)

    def test_constants_are_defined_once(self):
        for site in agent_policy.PERSISTENT_SITES:
            for path in CONSUMERS:
                self.assertNotIn(f'"{site}"', path.read_text(), path)
        for path in CONSUMERS:
            self.assertNotIn("[0-9a-f]{32}", path.read_text(), path)

    def test_classify_site(self):
        for site in agent_policy.PERSISTENT_SITES:
            self.assertEqual(agent_policy.classify_site(site), agent_policy.PERSISTENT)
        self.assertEqual(agent_policy.classify_site(TEMPORARY), agent_policy.TEMPORARY)
        self.assertEqual(agent_policy.classify_site(f"bond-management-race-{HEX}.localhost"), "temporary")
        for site in (*FOREIGN, None, 1, ["bond-management-dev.localhost"]):
            self.assertEqual(agent_policy.classify_site(site), agent_policy.FOREIGN, site)

    def test_hex_suffix_boundary(self):
        # Less than, equal to and greater than the 32 hex characters.
        for length, kind in ((31, "foreign"), (32, "temporary"), (33, "foreign")):
            site = f"bond-management-x-{('a' * length)}.localhost"
            self.assertEqual(agent_policy.classify_site(site), kind, length)

    def test_every_destructive_verb_against_every_site_class(self):
        cases = [(site, PERSISTENT_REASON) for site in sorted(agent_policy.PERSISTENT_SITES)]
        cases += [(TEMPORARY, None)] + [(site, FOREIGN_REASON) for site in FOREIGN]
        for verb in DESTRUCTIVE:
            for site, expected in cases:
                for argv in spellings(verb, site):
                    with self.subTest(verb=verb, site=site, argv=argv):
                        self.assert_violation(argv, expected)
                        self.assert_violation(["cd", "../..", *argv], expected)

    def test_destructive_verb_without_one_site(self):
        for verb in DESTRUCTIVE:
            force = ["--force"] if verb == "new-site" else []
            with self.subTest(verb=verb):
                self.assert_violation(["bench", verb, *force], FOREIGN_REASON)
                self.assert_violation(
                    ["bench", "--site", TEMPORARY, "--site", TEMPORARY, verb, *force], FOREIGN_REASON
                )
                self.assert_violation(["bench", verb, *force, "--site"], FOREIGN_REASON)

    def test_positional_verbs_reject_a_site_option(self):
        for verb in sorted(agent_policy.POSITIONAL_SITE_VERBS):
            force = ["--force"] if verb == "new-site" else []
            self.assert_violation(["bench", "--site", TEMPORARY, verb, TEMPORARY, *force], FOREIGN_REASON)
            self.assert_violation(["bench", verb, "--no-backup", TEMPORARY, *force], FOREIGN_REASON)

    def test_two_destructive_verbs_are_ambiguous(self):
        argv = ["bench", "--site", TEMPORARY, "restore", "reinstall"]
        self.assert_violation(argv, "Ambiguous destructive bench command.")

    def test_non_destructive_calls_are_not_checked(self):
        for site in agent_policy.PERSISTENT_SITES:
            self.assert_violation(["bench", "--site", site, "migrate"], None)
            self.assert_violation(["bench", "new-site", site], None)
            self.assert_violation(["echo", "drop-site", site], None)
        self.assert_violation([], None)

    def test_bench_is_matched_by_path_name(self):
        site = "bond-management-dev.localhost"
        for program in ("bench", "/usr/local/bin/bench", "env/bin/BENCH"):
            self.assert_violation([program, "drop-site", site], PERSISTENT_REASON)

    def test_secret_names(self):
        # The observer socket and user are scrubbed by name, not by pattern.
        for name in agent_policy.SECRET_ENV_VARS:
            if name.endswith("PASSWORD"):
                self.assertRegex(name, agent_policy.SECRET_NAME)
        for name in ("db_password", "API_KEY", "GITHUB_TOKEN", "CLIENT_SECRET"):
            self.assertRegex(name, agent_policy.SECRET_NAME)
        self.assertIsNone(agent_policy.SECRET_NAME.search("FRAPPE_USER"))

    def test_script_accepts_only_one_temporary_site(self):
        # scripts/verify.sh runs the core this way before every temporary-site bench call.
        cases = [([TEMPORARY], 0), ([], 1), ([TEMPORARY, TEMPORARY], 1)]
        cases += [([site], 1) for site in (*sorted(agent_policy.PERSISTENT_SITES), *FOREIGN)]
        for argv, expected in cases:
            with self.subTest(argv=argv):
                result = subprocess.run(
                    [sys.executable, "-I", str(CORE), *argv], capture_output=True, text=True, check=False
                )
                self.assertEqual(result.returncode, expected)
                self.assertEqual(result.stdout, "")
                for site in argv:
                    self.assertNotIn(site or "\0", result.stderr)

    def test_protected_files(self):
        expected = {"site_config.json", "common_site_config.json", "test-browser.env"}
        self.assertEqual(agent_policy.PROTECTED_FILES, expected)


class ClaudeSettingsSyncTests(unittest.TestCase):
    """.claude/settings.json carries rules generated from the core; hand edits fail here."""

    def setUp(self):
        self.settings = json.loads(CLAUDE_SETTINGS.read_text())

    def test_read_deny_rules_match_the_core(self):
        expected = agent_policy.claude_read_deny_rules()
        self.assertEqual(self.settings["permissions"]["deny"], expected)
        self.assertEqual(
            expected,
            [
                "Read(//**/common_site_config.json)",
                "Read(//**/site_config.json)",
                "Read(~/.config/bond_management/test-browser.env)",
            ],
        )

    def test_every_protected_file_has_a_rule(self):
        rules = agent_policy.claude_read_deny_rules()
        for name in agent_policy.PROTECTED_FILES:
            self.assertEqual(sum(rule.endswith(f"/{name})") for rule in rules), 1, name)
        # The fixture-safe anchor must name the file verify.sh loads.
        loader = f'local file="${{HOME:-}}/{agent_policy.BROWSER_CREDENTIALS}"'
        self.assertIn(loader, (APP_ROOT / "scripts" / "verify.sh").read_text())

    def test_guard_hook_entry_is_unchanged(self):
        hook = {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/scripts/claude_guard.py"'}
        expected = {"PreToolUse": [{"matcher": "Bash|Read", "hooks": [hook]}]}
        self.assertEqual(self.settings["hooks"], expected)

    def test_no_unreviewed_settings(self):
        # The sandbox block lands only after its tracer passes (spec, decision 3).
        self.assertEqual(set(self.settings), {"permissions", "hooks"})
        self.assertEqual(set(self.settings["permissions"]), {"deny"})


class CodexConfigSyncTests(unittest.TestCase):
    """.codex/ carries rules generated from the core and the shared guard hook."""

    def test_generated_files_match_the_core(self):
        self.assertEqual(set(agent_policy.GENERATED_FILES), {"--codex-rules", "--codex-config"})
        for flag, (path, generate) in agent_policy.GENERATED_FILES.items():
            with self.subTest(path=path):
                regenerate = f"Regenerate: python3 -I bond_management/agent_policy.py {flag} > {path}"
                self.assertEqual((APP_ROOT / path).read_text(), generate(), regenerate)
                result = subprocess.run(
                    [sys.executable, "-I", str(CORE), flag], capture_output=True, text=True, check=True
                )
                self.assertEqual(result.stdout, generate())

    def test_environment_filter_excludes_every_secret_variable(self):
        filters = tomllib.loads(CODEX_CONFIG.read_text())["shell_environment_policy"]["filters"]
        self.assertEqual(set(filters.values()), {"exclude"})
        # Codex matches filters case-insensitively.
        for name in (*agent_policy.SECRET_ENV_VARS, "frappe_password", "OTHER_PASSWORD"):
            self.assertTrue(any(fnmatch.fnmatch(name.upper(), key.upper()) for key in filters), name)
        for name in ("PATH", "HOME", "BOND_INVESTOR_SPA", "TEST_SITE"):
            self.assertFalse(any(fnmatch.fnmatch(name, key.upper()) for key in filters), name)

    def test_rules_forbid_every_destructive_verb_on_every_persistent_site(self):
        prefixes = agent_policy.codex_rule_prefixes()
        expected = []
        option_verbs = ("partial-restore", "reinstall", "restore", "trim-database", "trim-tables")
        for site in sorted(agent_policy.PERSISTENT_SITES):
            expected += [["bench", "--site", site, verb] for verb in option_verbs]
            expected += [["bench", "drop-site", site], ["bench", "new-site", site]]
        self.assertEqual(prefixes, expected)
        for prefix in prefixes:
            argv = [*prefix, "--force"] if "new-site" in prefix else prefix
            self.assertEqual(agent_policy.destructive_site_violation(argv), PERSISTENT_REASON, argv)

    def test_project_layer_has_no_unreviewed_files(self):
        # The permission profile stays user-level (spec, decision 2): its paths are per machine.
        files = {path.relative_to(CODEX_DIR).as_posix() for path in CODEX_DIR.rglob("*") if path.is_file()}
        self.assertEqual(files, {"config.toml", "hooks.json", "rules/bond_management.rules"})
        self.assertEqual(set(tomllib.loads(CODEX_CONFIG.read_text())), {"shell_environment_policy"})

    def test_hook_runs_the_shared_guard_on_shell_calls(self):
        hook = {"type": "command", "command": CODEX_HOOK_COMMAND}
        expected = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [hook]}]}}
        self.assertEqual(json.loads((CODEX_DIR / "hooks.json").read_text()), expected)

    def test_hook_blocks_with_the_codex_payload(self):
        # Shape built by codex-rs exec_command.rs at rust-v0.163.0: tool_input.command is a string.
        cases = [
            ("cat sites/common_site_config.json", 2),
            (f"bench --site {sorted(agent_policy.PERSISTENT_SITES)[0]} reinstall", 2),
            ("git status", 0),
        ]
        for command, expected in cases:
            payload = {
                "session_id": "s",
                "turn_id": "t",
                "transcript_path": None,
                "cwd": str(APP_ROOT),
                "hook_event_name": "PreToolUse",
                "model": "m",
                "permission_mode": "default",
                "tool_name": "Bash",
                "tool_input": {"command": command},
                "tool_use_id": "u",
            }
            with self.subTest(command=command):
                result = subprocess.run(
                    ["sh", "-c", CODEX_HOOK_COMMAND],
                    cwd=APP_ROOT,
                    input=json.dumps(payload),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, expected, result.stderr)
                # Codex blocks on exit 2 only with a reason on stderr.
                self.assertEqual(bool(result.stderr.strip()), expected == 2)

    def test_hook_blocks_outside_a_checkout(self):
        # Codex runs hooks from the session cwd; without a checkout the guard is not found.
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                ["sh", "-c", CODEX_HOOK_COMMAND],
                cwd=directory,
                input='{"tool_name": "Bash", "tool_input": {"command": "git status"}}',
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.strip())

    @unittest.skipUnless(shutil.which("codex"), "codex CLI not installed; the sync test above is the gate")
    def test_codex_loads_and_applies_the_rules(self):
        for prefix in agent_policy.codex_rule_prefixes():
            temporary = [TEMPORARY if word in agent_policy.PERSISTENT_SITES else word for word in prefix]
            with self.subTest(prefix=prefix):
                self.assertEqual(self.codex_check(CODEX_RULES, [*prefix, "--yes"])["decision"], "forbidden")
                self.assertEqual(self.codex_check(CODEX_RULES, temporary)["matchedRules"], [])
        # A not_match example that the rule matches fails at load.
        persistent = sorted(agent_policy.PERSISTENT_SITES)[0]
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / "broken.rules"
            text = CODEX_RULES.read_text().replace(agent_policy.EXAMPLE_TEMPORARY_SITE, persistent, 1)
            broken.write_text(text)
            self.assertIsNone(self.codex_check(broken, ["bench", "version"]))

    def codex_check(self, rules, argv):
        result = subprocess.run(
            ["codex", "execpolicy", "check", "--rules", str(rules), *argv],
            capture_output=True,
            text=True,
            check=False,
        )
        return json.loads(result.stdout) if result.returncode == 0 else None


if __name__ == "__main__":
    unittest.main()
