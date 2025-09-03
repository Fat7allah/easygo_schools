"""Course Schedule doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import time_diff_in_hours, get_time


class CourseSchedule(Document):
    """Course Schedule doctype controller with business rules."""
    
    def validate(self):
        """Validate course schedule data."""
        self.validate_time_slots()
        self.validate_instructor_availability()
        self.validate_class_availability()
        self.calculate_duration()
        self.set_defaults()
    
    def validate_time_slots(self):
        """Validate start and end times."""
        if self.start_time and self.end_time:
            if get_time(self.start_time) >= get_time(self.end_time):
                frappe.throw(_("End time must be after start time"))
            
            # Check if duration is reasonable (between 30 minutes and 4 hours)
            duration_hours = time_diff_in_hours(self.end_time, self.start_time)
            if duration_hours < 0.5:
                frappe.throw(_("Class duration must be at least 30 minutes"))
            if duration_hours > 4:
                frappe.throw(_("Class duration cannot exceed 4 hours"))
    
    def validate_instructor_availability(self):
        """Check if instructor is available at this time."""
        if not self.instructor or not self.day_of_week or not self.start_time or not self.end_time:
            return
        
        # Check for overlapping schedules for the same instructor
        overlapping_schedules = frappe.db.sql("""
            SELECT name, school_class, subject
            FROM `tabCourse Schedule`
            WHERE instructor = %s 
                AND day_of_week = %s
                AND academic_year = %s
                AND is_active = 1
                AND name != %s
                AND (
                    (start_time <= %s AND end_time > %s) OR
                    (start_time < %s AND end_time >= %s) OR
                    (start_time >= %s AND end_time <= %s)
                )
        """, (
            self.instructor, self.day_of_week, self.academic_year, self.name or '',
            self.start_time, self.start_time,
            self.end_time, self.end_time,
            self.start_time, self.end_time
        ), as_dict=True)
        
        if overlapping_schedules:
            schedule = overlapping_schedules[0]
            frappe.throw(_("Instructor {0} is already scheduled for {1} - {2} on {3}").format(
                self.instructor, schedule.school_class, schedule.subject, self.day_of_week
            ))
    
    def validate_class_availability(self):
        """Check if class is available at this time."""
        if not self.school_class or not self.day_of_week or not self.start_time or not self.end_time:
            return
        
        # Check for overlapping schedules for the same class
        overlapping_schedules = frappe.db.sql("""
            SELECT name, instructor, subject
            FROM `tabCourse Schedule`
            WHERE school_class = %s 
                AND day_of_week = %s
                AND academic_year = %s
                AND is_active = 1
                AND name != %s
                AND (
                    (start_time <= %s AND end_time > %s) OR
                    (start_time < %s AND end_time >= %s) OR
                    (start_time >= %s AND end_time <= %s)
                )
        """, (
            self.school_class, self.day_of_week, self.academic_year, self.name or '',
            self.start_time, self.start_time,
            self.end_time, self.end_time,
            self.start_time, self.end_time
        ), as_dict=True)
        
        if overlapping_schedules:
            schedule = overlapping_schedules[0]
            frappe.throw(_("Class {0} already has {1} scheduled with {2} on {3}").format(
                self.school_class, schedule.subject, schedule.instructor, self.day_of_week
            ))
    
    def calculate_duration(self):
        """Calculate duration in minutes."""
        if self.start_time and self.end_time:
            duration_hours = time_diff_in_hours(self.end_time, self.start_time)
            self.duration = int(duration_hours * 60)
    
    def set_defaults(self):
        """Set default values."""
        if not self.effective_from:
            # Get academic year start date
            if self.academic_year:
                academic_year_doc = frappe.get_doc("Academic Year", self.academic_year)
                self.effective_from = academic_year_doc.start_date
        
        if not self.effective_to:
            # Get academic year end date
            if self.academic_year:
                academic_year_doc = frappe.get_doc("Academic Year", self.academic_year)
                self.effective_to = academic_year_doc.end_date
        
        # Set default color based on subject
        if not self.color and self.subject:
            subject_color = frappe.db.get_value("Subject", self.subject, "color")
            if subject_color:
                self.color = subject_color
    
    def after_insert(self):
        """Actions after course schedule creation."""
        self.update_class_timetable()
    
    def on_update(self):
        """Actions on course schedule update."""
        if self.has_value_changed("is_active"):
            self.update_class_timetable()
    
    def on_trash(self):
        """Actions before course schedule deletion."""
        self.update_class_timetable()
    
    def update_class_timetable(self):
        """Update class timetable summary."""
        try:
            # Update total weekly hours for the class
            total_hours = frappe.db.sql("""
                SELECT SUM(duration) as total_minutes
                FROM `tabCourse Schedule`
                WHERE school_class = %s 
                    AND academic_year = %s
                    AND is_active = 1
            """, (self.school_class, self.academic_year), as_dict=True)
            
            if total_hours and total_hours[0].total_minutes:
                weekly_hours = total_hours[0].total_minutes / 60
                
                # Update school class with weekly hours
                frappe.db.set_value("School Class", self.school_class, "weekly_hours", weekly_hours)
                
        except Exception as e:
            frappe.log_error(f"Failed to update class timetable for {self.name}: {str(e)}")
    
    @frappe.whitelist()
    def get_class_timetable(self):
        """Get complete timetable for this class."""
        schedules = frappe.get_list("Course Schedule",
            filters={
                "school_class": self.school_class,
                "academic_year": self.academic_year,
                "is_active": 1
            },
            fields=[
                "day_of_week", "start_time", "end_time", "subject", 
                "instructor", "room_number", "color", "notes"
            ],
            order_by="day_of_week, start_time"
        )
        
        # Group by day of week
        timetable = {}
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        for day in days:
            timetable[day] = []
        
        for schedule in schedules:
            if schedule.day_of_week in timetable:
                timetable[schedule.day_of_week].append(schedule)
        
        return timetable
    
    @frappe.whitelist()
    def get_instructor_schedule(self):
        """Get complete schedule for this instructor."""
        schedules = frappe.get_list("Course Schedule",
            filters={
                "instructor": self.instructor,
                "academic_year": self.academic_year,
                "is_active": 1
            },
            fields=[
                "day_of_week", "start_time", "end_time", "subject", 
                "school_class", "room_number", "color", "notes"
            ],
            order_by="day_of_week, start_time"
        )
        
        # Group by day of week
        schedule = {}
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        for day in days:
            schedule[day] = []
        
        for item in schedules:
            if item.day_of_week in schedule:
                schedule[item.day_of_week].append(item)
        
        return schedule
