"""Extended Portal API endpoints for additional functionality."""

import frappe
from frappe import _
from frappe.utils import getdate, today, add_days
import json


@frappe.whitelist(allow_guest=False)
def save_bulk_attendance(attendance_data):
    """Save bulk attendance records for teachers."""
    user = frappe.session.user
    user_roles = frappe.get_roles(user)
    
    if "Teacher" not in user_roles:
        frappe.throw(_("Access denied. Teacher role required."))
    
    attendance_records = json.loads(attendance_data) if isinstance(attendance_data, str) else attendance_data
    
    created_records = []
    for record in attendance_records:
        # Check if attendance already exists
        existing = frappe.db.exists("Student Attendance", {
            "student": record["student"],
            "attendance_date": record["attendance_date"]
        })
        
        if existing:
            # Update existing record
            doc = frappe.get_doc("Student Attendance", existing)
            doc.status = record["status"]
            doc.save(ignore_permissions=True)
            created_records.append(doc.name)
        else:
            # Create new record
            doc = frappe.get_doc({
                "doctype": "Student Attendance",
                "student": record["student"],
                "attendance_date": record["attendance_date"],
                "status": record["status"]
            })
            doc.insert(ignore_permissions=True)
            created_records.append(doc.name)
    
    return {"message": _("Attendance saved successfully"), "records": created_records}


@frappe.whitelist(allow_guest=False)
def get_message_recipients(type, teacher=None):
    """Get message recipients based on type."""
    user = frappe.session.user
    user_roles = frappe.get_roles(user)
    
    if "Teacher" not in user_roles:
        frappe.throw(_("Access denied"))
    
    recipients = []
    
    if type == "student":
        # Get students from teacher's classes
        classes = frappe.get_all("Course Schedule",
            filters={"instructor": teacher, "is_active": 1},
            fields=["school_class"],
            distinct=True
        )
        
        for cls in classes:
            students = frappe.get_all("Student",
                filters={"school_class": cls.school_class, "status": "Active"},
                fields=["name", "student_name"]
            )
            for student in students:
                recipients.append({
                    "value": student.name,
                    "label": f"{student.student_name} ({cls.school_class})"
                })
    
    elif type == "parent":
        # Get parents from teacher's classes
        classes = frappe.get_all("Course Schedule",
            filters={"instructor": teacher, "is_active": 1},
            fields=["school_class"],
            distinct=True
        )
        
        for cls in classes:
            students = frappe.get_all("Student",
                filters={"school_class": cls.school_class, "status": "Active"},
                fields=["guardian_email", "student_name"]
            )
            for student in students:
                if student.guardian_email:
                    recipients.append({
                        "value": student.guardian_email,
                        "label": f"Parent of {student.student_name}"
                    })
    
    return recipients


@frappe.whitelist(allow_guest=False)
def send_message(message_data):
    """Send message to recipients."""
    user = frappe.session.user
    user_roles = frappe.get_roles(user)
    
    if "Teacher" not in user_roles:
        frappe.throw(_("Access denied"))
    
    data = json.loads(message_data) if isinstance(message_data, str) else message_data
    
    # Create message thread
    thread = frappe.get_doc({
        "doctype": "Message Thread",
        "subject": data["subject"],
        "participants": f"{user},{data['recipient']}",
        "created_by": user
    })
    thread.insert(ignore_permissions=True)
    
    # Create message
    message = frappe.get_doc({
        "doctype": "Message",
        "thread": thread.name,
        "sender": user,
        "content": data["content"],
        "message_type": "Text"
    })
    message.insert(ignore_permissions=True)
    
    # Send email notification
    try:
        recipient_email = data["recipient"]
        if data["recipient_type"] == "student":
            recipient_email = frappe.db.get_value("Student", data["recipient"], "guardian_email")
        
        if recipient_email:
            frappe.sendmail(
                recipients=[recipient_email],
                subject=f"Message from Teacher: {data['subject']}",
                message=f"""
                <p>You have received a new message:</p>
                <p><strong>Subject:</strong> {data['subject']}</p>
                <p><strong>Message:</strong></p>
                <p>{data['content']}</p>
                <p>Please log in to the portal to reply.</p>
                """
            )
    except Exception as e:
        frappe.log_error(f"Failed to send message notification: {str(e)}")
    
    return {"message": _("Message sent successfully"), "thread": thread.name}


@frappe.whitelist(allow_guest=False)
def get_student_grades(student=None):
    """Get grades for a student."""
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
    
    # Get grades
    grades = frappe.get_all("Grade",
        filters={"student": student, "is_published": 1},
        fields=[
            "subject", "grade", "max_grade", "percentage", "letter_grade",
            "assessment", "assessment_date", "remarks"
        ],
        order_by="assessment_date desc"
    )
    
    # Group by subject
    subject_grades = {}
    for grade in grades:
        subject = grade.subject
        if subject not in subject_grades:
            subject_grades[subject] = []
        subject_grades[subject].append(grade)
    
    # Calculate subject averages
    subject_summaries = {}
    for subject, grades_list in subject_grades.items():
        if grades_list:
            avg_percentage = sum([g.percentage for g in grades_list if g.percentage]) / len(grades_list)
            subject_summaries[subject] = {
                "average_percentage": avg_percentage,
                "total_assessments": len(grades_list),
                "latest_grade": grades_list[0] if grades_list else None
            }
    
    return {
        "grades": grades,
        "subject_grades": subject_grades,
        "subject_summaries": subject_summaries
    }


@frappe.whitelist(allow_guest=False)
def get_fee_summary(student=None):
    """Get fee summary for a student."""
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
    
    # Get fee bills
    fee_bills = frappe.get_all("Fee Bill",
        filters={"student": student, "docstatus": 1},
        fields=[
            "name", "bill_date", "due_date", "total_amount", "paid_amount",
            "outstanding_amount", "status"
        ],
        order_by="due_date desc"
    )
    
    # Calculate totals
    total_billed = sum([bill.total_amount for bill in fee_bills])
    total_paid = sum([bill.paid_amount for bill in fee_bills])
    total_outstanding = sum([bill.outstanding_amount for bill in fee_bills])
    
    # Get overdue bills
    overdue_bills = [bill for bill in fee_bills 
                    if bill.outstanding_amount > 0 and getdate(bill.due_date) < getdate(today())]
    
    return {
        "fee_bills": fee_bills,
        "summary": {
            "total_billed": total_billed,
            "total_paid": total_paid,
            "total_outstanding": total_outstanding,
            "overdue_count": len(overdue_bills),
            "overdue_amount": sum([bill.outstanding_amount for bill in overdue_bills])
        }
    }


@frappe.whitelist(allow_guest=False)
def create_meeting_request(meeting_data):
    """Create a meeting request."""
    user = frappe.session.user
    user_roles = frappe.get_roles(user)
    
    if "Parent" not in user_roles:
        frappe.throw(_("Access denied. Parent role required."))
    
    data = json.loads(meeting_data) if isinstance(meeting_data, str) else meeting_data
    
    # Create meeting request
    meeting = frappe.get_doc({
        "doctype": "Meeting Request",
        "student": data["student"],
        "teacher": data["teacher"],
        "purpose": data["purpose"],
        "preferred_date": data["preferred_date"],
        "preferred_time": data["preferred_time"],
        "notes": data.get("notes", ""),
        "requested_by": user,
        "status": "Pending"
    })
    meeting.insert(ignore_permissions=True)
    
    # Send notification to teacher
    try:
        teacher_email = frappe.db.get_value("Employee", data["teacher"], "company_email")
        student_name = frappe.db.get_value("Student", data["student"], "student_name")
        
        if teacher_email:
            frappe.sendmail(
                recipients=[teacher_email],
                subject=f"Meeting Request - {student_name}",
                message=f"""
                <p>You have received a meeting request:</p>
                <ul>
                    <li><strong>Student:</strong> {student_name}</li>
                    <li><strong>Purpose:</strong> {data['purpose']}</li>
                    <li><strong>Preferred Date:</strong> {data['preferred_date']}</li>
                    <li><strong>Preferred Time:</strong> {data['preferred_time']}</li>
                    <li><strong>Notes:</strong> {data.get('notes', 'None')}</li>
                </ul>
                <p>Please log in to the teacher portal to respond to this request.</p>
                """
            )
    except Exception as e:
        frappe.log_error(f"Failed to send meeting request notification: {str(e)}")
    
    return {"message": _("Meeting request submitted successfully"), "name": meeting.name}
