import frappe
from frappe import _
from frappe.utils import flt, cint, getdate


def execute(filters=None):
    """Execute Discipline Report"""
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
            "fieldname": "incident_date",
            "label": _("Incident Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "incident_type",
            "label": _("Incident Type"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "severity",
            "label": _("Severity"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "action_taken",
            "label": _("Action Taken"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "total_incidents",
            "label": _("Total Incidents"),
            "fieldtype": "Int",
            "width": 120
        }
    ]


def get_data(filters):
    """Get report data"""
    conditions = get_conditions(filters)
    
    data = frappe.db.sql(f"""
        SELECT 
            dr.student,
            s.student_name,
            dr.class,
            dr.incident_date,
            dr.incident_type,
            dr.severity,
            dr.action_taken,
            dr.status,
            COUNT(*) OVER (PARTITION BY dr.student) as total_incidents
        FROM `tabDiscipline Record` dr
        JOIN `tabStudent` s ON dr.student = s.name
        WHERE dr.docstatus = 1 {conditions}
        ORDER BY dr.incident_date DESC, s.student_name
    """, filters, as_dict=True)
    
    return data


def get_conditions(filters):
    """Build SQL conditions from filters"""
    conditions = []
    
    if filters.get("from_date"):
        conditions.append("dr.incident_date >= %(from_date)s")
        
    if filters.get("to_date"):
        conditions.append("dr.incident_date <= %(to_date)s")
        
    if filters.get("student"):
        conditions.append("dr.student = %(student)s")
        
    if filters.get("class"):
        conditions.append("dr.class = %(class)s")
        
    if filters.get("incident_type"):
        conditions.append("dr.incident_type = %(incident_type)s")
        
    if filters.get("severity"):
        conditions.append("dr.severity = %(severity)s")
        
    if filters.get("status"):
        conditions.append("dr.status = %(status)s")
        
    return " AND " + " AND ".join(conditions) if conditions else ""


def get_chart_data(data, filters):
    """Generate chart data for discipline report"""
    if not data:
        return None
        
    # Incident type distribution
    incident_counts = {}
    for row in data:
        incident_type = row.get("incident_type", "Unknown")
        incident_counts[incident_type] = incident_counts.get(incident_type, 0) + 1
        
    return {
        "data": {
            "labels": list(incident_counts.keys()),
            "datasets": [
                {
                    "name": _("Incidents"),
                    "values": list(incident_counts.values())
                }
            ]
        },
        "type": "donut",
        "colors": ["#dc3545", "#ffc107", "#fd7e14", "#6f42c1"]
    }


@frappe.whitelist()
def get_discipline_summary(filters=None):
    """Get discipline summary for dashboard"""
    conditions = get_conditions(filters)
    
    summary = frappe.db.sql(f"""
        SELECT 
            COUNT(*) as total_incidents,
            COUNT(DISTINCT dr.student) as students_involved,
            COUNT(CASE WHEN dr.severity = 'High' THEN 1 END) as high_severity,
            COUNT(CASE WHEN dr.severity = 'Medium' THEN 1 END) as medium_severity,
            COUNT(CASE WHEN dr.severity = 'Low' THEN 1 END) as low_severity,
            COUNT(CASE WHEN dr.status = 'Resolved' THEN 1 END) as resolved_cases,
            COUNT(CASE WHEN dr.status = 'Pending' THEN 1 END) as pending_cases
        FROM `tabDiscipline Record` dr
        WHERE dr.docstatus = 1 {conditions}
    """, filters, as_dict=True)
    
    return summary[0] if summary else {}
