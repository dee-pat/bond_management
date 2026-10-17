"""Agent safety policy data and pure checks; see docs/specs/agent-safety-policy.md.

Standard library only: scripts/claude_guard.py loads this file by path without
package init, and bench code imports it as ``bond_management.agent_policy``.
scripts/verify.sh runs it as a script to check a temporary site; see main().
"""

import json
import re
import sys
from pathlib import PurePosixPath

PERSISTENT_SITES = frozenset({"bond-management-dev.localhost", "bond-management-test.localhost"})
TEMPORARY_SITE_SUFFIX = r"[0-9a-f]{32}\.localhost"
TEMPORARY_SITE = re.compile(r"bond-management-[a-z0-9-]+-" + TEMPORARY_SITE_SUFFIX)
DESTRUCTIVE_VERBS = frozenset(
    {"drop-site", "trim-database", "trim-tables", "restore", "partial-restore", "reinstall"}
)
POSITIONAL_SITE_VERBS = frozenset({"drop-site", "new-site"})
PROTECTED_FILES = frozenset({"site_config.json", "common_site_config.json", "test-browser.env"})
# Relative to the home directory; scripts/verify.sh loads it for the UI gate.
BROWSER_CREDENTIALS = ".config/bond_management/test-browser.env"
SECRET_NAME = re.compile(r"PASSWORD|SECRET|TOKEN|API_KEY", re.IGNORECASE)
SECRET_ENV_VARS = (
    "FRAPPE_PASSWORD",
    "FRAPPE_ADMIN_PASSWORD",
    "DB_ROOT_PASSWORD",
    "BOND_SHARE_LOCK_SOCKET",
    "BOND_SHARE_LOCK_USER",
    "BOND_SHARE_LOCK_PASSWORD",
)

PERSISTENT_REASON = "Never destroy or overwrite the persistent Bond Management sites."
# Example only: the not_match case showing that Codex rules leave temporary sites to the hook.
EXAMPLE_TEMPORARY_SITE = f"bond-management-example-{'0' * 32}.localhost"

PERSISTENT = "persistent"
TEMPORARY = "temporary"
FOREIGN = "foreign"


def classify_site(name):
    """Return PERSISTENT, TEMPORARY or FOREIGN for a literal site name."""
    if not isinstance(name, str):
        return FOREIGN
    if name in PERSISTENT_SITES:
        return PERSISTENT
    return TEMPORARY if TEMPORARY_SITE.fullmatch(name) else FOREIGN


def destructive_site_violation(argv):
    """Return a reason when a bench call in argv destroys a non-temporary site."""
    for index, word in enumerate(argv):
        if _program(word) != "bench":
            continue
        arguments = argv[index + 1 :]
        verbs = [arg for arg in arguments if arg in DESTRUCTIVE_VERBS | {"new-site"}]
        if not verbs or (verbs == ["new-site"] and "--force" not in arguments):
            continue
        if len(verbs) != 1:
            return "Ambiguous destructive bench command."
        kind = classify_site(_site_argument(arguments, verbs[0]))
        if kind == PERSISTENT:
            return PERSISTENT_REASON
        if kind != TEMPORARY:
            return "Destructive bench commands require one literal temporary Bond Management site."
    return None


def claude_read_deny_rules():
    """Claude Code Read deny rules for the protected files.

    Site config: `//**/NAME`, because the bench's sites/ sit outside the session's
    working directory. Browser credentials: their one home path, so test fixtures
    of the same name under a temporary HOME stay usable once the Bash sandbox,
    which takes in these rules, is on.
    """
    site_config = sorted(PROTECTED_FILES - {PurePosixPath(BROWSER_CREDENTIALS).name})
    return [f"Read(//**/{name})" for name in site_config] + [f"Read(~/{BROWSER_CREDENTIALS})"]


def claude_sandbox_settings():
    """The `sandbox` block of .claude/settings.json: a strict OS sandbox for Claude's shell.

    denyRead repeats the Read deny paths (sandbox paths take the same `//` and `~/`
    prefixes). bench and verify.sh run outside it because bench reads the protected
    config in-process (spec decision 1); Semgrep opens its log under ~/.semgrep.
    """
    return {
        "enabled": True,
        "failIfUnavailable": True,
        "allowUnsandboxedCommands": False,
        "excludedCommands": ["bench *", "scripts/verify.sh *", "apps/bond_management/scripts/verify.sh *"],
        "filesystem": {
            "denyRead": [rule.removeprefix("Read(").removesuffix(")") for rule in claude_read_deny_rules()],
            "allowWrite": ["~/.semgrep"],
        },
        "credentials": {"envVars": [{"name": name, "mode": "deny"} for name in SECRET_ENV_VARS]},
    }


def codex_rule_prefixes():
    """Canonical bench argv prefixes that destroy or recreate a persistent site."""
    prefixes = []
    option_verbs = sorted(DESTRUCTIVE_VERBS - POSITIONAL_SITE_VERBS)
    for site in sorted(PERSISTENT_SITES):
        prefixes += [["bench", "--site", site, verb] for verb in option_verbs]
        prefixes += [["bench", verb, site] for verb in sorted(POSITIONAL_SITE_VERBS)]
    return prefixes


def codex_rules():
    """Text of .codex/rules/bond_management.rules: one forbidden prefix_rule per prefix.

    Codex matches literal argv prefixes only; other spellings reach the
    PreToolUse hook (scripts/claude_guard.py), which applies the full check.
    """
    justification = json.dumps(f"{PERSISTENT_REASON} See docs/verification.md.")
    lines = _generated_header("--codex-rules")
    for prefix in codex_rule_prefixes():
        example = [EXAMPLE_TEMPORARY_SITE if word in PERSISTENT_SITES else word for word in prefix]
        lines += [
            "prefix_rule(",
            f"    pattern = {json.dumps(prefix)},",
            '    decision = "forbidden",',
            f"    justification = {justification},",
            f"    match = {json.dumps([' '.join(prefix)])},",
            f"    not_match = {json.dumps([' '.join(example)])},",
            ")",
            "",
        ]
    return "\n".join(lines)


def codex_environment_filters():
    """Names Codex removes from agent shells: every password, plus the other secret variables."""
    names = [name for name in SECRET_ENV_VARS if "PASSWORD" not in name]
    return ["*PASSWORD*", *names]


def codex_config():
    """Text of .codex/config.toml: the environment filter only.

    The permission profile stays user-level; see docs/agents/codex-user-config.md.
    """
    filters = [f'"{name}" = "exclude"' for name in codex_environment_filters()]
    return "\n".join(
        [*_generated_header("--codex-config"), "[shell_environment_policy.filters]", *filters, ""]
    )


GENERATED_FILES = {
    "--codex-rules": (".codex/rules/bond_management.rules", codex_rules),
    "--codex-config": (".codex/config.toml", codex_config),
}


def main(argv):
    """Exit 0 only for exactly one temporary site name; never echo the input.

    A GENERATED_FILES flag prints that generated file instead.
    """
    if len(argv) == 1 and argv[0] in GENERATED_FILES:
        sys.stdout.write(GENERATED_FILES[argv[0]][1]())
        return 0
    if len(argv) == 1 and classify_site(argv[0]) == TEMPORARY:
        return 0
    print("Refusing a site that is not one temporary Bond Management site.", file=sys.stderr)
    return 1


def _generated_header(flag):
    path = GENERATED_FILES[flag][0]
    return [
        "# Generated from bond_management/agent_policy.py; do not edit. Regenerate with:",
        f"# python3 -I bond_management/agent_policy.py {flag} > {path}",
        "",
    ]


def _site_argument(words, verb):
    sites = []
    for index, word in enumerate(words):
        if word.startswith("--site="):
            sites.append(word.removeprefix("--site="))
        elif word == "--site":
            sites.append(words[index + 1] if index + 1 < len(words) else "")
    if verb in POSITIONAL_SITE_VERBS:
        if sites:
            return None
        after = words[words.index(verb) + 1 :]
        return after[0] if after and not after[0].startswith("-") else None
    return sites[0] if len(sites) == 1 else None


def _program(word):
    return PurePosixPath(word).name.casefold()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
