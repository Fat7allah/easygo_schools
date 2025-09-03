import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, add_days, get_datetime
from frappe import _


class Correspondence(Document):
    def validate(self):
        self.validate_dates()
        self.validate_contact_info()
        self.set_response_date()
        
    def validate_dates(self):
        """Validate date fields"""
        if self.response_required and self.response_deadline:
            if self.response_deadline < self.date:
                frappe.throw(_("Response deadline cannot be before correspondence date"))
                
    def validate_contact_info(self):
        """Validate sender and recipient information"""
        if self.correspondence_type == "Outgoing" and not self.recipient_name:
            frappe.throw(_("Recipient name is required for outgoing correspondence"))
            
        if self.correspondence_type == "Incoming" and not self.sender_name:
            frappe.throw(_("Sender name is required for incoming correspondence"))
            
    def set_response_date(self):
        """Set response date when response content is provided"""
        if self.response_content and not self.response_date:
            self.response_date = nowdate()
            
    def on_update(self):
        self.update_status()
        self.send_notifications()
        
    def update_status(self):
        """Auto-update status based on content"""
        if self.status == "Draft":
            if self.correspondence_type == "Outgoing" and self.content:
                self.status = "Sent"
            elif self.correspondence_type == "Incoming":
                self.status = "Received"
                
        if self.response_required and self.response_content:
            self.status = "Completed"
            
    def send_notifications(self):
        """Send notifications for important correspondence"""
        if self.priority in ["High", "Urgent"]:
            self.notify_stakeholders()
            
        if self.response_required and self.response_deadline:
            self.schedule_reminder()
            
    def notify_stakeholders(self):
        """Notify relevant stakeholders"""
        recipients = []
        
        if self.recipient_email:
            recipients.append(self.recipient_email)
            
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=f"Important Correspondence: {self.subject}",
                message=f"""
                <p>Dear {self.recipient_name or 'Recipient'},</p>
                <p>You have received important correspondence:</p>
                <p><strong>Subject:</strong> {self.subject}</p>
                <p><strong>Priority:</strong> {self.priority}</p>
                <p><strong>Date:</strong> {self.date}</p>
                {f'<p><strong>Response Required by:</strong> {self.response_deadline}</p>' if self.response_required else ''}
                <p>Please check the system for full details.</p>
                """,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
            
    def schedule_reminder(self):
        """Schedule reminder for response deadline"""
        if self.response_deadline and self.status not in ["Completed", "Archived"]:
            reminder_date = add_days(self.response_deadline, -1)
            
            if reminder_date >= nowdate():
                # Create a scheduled job for reminder
                frappe.enqueue(
                    'easygo_education.administration_comms.doctype.correspondence.correspondence.send_response_reminder',
                    correspondence_name=self.name,
                    enqueue_at=get_datetime(reminder_date + " 09:00:00")
                )
                
    @frappe.whitelist()
    def mark_as_completed(self):
        """Mark correspondence as completed"""
        self.status = "Completed"
        self.save()
        
        frappe.msgprint(_("Correspondence marked as completed"))
        
    @frappe.whitelist()
    def archive_correspondence(self):
        """Archive correspondence"""
        self.status = "Archived"
        self.save()
        
        frappe.msgprint(_("Correspondence archived"))


@frappe.whitelist()
def send_response_reminder(correspondence_name):
    """Send reminder for pending response"""
    doc = frappe.get_doc("Correspondence", correspondence_name)
    
    if doc.status not in ["Completed", "Archived"] and doc.response_required:
        if doc.recipient_email:
            frappe.sendmail(
                recipients=[doc.recipient_email],
                subject=f"Response Reminder: {doc.subject}",
                message=f"""
                <p>Dear {doc.recipient_name},</p>
                <p>This is a reminder that a response is required for the following correspondence:</p>
                <p><strong>Subject:</strong> {doc.subject}</p>
                <p><strong>Response Deadline:</strong> {doc.response_deadline}</p>
                <p>Please provide your response as soon as possible.</p>
                """,
                reference_doctype=doc.doctype,
                reference_name=doc.name
            )


@frappe.whitelist()
def get_correspondence_analytics():
    """Get correspondence analytics"""
    return {
        "total_correspondence": frappe.db.count("Correspondence"),
        "pending_responses": frappe.db.count("Correspondence", {
            "response_required": 1,
            "status": ["not in", ["Completed", "Archived"]]
        }),
        "overdue_responses": frappe.db.count("Correspondence", {
            "response_required": 1,
            "response_deadline": ["<", nowdate()],
            "status": ["not in", ["Completed", "Archived"]]
        }),
        "by_type": frappe.db.sql("""
            SELECT correspondence_type, COUNT(*) as count
            FROM `tabCorrespondence`
            GROUP BY correspondence_type
        """, as_dict=True),
        "by_priority": frappe.db.sql("""
            SELECT priority, COUNT(*) as count
            FROM `tabCorrespondence`
            GROUP BY priority
        """, as_dict=True)
    }
