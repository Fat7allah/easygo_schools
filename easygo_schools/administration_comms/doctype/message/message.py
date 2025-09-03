"""Message doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now


class Message(Document):
    """Message doctype controller for portal messaging."""
    
    def validate(self):
        """Validate message data."""
        self.validate_thread_access()
        self.set_defaults()
    
    def validate_thread_access(self):
        """Validate user has access to the thread."""
        if not self.thread:
            frappe.throw(_("Thread is required"))
        
        # Check if sender is participant in the thread
        thread_doc = frappe.get_doc("Message Thread", self.thread)
        
        sender_is_participant = False
        for participant in thread_doc.participants:
            if participant.user == self.sender:
                sender_is_participant = True
                break
        
        if not sender_is_participant:
            frappe.throw(_("You are not a participant in this thread"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.sender:
            self.sender = frappe.session.user
        
        if not self.sent_date:
            self.sent_date = now()
        
        if not self.status:
            self.status = "Sent"
    
    def after_insert(self):
        """Actions after message creation."""
        self.update_thread_stats()
        self.send_notifications()
    
    def update_thread_stats(self):
        """Update thread statistics."""
        try:
            thread_doc = frappe.get_doc("Message Thread", self.thread)
            thread_doc.last_message_date = self.sent_date
            thread_doc.last_message_by = self.sender
            thread_doc.message_count = frappe.db.count("Message", {"thread": self.thread})
            
            # Update thread status if it was resolved/closed
            if thread_doc.status in ["Resolved", "Closed"]:
                thread_doc.status = "In Progress"
            
            thread_doc.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Failed to update thread stats: {str(e)}")
    
    def send_notifications(self):
        """Send notifications to thread participants."""
        try:
            thread_doc = frappe.get_doc("Message Thread", self.thread)
            
            if not thread_doc.notifications_enabled:
                return
            
            # Send to all participants except sender
            for participant in thread_doc.participants:
                if participant.user != self.sender and participant.notifications_enabled:
                    user_email = frappe.db.get_value("User", participant.user, "email")
                    
                    if user_email:
                        frappe.sendmail(
                            recipients=[user_email],
                            subject=_("New Message in Thread: {0}").format(thread_doc.thread_title),
                            message=_("You have received a new message in the thread '{0}' from {1}.").format(
                                thread_doc.thread_title, self.sender
                            ),
                            reference_doctype=self.doctype,
                            reference_name=self.name
                        )
        
        except Exception as e:
            frappe.log_error(f"Failed to send message notifications: {str(e)}")
    
    @frappe.whitelist()
    def mark_as_read(self, user=None):
        """Mark message as read by user."""
        if not user:
            user = frappe.session.user
        
        # Check if already marked as read by this user
        existing_receipt = frappe.db.get_value("Message Read Receipt", 
            {"parent": self.name, "user": user}, "name")
        
        if not existing_receipt:
            self.append("read_by", {
                "user": user,
                "read_date": now()
            })
            
            self.save(ignore_permissions=True)
        
        return True
    
    @frappe.whitelist()
    def get_thread_messages(self):
        """Get all messages in the thread."""
        messages = frappe.get_list("Message",
            filters={"thread": self.thread},
            fields=[
                "name", "sender", "sent_date", "content", "message_type",
                "status", "reply_to", "edited"
            ],
            order_by="sent_date asc"
        )
        
        # Add sender details
        for message in messages:
            sender_details = frappe.db.get_value("User", message.sender, 
                ["full_name", "user_image"], as_dict=True)
            message.update(sender_details or {})
        
        return messages
