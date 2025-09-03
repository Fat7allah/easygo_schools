"""Message Thread doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, add_days


class MessageThread(Document):
    """Message Thread doctype controller for portal messaging."""
    
    def validate(self):
        """Validate message thread data."""
        self.validate_participants()
        self.set_defaults()
    
    def validate_participants(self):
        """Validate thread participants."""
        if not self.participants:
            frappe.throw(_("At least one participant is required"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.message_count:
            self.message_count = 0
        
        if not self.last_message_date:
            self.last_message_date = now()
    
    def after_insert(self):
        """Actions after thread creation."""
        self.send_creation_notifications()
    
    def send_creation_notifications(self):
        """Send notifications when thread is created."""
        if not self.notifications_enabled:
            return
        
        try:
            for participant in self.participants:
                if participant.user != self.created_by and participant.notifications_enabled:
                    user_email = frappe.db.get_value("User", participant.user, "email")
                    
                    if user_email:
                        frappe.sendmail(
                            recipients=[user_email],
                            subject=_("New Message Thread: {0}").format(self.thread_title),
                            message=_("A new message thread has been created: {0}").format(self.thread_title),
                            reference_doctype=self.doctype,
                            reference_name=self.name
                        )
        
        except Exception as e:
            frappe.log_error(f"Failed to send notifications: {str(e)}")
    
    @frappe.whitelist()
    def update_message_count(self):
        """Update message count."""
        count = frappe.db.count("Message", {"thread": self.name})
        self.message_count = count
        self.last_message_date = now()
        self.save(ignore_permissions=True)
