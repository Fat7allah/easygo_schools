"""Dashboard configuration for Teachers."""

from frappe import _


def get_data():
    """Get dashboard data for Teachers."""
    return {
        "heatmap": True,
        "heatmap_message": _("This is based on your class attendance records"),
        "fieldname": "attendance_date",
        "transactions": [
            {
                "label": _("My Classes"),
                "items": ["Course Schedule", "Student Attendance"]
            },
            {
                "label": _("Assessments"),
                "items": ["Assessment", "Exam", "Grade"]
            },
            {
                "label": _("Assignments"),
                "items": ["Homework", "Homework Submission"]
            },
            {
                "label": _("Communication"),
                "items": ["Meeting Request", "Communication Log"]
            }
        ],
        "charts": [
            {
                "chart_name": _("My Classes Attendance"),
                "chart_type": "line",
                "document_type": "Student Attendance",
                "based_on": "attendance_date",
                "timespan": "Last Month",
                "time_interval": "Daily",
                "filters_json": '{"instructor": ["=", "{{ user }}"]}',
                "custom_options": {
                    "type": "line",
                    "axisOptions": {
                        "xIsSeries": 1
                    }
                }
            },
            {
                "chart_name": _("Homework Submission Status"),
                "chart_type": "donut",
                "document_type": "Homework Submission",
                "based_on": "status",
                "filters_json": '{"teacher": ["=", "{{ user }}"]}'
            },
            {
                "chart_name": _("Grade Distribution"),
                "chart_type": "bar",
                "document_type": "Grade",
                "based_on": "letter_grade",
                "filters_json": '{"instructor": ["=", "{{ user }}"]}'
            },
            {
                "chart_name": _("Student Performance Trend"),
                "chart_type": "line",
                "document_type": "Grade",
                "based_on": "creation",
                "timespan": "Last 3 Months",
                "time_interval": "Weekly",
                "filters_json": '{"instructor": ["=", "{{ user }}"]}'
            }
        ],
        "number_cards": [
            {
                "label": _("My Students"),
                "function": "Custom",
                "method": "easygo_education.api.dashboard.get_teacher_student_count"
            },
            {
                "label": _("My Classes"),
                "function": "Count",
                "document_type": "Course Schedule",
                "filters_json": '{"instructor": ["=", "{{ user }}"], "is_active": 1}'
            },
            {
                "label": _("Pending Homework"),
                "function": "Count",
                "document_type": "Homework",
                "filters_json": '{"teacher": ["=", "{{ user }}"], "status": "Active"}'
            },
            {
                "label": _("Ungraded Submissions"),
                "function": "Count",
                "document_type": "Homework Submission",
                "filters_json": '{"teacher": ["=", "{{ user }}"], "status": "Submitted", "score": ["is", "not set"]}'
            },
            {
                "label": _("Meeting Requests"),
                "function": "Count",
                "document_type": "Meeting Request",
                "filters_json": '{"teacher": ["=", "{{ user }}"], "status": "Pending"}'
            },
            {
                "label": _("Today's Classes"),
                "function": "Custom",
                "method": "easygo_education.api.dashboard.get_today_classes_count"
            }
        ]
    }
