"""Portal API endpoints for Student/Parent/Teacher portals."""

import frappe
from frappe import _
from frappe.utils import getdate, today, add_days
import json


@frappe.whitelist(allow_guest=False)
def get_portal_home(role=None):
    """Get portal home dashboard data based on user role."""
    user = frappe.session.user
    if not role:
        # Determine role from user
        user_roles = frappe.get_roles(user)
        if "Student" in user_roles:
            role = "Student"
        elif "Parent" in user_roles:
            role = "Parent"
        elif "Teacher" in user_roles:
            role = "Teacher"
        else:
            frappe.throw(_("Access denied. Invalid role."))
    
    if role == "Student":
        return get_student_dashboard()
    elif role == "Parent":
        return get_parent_dashboard()
    elif role == "Teacher":
        return get_teacher_dashboard()
    else:
        frappe.throw(_("Invalid role specified"))


def get_student_dashboard():
    """Get student dashboard data."""
    user = frappe.session.user
    
    # Get student record
    student = frappe.db.get_value("Student", {"user_id": user}, ["name", "student_name", "school_class", "photo"])
    if not student:
        frappe.throw(_("Student record not found"))
    
    student_id = student[0]
    
    # Get today's schedule
    today_schedule = frappe.db.sql("""
        SELECT subject, instructor, room, start_time, end_time
        FROM `tabCourse Schedule`
        WHERE school_class = %s
        AND day_of_week = DAYNAME(CURDATE())
        AND is_active = 1
        ORDER BY start_time
    """, student[2], as_dict=True)
    
    # Get recent attendance
    attendance_summary = frappe.db.sql("""
        SELECT 
            COUNT(*) as total_days,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days
        FROM `tabStudent Attendance`
        WHERE student = %s
        AND attendance_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    """, student_id, as_dict=True)[0]
    
    attendance_percentage = 0
    if attendance_summary.total_days > 0:
        attendance_percentage = (attendance_summary.present_days / attendance_summary.total_days) * 100
    
    # Get recent grades
    recent_grades = frappe.db.sql("""
        SELECT g.subject, g.grade, g.max_grade, a.assessment_name, a.assessment_date
        FROM `tabGrade` g
        JOIN `tabAssessment` a ON g.assessment = a.name
        WHERE g.student = %s
        AND g.is_published = 1
        ORDER BY a.assessment_date DESC
        LIMIT 5
    """, student_id, as_dict=True)
    
    # Get pending homework
    pending_homework = frappe.db.sql("""
        SELECT h.title, h.subject, h.due_date, h.description
        FROM `tabHomework` h
        LEFT JOIN `tabHomework Submission` hs ON h.name = hs.homework AND hs.student = %s
        WHERE h.school_class = %s
        AND h.due_date >= CURDATE()
        AND hs.name IS NULL
        ORDER BY h.due_date
        LIMIT 5
    """, (student_id, student[2]), as_dict=True)
    
    return {
        "student_info": {
            "name": student[1],
            "class": student[2],
            "photo": student[3]
        },
        "today_schedule": today_schedule,
        "attendance_summary": {
            "percentage": round(attendance_percentage, 1),
            "present_days": attendance_summary.present_days,
            "absent_days": attendance_summary.absent_days,
            "total_days": attendance_summary.total_days
        },
        "recent_grades": recent_grades,
        "pending_homework": pending_homework
    }


def get_parent_dashboard():
    """Get parent dashboard data."""
    user = frappe.session.user
    
    # Get children records
    children = frappe.db.sql("""
        SELECT name, student_name, school_class, photo, status
        FROM `tabStudent`
        WHERE guardian_email = %s
        AND status = 'Active'
        ORDER BY student_name
    """, user, as_dict=True)
    
    if not children:
        frappe.throw(_("No student records found for this parent"))
    
    children_data = []
    for child in children:
        # Get alerts for this child
        alerts = []
        
        # Check for recent absences
        recent_absences = frappe.db.count("Student Attendance", {
            "student": child.name,
            "status": ["in", ["Absent", "Late"]],
            "attendance_date": [">=", add_days(today(), -7)]
        })
        if recent_absences > 0:
            alerts.append({
                "type": "attendance",
                "message": f"{recent_absences} absence(s) this week",
                "severity": "warning"
            })
        
        # Check for overdue fees
        overdue_fees = frappe.db.sql("""
            SELECT COUNT(*) as count, SUM(outstanding_amount) as amount
            FROM `tabFee Bill`
            WHERE student = %s
            AND outstanding_amount > 0
            AND due_date < CURDATE()
            AND docstatus = 1
        """, child.name, as_dict=True)[0]
        
        if overdue_fees.count > 0:
            alerts.append({
                "type": "fees",
                "message": f"{overdue_fees.amount:.2f} MAD overdue",
                "severity": "danger"
            })
        
        # Get latest grades
        latest_grade = frappe.db.sql("""
            SELECT g.subject, g.grade, g.max_grade
            FROM `tabGrade` g
            JOIN `tabAssessment` a ON g.assessment = a.name
            WHERE g.student = %s
            AND g.is_published = 1
            ORDER BY a.assessment_date DESC
            LIMIT 1
        """, child.name, as_dict=True)
        
        children_data.append({
            "student_info": child,
            "alerts": alerts,
            "latest_grade": latest_grade[0] if latest_grade else None
        })
    
    return {
        "children": children_data
    }


def get_teacher_dashboard():
    """Get teacher dashboard data."""
    user = frappe.session.user
    
    # Get teacher record
    teacher = frappe.db.get_value("Employee", {"user_id": user}, ["name", "employee_name"])
    if not teacher:
        frappe.throw(_("Teacher record not found"))
    
    teacher_id = teacher[0]
    
    # Get today's classes
    today_classes = frappe.db.sql("""
        SELECT cs.subject, cs.school_class, cs.room, cs.start_time, cs.end_time,
               COUNT(s.name) as student_count
        FROM `tabCourse Schedule` cs
        LEFT JOIN `tabStudent` s ON s.school_class = cs.school_class AND s.status = 'Active'
        WHERE cs.instructor = %s
        AND cs.day_of_week = DAYNAME(CURDATE())
        AND cs.is_active = 1
        GROUP BY cs.name
        ORDER BY cs.start_time
    """, teacher_id, as_dict=True)
    
    # Get pending grading
    pending_grading = frappe.db.sql("""
        SELECT a.assessment_name, a.subject, a.school_class, a.assessment_date,
               COUNT(g.name) as graded_count,
               (SELECT COUNT(*) FROM `tabStudent` WHERE school_class = a.school_class AND status = 'Active') as total_students
        FROM `tabAssessment` a
        LEFT JOIN `tabGrade` g ON a.name = g.assessment
        WHERE a.instructor = %s
        AND a.status = 'Completed'
        GROUP BY a.name
        HAVING graded_count < total_students
        ORDER BY a.assessment_date DESC
        LIMIT 5
    """, teacher_id, as_dict=True)
    
    # Get assigned classes
    assigned_classes = frappe.db.sql("""
        SELECT name, class_name, level
        FROM `tabSchool Class`
        WHERE class_teacher = %s
        AND is_active = 1
    """, teacher_id, as_dict=True)
    
    # Get recent messages
    recent_messages = frappe.db.sql("""
        SELECT mt.subject, mt.participants, m.content, m.creation
        FROM `tabMessage Thread` mt
        JOIN `tabMessage` m ON mt.name = m.thread
        WHERE mt.participants LIKE %s
        ORDER BY m.creation DESC
        LIMIT 5
    """, f"%{user}%", as_dict=True)
    
    return {
        "teacher_info": {
            "name": teacher[1]
        },
        "today_classes": today_classes,
        "pending_grading": pending_grading,
        "assigned_classes": assigned_classes,
        "recent_messages": recent_messages
    }


@frappe.whitelist(allow_guest=False)
def get_timetable(student_or_teacher=None):
    """Get timetable for student or teacher."""
    user = frappe.session.user
    user_roles = frappe.get_roles(user)
    
    if "Student" in user_roles:
        # Get student's class timetable
        student = frappe.db.get_value("Student", {"user_id": user}, "school_class")
        if not student:
            frappe.throw(_("Student record not found"))
        
        timetable = frappe.db.sql("""
            SELECT day_of_week, subject, instructor, room, start_time, end_time, duration_minutes
            FROM `tabCourse Schedule`
            WHERE school_class = %s
            AND is_active = 1
            ORDER BY 
                FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'),
                start_time
        """, student, as_dict=True)
        
    elif "Teacher" in user_roles:
        # Get teacher's schedule
        teacher = frappe.db.get_value("Employee", {"user_id": user}, "name")
        if not teacher:
            frappe.throw(_("Teacher record not found"))
        
        timetable = frappe.db.sql("""
            SELECT day_of_week, subject, school_class, room, start_time, end_time, duration_minutes
            FROM `tabCourse Schedule`
            WHERE instructor = %s
            AND is_active = 1
            ORDER BY 
                FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'),
                start_time
        """, teacher, as_dict=True)
        
    else:
        frappe.throw(_("Access denied"))
    
    # Group by day
    grouped_timetable = {}
    for entry in timetable:
        day = entry.day_of_week
        if day not in grouped_timetable:
            grouped_timetable[day] = []
        grouped_timetable[day].append(entry)
    
    return grouped_timetable


@frappe.whitelist(allow_guest=False)
def get_attendance(student=None):
    """Get attendance records for student."""
    user = frappe.session.user
    user_roles = frappe.get_roles(user)
    
    if "Student" in user_roles:
        student = frappe.db.get_value("Student", {"user_id": user}, "name")
    elif "Parent" in user_roles and student:
        # Verify parent has access to this student
        guardian_email = frappe.db.get_value("Student", student, "guardian_email")
        if guardian_email != user:
            frappe.throw(_("Access denied"))
    else:
        frappe.throw(_("Access denied"))
    
    if not student:
        frappe.throw(_("Student not specified"))
    
    # Get attendance records for last 30 days
    attendance = frappe.db.sql("""
        SELECT attendance_date, status, time_in, time_out, is_justified, justification_reason
        FROM `tabStudent Attendance`
        WHERE student = %s
        AND attendance_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        ORDER BY attendance_date DESC
    """, student, as_dict=True)
    
    return attendance


@frappe.whitelist(allow_guest=False)
def submit_attendance_justification(payload):
    """Submit attendance justification."""
    data = json.loads(payload) if isinstance(payload, str) else payload
    
    user = frappe.session.user
    user_roles = frappe.get_roles(user)
    
    if "Parent" not in user_roles and "Student" not in user_roles:
        frappe.throw(_("Access denied"))
    
    # Create attendance justification record
    justification = frappe.get_doc({
        "doctype": "Attendance Justification",
        "student": data.get("student"),
        "attendance_date": data.get("attendance_date"),
        "reason": data.get("reason"),
        "submitted_by": user,
        "status": "Pending"
    })
    
    if data.get("attachment"):
        justification.attachment = data.get("attachment")
    
    justification.insert(ignore_permissions=True)
    
    return {"message": _("Justification submitted successfully"), "name": justification.name}


@frappe.whitelist(allow_guest=False)
def list_homework(student=None):
    """List homework for student."""
    user = frappe.session.user
    user_roles = frappe.get_roles(user)
    
    if "Student" in user_roles:
        student = frappe.db.get_value("Student", {"user_id": user}, "name")
        student_class = frappe.db.get_value("Student", student, "school_class")
    elif "Parent" in user_roles and student:
        # Verify parent has access to this student
        guardian_email = frappe.db.get_value("Student", student, "guardian_email")
        if guardian_email != user:
            frappe.throw(_("Access denied"))
        student_class = frappe.db.get_value("Student", student, "school_class")
    else:
        frappe.throw(_("Access denied"))
    
    if not student or not student_class:
        frappe.throw(_("Student not found"))
    
    # Get homework assignments
    homework = frappe.db.sql("""
        SELECT h.name, h.title, h.subject, h.description, h.due_date, h.attachment,
               hs.name as submission_id, hs.submission_date, hs.grade, hs.feedback
        FROM `tabHomework` h
        LEFT JOIN `tabHomework Submission` hs ON h.name = hs.homework AND hs.student = %s
        WHERE h.school_class = %s
        ORDER BY h.due_date DESC
        LIMIT 20
    """, (student, student_class), as_dict=True)
    
    return homework


@frappe.whitelist(allow_guest=False)
def submit_homework(student, homework, files=None, notes=None):
    """Submit homework."""
    user = frappe.session.user
    user_roles = frappe.get_roles(user)
    
    if "Student" not in user_roles:
        frappe.throw(_("Access denied"))
    
    # Verify student ownership
    student_user = frappe.db.get_value("Student", {"user_id": user}, "name")
    if student_user != student:
        frappe.throw(_("Access denied"))
    
    # Check if already submitted
    existing = frappe.db.exists("Homework Submission", {"homework": homework, "student": student})
    if existing:
        frappe.throw(_("Homework already submitted"))
    
    # Create submission
    submission = frappe.get_doc({
        "doctype": "Homework Submission",
        "homework": homework,
        "student": student,
        "submission_date": today(),
        "notes": notes,
        "status": "Submitted"
    })
    
    if files:
        submission.attachment = files
    
    submission.insert(ignore_permissions=True)
    
    return {"message": _("Homework submitted successfully"), "name": submission.name}
