"""Agent safety policy data and pure checks; see docs/specs/agent-safety-policy.md.

Standard library only: scripts/claude_guard.py loads this file by path without
package init, and bench code imports it as ``bond_management.agent_policy``.
"""

import re
from pathlib import PurePosixPath

PERSISTENT_SITES = frozenset({"bond-management-dev.localhost", "bond-management-test.localhost"})
TEMPORARY_SITE_SUFFIX = r"[0-9a-f]{32}\.localhost"
TEMPORARY_SITE = re.compile(r"bond-management-[a-z0-9-]+-" + TEMPORARY_SITE_SUFFIX)
DESTRUCTIVE_VERBS = frozenset(
    {"drop-site", "trim-database", "trim-tables", "restore", "partial-restore", "reinstall"}
)
POSITIONAL_SITE_VERBS = frozenset({"drop-site", "new-site"})
PROTECTED_FILES = frozenset({"site_config.json", "common_site_config.json", "test-browser.env"})
SECRET_NAME = re.compile(r"PASSWORD|SECRET|TOKEN|API_KEY", re.IGNORECASE)
SECRET_ENV_VARS = (
    "FRAPPE_PASSWORD",
    "FRAPPE_ADMIN_PASSWORD",
    "DB_ROOT_PASSWORD",
    "BOND_SHARE_LOCK_SOCKET",
    "BOND_SHARE_LOCK_USER",
    "BOND_SHARE_LOCK_PASSWORD",
)

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
            return "Never destroy or overwrite the persistent Bond Management sites."
        if kind != TEMPORARY:
            return "Destructive bench commands require one literal temporary Bond Management site."
    return None


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
