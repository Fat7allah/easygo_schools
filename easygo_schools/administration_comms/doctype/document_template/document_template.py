"""Document Template DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, cstr
import re
import json


class DocumentTemplate(Document):
    """Document template management for standardized document generation."""
    
    def validate(self):
        """Validate document template data."""
        self.validate_template_name()
        self.validate_template_content()
        self.validate_variables()
        self.validate_access_roles()
        self.set_defaults()
    
    def validate_template_name(self):
        """Validate template name uniqueness."""
        if not self.template_name:
            frappe.throw(_("Template name is required"))
        
        # Check for duplicate template names
        existing = frappe.db.get_value("Document Template", 
            {"template_name": self.template_name, "name": ["!=", self.name]})
        
        if existing:
            frappe.throw(_("Template name '{0}' already exists").format(self.template_name))
    
    def validate_template_content(self):
        """Validate template content."""
        if not self.template_content:
            frappe.throw(_("Template content is required"))
        
        # Basic HTML validation
        if self.template_content.strip().startswith('<'):
            # Check for balanced tags (basic validation)
            self.validate_html_structure()
        
        # Validate template variables in content
        self.validate_template_variables_in_content()
    
    def validate_html_structure(self):
        """Basic HTML structure validation."""
        content = self.template_content
        
        # Check for common HTML issues
        if '<script>' in content.lower() and not self.javascript_code:
            frappe.msgprint(_("Consider moving script tags to JavaScript Code field"))
        
        if '<style>' in content.lower() and not self.css_styles:
            frappe.msgprint(_("Consider moving style tags to CSS Styles field"))
    
    def validate_template_variables_in_content(self):
        """Validate that variables used in content are defined."""
        if not self.template_content:
            return
        
        # Find all variables in template content (format: {{variable_name}})
        variables_in_content = re.findall(r'\{\{([^}]+)\}\}', self.template_content)
        
        # Get defined variables
        defined_variables = [var.variable_name for var in self.variables] if self.variables else []
        
        # Check for undefined variables
        undefined_vars = []
        for var in variables_in_content:
            var_name = var.strip()
            if var_name not in defined_variables:
                undefined_vars.append(var_name)
        
        if undefined_vars:
            frappe.msgprint(_("Undefined variables found in template: {0}").format(", ".join(undefined_vars)))
    
    def validate_variables(self):
        """Validate template variables."""
        if not self.variables:
            return
        
        variable_names = []
        for var in self.variables:
            if not var.variable_name:
                frappe.throw(_("Variable name is required in row {0}").format(var.idx))
            
            # Check for duplicate variable names
            if var.variable_name in variable_names:
                frappe.throw(_("Duplicate variable name '{0}' in row {1}").format(var.variable_name, var.idx))
            
            variable_names.append(var.variable_name)
            
            # Validate variable name format (alphanumeric and underscore only)
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var.variable_name):
                frappe.throw(_("Invalid variable name '{0}' in row {1}. Use only letters, numbers, and underscores").format(var.variable_name, var.idx))
    
    def validate_access_roles(self):
        """Validate access roles."""
        if self.access_roles:
            for role in self.access_roles:
                if not frappe.db.exists("Role", role.role):
                    frappe.throw(_("Role '{0}' does not exist").format(role.role))
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.version:
            self.version = "1.0"
        
        if not self.language:
            self.language = "en"
        
        # Set default margins if not specified
        if not self.margins:
            self.margins = "20px"
    
    def before_save(self):
        """Actions before saving template."""
        # Update version if content changed
        if self.has_value_changed("template_content") and self.version:
            version_parts = self.version.split(".")
            if len(version_parts) == 2:
                minor = int(version_parts[1]) + 1
                self.version = f"{version_parts[0]}.{minor}"
    
    def on_update(self):
        """Actions on template update."""
        if self.has_value_changed("status"):
            self.handle_status_change()
        
        if self.has_value_changed("is_default") and self.is_default:
            self.set_as_default_template()
    
    def handle_status_change(self):
        """Handle template status changes."""
        if self.status == "Active":
            self.send_activation_notification()
        elif self.status == "Inactive":
            self.send_deactivation_notification()
    
    def set_as_default_template(self):
        """Set this template as default for its type."""
        if self.is_default:
            # Remove default flag from other templates of same type
            frappe.db.sql("""
                UPDATE `tabDocument Template`
                SET is_default = 0
                WHERE template_type = %s
                AND name != %s
            """, (self.template_type, self.name))
    
    def on_submit(self):
        """Actions on template submission."""
        self.validate_submission()
        self.send_template_notifications()
        self.create_template_version()
    
    def validate_submission(self):
        """Validate template before submission."""
        if not self.approved_by:
            frappe.throw(_("Template must be approved before submission"))
        
        if self.status != "Active":
            frappe.throw(_("Only active templates can be submitted"))
        
        if not self.template_content:
            frappe.throw(_("Template content is required for submission"))
    
    def send_template_notifications(self):
        """Send template notifications."""
        # Notify template managers
        self.send_manager_notification()
        
        # Notify users with access roles
        self.send_user_notifications()
    
    def send_manager_notification(self):
        """Send notification to template managers."""
        managers = frappe.get_all("Has Role",
            filters={"role": "Template Manager"},
            fields=["parent"]
        )
        
        if managers:
            recipients = [user.parent for user in managers]
            
            frappe.sendmail(
                recipients=recipients,
                subject=_("Document Template Submitted - {0}").format(self.template_name),
                message=self.get_manager_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_manager_notification_message(self):
        """Get manager notification message."""
        return _("""
        Document Template Submitted
        
        Template: {template_name}
        Type: {template_type}
        Category: {category}
        Version: {version}
        
        Created By: {created_by}
        Approved By: {approved_by}
        
        Description:
        {description}
        
        Applicable DocTypes: {doctypes}
        Access Roles: {roles}
        
        The template is now available for use.
        
        Template Management System
        """).format(
            template_name=self.template_name,
            template_type=self.template_type,
            category=self.category or "Not specified",
            version=self.version,
            created_by=self.created_by,
            approved_by=self.approved_by,
            description=self.description or "None",
            doctypes=", ".join([dt.doctype for dt in self.applicable_doctypes]) if self.applicable_doctypes else "All",
            roles=", ".join([role.role for role in self.access_roles]) if self.access_roles else "All"
        )
    
    def send_user_notifications(self):
        """Send notifications to users with access roles."""
        if not self.access_roles:
            return
        
        for role_row in self.access_roles:
            role_users = frappe.get_all("Has Role",
                filters={"role": role_row.role},
                fields=["parent"]
            )
            
            if role_users:
                recipients = [user.parent for user in role_users]
                
                frappe.sendmail(
                    recipients=recipients,
                    subject=_("New Document Template Available - {0}").format(self.template_name),
                    message=self.get_user_notification_message(),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
    
    def get_user_notification_message(self):
        """Get user notification message."""
        return _("""
        New Document Template Available
        
        Template: {template_name}
        Type: {template_type}
        Category: {category}
        
        Description:
        {description}
        
        Usage Instructions:
        {usage_instructions}
        
        You can now use this template for document generation.
        
        Template Management System
        """).format(
            template_name=self.template_name,
            template_type=self.template_type,
            category=self.category or "General",
            description=self.description or "No description provided",
            usage_instructions=self.usage_instructions or "Standard template usage applies"
        )
    
    def send_activation_notification(self):
        """Send template activation notification."""
        if self.access_roles:
            for role_row in self.access_roles:
                role_users = frappe.get_all("Has Role",
                    filters={"role": role_row.role},
                    fields=["parent"]
                )
                
                if role_users:
                    recipients = [user.parent for user in role_users]
                    
                    frappe.sendmail(
                        recipients=recipients,
                        subject=_("Template Activated - {0}").format(self.template_name),
                        message=_("Document template '{0}' has been activated and is now available for use.").format(self.template_name),
                        reference_doctype=self.doctype,
                        reference_name=self.name
                    )
    
    def send_deactivation_notification(self):
        """Send template deactivation notification."""
        if self.access_roles:
            for role_row in self.access_roles:
                role_users = frappe.get_all("Has Role",
                    filters={"role": role_row.role},
                    fields=["parent"]
                )
                
                if role_users:
                    recipients = [user.parent for user in role_users]
                    
                    frappe.sendmail(
                        recipients=recipients,
                        subject=_("Template Deactivated - {0}").format(self.template_name),
                        message=_("Document template '{0}' has been deactivated and is no longer available for use.").format(self.template_name),
                        reference_doctype=self.doctype,
                        reference_name=self.name
                    )
    
    def create_template_version(self):
        """Create template version record."""
        # This would create a version history record
        version_data = {
            "template": self.name,
            "version": self.version,
            "content": self.template_content,
            "created_by": frappe.session.user,
            "created_on": now_datetime()
        }
        
        frappe.log_error(f"Template version created: {version_data}")
    
    @frappe.whitelist()
    def approve_template(self):
        """Approve template for use."""
        if self.status == "Active":
            frappe.throw(_("Template is already active"))
        
        self.status = "Active"
        self.approved_by = frappe.session.user
        self.approval_date = getdate()
        self.save()
        
        frappe.msgprint(_("Template approved successfully"))
        return self
    
    @frappe.whitelist()
    def deactivate_template(self):
        """Deactivate template."""
        if self.status == "Inactive":
            frappe.throw(_("Template is already inactive"))
        
        self.status = "Inactive"
        self.save()
        
        frappe.msgprint(_("Template deactivated"))
        return self
    
    @frappe.whitelist()
    def preview_template(self, sample_data=None):
        """Preview template with sample data."""
        if not self.template_content:
            frappe.throw(_("No template content to preview"))
        
        # Use sample data or default values
        if not sample_data:
            sample_data = self.get_sample_data()
        
        # Render template
        rendered_content = self.render_template(sample_data)
        
        return {
            "content": rendered_content,
            "css": self.css_styles,
            "javascript": self.javascript_code,
            "header": self.header_content,
            "footer": self.footer_content
        }
    
    def get_sample_data(self):
        """Get sample data for template preview."""
        sample_data = {}
        
        if self.variables:
            for var in self.variables:
                if var.sample_value:
                    sample_data[var.variable_name] = var.sample_value
                else:
                    # Generate sample based on data type
                    sample_data[var.variable_name] = self.get_sample_value_for_type(var.data_type)
        
        return sample_data
    
    def get_sample_value_for_type(self, data_type):
        """Get sample value based on data type."""
        samples = {
            "Text": "Sample Text",
            "Number": "123",
            "Date": "2024-01-01",
            "Currency": "1,000.00",
            "Email": "sample@example.com",
            "Phone": "+1234567890",
            "URL": "https://example.com"
        }
        
        return samples.get(data_type, "Sample Value")
    
    @frappe.whitelist()
    def render_template(self, data):
        """Render template with provided data."""
        if not self.template_content:
            return ""
        
        content = self.template_content
        
        # Replace variables in template
        if isinstance(data, str):
            data = json.loads(data)
        
        for key, value in data.items():
            placeholder = f"{{{{{key}}}}}"
            content = content.replace(placeholder, cstr(value))
        
        # Add CSS and JavaScript if present
        if self.css_styles:
            content = f"<style>{self.css_styles}</style>\n{content}"
        
        if self.javascript_code:
            content = f"{content}\n<script>{self.javascript_code}</script>"
        
        return content
    
    @frappe.whitelist()
    def generate_document(self, doctype, docname, output_format="HTML"):
        """Generate document using this template."""
        if self.status != "Active":
            frappe.throw(_("Template is not active"))
        
        # Check if template is applicable to doctype
        if self.applicable_doctypes:
            applicable = any(dt.doctype == doctype for dt in self.applicable_doctypes)
            if not applicable:
                frappe.throw(_("Template is not applicable to {0}").format(doctype))
        
        # Get document data
        doc = frappe.get_doc(doctype, docname)
        doc_data = doc.as_dict()
        
        # Add system variables
        doc_data.update({
            "current_date": frappe.utils.today(),
            "current_time": frappe.utils.now(),
            "current_user": frappe.session.user,
            "company": frappe.defaults.get_user_default("Company")
        })
        
        # Render template
        rendered_content = self.render_template(doc_data)
        
        if output_format.upper() == "PDF":
            return self.generate_pdf(rendered_content)
        
        return rendered_content
    
    def generate_pdf(self, content):
        """Generate PDF from HTML content."""
        # This would use a PDF generation library
        # For now, return the HTML content
        return content
    
    @frappe.whitelist()
    def duplicate_template(self, new_name):
        """Create a duplicate of this template."""
        if not new_name:
            frappe.throw(_("New template name is required"))
        
        # Check if name already exists
        if frappe.db.exists("Document Template", {"template_name": new_name}):
            frappe.throw(_("Template with name '{0}' already exists").format(new_name))
        
        # Create duplicate
        new_template = frappe.copy_doc(self)
        new_template.template_name = new_name
        new_template.status = "Draft"
        new_template.is_default = 0
        new_template.approved_by = None
        new_template.approval_date = None
        new_template.version = "1.0"
        
        new_template.insert()
        
        frappe.msgprint(_("Template duplicated as {0}").format(new_template.name))
        return new_template
    
    @frappe.whitelist()
    def get_template_analytics(self):
        """Get template usage analytics."""
        # Get usage statistics
        usage_stats = frappe.db.sql("""
            SELECT COUNT(*) as usage_count
            FROM `tabCommunication`
            WHERE reference_doctype = 'Document Template'
            AND reference_name = %s
        """, self.name, as_dict=True)
        
        # Get template type distribution
        type_distribution = frappe.db.sql("""
            SELECT template_type, COUNT(*) as count
            FROM `tabDocument Template`
            WHERE status = 'Active'
            GROUP BY template_type
            ORDER BY count DESC
        """, as_dict=True)
        
        # Get recent templates
        recent_templates = frappe.get_all("Document Template",
            filters={"status": "Active"},
            fields=["name", "template_name", "template_type", "modified"],
            order_by="modified desc",
            limit=10
        )
        
        return {
            "current_template": {
                "name": self.name,
                "template_name": self.template_name,
                "type": self.template_type,
                "status": self.status,
                "version": self.version,
                "is_default": self.is_default
            },
            "usage_statistics": usage_stats[0] if usage_stats else {"usage_count": 0},
            "type_distribution": type_distribution,
            "recent_templates": recent_templates,
            "variables_count": len(self.variables) if self.variables else 0,
            "applicable_doctypes": [dt.doctype for dt in self.applicable_doctypes] if self.applicable_doctypes else [],
            "access_roles": [role.role for role in self.access_roles] if self.access_roles else []
        }
    
    def get_template_summary(self):
        """Get template summary for reporting."""
        return {
            "template_name": self.template_name,
            "template_type": self.template_type,
            "category": self.category,
            "status": self.status,
            "version": self.version,
            "language": self.language,
            "is_default": self.is_default,
            "created_by": self.created_by,
            "approved_by": self.approved_by,
            "approval_date": self.approval_date,
            "variables_count": len(self.variables) if self.variables else 0,
            "applicable_doctypes_count": len(self.applicable_doctypes) if self.applicable_doctypes else 0,
            "access_roles_count": len(self.access_roles) if self.access_roles else 0
        }
