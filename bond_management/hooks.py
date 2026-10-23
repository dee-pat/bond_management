app_name = "bond_management"
app_title = "Bond Management"
app_publisher = "Deepak Patel"
app_description = "Portfolio management with bonds"
app_email = "deepak.patel@kaysalt.com"
app_license = "mit"

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
    {
        "name": "bond_management",
        "title": "Bond Management",
        "route": "/desk/bond-investor",
        "has_permission": "bond_management.bond_management.utils.investor_permissions.has_investor_desk_access",
    }
]

# The SPA keeps its own website entry while the existing investor Workspace
# remains the feature-flagged fallback. Nested client-side routes resolve to
# the same generated entry.
website_route_rules = [
    {"from_route": "/bond-investor/<path:app_path>", "to_route": "bond-investor"},
]

# include js, css files in header of desk.html
app_include_css = ["/assets/bond_management/css/attachment.css"]

# Installation marks patches as completed before running this hook, so
# invariants that must exist on a fresh site are also invoked here. DocPerms
# and report roles come from the DocType and report JSON instead.
after_install = [
    "bond_management.patches.add_bond_query_indexes.ensure_bond_query_indexes",
    "bond_management.patches.add_bond_exchange_rate_provenance.execute",
    "bond_management.patches.enforce_investor_share_boundary.execute",
]

# Frappe schema sync removes manual indexes when the DocField cannot declare
# them. Re-apply the indexes after every migration without rescanning tables;
# the registered patch and fresh-install hook perform duplicate validation.
after_migrate = [
    "bond_management.patches.add_bond_query_indexes.reapply_bond_query_indexes",
]

permission_query_conditions = {
    "File": "bond_management.bond_management.utils.investor_permissions.file_query_condition",
    "Bond Portfolio": "bond_management.bond_management.utils.investor_permissions.portfolio_query_condition",
    "Bond Transaction": "bond_management.bond_management.utils.investor_permissions.transaction_query_condition",
    "Bond Statement": "bond_management.bond_management.utils.investor_permissions.statement_query_condition",
    "Bond Exchange Rate": "bond_management.bond_management.utils.investor_permissions.exchange_rate_query_condition",
    "Bond Exchange Rate Source": "bond_management.bond_management.utils.investor_permissions.exchange_rate_source_query_condition",
}

has_permission = {
    "File": "bond_management.bond_management.utils.investor_permissions.has_file_permission",
    "Bond Portfolio": "bond_management.bond_management.utils.investor_permissions.has_portfolio_permission",
    "Bond Transaction": "bond_management.bond_management.utils.investor_permissions.has_transaction_permission",
    "Bond Statement": "bond_management.bond_management.utils.investor_permissions.has_statement_permission",
    "Bond Exchange Rate Source": "bond_management.bond_management.utils.investor_permissions.has_exchange_rate_source_permission",
}

_investor_shares = "bond_management.bond_management.utils.investor_shares"
_financial_doctypes = (
    "Bond Portfolio",
    "Bond Transaction",
    "Bond Statement",
    "Bond Master",
    "Bond Market Date",
    "Bond Exchange Rate",
    "Bond Exchange Rate Source",
)
extend_doctype_class = {
    doctype: [f"{_investor_shares}.InvestorBoundaryMixin"] for doctype in _financial_doctypes
}
extend_doctype_class["File"] = [
    "bond_management.bond_management.utils.investor_permissions.InvestorFileMixin"
]
doc_events = {
    doctype: {
        "validate_share": f"{_investor_shares}.validate_share",
        "before_insert": f"{_investor_shares}.reject_investor_mutation",
        "before_validate": f"{_investor_shares}.reject_investor_mutation",
        "before_cancel": f"{_investor_shares}.reject_investor_mutation",
        "before_update_after_submit": f"{_investor_shares}.reject_investor_mutation",
        "on_trash": f"{_investor_shares}.reject_investor_mutation",
        "on_update": f"{_investor_shares}.cleanup_document_shares",
    }
    for doctype in _financial_doctypes
}
doc_events.update(
    {
        "File": {
            "validate_share": f"{_investor_shares}.validate_file_share",
            "on_update": f"{_investor_shares}.cleanup_file_shares",
        },
        "User": {
            "before_validate": f"{_investor_shares}.lock_user_authorization",
            "on_update": f"{_investor_shares}.cleanup_user_shares",
        },
        "DocShare": {
            "before_insert": f"{_investor_shares}.lock_share_authorization",
            "before_validate": f"{_investor_shares}.lock_share_authorization",
            "on_trash": f"{_investor_shares}.reject_investor_share_mutation",
        },
        "User Permission": {
            "before_insert": f"{_investor_shares}.lock_assignment_authorization",
            "before_validate": f"{_investor_shares}.lock_assignment_authorization",
            "on_trash": f"{_investor_shares}.lock_assignment_authorization",
            "on_update": f"{_investor_shares}.cleanup_assignment_shares",
            "after_delete": f"{_investor_shares}.cleanup_assignment_shares",
        },
    }
)

override_whitelisted_methods = {
    "frappe.core.doctype.user_permission.user_permission.clear_user_permissions": (
        f"{_investor_shares}.clear_user_permissions"
    ),
}

on_session_creation = [
    "bond_management.bond_management.utils.investor_permissions.redirect_investor_to_workspace"
]

# Investor logouts from Desk include ``redirect-to=/desk`` in the login URL.
# Frappe's login client gives that URL precedence over the server-provided
# home_page, so redirect the resulting generic Desk route to the Vue app after
# boot. The app itself falls back to the restricted Workspace when disabled.
app_include_js = [
    "/assets/bond_management/js/clipboard.js",
    "/assets/bond_management/js/investor_desk_redirect.js",
]
