from . import __version__ as app_version

app_name = "easygo_schools"
app_title = "EasyGo Schools"
app_publisher = "EasyGo Education Team"
app_description = "Comprehensive educational institution management system for Morocco"
app_icon = "octicon octicon-mortar-board"
app_color = "blue"
app_email = "contact@easygo-education.ma"
app_license = "MIT"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "easygo_schools",
# 		"logo": "/assets/easygo_schools/logo.png",
# 		"title": "Easygo Schools",
# 		"route": "/easygo_schools",
# 		"has_permission": "easygo_schools.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/easygo_schools/css/easygo_schools.css"
# app_include_js = "/assets/easygo_schools/js/easygo_schools.js"

# include js, css files in header of web template
# web_include_css = "/assets/easygo_schools/css/easygo_schools.css"
# web_include_js = "/assets/easygo_schools/js/easygo_schools.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "easygo_schools/public/scss/website"

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
# app_include_icons = "easygo_schools/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "easygo_schools.utils.jinja_methods",
# 	"filters": "easygo_schools.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "easygo_schools.install.before_install"
after_install = "easygo_schools.patches.v1_bootstrap.execute"

# Uninstallation
# ------------

# before_uninstall = "easygo_schools.uninstall.before_uninstall"
# after_uninstall = "easygo_schools.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "easygo_schools.utils.before_app_install"
# after_app_install = "easygo_schools.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "easygo_schools.utils.before_app_uninstall"
# after_app_uninstall = "easygo_schools.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "easygo_schools.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"easygo_schools.tasks.all"
# 	],
# 	"daily": [
# 		"easygo_schools.tasks.daily"
# 	],
# 	"hourly": [
# 		"easygo_schools.tasks.hourly"
# 	],
# 	"weekly": [
# 		"easygo_schools.tasks.weekly"
# 	],
# 	"monthly": [
# 		"easygo_schools.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "easygo_schools.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "easygo_schools.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "easygo_schools.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["easygo_schools.utils.before_request"]
# after_request = ["easygo_schools.utils.after_request"]

# Job Events
# ----------
# before_job = ["easygo_schools.utils.before_job"]
# after_job = ["easygo_schools.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"easygo_schools.auth.validate"
# ]

# Fixtures
# --------
# Export fixtures for the app

fixtures = [
    {
        "doctype": "Role",
        "filters": [
            [
                "name",
                "in",
                [
                    "Student",
                    "Parent",
                    "Teacher",
                    "Principal",
                    "Accountant",
                    "HR Manager",
                    "Maintenance",
                    "Transport",
                    "Canteen",
                    "Director",
                ],
            ]
        ],
    },
    {
        "doctype": "Desktop Icon",
        "filters": [["module_name", "=", "EasyGo Schools"]],
    },
    "Letter Head",
    "Web Form",
]

# Website
# -------

website_route_rules = [
    {"from_route": "/student/<path:app_path>", "to_route": "student"},
    {"from_route": "/parent/<path:app_path>", "to_route": "parent"},
    {"from_route": "/teacher/<path:app_path>", "to_route": "teacher"},
]

# Portal menu items
portal_menu_items = [
    {
        "title": "Student Portal",
        "route": "/student",
        "reference_doctype": "Student",
        "role": "Student",
    },
    {
        "title": "Parent Portal",
        "route": "/parent",
        "reference_doctype": "Guardian",
        "role": "Parent",
    },
    {
        "title": "Teacher Portal",
        "route": "/teacher",
        "reference_doctype": "Employee",
        "role": "Teacher",
    },
]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

