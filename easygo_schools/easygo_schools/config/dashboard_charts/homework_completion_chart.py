"""Homework Completion Dashboard Chart."""

import frappe
from frappe import _


def get_data():
    """Get homework completion data for dashboard chart."""
    
    # Get weekly homework completion rates
    weekly_completion = frappe.db.sql("""
        SELECT 
            YEARWEEK(hs.submission_date) as week,
            COUNT(*) as total_submissions,
            COUNT(CASE WHEN hs.status = 'Submitted' THEN 1 END) as completed_count,
            ROUND((COUNT(CASE WHEN hs.status = 'Submitted' THEN 1 END) * 100.0 / COUNT(*)), 2) as completion_rate
        FROM `tabHomework Submission` hs
        WHERE hs.submission_date >= DATE_SUB(NOW(), INTERVAL 8 WEEK)
        GROUP BY YEARWEEK(hs.submission_date)
        ORDER BY week DESC
    """, as_dict=True)
    
    # Get subject-wise completion rates
    subject_completion = frappe.db.sql("""
        SELECT 
            h.subject,
            COUNT(hs.name) as total_assignments,
            COUNT(CASE WHEN hs.status = 'Submitted' THEN 1 END) as completed_assignments,
            ROUND((COUNT(CASE WHEN hs.status = 'Submitted' THEN 1 END) * 100.0 / COUNT(hs.name)), 2) as completion_rate
        FROM `tabHomework` h
        LEFT JOIN `tabHomework Submission` hs ON hs.homework = h.name
        WHERE h.due_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)
        GROUP BY h.subject
        ORDER BY completion_rate DESC
    """, as_dict=True)
    
    return {
        "weekly_trends": weekly_completion,
        "subject_breakdown": subject_completion
    }


def get_chart_config():
    """Get chart configuration."""
    return {
        "name": _("Homework Completion"),
        "chart_name": _("Weekly Homework Completion Rate"),
        "chart_type": "bar",
        "doctype": "Homework Submission",
        "is_public": 1,
        "module": "EasyGo Education",
        "type": "Count",
        "timeseries": 1,
        "time_interval": "Weekly",
        "timespan": "Last 2 Months",
        "filters_json": '{"status": "Submitted"}'
    }
