"""Fee Collection Summary Report."""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    """Execute the Fee Collection Summary Report."""
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data)
    
    return columns, data, None, chart


def get_columns():
    """Get report columns."""
    return [
        {
            "label": _("Fee Type"),
            "fieldname": "fee_type",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Class"),
            "fieldname": "school_class",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Total Billed"),
            "fieldname": "total_billed",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Total Collected"),
            "fieldname": "total_collected",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Outstanding"),
            "fieldname": "outstanding",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Collection %"),
            "fieldname": "collection_percentage",
            "fieldtype": "Percent",
            "width": 120
        },
        {
            "label": _("No. of Students"),
            "fieldname": "student_count",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": _("Paid Students"),
            "fieldname": "paid_students",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": _("Pending Students"),
            "fieldname": "pending_students",
            "fieldtype": "Int",
            "width": 120
        }
    ]


def get_data(filters):
    """Get report data."""
    conditions = get_conditions(filters)
    
    data = frappe.db.sql(f"""
        SELECT 
            COALESCE(fi.fee_type, 'Total') as fee_type,
            COALESCE(fb.school_class, 'All Classes') as school_class,
            SUM(fi.total_amount) as total_billed,
            SUM(CASE WHEN fb.status IN ('Paid', 'Partially Paid') 
                THEN fi.total_amount - fb.outstanding_amount 
                ELSE 0 END) as total_collected,
            SUM(fb.outstanding_amount) as outstanding,
            COUNT(DISTINCT fb.student) as student_count,
            COUNT(DISTINCT CASE WHEN fb.status = 'Paid' THEN fb.student END) as paid_students,
            COUNT(DISTINCT CASE WHEN fb.status IN ('Unpaid', 'Partially Paid') THEN fb.student END) as pending_students
        FROM `tabFee Bill` fb
        LEFT JOIN `tabFee Item` fi ON fi.parent = fb.name
        WHERE fb.docstatus = 1 {conditions}
        GROUP BY fi.fee_type, fb.school_class WITH ROLLUP
        ORDER BY fi.fee_type, fb.school_class
    """, as_dict=True)
    
    # Calculate collection percentage
    for row in data:
        if row.total_billed:
            row.collection_percentage = (row.total_collected / row.total_billed) * 100
        else:
            row.collection_percentage = 0
    
    return data


def get_conditions(filters):
    """Get query conditions based on filters."""
    conditions = ""
    
    if filters.get('from_date'):
        conditions += f" AND fb.posting_date >= '{filters['from_date']}'"
    
    if filters.get('to_date'):
        conditions += f" AND fb.posting_date <= '{filters['to_date']}'"
    
    if filters.get('school_class'):
        conditions += f" AND fb.school_class = '{filters['school_class']}'"
    
    if filters.get('fee_type'):
        conditions += f" AND fi.fee_type = '{filters['fee_type']}'"
    
    if filters.get('academic_year'):
        conditions += f" AND fb.academic_year = '{filters['academic_year']}'"
    
    return conditions


def get_chart_data(data):
    """Get chart data for visualization."""
    if not data:
        return None
    
    # Filter out rollup rows for chart
    chart_data = [row for row in data if row.fee_type != 'Total' and row.school_class != 'All Classes']
    
    if not chart_data:
        return None
    
    labels = []
    collected = []
    outstanding = []
    
    for row in chart_data:
        if row.fee_type and row.school_class:
            labels.append(f"{row.fee_type} - {row.school_class}")
            collected.append(flt(row.total_collected))
            outstanding.append(flt(row.outstanding))
    
    return {
        "data": {
            "labels": labels[:10],  # Limit to top 10 for readability
            "datasets": [
                {
                    "name": _("Collected"),
                    "values": collected[:10]
                },
                {
                    "name": _("Outstanding"),
                    "values": outstanding[:10]
                }
            ]
        },
        "type": "bar",
        "height": 300,
        "colors": ["#28a745", "#dc3545"]
    }
