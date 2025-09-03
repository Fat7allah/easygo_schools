"""Student Transfer doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate


class StudentTransfer(Document):
    """Student Transfer doctype controller."""
    
    def validate(self):
        """Validate student transfer data."""
        self.validate_transfer_date()
        self.validate_student_status()
        self.set_defaults()
    
    def validate_transfer_date(self):
        """Validate transfer date."""
        if self.transfer_date and getdate(self.transfer_date) < getdate():
            if self.status == "Draft":
                frappe.throw(_("Transfer date cannot be in the past for draft transfers"))
    
    def validate_student_status(self):
        """Validate student status."""
        if self.student:
            student_status = frappe.db.get_value("Student", self.student, "status")
            if student_status != "Active":
                frappe.throw(_("Can only transfer active students"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.requested_by:
            self.requested_by = frappe.session.user
        
        if not self.request_date:
            self.request_date = getdate()
        
        # Fetch student details
        if self.student and not self.student_name:
            student_doc = frappe.get_doc("Student", self.student)
            self.student_name = student_doc.student_name
            self.current_class = student_doc.school_class
            self.current_program = student_doc.program
            
            # Get current guardian
            guardian = frappe.db.get_value("Student Guardian", 
                {"student": self.student, "primary_guardian": 1}, "guardian")
            if guardian:
                self.current_guardian = guardian
    
    def on_submit(self):
        """Actions on transfer submission."""
        self.status = "Pending Approval"
        self.send_approval_notification()
    
    def on_cancel(self):
        """Actions on transfer cancellation."""
        self.status = "Cancelled"
    
    def send_approval_notification(self):
        """Send notification for approval."""
        try:
            # Get Education Managers for approval
            education_managers = frappe.get_list("User",
                filters={"enabled": 1},
                fields=["email", "full_name"]
            )
            
            # Filter users with Education Manager role
            managers_with_role = []
            for manager in education_managers:
                user_roles = frappe.get_roles(manager.name)
                if "Education Manager" in user_roles:
                    managers_with_role.append(manager)
            
            if managers_with_role:
                recipients = [manager.email for manager in managers_with_role if manager.email]
                
                frappe.sendmail(
                    recipients=recipients,
                    subject=_("Student Transfer Approval Required: {0}").format(self.student_name),
                    message=_("A student transfer request requires your approval.\n\nStudent: {0}\nTransfer Type: {1}\nReason: {2}\nTransfer Date: {3}").format(
                        self.student_name, self.transfer_type, self.reason, self.transfer_date
                    ),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        except Exception as e:
            frappe.log_error(f"Failed to send transfer approval notification: {str(e)}")
    
    @frappe.whitelist()
    def approve_transfer(self):
        """Approve the transfer."""
        if self.status != "Pending Approval":
            frappe.throw(_("Transfer can only be approved when status is 'Pending Approval'"))
        
        self.approved_by = frappe.session.user
        self.approval_date = getdate()
        self.status = "Approved"
        
        self.save()
        self.send_approval_confirmation()
        
        return True
    
    @frappe.whitelist()
    def complete_transfer(self):
        """Complete the transfer process."""
        if self.status != "Approved":
            frappe.throw(_("Transfer must be approved before completion"))
        
        # Update student status
        student_doc = frappe.get_doc("Student", self.student)
        
        if self.transfer_type == "External Transfer":
            student_doc.status = "Transferred"
        elif self.transfer_type == "Withdrawal":
            student_doc.status = "Withdrawn"
        elif self.transfer_type == "Graduation":
            student_doc.status = "Graduated"
        elif self.transfer_type == "Internal Transfer":
            # Update class/program for internal transfers
            if self.destination_class:
                # Find internal class
                internal_class = frappe.db.get_value("School Class", 
                    {"class_name": self.destination_class}, "name")
                if internal_class:
                    student_doc.school_class = internal_class
        
        student_doc.save()
        
        self.status = "Completed"
        self.save()
        
        self.send_completion_notification()
        
        return True
    
    def send_approval_confirmation(self):
        """Send approval confirmation."""
        try:
            # Notify requester
            requester_email = frappe.db.get_value("User", self.requested_by, "email")
            
            if requester_email:
                frappe.sendmail(
                    recipients=[requester_email],
                    subject=_("Student Transfer Approved: {0}").format(self.student_name),
                    message=_("The transfer request for student {0} has been approved by {1}.").format(
                        self.student_name, self.approved_by
                    ),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        except Exception as e:
            frappe.log_error(f"Failed to send approval confirmation: {str(e)}")
    
    def send_completion_notification(self):
        """Send completion notification."""
        try:
            # Notify guardian if available
            if self.current_guardian:
                guardian_email = frappe.db.get_value("Guardian", self.current_guardian, "email_address")
                
                if guardian_email:
                    frappe.sendmail(
                        recipients=[guardian_email],
                        subject=_("Student Transfer Completed: {0}").format(self.student_name),
                        message=_("The transfer process for {0} has been completed successfully.").format(
                            self.student_name
                        ),
                        reference_doctype=self.doctype,
                        reference_name=self.name
                    )
        
        except Exception as e:
            frappe.log_error(f"Failed to send completion notification: {str(e)}")
