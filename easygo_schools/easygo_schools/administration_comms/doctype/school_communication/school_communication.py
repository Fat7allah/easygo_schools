"""School Communication DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, add_days


class SchoolCommunication(Document):
    """School Communication management."""
    
    def validate(self):
        """Validate communication data."""
        self.validate_delivery_date()
        self.validate_acknowledgment_deadline()
        self.validate_recipients()
        self.set_defaults()
    
    def validate_delivery_date(self):
        """Validate delivery date."""
        if self.scheduled_delivery and self.delivery_date:
            if getdate(self.delivery_date) < getdate():
                frappe.throw(_("Delivery date cannot be in the past"))
    
    def validate_acknowledgment_deadline(self):
        """Validate acknowledgment deadline."""
        if self.requires_acknowledgment and self.acknowledgment_deadline:
            delivery_date = self.delivery_date or self.communication_date
            if getdate(self.acknowledgment_deadline) <= getdate(delivery_date):
                frappe.throw(_("Acknowledgment deadline must be after delivery date"))
    
    def validate_recipients(self):
        """Validate recipients configuration."""
        if self.target_audience == "Specific Recipients" and not self.specific_recipients:
            frappe.throw(_("Specific recipients are required when target audience is 'Specific Recipients'"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.sender:
            self.sender = frappe.session.user
        
        if not self.communication_date:
            self.communication_date = getdate()
        
        if not self.priority:
            self.priority = "Medium"
        
        if not self.delivery_method:
            self.delivery_method = "Email"
    
    def on_update(self):
        """Actions after update."""
        if self.has_value_changed("status") and self.status == "Sent":
            self.process_communication()
    
    @frappe.whitelist()
    def send_communication(self):
        """Send the communication."""
        if self.status != "Draft":
            frappe.throw(_("Only draft communications can be sent"))
        
        if self.scheduled_delivery and self.delivery_date:
            self.status = "Scheduled"
            self.save()
            self.schedule_delivery()
        else:
            self.status = "Sent"
            self.save()
            self.process_communication()
        
        frappe.msgprint(_("Communication processed successfully"))
        return self
    
    def process_communication(self):
        """Process and deliver the communication."""
        recipients = self.get_recipients()
        
        if not recipients:
            frappe.throw(_("No recipients found for this communication"))
        
        delivery_results = []
        
        for recipient in recipients:
            result = self.deliver_to_recipient(recipient)
            delivery_results.append(result)
        
        self.update_delivery_status(delivery_results)
        
        if self.requires_acknowledgment:
            self.create_acknowledgment_records(recipients)
    
    def get_recipients(self):
        """Get list of recipients based on target audience."""
        recipients = []
        
        if self.target_audience == "All Students":
            recipients = frappe.get_all("Student", 
                filters={"is_active": 1},
                fields=["name", "student_name", "user_id", "email"]
            )
        
        elif self.target_audience == "All Parents":
            recipients = frappe.get_all("Guardian", 
                fields=["name", "guardian_name", "email_address as email", "user_id"]
            )
        
        elif self.target_audience == "All Teachers":
            recipients = frappe.get_all("Employee", 
                filters={"department": "Education"},
                fields=["name", "employee_name as student_name", "user_id", "company_email as email"]
            )
        
        elif self.target_audience == "All Staff":
            recipients = frappe.get_all("Employee", 
                fields=["name", "employee_name as student_name", "user_id", "company_email as email"]
            )
        
        elif self.target_audience == "Specific Recipients":
            recipients = []
            for recipient in self.specific_recipients:
                recipient_data = frappe.get_doc(recipient.recipient_type, recipient.recipient_id)
                recipients.append({
                    "name": recipient_data.name,
                    "student_name": getattr(recipient_data, "student_name", None) or 
                                   getattr(recipient_data, "guardian_name", None) or
                                   getattr(recipient_data, "employee_name", None),
                    "email": getattr(recipient_data, "email", None) or 
                            getattr(recipient_data, "email_address", None) or
                            getattr(recipient_data, "company_email", None),
                    "user_id": getattr(recipient_data, "user_id", None)
                })
        
        return recipients
    
    def deliver_to_recipient(self, recipient):
        """Deliver communication to a specific recipient."""
        delivery_result = {
            "recipient": recipient.get("name"),
            "recipient_name": recipient.get("student_name"),
            "email": recipient.get("email"),
            "status": "Failed",
            "message": ""
        }
        
        try:
            if self.delivery_method in ["Email", "All Methods"] and recipient.get("email"):
                self.send_email(recipient)
                delivery_result["status"] = "Delivered"
                delivery_result["message"] = "Email sent successfully"
            
            if self.delivery_method in ["Portal Message", "All Methods"] and recipient.get("user_id"):
                self.create_portal_message(recipient)
                delivery_result["status"] = "Delivered"
                delivery_result["message"] = "Portal message created"
            
            if self.delivery_method in ["SMS", "All Methods"]:
                # SMS delivery would be implemented here
                delivery_result["message"] += " (SMS not implemented)"
            
        except Exception as e:
            delivery_result["status"] = "Failed"
            delivery_result["message"] = str(e)
        
        return delivery_result
    
    def send_email(self, recipient):
        """Send email to recipient."""
        frappe.sendmail(
            recipients=[recipient.get("email")],
            subject=self.subject,
            message=self.get_formatted_message(recipient),
            reference_doctype=self.doctype,
            reference_name=self.name,
            attachments=self.get_attachments()
        )
    
    def create_portal_message(self, recipient):
        """Create portal message for recipient."""
        if not recipient.get("user_id"):
            return
        
        message_doc = frappe.get_doc({
            "doctype": "Message",
            "sender": self.sender,
            "recipient": recipient.get("user_id"),
            "subject": self.subject,
            "message": self.message_content,
            "reference_doctype": self.doctype,
            "reference_name": self.name
        })
        
        message_doc.insert(ignore_permissions=True)
    
    def get_formatted_message(self, recipient):
        """Get formatted message for recipient."""
        message = self.message_content
        
        # Replace placeholders
        if recipient.get("student_name"):
            message = message.replace("{recipient_name}", recipient.get("student_name"))
        
        return message
    
    def get_attachments(self):
        """Get attachments for email."""
        attachments = []
        
        if self.attachments:
            file_doc = frappe.get_doc("File", {"file_url": self.attachments})
            attachments.append({
                "fname": file_doc.file_name,
                "fcontent": file_doc.get_content()
            })
        
        return attachments
    
    def update_delivery_status(self, delivery_results):
        """Update delivery status based on results."""
        total_recipients = len(delivery_results)
        successful_deliveries = len([r for r in delivery_results if r["status"] == "Delivered"])
        failed_deliveries = total_recipients - successful_deliveries
        
        self.delivery_status = _("Total: {0}, Delivered: {1}, Failed: {2}").format(
            total_recipients, successful_deliveries, failed_deliveries
        )
        
        # Create detailed delivery report
        report_lines = []
        for result in delivery_results:
            report_lines.append(_("{0} ({1}): {2} - {3}").format(
                result["recipient_name"] or result["recipient"],
                result["email"] or "No email",
                result["status"],
                result["message"]
            ))
        
        self.delivery_report = "\n".join(report_lines)
        
        # Update overall status
        if failed_deliveries == 0:
            self.status = "Delivered"
        elif successful_deliveries > 0:
            self.status = "Partially Delivered"
        else:
            self.status = "Failed"
        
        self.save()
    
    def create_acknowledgment_records(self, recipients):
        """Create acknowledgment records for recipients."""
        for recipient in recipients:
            if recipient.get("user_id"):
                ack_doc = frappe.get_doc({
                    "doctype": "Communication Acknowledgment",
                    "communication": self.name,
                    "recipient": recipient.get("user_id"),
                    "recipient_name": recipient.get("student_name"),
                    "acknowledgment_deadline": self.acknowledgment_deadline,
                    "status": "Pending"
                })
                
                ack_doc.insert(ignore_permissions=True)
    
    def schedule_delivery(self):
        """Schedule communication delivery."""
        # Create a scheduled job for delivery
        frappe.get_doc({
            "doctype": "Scheduled Job Type",
            "method": "easygo_education.administration_comms.doctype.school_communication.school_communication.deliver_scheduled_communication",
            "frequency": "Cron",
            "cron_format": self.get_cron_format(),
            "create_log": 1
        }).insert(ignore_permissions=True)
    
    def get_cron_format(self):
        """Get cron format for scheduled delivery."""
        from datetime import datetime
        
        dt = datetime.strptime(str(self.delivery_date), "%Y-%m-%d %H:%M:%S")
        return f"{dt.minute} {dt.hour} {dt.day} {dt.month} *"
    
    @frappe.whitelist()
    def get_acknowledgment_summary(self):
        """Get acknowledgment summary."""
        if not self.requires_acknowledgment:
            return {}
        
        acknowledgments = frappe.get_all("Communication Acknowledgment",
            filters={"communication": self.name},
            fields=["status", "acknowledged_on", "recipient_name"]
        )
        
        total = len(acknowledgments)
        acknowledged = len([a for a in acknowledgments if a.status == "Acknowledged"])
        pending = total - acknowledged
        overdue = len([a for a in acknowledgments 
                      if a.status == "Pending" and getdate() > getdate(self.acknowledgment_deadline)])
        
        summary = {
            "total_recipients": total,
            "acknowledged": acknowledged,
            "pending": pending,
            "overdue": overdue,
            "acknowledgment_rate": (acknowledged / total * 100) if total > 0 else 0
        }
        
        # Update acknowledgment summary field
        self.acknowledgment_summary = _("Total: {0}, Acknowledged: {1}, Pending: {2}, Overdue: {3}").format(
            total, acknowledged, pending, overdue
        )
        self.save()
        
        return summary


@frappe.whitelist()
def deliver_scheduled_communication(communication_name):
    """Deliver scheduled communication."""
    comm_doc = frappe.get_doc("School Communication", communication_name)
    if comm_doc.status == "Scheduled":
        comm_doc.status = "Sent"
        comm_doc.save()
        comm_doc.process_communication()
