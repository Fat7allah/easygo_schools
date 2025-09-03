"""Student Performance Report script."""

import frappe
from frappe import _


def execute(filters=None):
    """Execute Student Performance Report."""
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data, filters)
    
    return columns, data, None, chart


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
            "label": _("Subject"),
            "fieldname": "subject",
            "fieldtype": "Link",
            "options": "Subject",
            "width": 120
        },
        {
            "label": _("Assessment"),
            "fieldname": "assessment",
            "fieldtype": "Link",
            "options": "Assessment",
            "width": 150
        },
        {
            "label": _("Score"),
            "fieldname": "score",
            "fieldtype": "Float",
            "width": 80
        },
        {
            "label": _("Max Score"),
            "fieldname": "max_score",
            "fieldtype": "Float",
            "width": 80
        },
        {
            "label": _("Percentage"),
            "fieldname": "percentage",
            "fieldtype": "Percent",
            "width": 100
        },
        {
            "label": _("Letter Grade"),
            "fieldname": "letter_grade",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Grade Point"),
            "fieldname": "grade_point",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        }
    ]


def get_data(filters):
    """Get report data."""
    conditions = get_conditions(filters)
    
    query = f"""
        SELECT 
            g.student as student_id,
            s.student_name,
            s.school_class,
            g.subject,
            g.assessment,
            g.score,
            g.max_score,
            g.percentage,
            g.letter_grade,
            g.grade_point,
            CASE 
                WHEN g.percentage >= 60 THEN 'Pass'
                ELSE 'Fail'
            END as status
        FROM `tabGrade` g
        LEFT JOIN `tabStudent` s ON g.student = s.name
        WHERE g.docstatus = 1 {conditions}
        ORDER BY s.student_name, g.subject, g.assessment
    """
    
    return frappe.db.sql(query, as_dict=1)


def get_conditions(filters):
    """Build query conditions based on filters."""
    conditions = []
    
    if filters.get("academic_year"):
        conditions.append(f"AND g.academic_year = '{filters.get('academic_year')}'")
    
    if filters.get("school_class"):
        conditions.append(f"AND s.school_class = '{filters.get('school_class')}'")
    
    if filters.get("student"):
        conditions.append(f"AND g.student = '{filters.get('student')}'")
    
    if filters.get("subject"):
        conditions.append(f"AND g.subject = '{filters.get('subject')}'")
    
    if filters.get("from_date"):
        conditions.append(f"AND g.creation >= '{filters.get('from_date')}'")
    
    if filters.get("to_date"):
        conditions.append(f"AND g.creation <= '{filters.get('to_date')}'")
    
    return " ".join(conditions)


def get_chart_data(data, filters):
    """Generate chart data for performance visualization."""
    if not data:
        return None
    
    # Performance distribution chart
    performance_ranges = {
        "Excellent (90-100%)": 0,
        "Very Good (80-89%)": 0,
        "Good (70-79%)": 0,
        "Satisfactory (60-69%)": 0,
        "Needs Improvement (<60%)": 0
    }
    
    for row in data:
        percentage = row.get("percentage", 0)
        if percentage >= 90:
            performance_ranges["Excellent (90-100%)"] += 1
        elif percentage >= 80:
            performance_ranges["Very Good (80-89%)"] += 1
        elif percentage >= 70:
            performance_ranges["Good (70-79%)"] += 1
        elif percentage >= 60:
            performance_ranges["Satisfactory (60-69%)"] += 1
        else:
            performance_ranges["Needs Improvement (<60%)"] += 1
    
    chart = {
        "data": {
            "labels": list(performance_ranges.keys()),
            "datasets": [
                {
                    "name": _("Number of Students"),
                    "values": list(performance_ranges.values())
                }
            ]
        },
        "type": "donut",
        "height": 300,
        "colors": ["#28a745", "#17a2b8", "#ffc107", "#fd7e14", "#dc3545"]
    }
    
    return chart


def get_report_summary(data, filters):
    """Generate report summary statistics."""
    if not data:
        return []
    
    total_assessments = len(data)
    total_pass = len([d for d in data if d.get("status") == "Pass"])
    total_fail = total_assessments - total_pass
    pass_percentage = (total_pass / total_assessments * 100) if total_assessments > 0 else 0
    
    avg_score = sum([d.get("percentage", 0) for d in data]) / total_assessments if total_assessments > 0 else 0
    
    return [
        {
            "value": total_assessments,
            "label": _("Total Assessments"),
            "datatype": "Int"
        },
        {
            "value": total_pass,
            "label": _("Pass Count"),
            "datatype": "Int"
        },
        {
            "value": total_fail,
            "label": _("Fail Count"),
            "datatype": "Int"
        },
        {
            "value": f"{pass_percentage:.1f}%",
            "label": _("Pass Rate"),
            "datatype": "Data"
        },
        {
            "value": f"{avg_score:.1f}%",
            "label": _("Average Score"),
            "datatype": "Data"
        }
    ]
