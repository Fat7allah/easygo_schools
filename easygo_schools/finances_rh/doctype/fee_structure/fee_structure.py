"""Fee Structure doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate, add_months, flt


class FeeStructure(Document):
    """Fee Structure doctype controller."""
    
    def validate(self):
        """Validate fee structure data."""
        self.validate_components()
        self.calculate_total_amount()
        self.validate_installments()
        self.set_defaults()
    
    def validate_components(self):
        """Validate fee components."""
        if not self.components:
            frappe.throw(_("At least one fee component is required"))
        
        # Check for duplicate components
        component_names = []
        for component in self.components:
            if component.component_name in component_names:
                frappe.throw(_("Duplicate fee component: {0}").format(component.component_name))
            component_names.append(component.component_name)
    
    def calculate_total_amount(self):
        """Calculate total amount from components."""
        total = 0
        if self.components:
            for component in self.components:
                total += flt(component.amount)
        
        self.total_amount = total
    
    def validate_installments(self):
        """Validate installment structure."""
        if self.installments:
            total_percentage = sum([flt(installment.percentage) for installment in self.installments])
            
            if abs(total_percentage - 100) > 0.01:  # Allow small rounding differences
                frappe.throw(_("Total installment percentage must equal 100%"))
            
            # Calculate installment amounts
            for installment in self.installments:
                installment.amount = (flt(installment.percentage) / 100) * self.total_amount
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
        
        if not self.currency:
            self.currency = "MAD"
    
    def on_update(self):
        """Actions on fee structure update."""
        if self.has_value_changed("is_active") and self.is_active:
            self.update_related_fee_bills()
    
    def update_related_fee_bills(self):
        """Update related fee bills when structure becomes active."""
        try:
            # Find students who should use this fee structure
            students = self.get_applicable_students()
            
            for student in students:
                self.create_or_update_fee_bill(student)
        
        except Exception as e:
            frappe.log_error(f"Failed to update related fee bills: {str(e)}")
    
    def get_applicable_students(self):
        """Get students applicable for this fee structure."""
        filters = {
            "status": "Active",
            "academic_year": self.academic_year
        }
        
        if self.program:
            filters["program"] = self.program
        
        students = frappe.get_list("Student", 
            filters=filters,
            fields=["name", "student_name", "program", "school_class"]
        )
        
        return students
    
    def create_or_update_fee_bill(self, student):
        """Create or update fee bill for student."""
        try:
            # Check if fee bill already exists
            existing_bill = frappe.db.get_value("Fee Bill", {
                "student": student.name,
                "academic_year": self.academic_year,
                "fee_structure": self.name
            }, "name")
            
            if existing_bill:
                # Update existing bill
                bill_doc = frappe.get_doc("Fee Bill", existing_bill)
                bill_doc.fee_structure = self.name
                bill_doc.save(ignore_permissions=True)
            else:
                # Create new bill
                bill_doc = frappe.get_doc({
                    "doctype": "Fee Bill",
                    "student": student.name,
                    "academic_year": self.academic_year,
                    "fee_structure": self.name,
                    "total_amount": self.total_amount,
                    "outstanding_amount": self.total_amount,
                    "status": "Unpaid"
                })
                
                # Add fee components
                for component in self.components:
                    bill_doc.append("components", {
                        "component_name": component.component_name,
                        "amount": component.amount,
                        "description": component.description
                    })
                
                bill_doc.insert(ignore_permissions=True)
        
        except Exception as e:
            frappe.log_error(f"Failed to create fee bill for student {student.name}: {str(e)}")
    
    @frappe.whitelist()
    def calculate_student_fee(self, student, discount_percentage=0):
        """Calculate fee for a specific student with discounts."""
        base_amount = self.total_amount
        discount_amount = 0
        
        # Apply general discount
        if discount_percentage:
            discount_amount += (flt(discount_percentage) / 100) * base_amount
        
        # Apply sibling discount
        if self.sibling_discount:
            siblings_count = frappe.db.count("Student", {
                "status": "Active",
                "academic_year": self.academic_year
            })
            
            if siblings_count > 1:
                discount_amount += (flt(self.sibling_discount) / 100) * base_amount
        
        # Apply discount rules
        if self.discount_rules:
            for rule in self.discount_rules:
                if self.check_discount_eligibility(student, rule):
                    if rule.discount_type == "Percentage":
                        discount_amount += (flt(rule.discount_value) / 100) * base_amount
                    else:  # Fixed Amount
                        discount_amount += flt(rule.discount_value)
        
        final_amount = base_amount - discount_amount
        
        return {
            "base_amount": base_amount,
            "discount_amount": discount_amount,
            "final_amount": max(final_amount, 0),  # Ensure non-negative
            "components": [
                {
                    "component_name": comp.component_name,
                    "amount": comp.amount,
                    "description": comp.description
                } for comp in self.components
            ]
        }
    
    def check_discount_eligibility(self, student, discount_rule):
        """Check if student is eligible for discount rule."""
        try:
            if discount_rule.criteria == "Academic Performance":
                # Check student's average grade
                avg_grade = frappe.db.sql("""
                    SELECT AVG(percentage) 
                    FROM `tabGrade` 
                    WHERE student = %s 
                        AND academic_year = %s
                """, (student, self.academic_year))
                
                if avg_grade and avg_grade[0][0]:
                    return avg_grade[0][0] >= flt(discount_rule.threshold_value)
            
            elif discount_rule.criteria == "Financial Need":
                # This would require additional implementation based on family income
                return False
            
            elif discount_rule.criteria == "Early Payment":
                # Check if payment is made before due date
                return True  # Simplified logic
        
        except Exception as e:
            frappe.log_error(f"Failed to check discount eligibility: {str(e)}")
        
        return False
    
    @frappe.whitelist()
    def generate_installment_schedule(self, start_date=None):
        """Generate installment schedule based on payment frequency."""
        if not start_date:
            start_date = getdate()
        
        schedule = []
        
        if self.payment_frequency == "Annual":
            schedule.append({
                "installment_number": 1,
                "due_date": start_date,
                "amount": self.total_amount,
                "percentage": 100
            })
        
        elif self.payment_frequency == "Semi-Annual":
            for i in range(2):
                schedule.append({
                    "installment_number": i + 1,
                    "due_date": add_months(start_date, i * 6),
                    "amount": self.total_amount / 2,
                    "percentage": 50
                })
        
        elif self.payment_frequency == "Quarterly":
            for i in range(4):
                schedule.append({
                    "installment_number": i + 1,
                    "due_date": add_months(start_date, i * 3),
                    "amount": self.total_amount / 4,
                    "percentage": 25
                })
        
        elif self.payment_frequency == "Monthly":
            for i in range(12):
                schedule.append({
                    "installment_number": i + 1,
                    "due_date": add_months(start_date, i),
                    "amount": self.total_amount / 12,
                    "percentage": 8.33
                })
        
        return schedule
