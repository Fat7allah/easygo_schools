"""Fee Collection Dashboard Chart."""

import frappe
from frappe import _
from frappe.utils import getdate, add_months


def get_data():
    """Get fee collection data for dashboard chart."""
    
    # Get monthly collection data
    monthly_data = frappe.db.sql("""
        SELECT 
            DATE_FORMAT(pe.payment_date, '%Y-%m') as month,
            SUM(pe.amount) as collected_amount,
            COUNT(DISTINCT pe.student) as paying_students
        FROM `tabPayment Entry` pe
        WHERE pe.payment_date >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
        AND pe.docstatus = 1
        GROUP BY DATE_FORMAT(pe.payment_date, '%Y-%m')
        ORDER BY month
    """, as_dict=True)
    
    # Get outstanding amounts by fee type
    outstanding_data = frappe.db.sql("""
        SELECT 
            fi.fee_type,
            SUM(fb.outstanding_amount) as outstanding
        FROM `tabFee Bill` fb
        JOIN `tabFee Item` fi ON fi.parent = fb.name
        WHERE fb.status IN ('Unpaid', 'Partially Paid')
        GROUP BY fi.fee_type
        ORDER BY outstanding DESC
    """, as_dict=True)
    
    return {
        "monthly_collections": monthly_data,
        "outstanding_by_type": outstanding_data
    }


def get_chart_config():
    """Get chart configuration."""
    return {
        "name": _("Fee Collection Trends"),
        "chart_name": _("Monthly Fee Collections"),
        "chart_type": "line",
        "doctype": "Payment Entry",
        "is_public": 1,
        "module": "EasyGo Education",
        "type": "Sum",
        "value_based_on": "amount",
        "timeseries": 1,
        "time_interval": "Monthly",
        "timespan": "Last Year",
        "filters_json": '{"docstatus": 1}'
    }
