"""Learning Sequence doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate


class LearningSequence(Document):
    """Learning Sequence doctype controller."""
    
    def validate(self):
        """Validate learning sequence data."""
        self.validate_dates()
        self.update_progress()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate start and end dates."""
        if self.start_date and self.end_date:
            if getdate(self.start_date) >= getdate(self.end_date):
                frappe.throw(_("End date must be after start date"))
    
    def update_progress(self):
        """Update completion progress."""
        if self.lessons:
            completed_lessons = len([l for l in self.lessons if l.status == "Completed"])
            self.lessons_completed = completed_lessons
            self.total_lessons = len(self.lessons)
            
            if self.total_lessons > 0:
                self.completion_percentage = (completed_lessons / self.total_lessons) * 100
    
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
    def mark_lesson_completed(self, lesson_idx):
        """Mark a specific lesson as completed."""
        if lesson_idx < len(self.lessons):
            self.lessons[lesson_idx].status = "Completed"
            self.lessons[lesson_idx].completion_date = getdate()
            self.save()
            return True
        return False
    
    @frappe.whitelist()
    def get_sequence_analytics(self):
        """Get analytics for this learning sequence."""
        analytics = {
            "total_lessons": self.total_lessons,
            "completed_lessons": self.lessons_completed,
            "completion_rate": self.completion_percentage,
            "average_lesson_duration": 0,  # Would calculate from lesson plans
            "student_engagement": "High",  # Would calculate from feedback
            "on_schedule": getdate() <= getdate(self.end_date) if self.end_date else True
        }
        
        return analytics
