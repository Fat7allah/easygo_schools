"""Activity Enrollment doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate


class ActivityEnrollment(Document):
    """Activity Enrollment doctype controller."""
    
    def validate(self):
        """Validate enrollment data."""
        self.validate_enrollment_requirements()
        self.validate_withdrawal()
        self.set_defaults()
    
    def validate_enrollment_requirements(self):
        """Validate enrollment requirements."""
        activity = frappe.get_doc("Extracurricular Activity", self.activity)
        
        # Check if enrollment is open
        if not activity.enrollment_open and self.status == "Enrolled":
            frappe.throw(_("Enrollment is closed for this activity"))
        
        # Check enrollment deadline
        if activity.enrollment_deadline and getdate(self.enrollment_date) > getdate(activity.enrollment_deadline):
            frappe.throw(_("Enrollment date is past the deadline"))
        
        # Check capacity
        if activity.max_participants:
            current_count = frappe.db.count("Activity Enrollment", {
                "activity": self.activity,
                "status": "Enrolled",
                "name": ["!=", self.name]
            })
            
            if current_count >= activity.max_participants and self.status == "Enrolled":
                self.status = "Waitlisted"
                frappe.msgprint(_("Activity is at capacity. Student has been waitlisted."))
    
    def validate_withdrawal(self):
        """Validate withdrawal information."""
        if self.status == "Withdrawn":
            if not self.withdrawal_date:
                self.withdrawal_date = getdate()
            
            if not self.withdrawal_reason:
                frappe.throw(_("Withdrawal reason is required"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
        
        if not self.enrollment_date:
            self.enrollment_date = getdate()
    
    def before_save(self):
        """Actions before saving."""
        self.last_updated = now()
    
    def on_update(self):
        """Actions on document update."""
        self.update_activity_count()
        self.send_enrollment_notifications()
    
    def update_activity_count(self):
        """Update participant count in activity."""
        activity = frappe.get_doc("Extracurricular Activity", self.activity)
        activity.update_participant_count()
        activity.save(ignore_permissions=True)
    
    def send_enrollment_notifications(self):
        """Send enrollment notifications."""
        if self.has_value_changed("status"):
            student_doc = frappe.get_doc("Student", self.student)
            activity_doc = frappe.get_doc("Extracurricular Activity", self.activity)
            
            subject = f"Activity Enrollment Update - {activity_doc.activity_name}"
            
            if self.status == "Enrolled":
                message = f"""
                Congratulations! {student_doc.student_name} has been enrolled in {activity_doc.activity_name}.
                
                Activity Details:
                - Start Date: {activity_doc.start_date}
                - Schedule: {activity_doc.meeting_schedule}
                - Location: {activity_doc.location}
                - Supervisor: {activity_doc.supervisor}
                
                Please ensure all required documents and consents are submitted.
                """
            elif self.status == "Waitlisted":
                message = f"""
                {student_doc.student_name} has been placed on the waitlist for {activity_doc.activity_name}.
                
                You will be notified if a spot becomes available.
                """
            elif self.status == "Withdrawn":
                message = f"""
                {student_doc.student_name} has been withdrawn from {activity_doc.activity_name}.
                
                Withdrawal Date: {self.withdrawal_date}
                Reason: {self.withdrawal_reason}
                """
            
            # Send to student's parent/guardian
            try:
                parent_email = frappe.db.get_value("Student", self.student, "parent_email")
                if parent_email:
                    frappe.sendmail(
                        recipients=[parent_email],
                        subject=subject,
                        message=message
                    )
            except Exception as e:
                frappe.log_error(f"Failed to send enrollment notification: {str(e)}")
    
    @frappe.whitelist()
    def promote_from_waitlist(self):
        """Promote student from waitlist to enrolled."""
        if self.status != "Waitlisted":
            frappe.throw(_("Student is not on waitlist"))
        
        activity = frappe.get_doc("Extracurricular Activity", self.activity)
        
        if activity.max_participants:
            current_count = frappe.db.count("Activity Enrollment", {
                "activity": self.activity,
                "status": "Enrolled"
            })
            
            if current_count >= activity.max_participants:
                frappe.throw(_("Activity is still at maximum capacity"))
        
        self.status = "Enrolled"
        self.save()
        
        return True
    
    @frappe.whitelist()
    def calculate_refund(self):
        """Calculate refund amount based on withdrawal date."""
        if self.status != "Withdrawn":
            return 0
        
        activity = frappe.get_doc("Extracurricular Activity", self.activity)
        
        # Simple refund calculation - would be more complex in real implementation
        if not activity.start_date or not self.withdrawal_date:
            return 0
        
        from frappe.utils import date_diff
        days_before_start = date_diff(activity.start_date, self.withdrawal_date)
        
        # Full refund if withdrawn more than 7 days before start
        if days_before_start > 7:
            refund_percentage = 100
        # 50% refund if withdrawn 3-7 days before
        elif days_before_start > 3:
            refund_percentage = 50
        # No refund if withdrawn less than 3 days before or after start
        else:
            refund_percentage = 0
        
        # This would integrate with fee structure
        base_fee = activity.budget_allocated or 0
        refund_amount = (base_fee * refund_percentage) / 100
        
        self.refund_applicable = refund_percentage > 0
        self.refund_amount = refund_amount
        
        return refund_amount
