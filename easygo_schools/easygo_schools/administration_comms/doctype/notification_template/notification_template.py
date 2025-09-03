"""Notification Template doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now
import json
import re


class NotificationTemplate(Document):
    """Notification Template doctype controller."""
    
    def validate(self):
        """Validate notification template data."""
        self.validate_template_syntax()
        self.validate_approval_settings()
        self.set_defaults()
        self.generate_preview()
    
    def validate_template_syntax(self):
        """Validate template syntax and variables."""
        templates_to_check = [
            ("subject_template", self.subject_template),
            ("message_template", self.message_template),
            ("sms_template", self.sms_template),
            ("push_notification_template", self.push_notification_template)
        ]
        
        for template_name, template_content in templates_to_check:
            if template_content:
                # Check for valid Jinja2 syntax
                try:
                    # Extract variables from template
                    variables = re.findall(r'\{\{\s*(\w+)\s*\}\}', template_content)
                    
                    # Update available variables
                    if variables:
                        current_vars = self.available_variables or ""
                        new_vars = ", ".join(set(variables))
                        if new_vars not in current_vars:
                            self.available_variables = f"{current_vars}, {new_vars}".strip(", ")
                
                except Exception as e:
                    frappe.throw(_("Invalid template syntax in {0}: {1}").format(template_name, str(e)))
    
    def validate_approval_settings(self):
        """Validate approval settings."""
        if self.require_approval and not self.approval_role:
            frappe.throw(_("Approval role is required when approval is enabled"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
        
        if not self.priority:
            self.priority = "Medium"
        
        if not self.delivery_method:
            self.delivery_method = "Immediate"
    
    def generate_preview(self):
        """Generate template preview with sample data."""
        if not self.sample_data:
            return
        
        try:
            sample_data = json.loads(self.sample_data)
            preview_parts = []
            
            if self.subject_template:
                subject_preview = self.render_template(self.subject_template, sample_data)
                preview_parts.append(f"Subject: {subject_preview}")
            
            if self.message_template:
                message_preview = self.render_template(self.message_template, sample_data)
                preview_parts.append(f"Message: {message_preview}")
            
            if self.sms_template:
                sms_preview = self.render_template(self.sms_template, sample_data)
                preview_parts.append(f"SMS: {sms_preview}")
            
            self.template_preview = "\n\n".join(preview_parts)
        
        except Exception as e:
            self.template_preview = f"Preview generation failed: {str(e)}"
    
    def render_template(self, template, data):
        """Render template with data."""
        try:
            from jinja2 import Template
            jinja_template = Template(template)
            return jinja_template.render(**data)
        except Exception as e:
            return f"Template rendering error: {str(e)}"
    
    @frappe.whitelist()
    def send_notification(self, recipients=None, data=None, delivery_method=None):
        """Send notification using this template."""
        if not self.is_active:
            frappe.throw(_("Template is not active"))
        
        # Parse data
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                data = {}
        
        data = data or {}
        
        # Determine recipients
        final_recipients = self.get_recipients(recipients, data)
        
        if not final_recipients:
            frappe.throw(_("No recipients found"))
        
        # Check if approval is required
        if self.require_approval and not frappe.has_permission("Notification Template", "approve"):
            return self.create_approval_request(final_recipients, data)
        
        # Send notification
        return self.execute_send(final_recipients, data, delivery_method)
    
    def get_recipients(self, custom_recipients=None, data=None):
        """Get list of recipients."""
        recipients = []
        
        # Custom recipients
        if custom_recipients:
            if isinstance(custom_recipients, str):
                recipients.extend([r.strip() for r in custom_recipients.split(",")])
            else:
                recipients.extend(custom_recipients)
        
        # Default recipients
        if self.default_recipients:
            recipients.extend([r.strip() for r in self.default_recipients.split(",")])
        
        # Role-based recipients
        if self.recipient_roles:
            role_users = frappe.get_list("Has Role",
                filters={"role": ["in", self.recipient_roles]},
                fields=["parent"]
            )
            
            for user in role_users:
                user_email = frappe.db.get_value("User", user.parent, "email")
                if user_email:
                    recipients.append(user_email)
        
        # Student/Parent recipients
        if data and data.get("student"):
            if self.send_to_students:
                student_email = frappe.db.get_value("Student", data["student"], "email_address")
                if student_email:
                    recipients.append(student_email)
            
            if self.send_to_parents:
                parent_emails = frappe.db.sql("""
                    SELECT g.email_address
                    FROM `tabGuardian` g
                    INNER JOIN `tabStudent Guardian` sg ON g.name = sg.guardian
                    WHERE sg.student = %s AND g.email_address IS NOT NULL
                """, (data["student"],))
                
                for email in parent_emails:
                    if email[0]:
                        recipients.append(email[0])
        
        return list(set(recipients))  # Remove duplicates
    
    def execute_send(self, recipients, data, delivery_method=None):
        """Execute the notification send."""
        method = delivery_method or self.delivery_method
        
        try:
            # Render templates
            subject = self.render_template(self.subject_template, data) if self.subject_template else ""
            message = self.render_template(self.message_template, data) if self.message_template else ""
            
            # Send based on template type
            if self.template_type in ["Email", "Multi-Channel"]:
                frappe.sendmail(
                    recipients=recipients,
                    subject=subject,
                    message=message,
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
            
            # Log the notification
            self.log_notification(recipients, data, "Sent")
            
            return {"status": "success", "recipients_count": len(recipients)}
        
        except Exception as e:
            self.log_notification(recipients, data, "Failed", str(e))
            frappe.throw(_("Failed to send notification: {0}").format(str(e)))
    
    def log_notification(self, recipients, data, status, error=None):
        """Log notification send attempt."""
        try:
            log_doc = frappe.get_doc({
                "doctype": "Communication Log",
                "communication_type": "Notification",
                "template_used": self.name,
                "recipients": ", ".join(recipients),
                "status": status,
                "error_message": error,
                "data_used": json.dumps(data) if data else None
            })
            log_doc.insert(ignore_permissions=True)
        
        except Exception as e:
            frappe.log_error(f"Failed to log notification: {str(e)}")
    
    def create_approval_request(self, recipients, data):
        """Create approval request for notification."""
        # This would integrate with a workflow system
        # For now, just return a message
        return {
            "status": "pending_approval",
            "message": _("Notification sent for approval"),
            "recipients_count": len(recipients)
        }
    
    @frappe.whitelist()
    def test_template(self, test_data=None):
        """Test template with sample data."""
        if not test_data:
            test_data = self.sample_data
        
        if not test_data:
            frappe.throw(_("No test data provided"))
        
        try:
            data = json.loads(test_data) if isinstance(test_data, str) else test_data
            
            result = {
                "subject": self.render_template(self.subject_template, data) if self.subject_template else "",
                "message": self.render_template(self.message_template, data) if self.message_template else "",
                "sms": self.render_template(self.sms_template, data) if self.sms_template else "",
                "push_notification": self.render_template(self.push_notification_template, data) if self.push_notification_template else ""
            }
            
            return result
        
        except Exception as e:
            frappe.throw(_("Template test failed: {0}").format(str(e)))
    
    @frappe.whitelist()
    def get_template_usage(self):
        """Get template usage statistics."""
        usage_stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_sent,
                COUNT(CASE WHEN status = 'Sent' THEN 1 END) as successful,
                COUNT(CASE WHEN status = 'Failed' THEN 1 END) as failed,
                MAX(creation) as last_used
            FROM `tabCommunication Log`
            WHERE template_used = %s
        """, (self.name,), as_dict=True)
        
        return usage_stats[0] if usage_stats else {}
    
    @frappe.whitelist()
    def duplicate_template(self, new_name):
        """Create a duplicate of this template."""
        new_doc = frappe.copy_doc(self)
        new_doc.template_name = new_name
        new_doc.insert()
        
        return new_doc.name
