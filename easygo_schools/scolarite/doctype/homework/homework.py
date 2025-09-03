"""Homework doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class Homework(Document):
    """Homework doctype controller with business rules."""
    
    def validate(self):
        """Validate homework data."""
        self.validate_dates()
        self.validate_instructor_assignment()
        self.update_submission_counts()
    
    def validate_dates(self):
        """Validate assignment and due dates."""
        if self.assignment_date and self.due_date:
            if getdate(self.assignment_date) > getdate(self.due_date):
                frappe.throw(_("Assignment date cannot be after due date"))
        
        if self.assignment_date and getdate(self.assignment_date) > getdate(today()):
            frappe.throw(_("Assignment date cannot be in the future"))
    
    def validate_instructor_assignment(self):
        """Validate instructor teaches this subject to this class."""
        if self.instructor and self.subject and self.school_class:
            # Check if instructor teaches this subject to this class
            schedule_exists = frappe.db.exists("Course Schedule", {
                "instructor": self.instructor,
                "subject": self.subject,
                "school_class": self.school_class,
                "is_active": 1
            })
            
            if not schedule_exists:
                frappe.msgprint(_("Warning: Instructor {0} is not scheduled to teach {1} to {2}").format(
                    self.instructor, self.subject, self.school_class
                ), alert=True)
    
    def update_submission_counts(self):
        """Update submission and grading counts."""
        if not self.is_new():
            self.submission_count = frappe.db.count("Homework Submission", {
                "homework": self.name
            })
            
            self.graded_count = frappe.db.count("Homework Submission", {
                "homework": self.name,
                "grade": ["is", "set"]
            })
    
    def before_save(self):
        """Actions before saving."""
        # Auto-publish if status is Published
        if self.status == "Published":
            self.is_published = 1
        elif self.status == "Draft":
            self.is_published = 0
    
    def after_insert(self):
        """Actions after homework creation."""
        if self.is_published:
            self.notify_students()
    
    def on_update(self):
        """Actions on homework update."""
        # Notify students if homework is published for the first time
        if self.has_value_changed("is_published") and self.is_published:
            self.notify_students()
    
    def notify_students(self):
        """Send notification to students about new homework."""
        # Check if notifications are enabled
        enable_notifications = frappe.db.get_single_value("School Settings", "enable_email_notifications")
        if not enable_notifications:
            return
        
        # Get students in the class
        students = frappe.get_all("Student", 
            filters={"school_class": self.school_class, "status": "Active"},
            fields=["name", "student_name", "guardian_email"]
        )
        
        if not students:
            return
        
        try:
            school_name = frappe.db.get_single_value("School Settings", "school_name") or "School"
            
            subject = _("New Homework Assignment - {0}").format(self.title)
            message = _("""
            <p>Dear Student/Parent,</p>
            
            <p>A new homework assignment has been posted:</p>
            
            <ul>
                <li><strong>Subject:</strong> {0}</li>
                <li><strong>Title:</strong> {1}</li>
                <li><strong>Due Date:</strong> {2}</li>
                <li><strong>Class:</strong> {3}</li>
            </ul>
            
            <p><strong>Description:</strong></p>
            <p>{4}</p>
            
            {5}
            
            <p>Please log in to the student portal to view full details and submit your work.</p>
            
            <p>Best regards,<br>
            {6} Administration</p>
            """).format(
                self.subject,
                self.title,
                frappe.utils.formatdate(self.due_date),
                self.school_class,
                self.description,
                f"<p><strong>Instructions:</strong> {self.instructions}</p>" if self.instructions else "",
                school_name
            )
            
            # Send to students and parents
            recipients = []
            for student in students:
                if student.guardian_email:
                    recipients.append(student.guardian_email)
            
            if recipients:
                frappe.sendmail(
                    recipients=list(set(recipients)),  # Remove duplicates
                    subject=subject,
                    message=message
                )
                
                # Log the notification
                frappe.get_doc({
                    "doctype": "Communication Log",
                    "reference_doctype": "Homework",
                    "reference_name": self.name,
                    "communication_type": "Email",
                    "subject": subject,
                    "status": "Sent"
                }).insert(ignore_permissions=True)
        
        except Exception as e:
            frappe.log_error(f"Failed to send homework notification for {self.name}: {str(e)}")
    
    def get_submission_summary(self):
        """Get submission summary for this homework."""
        total_students = frappe.db.count("Student", {
            "school_class": self.school_class,
            "status": "Active"
        })
        
        submitted = self.submission_count
        pending = total_students - submitted
        graded = self.graded_count
        
        return {
            "total_students": total_students,
            "submitted": submitted,
            "pending": pending,
            "graded": graded,
            "submission_rate": (submitted / total_students * 100) if total_students > 0 else 0
        }
