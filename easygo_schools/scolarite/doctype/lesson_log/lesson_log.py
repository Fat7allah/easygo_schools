"""Lesson Log doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate, time_diff_in_hours


class LessonLog(Document):
    """Lesson Log doctype controller."""
    
    def validate(self):
        """Validate lesson log data."""
        self.validate_times()
        self.calculate_attendance()
        self.calculate_duration()
        self.set_defaults()
    
    def validate_times(self):
        """Validate start and end times."""
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                frappe.throw(_("End time must be after start time"))
    
    def calculate_attendance(self):
        """Calculate attendance statistics."""
        if self.students_present and self.students_absent:
            self.total_students = self.students_present + self.students_absent
            self.attendance_percentage = (self.students_present / self.total_students) * 100
    
    def calculate_duration(self):
        """Calculate lesson duration."""
        if self.start_time and self.end_time:
            duration_hours = time_diff_in_hours(self.end_time, self.start_time)
            self.duration_minutes = int(duration_hours * 60)
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
        
        if not self.teacher:
            self.teacher = frappe.session.user
    
    @frappe.whitelist()
    def get_lesson_analytics(self):
        """Get analytics for this lesson."""
        analytics = {
            "attendance_rate": self.attendance_percentage,
            "duration_actual": self.duration_minutes,
            "performance_rating": self.student_performance,
            "content_completion": "100%" if self.status == "Completed" else "Partial",
            "challenges_count": len(self.challenges_faced.split('\n')) if self.challenges_faced else 0
        }
        
        return analytics
