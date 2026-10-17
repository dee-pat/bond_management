"""Cases for the Claude Code PreToolUse guard."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parent / "claude_guard.py"


def run_guard(tool_name, **tool_input):
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
    return subprocess.run(
        [sys.executable, str(GUARD)], input=payload, capture_output=True, text=True, check=False
    ).returncode


class ClaudeGuardTests(unittest.TestCase):
    def assert_blocked(self, command):
        self.assertEqual(run_guard("Bash", command=command), 2, command)

    def assert_allowed(self, command):
        self.assertEqual(run_guard("Bash", command=command), 0, command)

    def test_destructive_commands_on_persistent_sites_are_blocked(self):
        self.assert_blocked("bench drop-site bond-management-dev.localhost --no-backup")
        self.assert_blocked("bench --site bond-management-test.localhost restore backup.sql.gz")
        self.assert_blocked("bench --site bond-management-test.localhost reinstall --yes")
        self.assert_blocked("bench --site=bond-management-dev.localhost trim-database")
        self.assert_blocked("bench new-site bond-management-test.localhost --force")

    def test_destructive_commands_without_a_site_are_blocked(self):
        self.assert_blocked("bench restore backup.sql.gz")
        self.assert_blocked("cd ../.. && bench trim-tables")

    def test_each_command_segment_needs_its_own_site(self):
        temporary = "bond-management-lifecycle-0123456789abcdef0123456789abcdef.localhost"
        self.assert_blocked(f"bench --site {temporary} migrate && bench reinstall --yes")
        self.assert_blocked(f"bench --site {temporary} migrate; bench restore backup.sql.gz")
        self.assert_allowed(f"bench --site {temporary} migrate && bench --site {temporary} reinstall --yes")

    def test_destructive_sites_must_be_literal(self):
        temporary = "bond-management-lifecycle-0123456789abcdef0123456789abcdef.localhost"
        self.assert_blocked('SITE=bond-management-dev.localhost; bench --site "$SITE" reinstall --yes')
        self.assert_blocked("bench --site $(cat site.txt) restore backup.sql.gz")
        self.assert_blocked("bench --site all reinstall --yes")
        self.assert_allowed(f'bench --site "{temporary}" reinstall --yes')

    def test_line_continuations_are_joined(self):
        self.assert_blocked("bench --site bond-management-dev.localhost \\\n reinstall --yes")
        self.assert_blocked("bench \\\n restore backup.sql.gz")

    def test_temporary_sites_and_routine_commands_are_allowed(self):
        temporary = "bond-management-lifecycle-0123456789abcdef0123456789abcdef.localhost"
        self.assert_allowed(f"bench drop-site {temporary} --no-backup")
        self.assert_allowed(f"bench --site {temporary} reinstall --yes")
        self.assert_allowed("bench --site bond-management-test.localhost migrate")
        self.assert_allowed("bench --site bond-management-test.localhost run-tests --app bond_management")
        self.assert_allowed("bench build && git restore bond_management/hooks.py")

    def test_credential_file_may_only_be_sourced(self):
        path = "$HOME/.config/bond_management/test-browser.env"
        self.assert_allowed(f'set -a; source "{path}"; set +a')
        self.assert_allowed(f"set -a && . {path} && set +a && yarn test:e2e")
        self.assert_blocked(f"cat {path}")
        self.assert_blocked(f"grep PASSWORD {path}")
        self.assert_allowed("gh pr create --body 'Blocks printing test-browser.env.'")
        self.assert_allowed("rg -n TODO README.md && gh pr create --body 'Do not print test-browser.env.'")
        self.assert_blocked(f"source {path} && cat {path}")
        self.assert_blocked(f"nl {path}")
        self.assert_blocked(f"cp {path} /tmp/copy")
        self.assertEqual(run_guard("Read", file_path="/Users/x/.config/bond_management/test-browser.env"), 2)

    def test_site_config_contents_are_not_printed(self):
        self.assert_blocked("cat sites/bond-management-dev.localhost/site_config.json")
        self.assert_blocked("head sites/common_site_config.json")
        self.assert_blocked("jq . sites/bond-management-dev.localhost/site_config.json")
        self.assert_blocked('python3 -c "print(1)" < sites/common_site_config.json')
        self.assertEqual(run_guard("Read", file_path="/bench/sites/common_site_config.json"), 2)
        self.assert_allowed("bench --site bond-management-test.localhost set-config allow_tests true")

    def test_secret_variables_and_environment_are_not_printed(self):
        self.assert_blocked('echo "$FRAPPE_PASSWORD"')
        self.assert_blocked("printf '%s' ${BOND_SHARE_LOCK_PASSWORD}")
        self.assert_blocked("printenv FRAPPE_ADMIN_PASSWORD")
        self.assert_blocked("env")
        self.assert_blocked("printenv | sort")
        self.assert_blocked('echo "$(printenv)"')
        self.assert_blocked("x=$(env); echo ok")
        self.assert_blocked("echo `env`")
        self.assert_blocked('echo "$(echo $FRAPPE_PASSWORD)"')
        self.assert_blocked("env -0")
        self.assert_blocked("/usr/bin/env")
        self.assert_blocked("env -i FOO=1")
        self.assert_blocked("env CI=Yes printenv")
        self.assert_blocked("export -p")
        self.assert_blocked("declare -x")
        self.assert_blocked("set")
        self.assert_allowed("set -euo pipefail; echo done")
        self.assert_allowed("env CI=Yes yarn lint")
        self.assert_allowed("export CI=Yes")

    def test_single_quoted_text_is_literal(self):
        self.assert_allowed("gh pr create --body 'avoid $(printenv)'")
        self.assert_allowed("printf '%s\\n' '$(env)'")
        self.assert_allowed("echo '$FRAPPE_PASSWORD'")
        self.assert_allowed("echo \\$FRAPPE_PASSWORD")
        self.assert_blocked('gh pr create --body "avoid $(printenv)"')

    def test_other_tools_are_allowed(self):
        self.assertEqual(run_guard("Read", file_path="/repo/docs/verification.md"), 0)
        self.assertEqual(run_guard("Edit", file_path="/repo/sites/common_site_config.json"), 0)


if __name__ == "__main__":
    unittest.main()
