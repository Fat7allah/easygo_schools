"""Extracurricular Activity doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate


class ExtracurricularActivity(Document):
    """Extracurricular Activity doctype controller."""
    
    def validate(self):
        """Validate activity data."""
        self.validate_dates()
        self.validate_capacity()
        self.update_participant_count()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate start and end dates."""
        if self.start_date and self.end_date:
            if getdate(self.start_date) >= getdate(self.end_date):
                frappe.throw(_("End date must be after start date"))
        
        if self.enrollment_deadline and self.start_date:
            if getdate(self.enrollment_deadline) > getdate(self.start_date):
                frappe.throw(_("Enrollment deadline must be before start date"))
    
    def validate_capacity(self):
        """Validate participant capacity."""
        if self.max_participants and self.current_participants:
            if self.current_participants > self.max_participants:
                frappe.throw(_("Current participants cannot exceed maximum capacity"))
    
    def update_participant_count(self):
        """Update current participant count."""
        count = frappe.db.count("Activity Enrollment", {
            "activity": self.name,
            "status": "Enrolled"
        })
        self.current_participants = count
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
    
    @frappe.whitelist()
    def enroll_student(self, student, enrollment_date=None):
        """Enroll a student in this activity."""
        if not self.enrollment_open:
            frappe.throw(_("Enrollment is closed for this activity"))
        
        if self.enrollment_deadline and getdate() > getdate(self.enrollment_deadline):
            frappe.throw(_("Enrollment deadline has passed"))
        
        if self.max_participants and self.current_participants >= self.max_participants:
            frappe.throw(_("Activity is at maximum capacity"))
        
        # Check if student is already enrolled
        existing = frappe.db.exists("Activity Enrollment", {
            "activity": self.name,
            "student": student,
            "status": "Enrolled"
        })
        
        if existing:
            frappe.throw(_("Student is already enrolled in this activity"))
        
        enrollment = frappe.get_doc({
            "doctype": "Activity Enrollment",
            "activity": self.name,
            "student": student,
            "enrollment_date": enrollment_date or getdate(),
            "status": "Enrolled"
        })
        
        enrollment.insert()
        
        # Update participant count
        self.update_participant_count()
        self.save()
        
        return enrollment.name
    
    @frappe.whitelist()
    def withdraw_student(self, student, reason=None):
        """Withdraw a student from this activity."""
        enrollment = frappe.get_doc("Activity Enrollment", {
            "activity": self.name,
            "student": student,
            "status": "Enrolled"
        })
        
        if not enrollment:
            frappe.throw(_("Student is not enrolled in this activity"))
        
        enrollment.status = "Withdrawn"
        enrollment.withdrawal_date = getdate()
        enrollment.withdrawal_reason = reason
        enrollment.save()
        
        # Update participant count
        self.update_participant_count()
        self.save()
        
        return True
    
    @frappe.whitelist()
    def get_enrolled_students(self):
        """Get list of enrolled students."""
        enrollments = frappe.get_list("Activity Enrollment",
            filters={
                "activity": self.name,
                "status": "Enrolled"
            },
            fields=["student", "enrollment_date"],
            order_by="enrollment_date"
        )
        
        students = []
        for enrollment in enrollments:
            student_info = frappe.get_doc("Student", enrollment.student)
            students.append({
                "student": enrollment.student,
                "student_name": student_info.student_name,
                "school_class": student_info.school_class,
                "enrollment_date": enrollment.enrollment_date
            })
        
        return students
    
    @frappe.whitelist()
    def get_activity_statistics(self):
        """Get activity statistics."""
        stats = {
            "total_enrolled": self.current_participants,
            "capacity_utilization": (self.current_participants / self.max_participants * 100) if self.max_participants else 0,
            "enrollment_status": "Open" if self.enrollment_open else "Closed",
            "days_until_deadline": None,
            "sessions_completed": 0,  # Would track from activity sessions
            "average_attendance": 0   # Would calculate from attendance records
        }
        
        if self.enrollment_deadline:
            from frappe.utils import date_diff
            days_left = date_diff(self.enrollment_deadline, getdate())
            stats["days_until_deadline"] = max(0, days_left)
        
        return stats
    
    @frappe.whitelist()
    def create_activity_session(self, session_date, session_time, topic=None):
        """Create an activity session."""
        session = frappe.get_doc({
            "doctype": "Activity Session",
            "activity": self.name,
            "session_date": session_date,
            "session_time": session_time,
            "topic": topic or f"{self.activity_name} Session",
            "supervisor": self.supervisor,
            "location": self.location
        })
        
        session.insert()
        
        return session.name
