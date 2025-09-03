import frappe
from frappe import _
from frappe.utils import getdate, flt


def execute(filters=None):
    """Execute Student Attendance Report"""
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data, filters)
    
    return columns, data, None, chart


def get_columns():
    """Get report columns"""
    return [
        {
            "fieldname": "student",
            "label": _("Student ID"),
            "fieldtype": "Link",
            "options": "Student",
            "width": 120
        },
        {
            "fieldname": "student_name",
            "label": _("Student Name"),
            "fieldtype": "Data",
            "width": 180
        },
        {
            "fieldname": "class",
            "label": _("Class"),
            "fieldtype": "Link",
            "options": "School Class",
            "width": 120
        },
        {
            "fieldname": "total_days",
            "label": _("Total Days"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "present_days",
            "label": _("Present"),
            "fieldtype": "Int",
            "width": 80
        },
        {
            "fieldname": "absent_days",
            "label": _("Absent"),
            "fieldtype": "Int",
            "width": 80
        },
        {
            "fieldname": "late_days",
            "label": _("Late"),
            "fieldtype": "Int",
            "width": 80
        },
        {
            "fieldname": "attendance_percentage",
            "label": _("Attendance %"),
            "fieldtype": "Percent",
            "width": 120
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 100
        }
    ]


def get_data(filters):
    """Get report data"""
    conditions = get_conditions(filters)
    
    data = frappe.db.sql(f"""
        SELECT 
            sa.student,
            s.student_name,
            sa.class,
            COUNT(*) as total_days,
            SUM(CASE WHEN sa.status = 'Present' THEN 1 ELSE 0 END) as present_days,
            SUM(CASE WHEN sa.status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
            SUM(CASE WHEN sa.late_entry = 1 THEN 1 ELSE 0 END) as late_days,
            (SUM(CASE WHEN sa.status = 'Present' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as attendance_percentage
        FROM `tabStudent Attendance` sa
        JOIN `tabStudent` s ON sa.student = s.name
        WHERE sa.docstatus = 1 {conditions}
        GROUP BY sa.student, s.student_name, sa.class
        ORDER BY s.student_name
    """, filters, as_dict=True)
    
    # Add status based on attendance percentage
    for row in data:
        if row.attendance_percentage >= 90:
            row.status = "Excellent"
        elif row.attendance_percentage >= 80:
            row.status = "Good"
        elif row.attendance_percentage >= 70:
            row.status = "Average"
        else:
            row.status = "Poor"
            
    return data


def get_conditions(filters):
    """Build SQL conditions from filters"""
    conditions = []
    
    if filters.get("from_date"):
        conditions.append("sa.attendance_date >= %(from_date)s")
        
    if filters.get("to_date"):
        conditions.append("sa.attendance_date <= %(to_date)s")
        
    if filters.get("class"):
        conditions.append("sa.class = %(class)s")
        
    if filters.get("student"):
        conditions.append("sa.student = %(student)s")
        
    if filters.get("academic_year"):
        conditions.append("sa.academic_year = %(academic_year)s")
        
    return " AND " + " AND ".join(conditions) if conditions else ""


def get_chart_data(data, filters):
    """Generate chart data for attendance report"""
    if not data:
        return None
        
    # Attendance status distribution
    status_counts = {}
    for row in data:
        status = row.get("status", "Unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        
    return {
        "data": {
            "labels": list(status_counts.keys()),
            "datasets": [
                {
                    "name": _("Students"),
                    "values": list(status_counts.values())
                }
            ]
        },
        "type": "donut",
        "colors": ["#28a745", "#17a2b8", "#ffc107", "#dc3545"]
    }


@frappe.whitelist()
def get_attendance_summary(filters=None):
    """Get attendance summary for dashboard"""
    conditions = get_conditions(filters)
    
    summary = frappe.db.sql(f"""
        SELECT 
            COUNT(DISTINCT sa.student) as total_students,
            COUNT(*) as total_records,
            SUM(CASE WHEN sa.status = 'Present' THEN 1 ELSE 0 END) as total_present,
            SUM(CASE WHEN sa.status = 'Absent' THEN 1 ELSE 0 END) as total_absent,
            AVG(CASE WHEN sa.status = 'Present' THEN 100.0 ELSE 0 END) as avg_attendance
        FROM `tabStudent Attendance` sa
        WHERE sa.docstatus = 1 {conditions}
    """, filters, as_dict=True)
    
    return summary[0] if summary else {}
