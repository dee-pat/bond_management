"""Claude Code PreToolUse hook: block destructive site commands and secret output.

Reads the hook payload on stdin. Exit status 2 blocks the tool call and shows
stderr to the agent; 0 allows it. The rules mirror docs/verification.md, which
stays the source of truth; this hook only catches the clear-cut cases.
"""

import json
import re
import sys

PERSISTENT_SITES = ("bond-management-dev.localhost", "bond-management-test.localhost")
DESTRUCTIVE = re.compile(
    r"\bbench\b[^;&|\n]*\b(drop-site|trim-database|trim-tables|restore|partial-restore|reinstall)\b"
)
OVERWRITE = re.compile(r"\bbench\b[^;&|\n]*\bnew-site\b[^;&|\n]*--force\b")
EXPLICIT_SITE = re.compile(r"--site[ =]\S+|\bdrop-site\s+\S+|\bnew-site\s+\S+")
CREDENTIAL_FILE = "test-browser.env"
SOURCE_CREDENTIAL_FILE = re.compile(r"(^|[;&|(]\s*|\s)(source|\.)\s+\S*test-browser\.env\b")
SITE_CONFIG = re.compile(r"\b(common_)?site_config\.json\b")
PRINT_FILE = re.compile(r"\b(cat|head|tail|less|more|bat|strings|xxd|od|grep|rg|sed|awk|cut|cp)\b")
SECRET_NAME = r"\w*(PASSWORD|SECRET|TOKEN|API_KEY)\w*"
ECHO_SECRET = re.compile(r"\b(echo|printf)\b[^|;&]*\$\{?" + SECRET_NAME)
DUMP_ENV = re.compile(r"(^|[;&|]\s*)(printenv|env|export -p|set)\s*($|[;&|])|\bprintenv\s+" + SECRET_NAME)


def bash_violation(command):
    if DESTRUCTIVE.search(command) or OVERWRITE.search(command):
        if any(site in command for site in PERSISTENT_SITES):
            return "Never drop, trim, restore, reinstall or overwrite the persistent Bond Management sites."
        if not EXPLICIT_SITE.search(command):
            return "Name the temporary site explicitly; the default site may be a persistent one."
    if (
        CREDENTIAL_FILE in command
        and PRINT_FILE.search(command)
        and not SOURCE_CREDENTIAL_FILE.search(command)
    ):
        return f"Load {CREDENTIAL_FILE} with `source`; never print its contents."
    if SITE_CONFIG.search(command) and PRINT_FILE.search(command):
        return "Site configuration holds database and encryption secrets; read only the keys you need."
    if ECHO_SECRET.search(command) or DUMP_ENV.search(command):
        return "Do not print passwords, tokens or the environment."
    return None


def read_violation(file_path):
    if file_path.endswith(CREDENTIAL_FILE) or SITE_CONFIG.search(file_path):
        return "This file holds credentials or site secrets; do not read it into the conversation."
    return None


def violation(payload):
    tool_input = payload.get("tool_input") or {}
    if payload.get("tool_name") == "Bash":
        return bash_violation(str(tool_input.get("command", "")))
    if payload.get("tool_name") == "Read":
        return read_violation(str(tool_input.get("file_path", "")))
    return None


def main():
    reason = violation(json.load(sys.stdin))
    if reason:
        print(f"Blocked by scripts/claude_guard.py: {reason} See docs/verification.md.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
