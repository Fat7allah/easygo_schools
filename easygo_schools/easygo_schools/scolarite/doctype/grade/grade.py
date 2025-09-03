"""Grade doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now


class Grade(Document):
    """Grade doctype controller with business rules."""
    
    def validate(self):
        """Validate grade data."""
        self.validate_grade_range()
        self.calculate_percentage()
        self.calculate_letter_grade()
        self.calculate_grade_point()
        self.validate_duplicate_grade()
    
    def validate_grade_range(self):
        """Validate grade is within acceptable range."""
        if self.grade < 0:
            frappe.throw(_("Grade cannot be negative"))
        
        if self.max_grade <= 0:
            frappe.throw(_("Maximum grade must be greater than zero"))
        
        if self.grade > self.max_grade:
            frappe.throw(_("Grade cannot exceed maximum grade of {0}").format(self.max_grade))
    
    def calculate_percentage(self):
        """Calculate percentage from grade."""
        if self.grade is not None and self.max_grade:
            self.percentage = (self.grade / self.max_grade) * 100
    
    def calculate_letter_grade(self):
        """Calculate letter grade based on percentage."""
        if self.percentage is not None:
            if self.percentage >= 97:
                self.letter_grade = "A+"
            elif self.percentage >= 93:
                self.letter_grade = "A"
            elif self.percentage >= 90:
                self.letter_grade = "A-"
            elif self.percentage >= 87:
                self.letter_grade = "B+"
            elif self.percentage >= 83:
                self.letter_grade = "B"
            elif self.percentage >= 80:
                self.letter_grade = "B-"
            elif self.percentage >= 77:
                self.letter_grade = "C+"
            elif self.percentage >= 73:
                self.letter_grade = "C"
            elif self.percentage >= 70:
                self.letter_grade = "C-"
            elif self.percentage >= 67:
                self.letter_grade = "D+"
            elif self.percentage >= 60:
                self.letter_grade = "D"
            else:
                self.letter_grade = "F"
    
    def calculate_grade_point(self):
        """Calculate grade point based on letter grade."""
        grade_points = {
            "A+": 4.0, "A": 4.0, "A-": 3.7,
            "B+": 3.3, "B": 3.0, "B-": 2.7,
            "C+": 2.3, "C": 2.0, "C-": 1.7,
            "D+": 1.3, "D": 1.0, "F": 0.0
        }
        self.grade_point = grade_points.get(self.letter_grade, 0.0)
    
    def validate_duplicate_grade(self):
        """Validate no duplicate grade for same student, subject, and assessment."""
        filters = {
            "student": self.student,
            "subject": self.subject,
            "assessment_date": self.assessment_date,
            "name": ["!=", self.name]
        }
        
        if self.assessment:
            filters["assessment"] = self.assessment
        
        existing = frappe.db.get_value("Grade", filters, "name")
        if existing:
            frappe.throw(_("Grade already exists for this student, subject, and assessment"))
    
    def before_save(self):
        """Actions before saving."""
        # Set grading information
        if not self.graded_by:
            self.graded_by = frappe.session.user
            self.graded_on = now()
        
        # Auto-publish if status is Published
        if self.status == "Published":
            self.is_published = 1
        elif self.status == "Draft":
            self.is_published = 0
    
    def after_insert(self):
        """Actions after grade creation."""
        if self.is_published:
            self.notify_student()
    
    def on_update(self):
        """Actions on grade update."""
        # Notify student if grade is published for the first time
        if self.has_value_changed("is_published") and self.is_published:
            self.notify_student()
    
    def notify_student(self):
        """Send notification to student about new grade."""
        # Check if notifications are enabled
        enable_notifications = frappe.db.get_single_value("School Settings", "enable_email_notifications")
        if not enable_notifications:
            return
        
        try:
            student = frappe.get_doc("Student", self.student)
            
            if not student.guardian_email:
                return
            
            school_name = frappe.db.get_single_value("School Settings", "school_name") or "School"
            
            subject = _("New Grade Posted - {0}").format(self.subject)
            message = _("""
            <p>Dear Student/Parent,</p>
            
            <p>A new grade has been posted for {0}:</p>
            
            <ul>
                <li><strong>Subject:</strong> {1}</li>
                <li><strong>Grade:</strong> {2}/{3} ({4}%)</li>
                <li><strong>Letter Grade:</strong> {5}</li>
                <li><strong>Assessment Date:</strong> {6}</li>
                {7}
            </ul>
            
            {8}
            
            <p>Please log in to the student portal to view detailed grade information.</p>
            
            <p>Best regards,<br>
            {9} Administration</p>
            """).format(
                student.student_name,
                self.subject,
                self.grade,
                self.max_grade,
                round(self.percentage, 1) if self.percentage else 0,
                self.letter_grade or "N/A",
                frappe.utils.formatdate(self.assessment_date),
                f"<li><strong>Assessment:</strong> {self.assessment}</li>" if self.assessment else "",
                f"<p><strong>Remarks:</strong> {self.remarks}</p>" if self.remarks else "",
                school_name
            )
            
            frappe.sendmail(
                recipients=[student.guardian_email],
                subject=subject,
                message=message
            )
            
            # Log the notification
            frappe.get_doc({
                "doctype": "Communication Log",
                "reference_doctype": "Grade",
                "reference_name": self.name,
                "communication_type": "Email",
                "subject": subject,
                "status": "Sent"
            }).insert(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Failed to send grade notification for {self.name}: {str(e)}")
    
    def get_grade_status(self):
        """Get grade status (Pass/Fail) based on subject passing criteria."""
        if not self.subject or self.percentage is None:
            return "Unknown"
        
        # Get subject passing score
        pass_score = frappe.db.get_value("Subject", self.subject, "pass_score") or 50
        pass_percentage = (pass_score / self.max_grade) * 100 if self.max_grade else 50
        
        return "Pass" if self.percentage >= pass_percentage else "Fail"
