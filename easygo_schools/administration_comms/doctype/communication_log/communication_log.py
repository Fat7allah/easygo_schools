"""Communication Log doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now


class CommunicationLog(Document):
    """Communication Log doctype controller for tracking communications."""
    
    def validate(self):
        """Validate communication log data."""
        self.validate_recipients()
        self.set_defaults()
    
    def validate_recipients(self):
        """Validate recipients format."""
        if self.recipients:
            # Split recipients by comma or semicolon
            recipients = [r.strip() for r in self.recipients.replace(';', ',').split(',')]
            
            # Validate email format for email communications
            if self.communication_type == "Email":
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                
                for recipient in recipients:
                    if recipient and not re.match(email_pattern, recipient):
                        frappe.throw(_("Invalid email format: {0}").format(recipient))
    
    def set_defaults(self):
        """Set default values."""
        if not self.sender:
            self.sender = frappe.session.user
        
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.modified_by:
            self.modified_by = frappe.session.user
    
    def before_insert(self):
        """Actions before communication log creation."""
        if self.status == "Sent" and not self.sent_date:
            self.sent_date = now()
    
    def on_update(self):
        """Actions on communication log update."""
        if self.has_value_changed("status"):
            if self.status == "Sent" and not self.sent_date:
                self.sent_date = now()
            elif self.status == "Delivered" and not self.delivered_date:
                self.delivered_date = now()
            elif self.status == "Read" and not self.read_date:
                self.read_date = now()
    
    @frappe.whitelist()
    def mark_as_sent(self):
        """Mark communication as sent."""
        self.status = "Sent"
        self.sent_date = now()
        self.save(ignore_permissions=True)
        
        frappe.msgprint(_("Communication marked as sent"))
    
    @frappe.whitelist()
    def mark_as_delivered(self):
        """Mark communication as delivered."""
        if self.status != "Sent":
            frappe.throw(_("Communication must be sent before marking as delivered"))
        
        self.status = "Delivered"
        self.delivered_date = now()
        self.save(ignore_permissions=True)
        
        frappe.msgprint(_("Communication marked as delivered"))
    
    @frappe.whitelist()
    def mark_as_read(self):
        """Mark communication as read."""
        if self.status not in ["Sent", "Delivered"]:
            frappe.throw(_("Communication must be sent/delivered before marking as read"))
        
        self.status = "Read"
        self.read_date = now()
        self.save(ignore_permissions=True)
        
        frappe.msgprint(_("Communication marked as read"))
    
    @frappe.whitelist()
    def mark_as_failed(self, error_message=None):
        """Mark communication as failed."""
        self.status = "Failed"
        if error_message:
            self.error_message = error_message
        
        self.retry_count = (self.retry_count or 0) + 1
        self.save(ignore_permissions=True)
        
        frappe.msgprint(_("Communication marked as failed"))
    
    @frappe.whitelist()
    def retry_communication(self):
        """Retry failed communication."""
        if self.status != "Failed":
            frappe.throw(_("Only failed communications can be retried"))
        
        if self.retry_count >= 3:
            frappe.throw(_("Maximum retry attempts reached"))
        
        self.status = "Draft"
        self.error_message = None
        self.save(ignore_permissions=True)
        
        frappe.msgprint(_("Communication queued for retry"))
    
    @staticmethod
    def log_communication(communication_type, subject, recipients, message_content=None, 
                         reference_doctype=None, reference_name=None, sender=None, 
                         priority="Medium", status="Sent"):
        """Helper method to log communications."""
        try:
            comm_log = frappe.get_doc({
                "doctype": "Communication Log",
                "communication_type": communication_type,
                "subject": subject,
                "recipients": recipients if isinstance(recipients, str) else ", ".join(recipients),
                "message_content": message_content,
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "sender": sender or frappe.session.user,
                "priority": priority,
                "status": status,
                "sent_date": now() if status == "Sent" else None
            })
            
            comm_log.insert(ignore_permissions=True)
            return comm_log.name
            
        except Exception as e:
            frappe.log_error(f"Failed to log communication: {str(e)}")
            return None
