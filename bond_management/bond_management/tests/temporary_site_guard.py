"""Safety checks for opt-in test helpers that mutate a temporary site."""

import json
import re
from pathlib import Path

from bond_management.agent_policy import PERSISTENT_SITES, TEMPORARY_SITE_SUFFIX


def validate_temporary_site(*, bench_path, site_path, site, user, config, site_prefix, required_flags=()):
    """Require a uniquely named test site directly under the configured bench."""
    bench = Path(bench_path).resolve()
    sites = (bench / "sites").resolve()
    if not sites.is_relative_to(bench):
        raise RuntimeError("Temporary test site must be inside the configured bench")

    resolved_site = Path(site_path).resolve()
    if resolved_site.parent != sites or resolved_site.name != site:
        raise RuntimeError("Temporary test site must be directly under the configured bench")

    pattern = re.escape(site_prefix) + TEMPORARY_SITE_SUFFIX
    if not isinstance(site, str) or site in PERSISTENT_SITES or re.fullmatch(pattern, site) is None:
        raise RuntimeError(f"Use a unique {site_prefix}<32-hex-id>.localhost test site")
    if user != "Administrator":
        raise RuntimeError("Temporary site helper requires Administrator")

    for flag in ("allow_tests", *required_flags):
        if not _true(config.get(flag)):
            raise RuntimeError(f"Temporary site helper requires {flag}=true")
    return bench


def _true(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return False
    return value is True or (type(value) is int and value == 1)
