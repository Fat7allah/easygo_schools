"""Assessment doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class Assessment(Document):
    """Assessment doctype controller with business rules."""
    
    def validate(self):
        """Validate assessment data."""
        self.validate_assessment_date()
        self.validate_instructor_assignment()
        self.validate_weightage()
        self.update_student_counts()
    
    def validate_assessment_date(self):
        """Validate assessment date."""
        if self.assessment_date and getdate(self.assessment_date) < getdate(today()):
            if self.status == "Scheduled":
                frappe.msgprint(_("Assessment date is in the past. Consider updating the status."), alert=True)
    
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
    
    def validate_weightage(self):
        """Validate weightage percentage."""
        if self.weightage and (self.weightage < 0 or self.weightage > 100):
            frappe.throw(_("Weightage must be between 0 and 100 percent"))
    
    def update_student_counts(self):
        """Update student counts."""
        if not self.is_new():
            self.total_students = frappe.db.count("Student", {
                "school_class": self.school_class,
                "status": "Active"
            })
            
            self.graded_students = frappe.db.count("Grade", {
                "assessment": self.name
            })
    
    def after_insert(self):
        """Actions after assessment creation."""
        if self.is_published:
            self.notify_students()
    
    def on_update(self):
        """Actions on assessment update."""
        # Notify students if assessment is published for the first time
        if self.has_value_changed("is_published") and self.is_published:
            self.notify_students()
    
    def notify_students(self):
        """Send notification to students about new assessment."""
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
            
            subject = _("Assessment Scheduled - {0}").format(self.assessment_name)
            message = _("""
            <p>Dear Student/Parent,</p>
            
            <p>A new assessment has been scheduled:</p>
            
            <ul>
                <li><strong>Assessment:</strong> {0}</li>
                <li><strong>Type:</strong> {1}</li>
                <li><strong>Subject:</strong> {2}</li>
                <li><strong>Date:</strong> {3}</li>
                <li><strong>Duration:</strong> {4} minutes</li>
                <li><strong>Maximum Score:</strong> {5}</li>
                <li><strong>Class:</strong> {6}</li>
            </ul>
            
            {7}
            
            {8}
            
            {9}
            
            <p>Please prepare accordingly and ensure you are present on the assessment date.</p>
            
            <p>Best regards,<br>
            {10} Administration</p>
            """).format(
                self.assessment_name,
                self.assessment_type,
                self.subject,
                frappe.utils.formatdate(self.assessment_date),
                self.duration_minutes or "Not specified",
                self.max_score,
                self.school_class,
                f"<p><strong>Description:</strong> {self.description}</p>" if self.description else "",
                f"<p><strong>Instructions:</strong> {self.instructions}</p>" if self.instructions else "",
                f"<p><strong>Topics Covered:</strong> {self.topics_covered}</p>" if self.topics_covered else "",
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
                    "reference_doctype": "Assessment",
                    "reference_name": self.name,
                    "communication_type": "Email",
                    "subject": subject,
                    "status": "Sent"
                }).insert(ignore_permissions=True)
        
        except Exception as e:
            frappe.log_error(f"Failed to send assessment notification for {self.name}: {str(e)}")
    
    def get_grading_summary(self):
        """Get grading summary for this assessment."""
        grades = frappe.get_all("Grade",
            filters={"assessment": self.name},
            fields=["grade", "max_grade", "percentage", "letter_grade"]
        )
        
        if not grades:
            return {
                "total_graded": 0,
                "average_score": 0,
                "average_percentage": 0,
                "highest_score": 0,
                "lowest_score": 0,
                "pass_rate": 0
            }
        
        scores = [g.grade for g in grades]
        percentages = [g.percentage for g in grades if g.percentage is not None]
        
        # Calculate pass rate (assuming 60% is passing)
        passing_grades = [p for p in percentages if p >= 60]
        pass_rate = (len(passing_grades) / len(percentages)) * 100 if percentages else 0
        
        return {
            "total_graded": len(grades),
            "average_score": sum(scores) / len(scores) if scores else 0,
            "average_percentage": sum(percentages) / len(percentages) if percentages else 0,
            "highest_score": max(scores) if scores else 0,
            "lowest_score": min(scores) if scores else 0,
            "pass_rate": pass_rate
        }
