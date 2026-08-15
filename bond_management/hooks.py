app_name = "bond_management"
app_title = "Bond Management"
app_publisher = "Deepak Patel"
app_description = "Portfolio management with bonds"
app_email = "deepak.patel@kaysalt.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
    {
        "name": "bond_management",
        "title": "Bond Management",
        "route": "/desk/bond-investor",
        "has_permission": "bond_management.bond_management.utils.investor_permissions.has_investor_desk_access",
    }
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/bond_management/css/bond_management.css"
# app_include_js = "/assets/bond_management/js/bond_management.js"

# include js, css files in header of web template
# web_include_css = "/assets/bond_management/css/bond_management.css"
# web_include_js = "/assets/bond_management/js/bond_management.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "bond_management/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "bond_management/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#     "Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#     "methods": "bond_management.utils.jinja_methods",
#     "filters": "bond_management.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "bond_management.install.before_install"
# Installation marks patches as completed before running this hook, so
# permission bootstrap that must exist on a fresh site is also invoked here.
after_install = [
    "bond_management.patches.add_bond_query_indexes.ensure_bond_query_indexes",
    "bond_management.patches.add_bond_investor_read_only_access.execute",
    "bond_management.patches.add_bond_investor_report_permission.execute",
    "bond_management.patches.add_bond_yield_comparison_report_permission.execute",
    "bond_management.patches.add_bond_management_manager_access.execute",
    "bond_management.patches.add_bond_management_report_permission.execute",
    "bond_management.patches.add_bond_exchange_rate_permissions.execute",
]

# Frappe schema sync removes manual indexes when the DocField cannot declare
# them. Re-apply the indexes after every migration without rescanning tables;
# the registered patch and fresh-install hook perform duplicate validation.
after_migrate = [
    "bond_management.patches.add_bond_query_indexes.reapply_bond_query_indexes",
    "bond_management.patches.add_bond_management_manager_access.execute",
    "bond_management.patches.add_bond_exchange_rate_permissions.execute",
    "bond_management.patches.add_bond_yield_comparison_report_permission.execute",
]

# Uninstallation
# ------------

# before_uninstall = "bond_management.uninstall.before_uninstall"
# after_uninstall = "bond_management.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "bond_management.utils.before_app_install"
# after_app_install = "bond_management.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "bond_management.utils.before_app_uninstall"
# after_app_uninstall = "bond_management.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "bond_management.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "bond_management.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
    "Bond Portfolio": "bond_management.bond_management.utils.investor_permissions.portfolio_query_condition",
    "Bond Transaction": "bond_management.bond_management.utils.investor_permissions.transaction_query_condition",
    "Bond Statement": "bond_management.bond_management.utils.investor_permissions.statement_query_condition",
}

has_permission = {
    "Bond Portfolio": "bond_management.bond_management.utils.investor_permissions.has_portfolio_permission",
    "Bond Transaction": "bond_management.bond_management.utils.investor_permissions.has_transaction_permission",
    "Bond Statement": "bond_management.bond_management.utils.investor_permissions.has_statement_permission",
}

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
#     "*": {
#         "on_update": "method",
#         "on_cancel": "method",
#         "on_trash": "method"
#     }
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
#     "all": [
#         "bond_management.tasks.all"
#     ],
#     "daily": [
#         "bond_management.tasks.daily"
#     ],
#     "hourly": [
#         "bond_management.tasks.hourly"
#     ],
#     "weekly": [
#         "bond_management.tasks.weekly"
#     ],
#     "monthly": [
#         "bond_management.tasks.monthly"
#     ],
# }

# Testing
# -------

# before_tests = "bond_management.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
#     "Task": "bond_management.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#     "frappe.desk.doctype.event.event.get_events": "bond_management.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#     "Task": "bond_management.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["bond_management.utils.before_request"]
# after_request = ["bond_management.utils.after_request"]

# Job Events
# ----------
# before_job = ["bond_management.utils.before_job"]
# after_job = ["bond_management.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
#     {
#         "doctype": "{doctype_1}",
#         "filter_by": "{filter_by}",
#         "redact_fields": ["{field_1}", "{field_2}"],
#         "partial": 1,
#     },
#     {
#         "doctype": "{doctype_2}",
#         "filter_by": "{filter_by}",
#         "partial": 1,
#     },
#     {
#         "doctype": "{doctype_3}",
#         "strict": False,
#     },
#     {
#         "doctype": "{doctype_4}"
#     }
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#     "bond_management.auth.validate"
# ]

on_session_creation = [
    "bond_management.bond_management.utils.investor_permissions.redirect_investor_to_workspace"
]

# Investor logouts from Desk include ``redirect-to=/desk`` in the login URL.
# Frappe's login client gives that URL precedence over the server-provided
# home_page, so redirect the resulting generic Desk route to the restricted
# investor Workspace after boot.
app_include_js = "/assets/bond_management/js/investor_desk_redirect.js"

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
#     "Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
