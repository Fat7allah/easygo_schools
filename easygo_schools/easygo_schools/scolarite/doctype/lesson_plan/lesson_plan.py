"""Lesson Plan doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate


class LessonPlan(Document):
    """Lesson Plan doctype controller."""
    
    def validate(self):
        """Validate lesson plan data."""
        self.validate_lesson_date()
        self.validate_duration()
        self.set_defaults()
    
    def validate_lesson_date(self):
        """Validate lesson date."""
        if self.lesson_date and getdate(self.lesson_date) < getdate():
            if self.status == "Draft":
                frappe.msgprint(_("Warning: Lesson date is in the past"), alert=True)
    
    def validate_duration(self):
        """Validate lesson duration."""
        if self.duration_minutes and self.duration_minutes <= 0:
            frappe.throw(_("Duration must be greater than 0"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
        
        if not self.teacher:
            self.teacher = frappe.session.user
        
        if not self.academic_year:
            current_year = frappe.db.get_single_value("School Settings", "current_academic_year")
            if current_year:
                self.academic_year = current_year
    
    @frappe.whitelist()
    def mark_completed(self, reflection_notes=None, student_feedback=None):
        """Mark lesson as completed."""
        if self.status == "Completed":
            frappe.throw(_("Lesson is already marked as completed"))
        
        self.status = "Completed"
        
        if reflection_notes:
            self.reflection_notes = reflection_notes
        
        if student_feedback:
            self.student_feedback = student_feedback
        
        self.save()
        
        # Create lesson log entry
        self.create_lesson_log()
        
        return True
    
    def create_lesson_log(self):
        """Create lesson log entry."""
        try:
            lesson_log = frappe.get_doc({
                "doctype": "Lesson Log",
                "lesson_plan": self.name,
                "lesson_title": self.lesson_title,
                "subject": self.subject,
                "school_class": self.school_class,
                "teacher": self.teacher,
                "lesson_date": self.lesson_date,
                "duration_minutes": self.duration_minutes,
                "status": "Completed",
                "content_covered": self.lesson_content,
                "activities_conducted": self.activities,
                "assessment_notes": self.assessment_methods,
                "teacher_reflection": self.reflection_notes,
                "student_feedback": self.student_feedback
            })
            
            lesson_log.insert(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Failed to create lesson log: {str(e)}")
    
    @frappe.whitelist()
    def duplicate_plan(self, new_date=None, new_class=None):
        """Duplicate lesson plan for another date or class."""
        new_doc = frappe.copy_doc(self)
        
        if new_date:
            new_doc.lesson_date = new_date
        
        if new_class:
            new_doc.school_class = new_class
        
        new_doc.status = "Draft"
        new_doc.reflection_notes = ""
        new_doc.student_feedback = ""
        
        new_doc.insert()
        
        return new_doc.name
    
    @frappe.whitelist()
    def get_related_resources(self):
        """Get related resources for this lesson."""
        resources = frappe.get_list("Resource",
            filters={
                "subject": self.subject,
                "is_active": 1
            },
            fields=["name", "resource_title", "resource_type", "file_url"]
        )
        
        return resources
