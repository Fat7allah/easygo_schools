"""Academic Term doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, date_diff, now


class AcademicTerm(Document):
    """Academic Term doctype controller."""
    
    def validate(self):
        """Validate academic term data."""
        self.validate_dates()
        self.validate_active_term()
        self.calculate_term_metrics()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate term dates."""
        if self.term_start_date and self.term_end_date:
            if getdate(self.term_start_date) >= getdate(self.term_end_date):
                frappe.throw(_("Term End Date must be after Term Start Date"))
        
        # Validate grade submission dates
        if self.grade_submission_start and self.grade_submission_end:
            if getdate(self.grade_submission_start) >= getdate(self.grade_submission_end):
                frappe.throw(_("Grade Submission End Date must be after Start Date"))
            
            # Grade submission should be within or after term dates
            if self.term_end_date and getdate(self.grade_submission_start) < getdate(self.term_end_date):
                frappe.msgprint(_("Warning: Grade submission starts before term ends"), alert=True)
    
    def validate_active_term(self):
        """Validate only one active term per academic year."""
        if self.is_active:
            existing_active = frappe.db.sql("""
                SELECT name, term_name 
                FROM `tabAcademic Term` 
                WHERE academic_year = %s 
                    AND is_active = 1 
                    AND name != %s
            """, (self.academic_year, self.name or ''), as_dict=True)
            
            if existing_active:
                frappe.msgprint(_("Warning: Another active term exists: {0}").format(
                    existing_active[0].term_name
                ), alert=True)
    
    def calculate_term_metrics(self):
        """Calculate term metrics like total weeks and teaching days."""
        if self.term_start_date and self.term_end_date:
            total_days = date_diff(self.term_end_date, self.term_start_date) + 1
            self.total_weeks = int(total_days / 7)
            
            # Calculate teaching days (excluding weekends and holidays)
            teaching_days = 0
            current_date = getdate(self.term_start_date)
            end_date = getdate(self.term_end_date)
            
            holiday_dates = []
            if self.holidays:
                holiday_dates = [getdate(holiday.holiday_date) for holiday in self.holidays]
            
            while current_date <= end_date:
                # Skip weekends (Friday=4, Saturday=5 in Python weekday)
                if current_date.weekday() not in [4, 5]:  # Not Friday or Saturday
                    if current_date not in holiday_dates:
                        teaching_days += 1
                current_date = frappe.utils.add_days(current_date, 1)
            
            self.teaching_days = teaching_days
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
        
        if not self.final_grade_calculation:
            self.final_grade_calculation = "Average"
    
    def on_update(self):
        """Actions on term update."""
        if self.has_value_changed("is_active") and self.is_active:
            self.update_related_documents()
    
    def update_related_documents(self):
        """Update related documents when term becomes active."""
        try:
            # Update academic year's current term
            if self.academic_year:
                academic_year_doc = frappe.get_doc("Academic Year", self.academic_year)
                academic_year_doc.current_term = self.name
                academic_year_doc.save(ignore_permissions=True)
        
        except Exception as e:
            frappe.log_error(f"Failed to update related documents: {str(e)}")
    
    @frappe.whitelist()
    def get_term_progress(self):
        """Get term progress information."""
        if not (self.term_start_date and self.term_end_date):
            return {"progress": 0, "status": "Not Started"}
        
        today = getdate()
        start_date = getdate(self.term_start_date)
        end_date = getdate(self.term_end_date)
        
        if today < start_date:
            return {
                "progress": 0,
                "status": "Not Started",
                "days_until_start": date_diff(start_date, today)
            }
        elif today > end_date:
            return {
                "progress": 100,
                "status": "Completed",
                "days_since_end": date_diff(today, end_date)
            }
        else:
            total_days = date_diff(end_date, start_date) + 1
            elapsed_days = date_diff(today, start_date) + 1
            progress = int((elapsed_days / total_days) * 100)
            
            return {
                "progress": progress,
                "status": "In Progress",
                "days_remaining": date_diff(end_date, today),
                "elapsed_days": elapsed_days,
                "total_days": total_days
            }
    
    @frappe.whitelist()
    def get_term_statistics(self):
        """Get term statistics."""
        stats = {
            "total_students": 0,
            "total_classes": 0,
            "total_assessments": 0,
            "average_attendance": 0
        }
        
        try:
            # Get total students enrolled in this term
            stats["total_students"] = frappe.db.count("Student", {
                "status": "Active",
                "academic_year": self.academic_year
            })
            
            # Get total classes for this term
            stats["total_classes"] = frappe.db.count("School Class", {
                "academic_year": self.academic_year
            })
            
            # Get total assessments for this term
            stats["total_assessments"] = frappe.db.count("Assessment", {
                "academic_term": self.name
            })
            
            # Calculate average attendance for this term
            if self.term_start_date and self.term_end_date:
                attendance_data = frappe.db.sql("""
                    SELECT AVG(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) * 100 as avg_attendance
                    FROM `tabStudent Attendance`
                    WHERE attendance_date BETWEEN %s AND %s
                """, (self.term_start_date, self.term_end_date))
                
                if attendance_data and attendance_data[0][0]:
                    stats["average_attendance"] = round(attendance_data[0][0], 2)
        
        except Exception as e:
            frappe.log_error(f"Failed to get term statistics: {str(e)}")
        
        return stats
