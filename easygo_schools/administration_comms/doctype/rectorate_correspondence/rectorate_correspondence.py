import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, add_days, get_datetime
from frappe import _


class RectorateCorrespondence(Document):
    def validate(self):
        self.validate_dates()
        self.validate_references()
        self.set_response_date()
        self.validate_classification()
        
    def validate_dates(self):
        """Validate date fields"""
        if self.response_required and self.response_deadline:
            if self.response_deadline < self.date:
                frappe.throw(_("Response deadline cannot be before correspondence date"))
                
    def validate_references(self):
        """Validate official references"""
        if self.correspondence_type in ["Circular", "Directive"] and not self.rectorate_reference:
            frappe.throw(_("Rectorate reference is required for {0}").format(self.correspondence_type))
            
    def validate_classification(self):
        """Validate classification and confidentiality"""
        if self.confidential and self.classification == "Public":
            frappe.throw(_("Confidential documents cannot have Public classification"))
            
    def set_response_date(self):
        """Set response date when response content is provided"""
        if self.response_content and not self.response_date:
            self.response_date = nowdate()
            
    def on_update(self):
        self.update_status()
        self.send_notifications()
        self.log_correspondence()
        
    def update_status(self):
        """Auto-update status based on content and type"""
        if self.status == "Draft":
            if self.correspondence_type in ["Circular", "Directive", "Notification"]:
                if self.content and self.rectorate_reference:
                    self.status = "Sent"
            elif self.correspondence_type in ["Request", "Report", "Inquiry"]:
                if self.content:
                    self.status = "Sent"
                    
        if self.response_required and self.response_content:
            self.status = "Completed"
            
    def send_notifications(self):
        """Send notifications for important correspondence"""
        if self.priority in ["High", "Urgent"]:
            self.notify_management()
            
        if self.correspondence_type == "Circular":
            self.notify_all_departments()
            
        if self.response_required and self.response_deadline:
            self.schedule_reminder()
            
    def notify_management(self):
        """Notify management for high priority correspondence"""
        management_users = frappe.get_all("User", {
            "role_profile_name": ["in", ["Education Manager", "System Manager"]],
            "enabled": 1
        }, ["email"])
        
        recipients = [user.email for user in management_users if user.email]
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=f"Important Rectorate Correspondence: {self.subject}",
                message=f"""
                <p>Important rectorate correspondence received:</p>
                <p><strong>Type:</strong> {self.correspondence_type}</p>
                <p><strong>Subject:</strong> {self.subject}</p>
                <p><strong>Priority:</strong> {self.priority}</p>
                <p><strong>Date:</strong> {self.date}</p>
                <p><strong>Rectorate Reference:</strong> {self.rectorate_reference or 'N/A'}</p>
                {f'<p><strong>Response Required by:</strong> {self.response_deadline}</p>' if self.response_required else ''}
                <p>Please review the correspondence in the system.</p>
                """,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
            
    def notify_all_departments(self):
        """Notify all departments for circulars"""
        if self.correspondence_type == "Circular":
            all_employees = frappe.get_all("Employee", {
                "status": "Active"
            }, ["user_id"])
            
            recipients = [emp.user_id for emp in all_employees if emp.user_id]
            
            if recipients:
                frappe.sendmail(
                    recipients=recipients,
                    subject=f"New Circular: {self.subject}",
                    message=f"""
                    <p>A new circular has been issued:</p>
                    <p><strong>Subject:</strong> {self.subject}</p>
                    <p><strong>Date:</strong> {self.date}</p>
                    <p><strong>Reference:</strong> {self.rectorate_reference}</p>
                    <p>Please check the system for full details.</p>
                    """,
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
                
    def schedule_reminder(self):
        """Schedule reminder for response deadline"""
        if self.response_deadline and self.status not in ["Completed", "Archived"]:
            reminder_date = add_days(self.response_deadline, -2)  # 2 days before deadline
            
            if reminder_date >= nowdate():
                frappe.enqueue(
                    'easygo_education.administration_comms.doctype.rectorate_correspondence.rectorate_correspondence.send_response_reminder',
                    correspondence_name=self.name,
                    enqueue_at=get_datetime(reminder_date + " 09:00:00")
                )
                
    def log_correspondence(self):
        """Log correspondence activity"""
        frappe.get_doc({
            "doctype": "Communication Log",
            "communication_type": "Official Correspondence",
            "subject": self.subject,
            "content": f"Rectorate correspondence: {self.correspondence_type}",
            "sender": self.sender_department or "Rectorate",
            "recipient": self.recipient_department or "School",
            "reference_doctype": self.doctype,
            "reference_name": self.name,
            "status": "Sent" if self.status != "Draft" else "Draft"
        }).insert(ignore_permissions=True)
        
    @frappe.whitelist()
    def acknowledge_receipt(self):
        """Acknowledge receipt of correspondence"""
        if self.acknowledgment_required:
            self.db_set("status", "Received")
            
            # Log acknowledgment
            frappe.get_doc({
                "doctype": "Communication Log",
                "communication_type": "Acknowledgment",
                "subject": f"Acknowledgment: {self.subject}",
                "content": "Receipt acknowledged",
                "sender": "School",
                "recipient": self.sender_department or "Rectorate",
                "reference_doctype": self.doctype,
                "reference_name": self.name,
                "status": "Sent"
            }).insert(ignore_permissions=True)
            
            frappe.msgprint(_("Receipt acknowledged"))
            
    @frappe.whitelist()
    def mark_as_completed(self):
        """Mark correspondence as completed"""
        self.status = "Completed"
        self.save()
        
        frappe.msgprint(_("Correspondence marked as completed"))


@frappe.whitelist()
def send_response_reminder(correspondence_name):
    """Send reminder for pending response"""
    doc = frappe.get_doc("Rectorate Correspondence", correspondence_name)
    
    if doc.status not in ["Completed", "Archived"] and doc.response_required:
        management_users = frappe.get_all("User", {
            "role_profile_name": ["in", ["Education Manager", "System Manager"]],
            "enabled": 1
        }, ["email"])
        
        recipients = [user.email for user in management_users if user.email]
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=f"Response Reminder: {doc.subject}",
                message=f"""
                <p>Reminder: Response required for rectorate correspondence</p>
                <p><strong>Subject:</strong> {doc.subject}</p>
                <p><strong>Type:</strong> {doc.correspondence_type}</p>
                <p><strong>Response Deadline:</strong> {doc.response_deadline}</p>
                <p><strong>Reference:</strong> {doc.rectorate_reference}</p>
                <p>Please provide response as soon as possible.</p>
                """,
                reference_doctype=doc.doctype,
                reference_name=doc.name
            )


@frappe.whitelist()
def get_rectorate_analytics():
    """Get rectorate correspondence analytics"""
    return {
        "total_correspondence": frappe.db.count("Rectorate Correspondence"),
        "pending_responses": frappe.db.count("Rectorate Correspondence", {
            "response_required": 1,
            "status": ["not in", ["Completed", "Archived"]]
        }),
        "overdue_responses": frappe.db.count("Rectorate Correspondence", {
            "response_required": 1,
            "response_deadline": ["<", nowdate()],
            "status": ["not in", ["Completed", "Archived"]]
        }),
        "by_type": frappe.db.sql("""
            SELECT correspondence_type, COUNT(*) as count
            FROM `tabRectorate Correspondence`
            GROUP BY correspondence_type
        """, as_dict=True),
        "by_priority": frappe.db.sql("""
            SELECT priority, COUNT(*) as count
            FROM `tabRectorate Correspondence`
            GROUP BY priority
        """, as_dict=True),
        "confidential_count": frappe.db.count("Rectorate Correspondence", {"confidential": 1})
    }
