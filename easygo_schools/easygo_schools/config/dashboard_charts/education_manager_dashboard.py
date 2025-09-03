"""Dashboard configuration for Education Manager."""

from frappe import _


def get_data():
    """Get dashboard data for Education Manager."""
    return {
        "heatmap": True,
        "heatmap_message": _("This is based on the attendance of students"),
        "fieldname": "attendance_date",
        "transactions": [
            {
                "label": _("Student Management"),
                "items": ["Student", "School Class", "Academic Year"]
            },
            {
                "label": _("Academic"),
                "items": ["Subject", "Course Schedule", "Assessment", "Exam", "Grade"]
            },
            {
                "label": _("Attendance & Discipline"),
                "items": ["Student Attendance", "Homework", "Homework Submission"]
            },
            {
                "label": _("Finance"),
                "items": ["Fee Bill", "Employee"]
            },
            {
                "label": _("Communication"),
                "items": ["Meeting Request", "Communication Log"]
            }
        ],
        "charts": [
            {
                "chart_name": _("Student Enrollment Trend"),
                "chart_type": "line",
                "document_type": "Student",
                "based_on": "creation",
                "timespan": "Last Year",
                "time_interval": "Monthly",
                "filters_json": '{"status": "Active"}'
            },
            {
                "chart_name": _("Fee Collection Status"),
                "chart_type": "donut",
                "document_type": "Fee Bill",
                "based_on": "status",
                "filters_json": '{"docstatus": 1}'
            },
            {
                "chart_name": _("Attendance Overview"),
                "chart_type": "bar",
                "document_type": "Student Attendance",
                "based_on": "status",
                "timespan": "Last Month",
                "filters_json": '{"docstatus": 1}'
            },
            {
                "chart_name": _("Grade Distribution"),
                "chart_type": "pie",
                "document_type": "Grade",
                "based_on": "letter_grade",
                "filters_json": '{"docstatus": 1}'
            }
        ],
        "number_cards": [
            {
                "label": _("Total Students"),
                "function": "Count",
                "document_type": "Student",
                "filters_json": '{"status": "Active"}'
            },
            {
                "label": _("Total Classes"),
                "function": "Count",
                "document_type": "School Class",
                "filters_json": '{"is_active": 1}'
            },
            {
                "label": _("Total Teachers"),
                "function": "Count",
                "document_type": "Employee",
                "filters_json": '{"status": "Active", "designation": ["like", "%Teacher%"]}'
            },
            {
                "label": _("Pending Fee Bills"),
                "function": "Count",
                "document_type": "Fee Bill",
                "filters_json": '{"status": "Pending", "docstatus": 1}'
            },
            {
                "label": _("Outstanding Amount"),
                "function": "Sum",
                "aggregate_function_based_on": "outstanding_amount",
                "document_type": "Fee Bill",
                "filters_json": '{"status": ["!=", "Paid"], "docstatus": 1}'
            },
            {
                "label": _("This Month Attendance Rate"),
                "function": "Custom",
                "method": "easygo_education.api.dashboard.get_attendance_rate"
            }
        ]
    }
