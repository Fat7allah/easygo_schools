"""Class Performance Report."""

import frappe
from frappe import _


def execute(filters=None):
    """Execute the Class Performance Report."""
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data


def get_columns():
    """Get report columns."""
    return [
        {
            "label": _("Student"),
            "fieldname": "student_name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Student ID"),
            "fieldname": "student_id",
            "fieldtype": "Link",
            "options": "Student",
            "width": 120
        },
        {
            "label": _("Class"),
            "fieldname": "school_class",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Average Grade"),
            "fieldname": "average_grade",
            "fieldtype": "Float",
            "width": 120,
            "precision": 2
        },
        {
            "label": _("Attendance %"),
            "fieldname": "attendance_percentage",
            "fieldtype": "Percent",
            "width": 120
        },
        {
            "label": _("Homework Completion %"),
            "fieldname": "homework_completion",
            "fieldtype": "Percent",
            "width": 150
        },
        {
            "label": _("Behavior Score"),
            "fieldname": "behavior_score",
            "fieldtype": "Float",
            "width": 120,
            "precision": 1
        },
        {
            "label": _("Overall Performance"),
            "fieldname": "performance_level",
            "fieldtype": "Data",
            "width": 150
        }
    ]


def get_data(filters):
    """Get report data."""
    conditions = get_conditions(filters)
    
    data = frappe.db.sql(f"""
        SELECT 
            s.name as student_id,
            s.student_name,
            s.school_class,
            COALESCE(AVG(g.grade), 0) as average_grade,
            COALESCE(att.attendance_percentage, 0) as attendance_percentage,
            COALESCE(hw.completion_percentage, 0) as homework_completion,
            COALESCE(beh.behavior_score, 5.0) as behavior_score
        FROM `tabStudent` s
        LEFT JOIN `tabGrade` g ON g.student = s.name {conditions.get('grade_conditions', '')}
        LEFT JOIN (
            SELECT 
                student,
                (COUNT(CASE WHEN status = 'Present' THEN 1 END) * 100.0 / COUNT(*)) as attendance_percentage
            FROM `tabStudent Attendance`
            WHERE 1=1 {conditions.get('attendance_conditions', '')}
            GROUP BY student
        ) att ON att.student = s.name
        LEFT JOIN (
            SELECT 
                student,
                (COUNT(CASE WHEN status = 'Submitted' THEN 1 END) * 100.0 / COUNT(*)) as completion_percentage
            FROM `tabHomework Submission`
            WHERE 1=1 {conditions.get('homework_conditions', '')}
            GROUP BY student
        ) hw ON hw.student = s.name
        LEFT JOIN (
            SELECT 
                student,
                AVG(CASE 
                    WHEN action_type = 'Positive' THEN 1.0
                    WHEN action_type = 'Warning' THEN -0.5
                    WHEN action_type = 'Suspension' THEN -2.0
                    ELSE 0
                END) + 5.0 as behavior_score
            FROM `tabDisciplinary Action`
            WHERE 1=1 {conditions.get('disciplinary_conditions', '')}
            GROUP BY student
        ) beh ON beh.student = s.name
        WHERE s.is_active = 1 {conditions.get('student_conditions', '')}
        GROUP BY s.name, s.student_name, s.school_class
        ORDER BY s.school_class, s.student_name
    """, as_dict=True)
    
    # Calculate performance levels
    for row in data:
        row['performance_level'] = calculate_performance_level(row)
    
    return data


def get_conditions(filters):
    """Get query conditions based on filters."""
    conditions = {
        'student_conditions': '',
        'grade_conditions': '',
        'attendance_conditions': '',
        'homework_conditions': '',
        'disciplinary_conditions': ''
    }
    
    if filters.get('school_class'):
        conditions['student_conditions'] += f" AND s.school_class = '{filters['school_class']}'"
    
    if filters.get('academic_year'):
        conditions['grade_conditions'] += f" AND g.academic_year = '{filters['academic_year']}'"
        conditions['attendance_conditions'] += f" AND academic_year = '{filters['academic_year']}'"
        conditions['homework_conditions'] += f" AND academic_year = '{filters['academic_year']}'"
        conditions['disciplinary_conditions'] += f" AND academic_year = '{filters['academic_year']}'"
    
    if filters.get('from_date'):
        conditions['attendance_conditions'] += f" AND attendance_date >= '{filters['from_date']}'"
        conditions['homework_conditions'] += f" AND submission_date >= '{filters['from_date']}'"
        conditions['disciplinary_conditions'] += f" AND incident_date >= '{filters['from_date']}'"
    
    if filters.get('to_date'):
        conditions['attendance_conditions'] += f" AND attendance_date <= '{filters['to_date']}'"
        conditions['homework_conditions'] += f" AND submission_date <= '{filters['to_date']}'"
        conditions['disciplinary_conditions'] += f" AND incident_date <= '{filters['to_date']}'"
    
    return conditions


def calculate_performance_level(row):
    """Calculate overall performance level."""
    avg_grade = row.get('average_grade', 0)
    attendance = row.get('attendance_percentage', 0)
    homework = row.get('homework_completion', 0)
    behavior = row.get('behavior_score', 5.0)
    
    # Weighted performance calculation
    performance_score = (
        (avg_grade / 20 * 0.4) +  # 40% weight for grades
        (attendance / 100 * 0.3) +  # 30% weight for attendance
        (homework / 100 * 0.2) +   # 20% weight for homework
        (behavior / 10 * 0.1)      # 10% weight for behavior
    ) * 100
    
    if performance_score >= 85:
        return _("Excellent")
    elif performance_score >= 75:
        return _("Good")
    elif performance_score >= 65:
        return _("Satisfactory")
    elif performance_score >= 50:
        return _("Needs Improvement")
    else:
        return _("Poor")
