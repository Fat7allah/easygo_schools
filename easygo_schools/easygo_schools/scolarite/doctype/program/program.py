"""Program doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now


class Program(Document):
    """Program doctype controller."""
    
    def validate(self):
        """Validate program data."""
        self.validate_age_requirements()
        self.validate_duration()
        self.calculate_program_metrics()
        self.set_defaults()
    
    def validate_age_requirements(self):
        """Validate age requirements."""
        if self.minimum_age and self.maximum_age:
            if self.minimum_age >= self.maximum_age:
                frappe.throw(_("Maximum age must be greater than minimum age"))
    
    def validate_duration(self):
        """Validate program duration."""
        if self.duration_years and self.duration_years <= 0:
            frappe.throw(_("Duration must be greater than 0"))
    
    def calculate_program_metrics(self):
        """Calculate program metrics."""
        if self.subjects:
            total_credits = sum([subject.credits or 0 for subject in self.subjects])
            if not self.total_credits_required:
                self.total_credits_required = total_credits
    
    def set_defaults(self):
        """Set default values."""
        if not self.program_code and self.program_name:
            # Generate program code from name
            self.program_code = "".join([word[0].upper() for word in self.program_name.split()[:3]])
    
    @frappe.whitelist()
    def get_program_statistics(self):
        """Get program statistics."""
        stats = {
            "total_students": 0,
            "total_classes": 0,
            "graduation_rate": 0,
            "average_grade": 0
        }
        
        try:
            # Get total active students in this program
            stats["total_students"] = frappe.db.count("Student", {
                "program": self.name,
                "status": "Active"
            })
            
            # Get total classes for this program
            stats["total_classes"] = frappe.db.count("School Class", {
                "program": self.name
            })
            
            # Calculate graduation rate (last 3 years)
            graduation_data = frappe.db.sql("""
                SELECT 
                    COUNT(CASE WHEN status = 'Graduated' THEN 1 END) as graduated,
                    COUNT(*) as total
                FROM `tabStudent`
                WHERE program = %s
                    AND YEAR(creation) >= YEAR(CURDATE()) - 3
            """, (self.name,))
            
            if graduation_data and graduation_data[0][1] > 0:
                stats["graduation_rate"] = round((graduation_data[0][0] / graduation_data[0][1]) * 100, 2)
            
            # Calculate average grade for current students
            grade_data = frappe.db.sql("""
                SELECT AVG(percentage) as avg_grade
                FROM `tabGrade` g
                INNER JOIN `tabStudent` s ON g.student = s.name
                WHERE s.program = %s AND s.status = 'Active'
            """, (self.name,))
            
            if grade_data and grade_data[0][0]:
                stats["average_grade"] = round(grade_data[0][0], 2)
        
        except Exception as e:
            frappe.log_error(f"Failed to get program statistics: {str(e)}")
        
        return stats
    
    @frappe.whitelist()
    def get_subject_list(self):
        """Get list of subjects in this program."""
        subjects = []
        
        if self.subjects:
            for subject_row in self.subjects:
                subject_details = frappe.db.get_value("Subject", 
                    subject_row.subject, 
                    ["subject_name", "subject_code", "description"], 
                    as_dict=True
                )
                
                if subject_details:
                    subject_details.update({
                        "credits": subject_row.credits,
                        "is_mandatory": subject_row.is_mandatory,
                        "year_level": subject_row.year_level
                    })
                    subjects.append(subject_details)
        
        return subjects
    
    @frappe.whitelist()
    def get_fee_breakdown(self):
        """Get detailed fee breakdown for this program."""
        fees = {
            "tuition_fee": self.tuition_fee or 0,
            "registration_fee": self.registration_fee or 0,
            "other_fees": [],
            "total_annual_fee": 0
        }
        
        if self.other_fees:
            for fee_row in self.other_fees:
                fees["other_fees"].append({
                    "fee_type": fee_row.fee_type,
                    "amount": fee_row.amount,
                    "frequency": fee_row.frequency,
                    "description": fee_row.description
                })
        
        # Calculate total annual fee
        total = fees["tuition_fee"] + fees["registration_fee"]
        
        for other_fee in fees["other_fees"]:
            if other_fee["frequency"] == "Annual":
                total += other_fee["amount"]
            elif other_fee["frequency"] == "Monthly":
                total += other_fee["amount"] * 12
            elif other_fee["frequency"] == "Term":
                total += other_fee["amount"] * 3  # Assuming 3 terms per year
        
        fees["total_annual_fee"] = total
        
        return fees
