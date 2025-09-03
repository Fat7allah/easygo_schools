"""Daily job for attendance reminders."""

import frappe
from frappe import _
from frappe.utils import getdate, add_days


def execute():
    """Send attendance reminders to teachers."""
    today = getdate()
    
    # Get classes that haven't marked attendance today
    classes_without_attendance = get_classes_without_attendance(today)
    
    for class_info in classes_without_attendance:
        send_attendance_reminder(class_info)
    
    # Send late arrival notifications to parents
    send_late_arrival_notifications(today)


def get_classes_without_attendance(date):
    """Get classes that haven't marked attendance for the given date."""
    return frappe.db.sql("""
        SELECT DISTINCT sc.name as class_name, sc.class_teacher
        FROM `tabSchool Class` sc
        WHERE sc.is_active = 1
        AND NOT EXISTS (
            SELECT 1 FROM `tabStudent Attendance` sa
            WHERE sa.school_class = sc.name
            AND sa.attendance_date = %s
        )
    """, (date,), as_dict=True)


def send_attendance_reminder(class_info):
    """Send attendance reminder to class teacher."""
    if not class_info.get('class_teacher'):
        return
    
    teacher_email = frappe.db.get_value("Employee", class_info['class_teacher'], "company_email")
    if not teacher_email:
        return
    
    subject = _("Attendance Reminder - {0}").format(class_info['class_name'])
    message = _("""
    Dear Teacher,
    
    This is a reminder that attendance has not been marked for class {0} today.
    
    Please mark attendance as soon as possible.
    
    Best regards,
    School Administration
    """).format(class_info['class_name'])
    
    try:
        frappe.sendmail(
            recipients=[teacher_email],
            subject=subject,
            message=message
        )
    except Exception as e:
        frappe.log_error(f"Failed to send attendance reminder: {str(e)}")


def send_late_arrival_notifications(date):
    """Send late arrival notifications to parents."""
    late_students = frappe.get_list("Student Attendance",
        filters={
            "attendance_date": date,
            "status": "Late"
        },
        fields=["student", "arrival_time", "school_class"]
    )
    
    for attendance in late_students:
        student_doc = frappe.get_doc("Student", attendance['student'])
        if student_doc.parent_email:
            send_late_notification(student_doc, attendance)


def send_late_notification(student, attendance):
    """Send late arrival notification to parent."""
    subject = _("Late Arrival Notification - {0}").format(student.student_name)
    message = _("""
    Dear Parent,
    
    Your child {0} arrived late to school today at {1}.
    
    Class: {2}
    
    Please ensure punctuality in the future.
    
    Best regards,
    School Administration
    """).format(
        student.student_name,
        attendance['arrival_time'],
        attendance['school_class']
    )
    
    try:
        frappe.sendmail(
            recipients=[student.parent_email],
            subject=subject,
            message=message
        )
    except Exception as e:
        frappe.log_error(f"Failed to send late notification: {str(e)}")
