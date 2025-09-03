"""Class Subject Teacher doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate


class ClassSubjectTeacher(Document):
    """Class Subject Teacher doctype controller."""
    
    def validate(self):
        """Validate class subject teacher assignment."""
        self.validate_dates()
        self.validate_unique_assignment()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate start and end dates."""
        if self.start_date and self.end_date:
            if getdate(self.start_date) >= getdate(self.end_date):
                frappe.throw(_("End date must be after start date"))
    
    def validate_unique_assignment(self):
        """Validate unique assignment for class-subject combination."""
        existing = frappe.db.exists("Class Subject Teacher", {
            "school_class": self.school_class,
            "subject": self.subject,
            "academic_year": self.academic_year,
            "is_active": 1,
            "name": ["!=", self.name]
        })
        
        if existing and self.is_primary_teacher:
            frappe.throw(_("A primary teacher is already assigned for this class-subject combination"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
        
        if not self.academic_year:
            current_year = frappe.db.get_single_value("School Settings", "current_academic_year")
            if current_year:
                self.academic_year = current_year
    
    def before_save(self):
        """Actions before saving."""
        self.last_updated = now()
    
    @frappe.whitelist()
    def get_teaching_load(self):
        """Get teaching load for this teacher."""
        assignments = frappe.get_list("Class Subject Teacher",
            filters={
                "teacher": self.teacher,
                "academic_year": self.academic_year,
                "is_active": 1
            },
            fields=["school_class", "subject"]
        )
        
        return {
            "total_assignments": len(assignments),
            "classes": list(set([a.school_class for a in assignments])),
            "subjects": list(set([a.subject for a in assignments]))
        }
