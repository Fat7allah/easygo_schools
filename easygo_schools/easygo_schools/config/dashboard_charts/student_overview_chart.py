"""Student Overview Dashboard Chart."""

import frappe
from frappe import _


def get_data():
    """Get student overview data for dashboard chart."""
    
    # Get total students by class
    class_data = frappe.db.sql("""
        SELECT 
            school_class,
            COUNT(*) as student_count
        FROM `tabStudent`
        WHERE is_active = 1
        GROUP BY school_class
        ORDER BY school_class
    """, as_dict=True)
    
    # Get enrollment trends (last 6 months)
    enrollment_trends = frappe.db.sql("""
        SELECT 
            DATE_FORMAT(creation, '%Y-%m') as month,
            COUNT(*) as new_enrollments
        FROM `tabStudent`
        WHERE creation >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(creation, '%Y-%m')
        ORDER BY month
    """, as_dict=True)
    
    return {
        "class_distribution": class_data,
        "enrollment_trends": enrollment_trends
    }


def get_chart_config():
    """Get chart configuration."""
    return {
        "name": _("Student Overview"),
        "chart_name": _("Student Distribution by Class"),
        "chart_type": "donut",
        "doctype": "Student",
        "is_public": 1,
        "module": "EasyGo Education",
        "type": "Count",
        "timeseries": 0,
        "filters_json": '{"is_active": 1}',
        "group_by_type": "Count",
        "group_by_based_on": "school_class"
    }
