"""Subject doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document


class Subject(Document):
    """Subject doctype controller with business rules."""
    
    def validate(self):
        """Validate subject data."""
        self.validate_scores()
        self.validate_subject_code()
    
    def validate_scores(self):
        """Validate score settings."""
        if self.pass_score and self.max_score:
            if self.pass_score > self.max_score:
                frappe.throw(_("Passing score cannot be greater than maximum score"))
            if self.pass_score < 0:
                frappe.throw(_("Passing score cannot be negative"))
        
        if self.max_score and self.max_score <= 0:
            frappe.throw(_("Maximum score must be greater than zero"))
    
    def validate_subject_code(self):
        """Validate and format subject code."""
        if self.subject_code:
            self.subject_code = self.subject_code.upper().strip()
    
    def on_update(self):
        """Actions on subject update."""
        # Update related records if subject name changed
        if self.has_value_changed("subject_name"):
            self.update_related_records()
    
    def update_related_records(self):
        """Update related records when subject name changes."""
        old_name = self.get_doc_before_save().subject_name
        
        # Update course schedules
        frappe.db.sql("""
            UPDATE `tabCourse Schedule` 
            SET subject = %s 
            WHERE subject = %s
        """, (self.subject_name, old_name))
        
        # Update homework
        frappe.db.sql("""
            UPDATE `tabHomework` 
            SET subject = %s 
            WHERE subject = %s
        """, (self.subject_name, old_name))
        
        # Update grades
        frappe.db.sql("""
            UPDATE `tabGrade` 
            SET subject = %s 
            WHERE subject = %s
        """, (self.subject_name, old_name))
