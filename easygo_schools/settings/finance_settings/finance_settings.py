"""Finance Settings controller."""

import frappe
from frappe.model.document import Document


class FinanceSettings(Document):
    """Finance Settings doctype controller."""
    
    def validate(self):
        """Validate finance settings."""
        self.validate_percentage_fields()
        self.validate_payment_terms()
    
    def validate_percentage_fields(self):
        """Validate percentage fields are within valid range."""
        if self.late_fee_percentage and (self.late_fee_percentage < 0 or self.late_fee_percentage > 100):
            frappe.throw("Late Fee Percentage must be between 0 and 100")
    
    def validate_payment_terms(self):
        """Validate payment terms are reasonable."""
        if self.default_payment_terms and self.default_payment_terms < 1:
            frappe.throw("Default Payment Terms must be at least 1 day")
    
    def on_update(self):
        """Update related settings when finance settings change."""
        # Clear cache to ensure updated settings are reflected
        frappe.clear_cache()
