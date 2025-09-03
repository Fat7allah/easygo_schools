"""Student Group doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate


class StudentGroup(Document):
    """Student Group doctype controller."""
    
    def validate(self):
        """Validate student group data."""
        self.validate_dates()
        self.validate_capacity()
        self.update_current_count()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate start and end dates."""
        if self.start_date and self.end_date:
            if getdate(self.start_date) >= getdate(self.end_date):
                frappe.throw(_("End date must be after start date"))
    
    def validate_capacity(self):
        """Validate group capacity."""
        if self.max_capacity and self.max_capacity <= 0:
            frappe.throw(_("Max capacity must be greater than 0"))
        
        if self.students and self.max_capacity:
            if len(self.students) > self.max_capacity:
                frappe.throw(_("Number of students exceeds maximum capacity"))
    
    def update_current_count(self):
        """Update current student count."""
        if self.students:
            self.current_count = len(self.students)
        else:
            self.current_count = 0
    
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
    def add_student(self, student):
        """Add a student to the group."""
        if self.max_capacity and len(self.students) >= self.max_capacity:
            frappe.throw(_("Group has reached maximum capacity"))
        
        # Check if student already exists
        existing = [s for s in self.students if s.student == student]
        if existing:
            frappe.throw(_("Student is already in this group"))
        
        # Add student
        self.append("students", {
            "student": student,
            "join_date": getdate(),
            "status": "Active"
        })
        
        self.save()
        return True
    
    @frappe.whitelist()
    def remove_student(self, student):
        """Remove a student from the group."""
        # Find and remove student
        for i, s in enumerate(self.students):
            if s.student == student:
                self.students.pop(i)
                break
        else:
            frappe.throw(_("Student not found in group"))
        
        self.save()
        return True
    
    @frappe.whitelist()
    def get_group_statistics(self):
        """Get group statistics."""
        stats = {
            "total_students": len(self.students),
            "capacity_utilization": (len(self.students) / self.max_capacity * 100) if self.max_capacity else 0,
            "active_students": len([s for s in self.students if s.status == "Active"]),
            "inactive_students": len([s for s in self.students if s.status == "Inactive"]),
            "average_join_duration": 0  # Would calculate based on join dates
        }
        
        return stats
