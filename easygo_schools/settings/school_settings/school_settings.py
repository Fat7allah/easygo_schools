"""School Settings controller."""

import frappe
from frappe.model.document import Document


class SchoolSettings(Document):
    """School Settings doctype controller."""
    
    def validate(self):
        """Validate school settings."""
        self.validate_massar_code()
        self.validate_email()
    
    def validate_massar_code(self):
        """Validate MASSAR code format."""
        if self.massar_code:
            import re
            if not re.fullmatch(r"\d{11}", self.massar_code):
                frappe.throw("MASSAR Code must be exactly 11 digits")
    
    def validate_email(self):
        """Validate email format."""
        if self.email:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, self.email):
                frappe.throw("Please enter a valid email address")
    
    def on_update(self):
        """Update related settings when school settings change."""
        # Clear cache to ensure updated settings are reflected
        frappe.clear_cache()
