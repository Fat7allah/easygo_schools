"""Fee Type doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now


class FeeType(Document):
    """Fee Type doctype controller."""
    
    def validate(self):
        """Validate fee type data."""
        self.validate_late_fee_settings()
        self.set_defaults()
    
    def validate_late_fee_settings(self):
        """Validate late fee settings."""
        if self.late_fee_applicable and not self.late_fee_amount:
            frappe.throw(_("Late fee amount is required when late fee is applicable"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
    
    @frappe.whitelist()
    def get_applicable_students(self, academic_year=None):
        """Get students applicable for this fee type."""
        filters = {"is_active": 1}
        
        if academic_year:
            filters["academic_year"] = academic_year
        
        students = frappe.get_list("Student",
            filters=filters,
            fields=["name", "student_name", "school_class"]
        )
        
        return students
    
    @frappe.whitelist()
    def calculate_due_amount(self, student, academic_year=None):
        """Calculate due amount for a specific student."""
        # This would integrate with fee structure and student discounts
        base_amount = self.default_amount or 0
        
        # Check for student-specific discounts or scholarships
        discount = 0
        
        # Apply any class-specific fee adjustments
        # This would be implemented based on fee structure
        
        final_amount = base_amount - discount
        
        return {
            "base_amount": base_amount,
            "discount": discount,
            "final_amount": final_amount,
            "late_fee": self.late_fee_amount if self.late_fee_applicable else 0
        }
