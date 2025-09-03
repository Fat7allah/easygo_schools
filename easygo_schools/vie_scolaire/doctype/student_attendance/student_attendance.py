"""Student Attendance doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class StudentAttendance(Document):
    """Student Attendance doctype controller with business rules."""
    
    def validate(self):
        """Validate attendance data."""
        self.validate_attendance_date()
        self.fetch_student_details()
        self.validate_duplicate()
        self.update_justification_status()
    
    def validate_attendance_date(self):
        """Validate attendance date is not in future."""
        if self.attendance_date and getdate(self.attendance_date) > getdate(today()):
            frappe.throw(_("Attendance Date cannot be in the future"))
    
    def fetch_student_details(self):
        """Fetch student details when student is selected."""
        if self.student:
            student = frappe.get_doc("Student", self.student)
            self.student_name = student.student_name
            self.school_class = student.school_class
    
    def validate_duplicate(self):
        """Validate no duplicate attendance for same student and date."""
        existing = frappe.db.get_value(
            "Student Attendance",
            {
                "student": self.student,
                "attendance_date": self.attendance_date,
                "name": ["!=", self.name]
            },
            "name"
        )
        if existing:
            frappe.throw(_("Attendance already marked for {0} on {1}").format(
                self.student_name, frappe.utils.formatdate(self.attendance_date)
            ))
    
    def update_justification_status(self):
        """Update status based on justification."""
        if self.status == "Absent" and self.is_justified:
            self.status = "Absent Justifié"
        elif self.status == "Absent Justifié" and not self.is_justified:
            self.status = "Absent"
    
    def after_insert(self):
        """Actions after attendance is marked."""
        self.notify_guardian()
    
    def notify_guardian(self):
        """Send notification to guardian for absences or late arrivals."""
        if self.status not in ["Absent", "Late"]:
            return
            
        # Get guardian email
        guardian_email = frappe.db.get_value("Student", self.student, "guardian_email")
        if not guardian_email:
            return
            
        # Check if notifications are enabled
        enable_notifications = frappe.db.get_single_value("School Settings", "enable_email_notifications")
        if not enable_notifications:
            return
            
        try:
            school_name = frappe.db.get_single_value("School Settings", "school_name") or "School"
            
            if self.status == "Absent":
                subject = _("Absence Notification - {0}").format(self.student_name)
                message = _("""
                <p>Dear Parent,</p>
                
                <p>This is to inform you that {0} was marked absent on {1}.</p>
                
                <p>If this absence was due to illness or other valid reason, please submit a justification through the parent portal or contact the school.</p>
                
                <p>Best regards,<br>
                {2} Administration</p>
                """).format(
                    self.student_name,
                    frappe.utils.formatdate(self.attendance_date),
                    school_name
                )
            else:  # Late
                subject = _("Late Arrival Notification - {0}").format(self.student_name)
                message = _("""
                <p>Dear Parent,</p>
                
                <p>This is to inform you that {0} arrived late to school on {1}.</p>
                
                <p>Arrival time: {2}</p>
                
                <p>Please ensure punctual arrival to avoid disruption to learning.</p>
                
                <p>Best regards,<br>
                {3} Administration</p>
                """).format(
                    self.student_name,
                    frappe.utils.formatdate(self.attendance_date),
                    self.time_in or "Not recorded",
                    school_name
                )
            
            frappe.sendmail(
                recipients=[guardian_email],
                subject=subject,
                message=message
            )
            
            # Log the notification
            frappe.get_doc({
                "doctype": "Communication Log",
                "reference_doctype": "Student Attendance",
                "reference_name": self.name,
                "communication_type": "Email",
                "subject": subject,
                "status": "Sent"
            }).insert(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Failed to send attendance notification for {self.name}: {str(e)}")


def notify_guardian(doc, method):
    """Hook function to notify guardian on attendance marking."""
    # This is called from hooks.py - the actual logic is in after_insert
    pass
