"""Attendance Summary Report script."""

import frappe
from frappe import _
from frappe.utils import getdate, add_days


def execute(filters=None):
    """Execute Attendance Summary Report."""
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data, filters)
    summary = get_report_summary(data, filters)
    
    return columns, data, summary, chart


def get_columns():
    """Get report columns."""
    return [
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
            "label": _("Total Days"),
            "fieldname": "total_days",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Present"),
            "fieldname": "present_days",
            "fieldtype": "Int",
            "width": 80
        },
        {
            "label": _("Absent"),
            "fieldname": "absent_days",
            "fieldtype": "Int",
            "width": 80
        },
        {
            "label": _("Late"),
            "fieldname": "late_days",
            "fieldtype": "Int",
            "width": 80
        },
        {
            "label": _("Excused"),
            "fieldname": "excused_days",
            "fieldtype": "Int",
            "width": 80
        },
        {
            "label": _("Attendance %"),
            "fieldname": "attendance_percentage",
            "fieldtype": "Percent",
            "width": 120
        },
        {
            "label": _("Status"),
            "fieldname": "attendance_status",
            "fieldtype": "Data",
            "width": 100
        }
    ]


def get_data(filters):
    """Get report data."""
    conditions = get_conditions(filters)
    
    query = f"""
        SELECT 
            s.name as student_id,
            s.student_name,
            s.school_class,
            COUNT(sa.name) as total_days,
            SUM(CASE WHEN sa.status = 'Present' THEN 1 ELSE 0 END) as present_days,
            SUM(CASE WHEN sa.status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
            SUM(CASE WHEN sa.status = 'Late' THEN 1 ELSE 0 END) as late_days,
            SUM(CASE WHEN sa.status = 'Excused' THEN 1 ELSE 0 END) as excused_days,
            CASE 
                WHEN COUNT(sa.name) > 0 THEN 
                    (SUM(CASE WHEN sa.status IN ('Present', 'Late') THEN 1 ELSE 0 END) * 100.0 / COUNT(sa.name))
                ELSE 0 
            END as attendance_percentage
        FROM `tabStudent` s
        LEFT JOIN `tabStudent Attendance` sa ON s.name = sa.student
        WHERE s.status = 'Active' {conditions}
        GROUP BY s.name, s.student_name, s.school_class
        ORDER BY s.school_class, s.student_name
    """
    
    data = frappe.db.sql(query, as_dict=1)
    
    # Add attendance status based on percentage
    for row in data:
        percentage = row.get("attendance_percentage", 0)
        if percentage >= 95:
            row["attendance_status"] = "Excellent"
        elif percentage >= 90:
            row["attendance_status"] = "Very Good"
        elif percentage >= 85:
            row["attendance_status"] = "Good"
        elif percentage >= 75:
            row["attendance_status"] = "Satisfactory"
        else:
            row["attendance_status"] = "Poor"
    
    return data


def get_conditions(filters):
    """Build query conditions based on filters."""
    conditions = []
    
    if filters.get("academic_year"):
        conditions.append(f"AND sa.academic_year = '{filters.get('academic_year')}'")
    
    if filters.get("school_class"):
        conditions.append(f"AND s.school_class = '{filters.get('school_class')}'")
    
    if filters.get("student"):
        conditions.append(f"AND s.name = '{filters.get('student')}'")
    
    if filters.get("from_date"):
        conditions.append(f"AND sa.attendance_date >= '{filters.get('from_date')}'")
    
    if filters.get("to_date"):
        conditions.append(f"AND sa.attendance_date <= '{filters.get('to_date')}'")
    
    return " ".join(conditions)


def get_chart_data(data, filters):
    """Generate chart data for attendance visualization."""
    if not data:
        return None
    
    # Attendance status distribution
    status_counts = {
        "Excellent": 0,
        "Very Good": 0,
        "Good": 0,
        "Satisfactory": 0,
        "Poor": 0
    }
    
    for row in data:
        status = row.get("attendance_status", "Poor")
        if status in status_counts:
            status_counts[status] += 1
    
    chart = {
        "data": {
            "labels": list(status_counts.keys()),
            "datasets": [
                {
                    "name": _("Number of Students"),
                    "values": list(status_counts.values())
                }
            ]
        },
        "type": "bar",
        "height": 300,
        "colors": ["#28a745", "#17a2b8", "#ffc107", "#fd7e14", "#dc3545"]
    }
    
    return chart


def get_report_summary(data, filters):
    """Generate report summary statistics."""
    if not data:
        return []
    
    total_students = len(data)
    total_days = sum([d.get("total_days", 0) for d in data])
    total_present = sum([d.get("present_days", 0) for d in data])
    total_absent = sum([d.get("absent_days", 0) for d in data])
    total_late = sum([d.get("late_days", 0) for d in data])
    
    overall_attendance = (total_present / total_days * 100) if total_days > 0 else 0
    
    # Count students by attendance status
    excellent_count = len([d for d in data if d.get("attendance_status") == "Excellent"])
    poor_count = len([d for d in data if d.get("attendance_status") == "Poor"])
    
    return [
        {
            "value": total_students,
            "label": _("Total Students"),
            "datatype": "Int"
        },
        {
            "value": f"{overall_attendance:.1f}%",
            "label": _("Overall Attendance Rate"),
            "datatype": "Data"
        },
        {
            "value": total_present,
            "label": _("Total Present Days"),
            "datatype": "Int"
        },
        {
            "value": total_absent,
            "label": _("Total Absent Days"),
            "datatype": "Int"
        },
        {
            "value": total_late,
            "label": _("Total Late Days"),
            "datatype": "Int"
        },
        {
            "value": excellent_count,
            "label": _("Students with Excellent Attendance"),
            "datatype": "Int"
        },
        {
            "value": poor_count,
            "label": _("Students with Poor Attendance"),
            "datatype": "Int"
        }
    ]
