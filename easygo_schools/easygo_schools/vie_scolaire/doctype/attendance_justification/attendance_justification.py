"""Attendance Justification doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate


class AttendanceJustification(Document):
    """Attendance Justification doctype controller for portal submissions."""
    
    def validate(self):
        """Validate attendance justification data."""
        self.validate_attendance_date()
        self.validate_existing_justification()
        self.set_defaults()
    
    def validate_attendance_date(self):
        """Validate attendance date."""
        if self.attendance_date and getdate(self.attendance_date) > getdate():
            frappe.throw(_("Attendance date cannot be in the future"))
    
    def validate_existing_justification(self):
        """Check for existing justification for the same date."""
        if self.student and self.attendance_date:
            existing = frappe.db.get_value("Attendance Justification",
                {
                    "student": self.student,
                    "attendance_date": self.attendance_date,
                    "name": ["!=", self.name or ""],
                    "status": ["!=", "Rejected"]
                },
                "name"
            )
            
            if existing:
                frappe.throw(_("Justification already exists for this date"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.submitted_by:
            self.submitted_by = frappe.session.user
        
        if not self.submission_date:
            self.submission_date = now()
        
        if not self.submitted_via:
            self.submitted_via = "Portal"
        
        # Fetch student name
        if self.student and not self.student_name:
            self.student_name = frappe.db.get_value("Student", self.student, "student_name")
    
    def after_insert(self):
        """Actions after justification creation."""
        self.send_submission_notification()
    
    def on_update(self):
        """Actions on justification update."""
        if self.has_value_changed("approval_status"):
            self.handle_approval_status_change()
    
    def send_submission_notification(self):
        """Send notification when justification is submitted."""
        try:
            # Get class teacher or education manager
            recipients = []
            
            if self.student:
                # Get student's class teacher
                student_class = frappe.db.get_value("Student", self.student, "school_class")
                if student_class:
                    class_teacher = frappe.db.get_value("School Class", student_class, "class_teacher")
                    if class_teacher:
                        teacher_email = frappe.db.get_value("User", class_teacher, "email")
                        if teacher_email:
                            recipients.append(teacher_email)
            
            # Also notify education managers
            education_managers = frappe.get_list("User",
                filters={"enabled": 1},
                fields=["email", "name"]
            )
            
            for manager in education_managers:
                user_roles = frappe.get_roles(manager.name)
                if "Education Manager" in user_roles and manager.email:
                    recipients.append(manager.email)
            
            if recipients:
                frappe.sendmail(
                    recipients=list(set(recipients)),  # Remove duplicates
                    subject=_("New Attendance Justification: {0}").format(self.student_name),
                    message=_("A new attendance justification has been submitted.\n\nStudent: {0}\nDate: {1}\nReason: {2}\nSubmitted by: {3}").format(
                        self.student_name, self.attendance_date, self.reason_type, self.submitted_by
                    ),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        except Exception as e:
            frappe.log_error(f"Failed to send submission notification: {str(e)}")
    
    def handle_approval_status_change(self):
        """Handle approval status changes."""
        if self.approval_status in ["Approved", "Rejected"]:
            self.reviewed_by = frappe.session.user
            self.review_date = now()
            
            if self.approval_status == "Approved":
                self.update_attendance_record()
            
            self.send_approval_notification()
    
    def update_attendance_record(self):
        """Update the attendance record when justified."""
        try:
            # Find the attendance record
            attendance_record = frappe.db.get_value("Student Attendance",
                {
                    "student": self.student,
                    "attendance_date": self.attendance_date
                },
                "name"
            )
            
            if attendance_record:
                attendance_doc = frappe.get_doc("Student Attendance", attendance_record)
                
                # Update status to justified
                if attendance_doc.status == "Absent":
                    attendance_doc.status = "Excused"
                    attendance_doc.justification = self.name
                    attendance_doc.save(ignore_permissions=True)
                    
                    frappe.msgprint(_("Attendance record updated to 'Excused'"))
            
        except Exception as e:
            frappe.log_error(f"Failed to update attendance record: {str(e)}")
    
    def send_approval_notification(self):
        """Send notification when justification is approved/rejected."""
        try:
            # Notify the submitter
            submitter_email = frappe.db.get_value("User", self.submitted_by, "email")
            
            if submitter_email:
                status_text = "approved" if self.approval_status == "Approved" else "rejected"
                
                frappe.sendmail(
                    recipients=[submitter_email],
                    subject=_("Attendance Justification {0}: {1}").format(status_text.title(), self.student_name),
                    message=_("Your attendance justification for {0} on {1} has been {2}.\n\nReview Comments: {3}").format(
                        self.student_name, self.attendance_date, status_text, self.review_comments or "None"
                    ),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
                
                self.notification_sent = 1
        
        except Exception as e:
            frappe.log_error(f"Failed to send approval notification: {str(e)}")
    
    @frappe.whitelist()
    def approve_justification(self, comments=None):
        """Approve the justification."""
        if self.approval_status == "Approved":
            frappe.throw(_("Justification is already approved"))
        
        self.approval_status = "Approved"
        self.status = "Approved"
        
        if comments:
            self.review_comments = comments
        
        self.save()
        
        return True
    
    @frappe.whitelist()
    def reject_justification(self, comments=None):
        """Reject the justification."""
        if self.approval_status == "Rejected":
            frappe.throw(_("Justification is already rejected"))
        
        self.approval_status = "Rejected"
        self.status = "Rejected"
        
        if comments:
            self.review_comments = comments
        
        self.save()
        
        return True
