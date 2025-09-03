"""Exam doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today, time_diff_in_hours, get_time, now


class Exam(Document):
    """Exam doctype controller with business rules."""
    
    def validate(self):
        """Validate exam data."""
        self.validate_dates()
        self.validate_time_slots()
        self.validate_marks()
        self.calculate_duration()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate exam dates."""
        if self.exam_date and getdate(self.exam_date) < getdate(today()):
            if self.status == "Draft":
                frappe.throw(_("Exam date cannot be in the past"))
    
    def validate_time_slots(self):
        """Validate start and end times."""
        if self.start_time and self.end_time:
            if get_time(self.start_time) >= get_time(self.end_time):
                frappe.throw(_("End time must be after start time"))
            
            # Check if duration is reasonable (between 30 minutes and 6 hours)
            duration_hours = time_diff_in_hours(self.end_time, self.start_time)
            if duration_hours < 0.5:
                frappe.throw(_("Exam duration must be at least 30 minutes"))
            if duration_hours > 6:
                frappe.throw(_("Exam duration cannot exceed 6 hours"))
    
    def validate_marks(self):
        """Validate marks configuration."""
        if self.max_marks and self.max_marks <= 0:
            frappe.throw(_("Maximum marks must be greater than 0"))
        
        if self.passing_marks and self.max_marks:
            if self.passing_marks > self.max_marks:
                frappe.throw(_("Passing marks cannot be greater than maximum marks"))
            if self.passing_marks < 0:
                frappe.throw(_("Passing marks cannot be negative"))
    
    def calculate_duration(self):
        """Calculate duration in minutes."""
        if self.start_time and self.end_time:
            duration_hours = time_diff_in_hours(self.end_time, self.start_time)
            self.duration = int(duration_hours * 60)
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.passing_marks and self.max_marks:
            # Set passing marks to 40% of max marks by default
            self.passing_marks = self.max_marks * 0.4
    
    def before_submit(self):
        """Actions before exam submission."""
        self.validate_exam_ready()
        self.status = "Scheduled"
        self.published_date = now()
    
    def validate_exam_ready(self):
        """Validate exam is ready to be scheduled."""
        if not self.exam_date:
            frappe.throw(_("Exam date is required"))
        
        if not self.start_time or not self.end_time:
            frappe.throw(_("Start time and end time are required"))
        
        if not self.max_marks:
            frappe.throw(_("Maximum marks is required"))
        
        # Check if there are conflicting exams
        self.check_exam_conflicts()
    
    def check_exam_conflicts(self):
        """Check for conflicting exams."""
        conflicts = frappe.db.sql("""
            SELECT name, exam_name, subject
            FROM `tabExam`
            WHERE school_class = %s 
                AND exam_date = %s
                AND status IN ('Scheduled', 'Ongoing')
                AND name != %s
                AND (
                    (start_time <= %s AND end_time > %s) OR
                    (start_time < %s AND end_time >= %s) OR
                    (start_time >= %s AND end_time <= %s)
                )
        """, (
            self.school_class, self.exam_date, self.name or '',
            self.start_time, self.start_time,
            self.end_time, self.end_time,
            self.start_time, self.end_time
        ), as_dict=True)
        
        if conflicts:
            conflict = conflicts[0]
            frappe.throw(_("Exam conflicts with {0} ({1}) scheduled at the same time").format(
                conflict.exam_name, conflict.subject
            ))
    
    def after_insert(self):
        """Actions after exam creation."""
        self.update_class_statistics()
    
    def on_update(self):
        """Actions on exam update."""
        if self.has_value_changed("status"):
            if self.status == "Scheduled":
                self.notify_students_and_parents()
            elif self.status == "Completed":
                self.calculate_results_summary()
    
    def notify_students_and_parents(self):
        """Send notification about scheduled exam."""
        # Check if notifications are enabled
        enable_notifications = frappe.db.get_single_value("School Settings", "enable_email_notifications")
        if not enable_notifications:
            return
        
        try:
            # Get students in the class
            students = frappe.get_list("Student", 
                filters={"school_class": self.school_class, "status": "Active"},
                fields=["name", "student_name", "guardian_email"]
            )
            
            school_name = frappe.db.get_single_value("School Settings", "school_name") or "School"
            
            for student in students:
                if student.guardian_email:
                    subject = _("Exam Scheduled - {0}").format(self.exam_name)
                    message = _("""
                    <p>Dear Parent,</p>
                    
                    <p>An exam has been scheduled for your child:</p>
                    
                    <ul>
                        <li><strong>Student:</strong> {0}</li>
                        <li><strong>Exam:</strong> {1}</li>
                        <li><strong>Subject:</strong> {2}</li>
                        <li><strong>Date:</strong> {3}</li>
                        <li><strong>Time:</strong> {4} - {5}</li>
                        <li><strong>Duration:</strong> {6} minutes</li>
                        <li><strong>Room:</strong> {7}</li>
                        <li><strong>Maximum Marks:</strong> {8}</li>
                    </ul>
                    
                    {9}
                    
                    {10}
                    
                    <p>Please ensure your child is well-prepared and arrives on time.</p>
                    
                    <p>Best regards,<br>
                    {11} Administration</p>
                    """).format(
                        student.student_name,
                        self.exam_name,
                        self.subject,
                        frappe.utils.formatdate(self.exam_date),
                        self.start_time,
                        self.end_time,
                        self.duration,
                        self.room_number or _("TBA"),
                        self.max_marks,
                        f"<p><strong>Instructions:</strong> {self.instructions}</p>" if self.instructions else "",
                        f"<p><strong>Materials Allowed:</strong> {self.materials_allowed}</p>" if self.materials_allowed else "",
                        school_name
                    )
                    
                    frappe.sendmail(
                        recipients=[student.guardian_email],
                        subject=subject,
                        message=message
                    )
            
        except Exception as e:
            frappe.log_error(f"Failed to send exam notification for {self.name}: {str(e)}")
    
    def calculate_results_summary(self):
        """Calculate exam results summary."""
        try:
            # Get all grades for this exam
            grades = frappe.get_list("Grade",
                filters={
                    "exam": self.name,
                    "subject": self.subject,
                    "academic_year": self.academic_year
                },
                fields=["score", "student"]
            )
            
            if grades:
                scores = [grade.score for grade in grades if grade.score is not None]
                
                if scores:
                    self.students_appeared = len(scores)
                    self.average_score = sum(scores) / len(scores)
                    self.highest_score = max(scores)
                    self.lowest_score = min(scores)
                else:
                    self.students_appeared = 0
                    self.average_score = 0
                    self.highest_score = 0
                    self.lowest_score = 0
            
            # Get total students in class
            total_students = frappe.db.count("Student", {
                "school_class": self.school_class,
                "status": "Active"
            })
            self.total_students = total_students
            
            self.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Failed to calculate results summary for {self.name}: {str(e)}")
    
    def update_class_statistics(self):
        """Update class exam statistics."""
        try:
            # Count total exams for this class
            total_exams = frappe.db.count("Exam", {
                "school_class": self.school_class,
                "academic_year": self.academic_year,
                "status": ["!=", "Cancelled"]
            })
            
            # Update school class with exam count
            frappe.db.set_value("School Class", self.school_class, "total_exams", total_exams)
            
        except Exception as e:
            frappe.log_error(f"Failed to update class statistics for {self.name}: {str(e)}")
    
    @frappe.whitelist()
    def start_exam(self):
        """Mark exam as ongoing."""
        if self.status != "Scheduled":
            frappe.throw(_("Only scheduled exams can be started"))
        
        self.status = "Ongoing"
        self.save(ignore_permissions=True)
        
        frappe.msgprint(_("Exam has been started"))
    
    @frappe.whitelist()
    def complete_exam(self):
        """Mark exam as completed."""
        if self.status != "Ongoing":
            frappe.throw(_("Only ongoing exams can be completed"))
        
        self.status = "Completed"
        self.save(ignore_permissions=True)
        
        # Calculate results summary
        self.calculate_results_summary()
        
        frappe.msgprint(_("Exam has been completed"))
    
    @frappe.whitelist()
    def cancel_exam(self, reason=None):
        """Cancel the exam."""
        if self.status in ["Completed"]:
            frappe.throw(_("Completed exams cannot be cancelled"))
        
        self.status = "Cancelled"
        if reason:
            self.notes = (self.notes or "") + f"\n\nCancellation Reason: {reason}"
        
        self.save(ignore_permissions=True)
        
        frappe.msgprint(_("Exam has been cancelled"))
