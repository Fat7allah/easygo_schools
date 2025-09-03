import frappe
from frappe import _
from frappe.utils import flt, cint


def execute(filters=None):
    """Execute Payroll Summary Report"""
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data, filters)
    
    return columns, data, None, chart


def get_columns():
    """Get report columns"""
    return [
        {
            "fieldname": "employee",
            "label": _("Employee ID"),
            "fieldtype": "Link",
            "options": "Employee",
            "width": 120
        },
        {
            "fieldname": "employee_name",
            "label": _("Employee Name"),
            "fieldtype": "Data",
            "width": 180
        },
        {
            "fieldname": "department",
            "label": _("Department"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "designation",
            "label": _("Designation"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "basic_salary",
            "label": _("Basic Salary"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "total_earnings",
            "label": _("Total Earnings"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "total_deductions",
            "label": _("Total Deductions"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "net_pay",
            "label": _("Net Pay"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "payment_status",
            "label": _("Payment Status"),
            "fieldtype": "Data",
            "width": 120
        }
    ]


def get_data(filters):
    """Get report data"""
    conditions = get_conditions(filters)
    
    data = frappe.db.sql(f"""
        SELECT 
            ss.employee,
            e.employee_name,
            e.department,
            e.designation,
            ss.basic_salary,
            ss.gross_pay as total_earnings,
            ss.total_deduction as total_deductions,
            ss.net_pay,
            CASE 
                WHEN ss.payment_status = 'Paid' THEN 'Paid'
                WHEN ss.payment_status = 'Pending' THEN 'Pending'
                ELSE 'Draft'
            END as payment_status
        FROM `tabSalary Slip` ss
        JOIN `tabEmployee` e ON ss.employee = e.name
        WHERE ss.docstatus = 1 {conditions}
        ORDER BY e.employee_name
    """, filters, as_dict=True)
    
    return data


def get_conditions(filters):
    """Build SQL conditions from filters"""
    conditions = []
    
    if filters.get("from_date"):
        conditions.append("ss.start_date >= %(from_date)s")
        
    if filters.get("to_date"):
        conditions.append("ss.end_date <= %(to_date)s")
        
    if filters.get("employee"):
        conditions.append("ss.employee = %(employee)s")
        
    if filters.get("department"):
        conditions.append("e.department = %(department)s")
        
    if filters.get("payroll_cycle"):
        conditions.append("ss.payroll_cycle = %(payroll_cycle)s")
        
    if filters.get("payment_status"):
        conditions.append("ss.payment_status = %(payment_status)s")
        
    return " AND " + " AND ".join(conditions) if conditions else ""


def get_chart_data(data, filters):
    """Generate chart data for payroll report"""
    if not data:
        return None
        
    # Department-wise payroll distribution
    dept_data = {}
    for row in data:
        dept = row.get("department", "Unknown")
        if dept not in dept_data:
            dept_data[dept] = {"count": 0, "total_pay": 0}
        dept_data[dept]["count"] += 1
        dept_data[dept]["total_pay"] += flt(row.get("net_pay", 0))
        
    return {
        "data": {
            "labels": list(dept_data.keys()),
            "datasets": [
                {
                    "name": _("Total Net Pay"),
                    "values": [dept_data[dept]["total_pay"] for dept in dept_data.keys()]
                }
            ]
        },
        "type": "bar"
    }


@frappe.whitelist()
def get_payroll_analytics(filters=None):
    """Get payroll analytics for dashboard"""
    conditions = get_conditions(filters)
    
    analytics = frappe.db.sql(f"""
        SELECT 
            COUNT(*) as total_employees,
            SUM(ss.gross_pay) as total_gross_pay,
            SUM(ss.total_deduction) as total_deductions,
            SUM(ss.net_pay) as total_net_pay,
            AVG(ss.net_pay) as avg_net_pay,
            COUNT(CASE WHEN ss.payment_status = 'Paid' THEN 1 END) as paid_count,
            COUNT(CASE WHEN ss.payment_status = 'Pending' THEN 1 END) as pending_count
        FROM `tabSalary Slip` ss
        JOIN `tabEmployee` e ON ss.employee = e.name
        WHERE ss.docstatus = 1 {conditions}
    """, filters, as_dict=True)
    
    return analytics[0] if analytics else {}
