import frappe

ROLE = "Bond Management Manager"
REPORT = "Portfolio Performance"


def execute():
    """Allow the app manager role to run the Portfolio Performance report."""
    report = frappe.get_doc("Report", REPORT)
    if ROLE not in {row.role for row in report.roles}:
        report.append("roles", {"role": ROLE})
        report.save(ignore_permissions=True)
