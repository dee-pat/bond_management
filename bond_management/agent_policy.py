"""Site classification shared by scripts/verify.sh and the temporary-site test helper.

Standard library only. scripts/verify.sh runs this file as a script before every
bench call on a temporary site (see main()), and bench code imports it as
``bond_management.agent_policy``. See docs/verification.md#temporary-sites.
"""

import re
import sys

PERSISTENT_SITES = frozenset({"bond-management-dev.localhost", "bond-management-test.localhost"})
TEMPORARY_SITE_SUFFIX = r"[0-9a-f]{32}\.localhost"
TEMPORARY_SITE = re.compile(r"bond-management-[a-z0-9-]+-" + TEMPORARY_SITE_SUFFIX)

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


def main(argv):
    """Exit 0 only for exactly one temporary site name; never echo the input."""
    if len(argv) == 1 and classify_site(argv[0]) == TEMPORARY:
        return 0
    print("Refusing a site that is not one temporary Bond Management site.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
