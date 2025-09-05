"""Notification Rule DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, cint, flt, add_to_date
import json


class NotificationRule(Document):
    """Automated notification rule management."""
    
    def validate(self):
        """Validate notification rule configuration."""
        self.validate_trigger_configuration()
        self.validate_notification_settings()
        self.validate_templates()
        self.set_defaults()
    
    def validate_trigger_configuration(self):
        """Validate trigger event and conditions."""
        if not self.trigger_event:
            frappe.throw(_("Trigger event is required"))
        
        if not self.document_type:
            frappe.throw(_("Document type is required"))
        
        # Validate condition script if provided
        if self.condition_script:
            try:
                compile(self.condition_script, '<string>', 'exec')
            except SyntaxError as e:
                frappe.throw(_("Invalid condition script: {0}").format(str(e)))
    
    def validate_notification_settings(self):
        """Validate notification configuration."""
        if not self.notification_type:
            frappe.throw(_("Notification type is required"))
        
        # Validate recipients
        if not self.send_to_roles and not self.send_to_users:
            frappe.throw(_("At least one recipient role or user must be specified"))
        
        # Validate retry attempts
        if self.retry_attempts < 0:
            self.retry_attempts = 0
        elif self.retry_attempts > 10:
            self.retry_attempts = 10
    
    def validate_templates(self):
        """Validate message templates."""
        if self.notification_type in ["Email", "All Methods"]:
            if not self.email_template and not self.message_template:
                frappe.throw(_("Email template or message template is required for email notifications"))
        
        if self.notification_type in ["SMS", "All Methods"]:
            if not self.sms_template and not self.message_template:
                frappe.throw(_("SMS template or message template is required for SMS notifications"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.priority:
            self.priority = "Medium"
        
        if not self.execution_order:
            self.execution_order = 100
        
        if not self.delivery_method:
            self.delivery_method = "Immediate"
        
        if not self.retry_attempts:
            self.retry_attempts = 3
        
        if not self.created_by_user:
            self.created_by_user = frappe.session.user
        
        self.last_modified_by = frappe.session.user
    
    def on_update(self):
        """Actions on update."""
        # Update hook registration
        self.register_notification_hook()
    
    def on_trash(self):
        """Actions on delete."""
        # Remove hook registration
        self.unregister_notification_hook()
    
    def register_notification_hook(self):
        """Register notification hook for the document type."""
        if self.is_active:
            # This would typically register with Frappe's hook system
            # For now, we'll store the rule for manual execution
            pass
    
    def unregister_notification_hook(self):
        """Unregister notification hook."""
        # Remove from hook system
        pass
    
    @frappe.whitelist()
    def execute_rule(self, doc, method=None):
        """Execute the notification rule."""
        try:
            if not self.is_active:
                return
            
            # Check trigger condition
            if not self.check_trigger_condition(doc):
                return
            
            # Get recipients
            recipients = self.get_recipients(doc)
            
            if not recipients:
                return
            
            # Send notifications
            self.send_notifications(doc, recipients)
            
            # Update statistics
            self.update_execution_stats(success=True)
            
        except Exception as e:
            frappe.log_error(f"Notification rule execution failed: {str(e)}", "Notification Rule Error")
            self.update_execution_stats(success=False)
    
    def check_trigger_condition(self, doc):
        """Check if trigger condition is met."""
        if not self.trigger_condition and not self.condition_script:
            return True
        
        # Simple condition check
        if self.trigger_condition:
            try:
                # Parse simple conditions like "status == 'Approved'"
                condition = self.trigger_condition.replace("doc.", "")
                return eval(f"doc.{condition}")
            except:
                pass
        
        # Advanced script condition
        if self.condition_script:
            try:
                local_vars = {"doc": doc, "frappe": frappe}
                exec(self.condition_script, {"__builtins__": {}}, local_vars)
                return local_vars.get("result", True)
            except Exception as e:
                frappe.log_error(f"Condition script error: {str(e)}", "Notification Rule Condition")
                return False
        
        return True
    
    def get_recipients(self, doc):
        """Get notification recipients."""
        recipients = {
            "email": [],
            "sms": [],
            "users": []
        }
        
        # Get users from roles
        if self.send_to_roles:
            for role_row in self.send_to_roles:
                role_users = frappe.get_all("Has Role",
                    filters={"role": role_row.role},
                    fields=["parent"]
                )
                
                for user in role_users:
                    user_doc = frappe.get_doc("User", user.parent)
                    if user_doc.email:
                        recipients["email"].append(user_doc.email)
                        recipients["users"].append(user.parent)
                    
                    if user_doc.mobile_no:
                        recipients["sms"].append(user_doc.mobile_no)
        
        # Get specific users
        if self.send_to_users:
            for user_row in self.send_to_users:
                user_doc = frappe.get_doc("User", user_row.user)
                if user_doc.email:
                    recipients["email"].append(user_doc.email)
                    recipients["users"].append(user_row.user)
                
                if user_doc.mobile_no:
                    recipients["sms"].append(user_doc.mobile_no)
        
        # Get document-specific recipients
        doc_recipients = self.get_document_recipients(doc)
        for key in recipients:
            recipients[key].extend(doc_recipients.get(key, []))
        
        # Remove duplicates
        for key in recipients:
            recipients[key] = list(set(recipients[key]))
        
        return recipients
    
    def get_document_recipients(self, doc):
        """Get recipients from document fields."""
        recipients = {"email": [], "sms": [], "users": []}
        
        # Common document fields that might contain recipients
        email_fields = ["email", "email_id", "contact_email", "guardian_email", "student_email_id"]
        phone_fields = ["mobile", "mobile_no", "phone", "contact_mobile", "guardian_mobile"]
        user_fields = ["user", "user_id", "assigned_to", "created_by", "owner"]
        
        for field in email_fields:
            if hasattr(doc, field) and getattr(doc, field):
                recipients["email"].append(getattr(doc, field))
        
        for field in phone_fields:
            if hasattr(doc, field) and getattr(doc, field):
                recipients["sms"].append(getattr(doc, field))
        
        for field in user_fields:
            if hasattr(doc, field) and getattr(doc, field):
                user = getattr(doc, field)
                recipients["users"].append(user)
                
                # Get user's email and mobile
                user_doc = frappe.get_doc("User", user)
                if user_doc.email:
                    recipients["email"].append(user_doc.email)
                if user_doc.mobile_no:
                    recipients["sms"].append(user_doc.mobile_no)
        
        return recipients
    
    def send_notifications(self, doc, recipients):
        """Send notifications to recipients."""
        if self.delay_minutes > 0:
            # Schedule for later execution
            self.schedule_notification(doc, recipients)
            return
        
        # Send immediately
        self.send_immediate_notifications(doc, recipients)
    
    def send_immediate_notifications(self, doc, recipients):
        """Send immediate notifications."""
        if self.notification_type in ["Email", "All Methods"] and recipients["email"]:
            self.send_email_notifications(doc, recipients["email"])
        
        if self.notification_type in ["SMS", "All Methods"] and recipients["sms"]:
            self.send_sms_notifications(doc, recipients["sms"])
        
        if self.notification_type in ["System Notification", "All Methods"] and recipients["users"]:
            self.send_system_notifications(doc, recipients["users"])
    
    def send_email_notifications(self, doc, email_recipients):
        """Send email notifications."""
        try:
            subject = self.render_template(self.subject_template or "Notification", doc)
            message = self.get_email_message(doc)
            
            frappe.sendmail(
                recipients=email_recipients,
                subject=subject,
                message=message,
                reference_doctype=doc.doctype,
                reference_name=doc.name,
                retry=self.retry_attempts
            )
            
        except Exception as e:
            frappe.log_error(f"Email notification failed: {str(e)}", "Notification Rule Email")
            raise
    
    def get_email_message(self, doc):
        """Get email message content."""
        if self.email_template:
            # Use email template
            template_doc = frappe.get_doc("Email Template", self.email_template)
            return frappe.render_template(template_doc.response, {"doc": doc})
        
        elif self.message_template:
            # Use custom message template
            return self.render_template(self.message_template, doc)
        
        else:
            # Default message
            return f"Notification for {doc.doctype}: {doc.name}"
    
    def send_sms_notifications(self, doc, sms_recipients):
        """Send SMS notifications."""
        try:
            message = self.get_sms_message(doc)
            
            for mobile in sms_recipients:
                frappe.sendmail(
                    recipients=[],
                    subject="SMS Notification",
                    message=message,
                    as_sms=True,
                    mobile_no=mobile
                )
                
        except Exception as e:
            frappe.log_error(f"SMS notification failed: {str(e)}", "Notification Rule SMS")
            raise
    
    def get_sms_message(self, doc):
        """Get SMS message content."""
        if self.sms_template:
            # Use SMS template
            template_doc = frappe.get_doc("SMS Template", self.sms_template)
            return frappe.render_template(template_doc.message, {"doc": doc})
        
        elif self.message_template:
            # Use custom message template (truncated for SMS)
            message = self.render_template(self.message_template, doc)
            return message[:160]  # SMS character limit
        
        else:
            # Default SMS message
            return f"Update: {doc.doctype} {doc.name}"
    
    def send_system_notifications(self, doc, user_recipients):
        """Send system notifications."""
        try:
            subject = self.render_template(self.subject_template or "System Notification", doc)
            message = self.render_template(self.message_template or "Document updated", doc)
            
            for user in user_recipients:
                frappe.get_doc({
                    "doctype": "Notification Log",
                    "subject": subject,
                    "email_content": message,
                    "for_user": user,
                    "type": "Alert",
                    "document_type": doc.doctype,
                    "document_name": doc.name
                }).insert(ignore_permissions=True)
                
        except Exception as e:
            frappe.log_error(f"System notification failed: {str(e)}", "Notification Rule System")
            raise
    
    def render_template(self, template, doc):
        """Render template with document data."""
        if not template:
            return ""
        
        try:
            return frappe.render_template(template, {"doc": doc, "frappe": frappe})
        except Exception as e:
            frappe.log_error(f"Template rendering failed: {str(e)}", "Notification Rule Template")
            return template
    
    def schedule_notification(self, doc, recipients):
        """Schedule notification for later execution."""
        scheduled_time = add_to_date(now_datetime(), minutes=self.delay_minutes)
        
        frappe.get_doc({
            "doctype": "Scheduled Job Type",
            "method": "easygo_education.administration_comms.doctype.notification_rule.notification_rule.execute_scheduled_notification",
            "frequency": "Cron",
            "cron_format": f"0 {scheduled_time.minute} {scheduled_time.hour} {scheduled_time.day} {scheduled_time.month} *",
            "create_log": 1
        }).insert(ignore_permissions=True)
    
    def update_execution_stats(self, success=True):
        """Update execution statistics."""
        self.execution_count = cint(self.execution_count) + 1
        self.last_executed = now_datetime()
        
        if success:
            self.success_count = cint(self.success_count) + 1
        else:
            self.failure_count = cint(self.failure_count) + 1
        
        # Save without triggering hooks
        frappe.db.set_value(self.doctype, self.name, {
            "execution_count": self.execution_count,
            "last_executed": self.last_executed,
            "success_count": self.success_count,
            "failure_count": self.failure_count
        })
        
        frappe.db.commit()
    
    @frappe.whitelist()
    def test_rule(self, test_document=None):
        """Test the notification rule."""
        if not test_document:
            # Create a test document
            test_doc = frappe.new_doc(self.document_type)
            test_doc.update({
                "name": "TEST-NOTIFICATION-001",
                "docstatus": 0
            })
        else:
            test_doc = frappe.get_doc(self.document_type, test_document)
        
        try:
            # Test condition
            condition_result = self.check_trigger_condition(test_doc)
            
            # Get test recipients
            recipients = self.get_recipients(test_doc)
            
            # Test template rendering
            subject = self.render_template(self.subject_template or "Test Notification", test_doc)
            message = self.render_template(self.message_template or "Test message", test_doc)
            
            return {
                "success": True,
                "condition_result": condition_result,
                "recipients": recipients,
                "subject": subject,
                "message": message[:200] + "..." if len(message) > 200 else message
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @frappe.whitelist()
    def get_rule_analytics(self):
        """Get rule analytics and performance metrics."""
        # Calculate success rate
        total_executions = cint(self.execution_count)
        success_rate = 0
        if total_executions > 0:
            success_rate = (cint(self.success_count) / total_executions) * 100
        
        # Get recent execution history
        recent_logs = frappe.get_all("Error Log",
            filters={
                "method": f"{self.doctype}.execute_rule",
                "creation": [">=", add_to_date(now_datetime(), days=-30)]
            },
            fields=["creation", "error"],
            order_by="creation desc",
            limit=10
        )
        
        return {
            "rule_summary": {
                "name": self.name,
                "rule_name": self.rule_name,
                "is_active": self.is_active,
                "document_type": self.document_type,
                "trigger_event": self.trigger_event
            },
            "execution_stats": {
                "total_executions": total_executions,
                "success_count": cint(self.success_count),
                "failure_count": cint(self.failure_count),
                "success_rate": success_rate,
                "last_executed": self.last_executed
            },
            "configuration": {
                "notification_type": self.notification_type,
                "delivery_method": self.delivery_method,
                "priority": self.priority,
                "delay_minutes": self.delay_minutes,
                "retry_attempts": self.retry_attempts
            },
            "recipients": {
                "role_count": len(self.send_to_roles) if self.send_to_roles else 0,
                "user_count": len(self.send_to_users) if self.send_to_users else 0
            },
            "recent_errors": recent_logs
        }
    
    def get_rule_summary(self):
        """Get rule summary for reporting."""
        return {
            "rule_name": self.rule_name,
            "document_type": self.document_type,
            "trigger_event": self.trigger_event,
            "notification_type": self.notification_type,
            "is_active": self.is_active,
            "priority": self.priority,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": (cint(self.success_count) / max(1, cint(self.execution_count))) * 100,
            "last_executed": self.last_executed,
            "created_by": self.created_by_user,
            "last_modified": self.modified
        }


@frappe.whitelist()
def execute_scheduled_notification(rule_name, doc_type, doc_name):
    """Execute scheduled notification."""
    try:
        rule = frappe.get_doc("Notification Rule", rule_name)
        doc = frappe.get_doc(doc_type, doc_name)
        
        rule.execute_rule(doc)
        
    except Exception as e:
        frappe.log_error(f"Scheduled notification failed: {str(e)}", "Scheduled Notification")


@frappe.whitelist()
def get_active_rules_for_doctype(doctype):
    """Get active notification rules for a document type."""
    return frappe.get_all("Notification Rule",
        filters={
            "document_type": doctype,
            "is_active": 1
        },
        fields=["name", "rule_name", "trigger_event", "priority"],
        order_by="execution_order, priority desc"
    )


@frappe.whitelist()
def execute_rules_for_document(doc, method):
    """Execute all applicable notification rules for a document."""
    rules = get_active_rules_for_doctype(doc.doctype)
    
    for rule_info in rules:
        if rule_info.trigger_event == method:
            try:
                rule = frappe.get_doc("Notification Rule", rule_info.name)
                rule.execute_rule(doc, method)
            except Exception as e:
                frappe.log_error(f"Rule execution failed for {rule_info.name}: {str(e)}", "Notification Rule Execution")
