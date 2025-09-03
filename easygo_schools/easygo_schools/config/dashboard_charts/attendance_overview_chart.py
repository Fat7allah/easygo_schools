"""Attendance Overview Dashboard Chart."""

import frappe
from frappe import _


def get_data():
    """Get attendance data for dashboard chart."""
    
    # Get daily attendance rates for last 30 days
    daily_attendance = frappe.db.sql("""
        SELECT 
            attendance_date,
            COUNT(*) as total_marked,
            COUNT(CASE WHEN status = 'Present' THEN 1 END) as present_count,
            COUNT(CASE WHEN status = 'Absent' THEN 1 END) as absent_count,
            COUNT(CASE WHEN status = 'Late' THEN 1 END) as late_count,
            ROUND((COUNT(CASE WHEN status IN ('Present', 'Late', 'Excused') THEN 1 END) * 100.0 / COUNT(*)), 2) as attendance_rate
        FROM `tabStudent Attendance`
        WHERE attendance_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        AND docstatus = 1
        GROUP BY attendance_date
        ORDER BY attendance_date DESC
    """, as_dict=True)
    
    # Get class-wise attendance summary
    class_attendance = frappe.db.sql("""
        SELECT 
            school_class,
            ROUND(AVG(CASE WHEN status IN ('Present', 'Late', 'Excused') THEN 100.0 ELSE 0 END), 2) as avg_attendance_rate
        FROM `tabStudent Attendance`
        WHERE attendance_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        AND docstatus = 1
        GROUP BY school_class
        ORDER BY avg_attendance_rate DESC
    """, as_dict=True)
    
    return {
        "daily_trends": daily_attendance,
        "class_summary": class_attendance
    }


def get_chart_config():
    """Get chart configuration."""
    return {
        "name": _("Attendance Overview"),
        "chart_name": _("Daily Attendance Trends"),
        "chart_type": "line",
        "doctype": "Student Attendance",
        "is_public": 1,
        "module": "EasyGo Education",
        "type": "Count",
        "timeseries": 1,
        "time_interval": "Daily",
        "timespan": "Last Month",
        "filters_json": '{"docstatus": 1, "status": ["in", ["Present", "Late", "Excused"]]}'
    }
