from bond_management.patches.access import INVESTOR_ROLE, ensure_report_role, ensure_role, upsert_docperm

ROLE = INVESTOR_ROLE
READ_ONLY_DOCTYPES = (
    "Bond Portfolio",
    "Bond Transaction",
    "Bond Statement",
    "Bond Master",
    "Bond Market Date",
    "Bond Exchange Rate Source",
)
PRINTABLE_DOCTYPES = {
    "Bond Transaction",
    "Bond Statement",
    "Bond Master",
    "Bond Market Date",
}
# Portfolio Performance and Interest Difference reference Bond Portfolio;
# Bond Yield Comparison references Bond Market Date.
REPORT_DOCTYPES = {"Bond Portfolio", "Bond Market Date"}


def execute():
    """Create the investor role and grant its non-mutating application access."""
    ensure_role(ROLE)
    for doctype in READ_ONLY_DOCTYPES:
        ensure_investor_read_only_docperm(doctype)
    ensure_report_role("Portfolio Performance", ROLE)


def ensure_investor_read_only_docperm(doctype: str) -> None:
    """Create or reset the investor's read-only DocPerm on ``doctype``."""
    upsert_docperm(
        doctype,
        ROLE,
        {
            "read": 1,
            "write": 0,
            "create": 0,
            "delete": 0,
            "submit": 0,
            "cancel": 0,
            "amend": 0,
            "print": int(doctype in PRINTABLE_DOCTYPES),
            "email": 0,
            "share": 0,
            "export": 0,
            "import": 0,
            "report": int(doctype in REPORT_DOCTYPES),
        },
    )
