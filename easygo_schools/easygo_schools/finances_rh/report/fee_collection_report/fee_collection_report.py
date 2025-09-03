"""Fee Collection Report script."""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    """Execute Fee Collection Report."""
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data, filters)
    summary = get_report_summary(data, filters)
    
    return columns, data, summary, chart


def get_columns():
    """Get report columns."""
    return [
        {
            "label": _("Fee Bill ID"),
            "fieldname": "fee_bill_id",
            "fieldtype": "Link",
            "options": "Fee Bill",
            "width": 120
        },
        {
            "label": _("Student ID"),
            "fieldname": "student_id",
            "fieldtype": "Link",
            "options": "Student",
            "width": 120
        },
        {
            "label": _("Student Name"),
            "fieldname": "student_name",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": _("Class"),
            "fieldname": "school_class",
            "fieldtype": "Link",
            "options": "School Class",
            "width": 120
        },
        {
            "label": _("Term"),
            "fieldname": "term",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Total Amount"),
            "fieldname": "total_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Paid Amount"),
            "fieldname": "paid_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Outstanding"),
            "fieldname": "outstanding_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Due Date"),
            "fieldname": "due_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Payment Method"),
            "fieldname": "payment_method",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Collection Rate"),
            "fieldname": "collection_rate",
            "fieldtype": "Percent",
            "width": 120
        }
    ]


def get_data(filters):
    """Get report data."""
    conditions = get_conditions(filters)
    
    query = f"""
        SELECT 
            fb.name as fee_bill_id,
            fb.student as student_id,
            s.student_name,
            s.school_class,
            fb.term,
            fb.total_amount,
            fb.paid_amount,
            fb.outstanding_amount,
            fb.due_date,
            fb.status,
            fb.payment_method,
            CASE 
                WHEN fb.total_amount > 0 THEN 
                    (fb.paid_amount * 100.0 / fb.total_amount)
                ELSE 0 
            END as collection_rate
        FROM `tabFee Bill` fb
        LEFT JOIN `tabStudent` s ON fb.student = s.name
        WHERE fb.docstatus = 1 {conditions}
        ORDER BY fb.due_date DESC, s.student_name
    """
    
    return frappe.db.sql(query, as_dict=1)


def get_conditions(filters):
    """Build query conditions based on filters."""
    conditions = []
    
    if filters.get("academic_year"):
        conditions.append(f"AND fb.academic_year = '{filters.get('academic_year')}'")
    
    if filters.get("school_class"):
        conditions.append(f"AND s.school_class = '{filters.get('school_class')}'")
    
    if filters.get("student"):
        conditions.append(f"AND fb.student = '{filters.get('student')}'")
    
    if filters.get("term"):
        conditions.append(f"AND fb.term = '{filters.get('term')}'")
    
    if filters.get("status"):
        conditions.append(f"AND fb.status = '{filters.get('status')}'")
    
    if filters.get("from_date"):
        conditions.append(f"AND fb.due_date >= '{filters.get('from_date')}'")
    
    if filters.get("to_date"):
        conditions.append(f"AND fb.due_date <= '{filters.get('to_date')}'")
    
    if filters.get("payment_method"):
        conditions.append(f"AND fb.payment_method = '{filters.get('payment_method')}'")
    
    return " ".join(conditions)


def get_chart_data(data, filters):
    """Generate chart data for fee collection visualization."""
    if not data:
        return None
    
    # Collection status distribution
    status_amounts = {}
    for row in data:
        status = row.get("status", "Unknown")
        amount = flt(row.get("total_amount", 0))
        
        if status in status_amounts:
            status_amounts[status] += amount
        else:
            status_amounts[status] = amount
    
    chart = {
        "data": {
            "labels": list(status_amounts.keys()),
            "datasets": [
                {
                    "name": _("Amount (MAD)"),
                    "values": list(status_amounts.values())
                }
            ]
        },
        "type": "pie",
        "height": 300,
        "colors": ["#28a745", "#ffc107", "#dc3545", "#17a2b8"]
    }
    
    return chart


def get_report_summary(data, filters):
    """Generate report summary statistics."""
    if not data:
        return []
    
    total_bills = len(data)
    total_amount = sum([flt(d.get("total_amount", 0)) for d in data])
    total_paid = sum([flt(d.get("paid_amount", 0)) for d in data])
    total_outstanding = sum([flt(d.get("outstanding_amount", 0)) for d in data])
    
    collection_rate = (total_paid / total_amount * 100) if total_amount > 0 else 0
    
    # Status counts
    paid_count = len([d for d in data if d.get("status") == "Paid"])
    pending_count = len([d for d in data if d.get("status") == "Pending"])
    overdue_count = len([d for d in data if d.get("status") == "Overdue"])
    
    # Average amounts
    avg_bill_amount = total_amount / total_bills if total_bills > 0 else 0
    avg_payment = total_paid / paid_count if paid_count > 0 else 0
    
    return [
        {
            "value": total_bills,
            "label": _("Total Fee Bills"),
            "datatype": "Int"
        },
        {
            "value": total_amount,
            "label": _("Total Amount (MAD)"),
            "datatype": "Currency"
        },
        {
            "value": total_paid,
            "label": _("Total Collected (MAD)"),
            "datatype": "Currency"
        },
        {
            "value": total_outstanding,
            "label": _("Total Outstanding (MAD)"),
            "datatype": "Currency"
        },
        {
            "value": f"{collection_rate:.1f}%",
            "label": _("Collection Rate"),
            "datatype": "Data"
        },
        {
            "value": paid_count,
            "label": _("Paid Bills"),
            "datatype": "Int"
        },
        {
            "value": pending_count,
            "label": _("Pending Bills"),
            "datatype": "Int"
        },
        {
            "value": overdue_count,
            "label": _("Overdue Bills"),
            "datatype": "Int"
        },
        {
            "value": avg_bill_amount,
            "label": _("Average Bill Amount (MAD)"),
            "datatype": "Currency"
        },
        {
            "value": avg_payment,
            "label": _("Average Payment (MAD)"),
            "datatype": "Currency"
        }
    ]
