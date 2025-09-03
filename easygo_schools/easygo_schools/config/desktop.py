"""Desktop configuration for EasyGo Education."""

from frappe import _


def get_data():
    """Get desktop configuration data."""
    return [
        # Education Management
        {
            "module_name": "EasyGo Education",
            "category": "Modules",
            "label": _("Education"),
            "color": "#4CAF50",
            "icon": "fa fa-graduation-cap",
            "type": "module",
            "description": _("Comprehensive school management system")
        },
        
        # Quick Access Cards
        {
            "module_name": "EasyGo Education",
            "category": "Places",
            "label": _("Student Portal"),
            "color": "#2196F3",
            "icon": "fa fa-user-graduate",
            "type": "page",
            "link": "student-portal",
            "description": _("Student dashboard and portal")
        },
        {
            "module_name": "EasyGo Education",
            "category": "Places",
            "label": _("Teacher Portal"),
            "color": "#FF9800",
            "icon": "fa fa-chalkboard-teacher",
            "type": "page",
            "link": "teacher-portal",
            "description": _("Teacher dashboard and tools")
        },
        {
            "module_name": "EasyGo Education",
            "category": "Places",
            "label": _("Parent Portal"),
            "color": "#9C27B0",
            "icon": "fa fa-users",
            "type": "page",
            "link": "parent-portal",
            "description": _("Parent dashboard and communication")
        },
        
        # Reports
        {
            "module_name": "EasyGo Education",
            "category": "Reports",
            "label": _("Class Performance"),
            "color": "#607D8B",
            "icon": "fa fa-chart-line",
            "type": "report",
            "link": "query-report/Class Performance Report",
            "description": _("Student performance analytics")
        },
        {
            "module_name": "EasyGo Education",
            "category": "Reports",
            "label": _("Fee Collection"),
            "color": "#4CAF50",
            "icon": "fa fa-money-bill",
            "type": "report",
            "link": "query-report/Fee Collection Summary",
            "description": _("Fee collection and outstanding reports")
        },
        {
            "module_name": "EasyGo Education",
            "category": "Reports",
            "label": _("Attendance Analytics"),
            "color": "#FF5722",
            "icon": "fa fa-calendar-check",
            "type": "report",
            "link": "query-report/Attendance Analytics",
            "description": _("Attendance trends and analysis")
        },
        {
            "module_name": "Scolarité",
            "category": "Modules",
            "label": _("Academics"),
            "color": "blue",
            "icon": "octicon octicon-book",
            "type": "module",
            "description": _("Student management, academics, timetables, assessments"),
        },
        {
            "module_name": "Vie Scolaire",
            "category": "Modules", 
            "label": _("School Life"),
            "color": "green",
            "icon": "octicon octicon-calendar",
            "type": "module",
            "description": _("Attendance, discipline, health, activities"),
        },
        {
            "module_name": "Finances RH",
            "category": "Modules",
            "label": _("Finance & HR"),
            "color": "orange",
            "icon": "octicon octicon-credit-card",
            "type": "module",
            "description": _("Fee management, payroll, budgeting"),
        },
        {
            "module_name": "Administration Comms",
            "category": "Modules",
            "label": _("Administration"),
            "color": "purple",
            "icon": "octicon octicon-megaphone",
            "type": "module",
            "description": _("Communications, notifications, meetings"),
        },
        {
            "module_name": "Gestion Etablissement",
            "category": "Modules",
            "label": _("Facility Management"),
            "color": "red",
            "icon": "octicon octicon-home",
            "type": "module",
            "description": _("Assets, maintenance, transport, canteen"),
        },
        {
            "module_name": "Referentiels",
            "category": "Modules",
            "label": _("References"),
            "color": "grey",
            "icon": "octicon octicon-gear",
            "type": "module",
            "description": _("Settings, grading scales, reference data"),
        },
    ]
