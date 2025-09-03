"""Meeting Request doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today, now


class MeetingRequest(Document):
    """Meeting Request doctype controller with business rules."""
    
    def validate(self):
        """Validate meeting request data."""
        self.validate_dates()
        self.validate_teacher_student_relationship()
        self.set_request_info()
    
    def validate_dates(self):
        """Validate meeting dates."""
        if self.preferred_date and getdate(self.preferred_date) <= getdate(today()):
            frappe.throw(_("Preferred date must be in the future"))
        
        if self.alternative_date and getdate(self.alternative_date) <= getdate(today()):
            frappe.throw(_("Alternative date must be in the future"))
        
        if self.scheduled_date and getdate(self.scheduled_date) <= getdate(today()):
            frappe.throw(_("Scheduled date must be in the future"))
    
    def validate_teacher_student_relationship(self):
        """Validate teacher teaches this student."""
        if self.teacher and self.student:
            student_class = frappe.db.get_value("Student", self.student, "school_class")
            
            # Check if teacher teaches this student's class
            schedule_exists = frappe.db.exists("Course Schedule", {
                "instructor": self.teacher,
                "school_class": student_class,
                "is_active": 1
            })
            
            if not schedule_exists:
                frappe.msgprint(_("Warning: Teacher {0} is not scheduled to teach {1}'s class").format(
                    self.teacher, self.student
                ), alert=True)
    
    def set_request_info(self):
        """Set request information."""
        if not self.requested_by:
            self.requested_by = frappe.session.user
        
        if not self.request_date:
            self.request_date = now()
        
        # Set email from user if not provided
        if not self.email:
            self.email = frappe.session.user
    
    def after_insert(self):
        """Actions after meeting request creation."""
        self.notify_teacher()
    
    def on_update(self):
        """Actions on meeting request update."""
        # Notify parent if status changed
        if self.has_value_changed("status"):
            if self.status in ["Approved", "Rejected"]:
                self.set_response_info()
                self.notify_parent()
    
    def set_response_info(self):
        """Set response information."""
        if not self.responded_by:
            self.responded_by = frappe.session.user
        
        if not self.response_date:
            self.response_date = now()
    
    def notify_teacher(self):
        """Send notification to teacher about new meeting request."""
        # Check if notifications are enabled
        enable_notifications = frappe.db.get_single_value("School Settings", "enable_email_notifications")
        if not enable_notifications:
            return
        
        try:
            teacher_email = frappe.db.get_value("Employee", self.teacher, "company_email")
            student_name = frappe.db.get_value("Student", self.student, "student_name")
            teacher_name = frappe.db.get_value("Employee", self.teacher, "employee_name")
            
            if not teacher_email:
                return
            
            school_name = frappe.db.get_single_value("School Settings", "school_name") or "School"
            
            subject = _("New Meeting Request - {0}").format(student_name)
            message = _("""
            <p>Dear {0},</p>
            
            <p>You have received a new meeting request:</p>
            
            <ul>
                <li><strong>Student:</strong> {1}</li>
                <li><strong>Purpose:</strong> {2}</li>
                <li><strong>Preferred Date:</strong> {3}</li>
                <li><strong>Preferred Time:</strong> {4}</li>
                <li><strong>Meeting Type:</strong> {5}</li>
                <li><strong>Duration:</strong> {6}</li>
                {7}
                {8}
            </ul>
            
            {9}
            
            {10}
            
            <p>Please log in to the teacher portal to respond to this request.</p>
            
            <p>Best regards,<br>
            {11} Administration</p>
            """).format(
                teacher_name,
                student_name,
                self.purpose,
                frappe.utils.formatdate(self.preferred_date),
                self.preferred_time,
                self.meeting_type,
                self.duration,
                f"<li><strong>Alternative Date:</strong> {frappe.utils.formatdate(self.alternative_date)}</li>" if self.alternative_date else "",
                f"<li><strong>Alternative Time:</strong> {self.alternative_time}</li>" if self.alternative_time else "",
                f"<p><strong>Description:</strong> {self.description}</p>" if self.description else "",
                f"<p><strong>Additional Notes:</strong> {self.notes}</p>" if self.notes else "",
                school_name
            )
            
            frappe.sendmail(
                recipients=[teacher_email],
                subject=subject,
                message=message,
                priority=1 if self.is_urgent else 3
            )
            
            # Log the notification
            frappe.get_doc({
                "doctype": "Communication Log",
                "reference_doctype": "Meeting Request",
                "reference_name": self.name,
                "communication_type": "Email",
                "subject": subject,
                "status": "Sent"
            }).insert(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Failed to send meeting request notification for {self.name}: {str(e)}")
    
    def notify_parent(self):
        """Send notification to parent about meeting request response."""
        # Check if notifications are enabled
        enable_notifications = frappe.db.get_single_value("School Settings", "enable_email_notifications")
        if not enable_notifications:
            return
        
        try:
            student_name = frappe.db.get_value("Student", self.student, "student_name")
            teacher_name = frappe.db.get_value("Employee", self.teacher, "employee_name")
            
            if not self.email:
                return
            
            school_name = frappe.db.get_single_value("School Settings", "school_name") or "School"
            
            if self.status == "Approved":
                subject = _("Meeting Request Approved - {0}").format(student_name)
                message = _("""
                <p>Dear Parent,</p>
                
                <p>Your meeting request has been approved:</p>
                
                <ul>
                    <li><strong>Student:</strong> {0}</li>
                    <li><strong>Teacher:</strong> {1}</li>
                    <li><strong>Purpose:</strong> {2}</li>
                    <li><strong>Scheduled Date:</strong> {3}</li>
                    <li><strong>Scheduled Time:</strong> {4}</li>
                    <li><strong>Meeting Type:</strong> {5}</li>
                    <li><strong>Duration:</strong> {6}</li>
                    {7}
                </ul>
                
                {8}
                
                <p>Please make sure to attend the meeting at the scheduled time.</p>
                
                <p>Best regards,<br>
                {9} Administration</p>
                """).format(
                    student_name,
                    teacher_name,
                    self.purpose,
                    frappe.utils.formatdate(self.scheduled_date) if self.scheduled_date else frappe.utils.formatdate(self.preferred_date),
                    self.scheduled_time if self.scheduled_time else self.preferred_time,
                    self.meeting_type,
                    self.duration,
                    f"<li><strong>Meeting Link:</strong> <a href='{self.meeting_link}'>{self.meeting_link}</a></li>" if self.meeting_link else "",
                    f"<p><strong>Teacher's Notes:</strong> {self.response_notes}</p>" if self.response_notes else "",
                    school_name
                )
            else:  # Rejected
                subject = _("Meeting Request Declined - {0}").format(student_name)
                message = _("""
                <p>Dear Parent,</p>
                
                <p>Unfortunately, your meeting request has been declined:</p>
                
                <ul>
                    <li><strong>Student:</strong> {0}</li>
                    <li><strong>Teacher:</strong> {1}</li>
                    <li><strong>Purpose:</strong> {2}</li>
                    <li><strong>Requested Date:</strong> {3}</li>
                </ul>
                
                {4}
                
                <p>Please feel free to submit another request with different dates or contact the school administration.</p>
                
                <p>Best regards,<br>
                {5} Administration</p>
                """).format(
                    student_name,
                    teacher_name,
                    self.purpose,
                    frappe.utils.formatdate(self.preferred_date),
                    f"<p><strong>Reason:</strong> {self.response_notes}</p>" if self.response_notes else "",
                    school_name
                )
            
            frappe.sendmail(
                recipients=[self.email],
                subject=subject,
                message=message
            )
            
        except Exception as e:
            frappe.log_error(f"Failed to send meeting response notification for {self.name}: {str(e)}")
    
    def approve_meeting(self, scheduled_date=None, scheduled_time=None, meeting_link=None, notes=None):
        """Approve the meeting request."""
        self.status = "Approved"
        self.scheduled_date = scheduled_date or self.preferred_date
        self.scheduled_time = scheduled_time or self.preferred_time
        
        if meeting_link:
            self.meeting_link = meeting_link
        
        if notes:
            self.response_notes = notes
        
        self.save(ignore_permissions=True)
    
    def reject_meeting(self, reason=None):
        """Reject the meeting request."""
        self.status = "Rejected"
        
        if reason:
            self.response_notes = reason
        
        self.save(ignore_permissions=True)
