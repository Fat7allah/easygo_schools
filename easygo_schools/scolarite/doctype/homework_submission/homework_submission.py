"""Homework Submission doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now


class HomeworkSubmission(Document):
    """Homework Submission doctype controller with business rules."""
    
    def validate(self):
        """Validate submission data."""
        self.validate_duplicate_submission()
        self.validate_submission_deadline()
        self.fetch_homework_details()
        self.validate_grade()
    
    def validate_duplicate_submission(self):
        """Validate no duplicate submission for same homework and student."""
        existing = frappe.db.get_value(
            "Homework Submission",
            {
                "homework": self.homework,
                "student": self.student,
                "name": ["!=", self.name]
            },
            "name"
        )
        if existing:
            frappe.throw(_("Submission already exists for this homework"))
    
    def validate_submission_deadline(self):
        """Check if submission is late."""
        if self.homework and self.submission_date:
            homework = frappe.get_doc("Homework", self.homework)
            due_date = getdate(homework.due_date)
            submission_date = getdate(self.submission_date)
            
            if submission_date > due_date:
                self.status = "Late"
                frappe.msgprint(_("This submission is late. Due date was {0}").format(
                    frappe.utils.formatdate(due_date)
                ), alert=True)
    
    def fetch_homework_details(self):
        """Fetch homework details."""
        if self.homework:
            homework = frappe.get_doc("Homework", self.homework)
            self.max_grade = homework.max_score
    
    def validate_grade(self):
        """Validate grade is within limits."""
        if self.grade is not None and self.max_grade:
            if self.grade > self.max_grade:
                frappe.throw(_("Grade cannot exceed maximum grade of {0}").format(self.max_grade))
            if self.grade < 0:
                frappe.throw(_("Grade cannot be negative"))
    
    def before_save(self):
        """Actions before saving."""
        # Set grading information
        if self.grade is not None and not self.graded_by:
            self.graded_by = frappe.session.user
            self.graded_on = now()
            self.status = "Graded"
    
    def after_insert(self):
        """Actions after submission creation."""
        self.notify_teacher()
        self.update_homework_counts()
    
    def on_update(self):
        """Actions on submission update."""
        # Notify student if graded
        if self.has_value_changed("grade") and self.grade is not None:
            self.notify_student_graded()
        
        self.update_homework_counts()
    
    def notify_teacher(self):
        """Notify teacher about new submission."""
        # Check if notifications are enabled
        enable_notifications = frappe.db.get_single_value("School Settings", "enable_email_notifications")
        if not enable_notifications:
            return
        
        try:
            homework = frappe.get_doc("Homework", self.homework)
            teacher_email = frappe.db.get_value("Employee", homework.instructor, "company_email")
            
            if not teacher_email:
                return
            
            student_name = frappe.db.get_value("Student", self.student, "student_name")
            school_name = frappe.db.get_single_value("School Settings", "school_name") or "School"
            
            subject = _("New Homework Submission - {0}").format(homework.title)
            message = _("""
            <p>Dear Teacher,</p>
            
            <p>A new homework submission has been received:</p>
            
            <ul>
                <li><strong>Student:</strong> {0}</li>
                <li><strong>Homework:</strong> {1}</li>
                <li><strong>Subject:</strong> {2}</li>
                <li><strong>Submitted On:</strong> {3}</li>
                <li><strong>Status:</strong> {4}</li>
            </ul>
            
            <p>Please log in to the teacher portal to review and grade the submission.</p>
            
            <p>Best regards,<br>
            {5} System</p>
            """).format(
                student_name,
                homework.title,
                homework.subject,
                frappe.utils.format_datetime(self.submission_date),
                self.status,
                school_name
            )
            
            frappe.sendmail(
                recipients=[teacher_email],
                subject=subject,
                message=message
            )
            
        except Exception as e:
            frappe.log_error(f"Failed to send submission notification for {self.name}: {str(e)}")
    
    def notify_student_graded(self):
        """Notify student when homework is graded."""
        # Check if notifications are enabled
        enable_notifications = frappe.db.get_single_value("School Settings", "enable_email_notifications")
        if not enable_notifications:
            return
        
        try:
            student = frappe.get_doc("Student", self.student)
            homework = frappe.get_doc("Homework", self.homework)
            
            if not student.guardian_email:
                return
            
            school_name = frappe.db.get_single_value("School Settings", "school_name") or "School"
            
            subject = _("Homework Graded - {0}").format(homework.title)
            message = _("""
            <p>Dear Student/Parent,</p>
            
            <p>Your homework has been graded:</p>
            
            <ul>
                <li><strong>Student:</strong> {0}</li>
                <li><strong>Homework:</strong> {1}</li>
                <li><strong>Subject:</strong> {2}</li>
                <li><strong>Grade:</strong> {3}/{4}</li>
                <li><strong>Graded On:</strong> {5}</li>
            </ul>
            
            {6}
            
            <p>Please log in to the student portal to view detailed feedback.</p>
            
            <p>Best regards,<br>
            {7} Administration</p>
            """).format(
                student.student_name,
                homework.title,
                homework.subject,
                self.grade,
                self.max_grade,
                frappe.utils.format_datetime(self.graded_on),
                f"<p><strong>Feedback:</strong> {self.feedback}</p>" if self.feedback else "",
                school_name
            )
            
            frappe.sendmail(
                recipients=[student.guardian_email],
                subject=subject,
                message=message
            )
            
        except Exception as e:
            frappe.log_error(f"Failed to send grading notification for {self.name}: {str(e)}")
    
    def update_homework_counts(self):
        """Update submission counts in homework."""
        homework = frappe.get_doc("Homework", self.homework)
        homework.update_submission_counts()
        homework.save(ignore_permissions=True)
