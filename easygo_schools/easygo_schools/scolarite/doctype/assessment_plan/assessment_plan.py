"""Assessment Plan DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, add_days


class AssessmentPlan(Document):
    """Assessment Plan management."""
    
    def validate(self):
        """Validate assessment plan data."""
        self.validate_marks()
        self.validate_dates()
        self.validate_teacher_assignment()
        self.set_defaults()
    
    def validate_marks(self):
        """Validate marks configuration."""
        if self.passing_marks and self.total_marks:
            if self.passing_marks > self.total_marks:
                frappe.throw(_("Passing marks cannot be greater than total marks"))
            
            if self.passing_marks < 0 or self.total_marks < 0:
                frappe.throw(_("Marks cannot be negative"))
    
    def validate_dates(self):
        """Validate assessment dates."""
        if self.planned_date:
            if getdate(self.planned_date) < getdate():
                frappe.throw(_("Planned date cannot be in the past"))
    
    def validate_teacher_assignment(self):
        """Validate teacher assignment to subject and class."""
        if self.teacher and self.subject and self.school_class:
            # Check if teacher is assigned to this subject and class
            assignment = frappe.db.exists("Class Subject Teacher", {
                "teacher": self.teacher,
                "subject": self.subject,
                "school_class": self.school_class
            })
            
            if not assignment:
                frappe.msgprint(_("Warning: Teacher {0} is not assigned to {1} for {2}").format(
                    self.teacher, self.subject, self.school_class
                ), alert=True)
    
    def set_defaults(self):
        """Set default values."""
        if not self.status:
            self.status = "Draft"
        
        if not self.duration_minutes and self.assessment_type:
            # Set default duration based on assessment type
            default_durations = {
                "Quiz": 30,
                "Test": 60,
                "Exam": 120,
                "Project": 0,  # No time limit
                "Presentation": 15,
                "Practical": 90,
                "Oral": 20,
                "Assignment": 0
            }
            self.duration_minutes = default_durations.get(self.assessment_type, 60)
    
    def on_update(self):
        """Actions after update."""
        if self.has_value_changed("status") and self.status == "Scheduled":
            self.notify_stakeholders()
            self.create_calendar_event()
    
    def notify_stakeholders(self):
        """Notify teacher and students about scheduled assessment."""
        # Notify teacher
        if self.teacher:
            frappe.sendmail(
                recipients=[self.teacher],
                subject=_("Assessment Scheduled: {0}").format(self.assessment_plan_name),
                message=self.get_teacher_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
        
        # Notify students
        students = frappe.get_all("Student", 
            filters={"school_class": self.school_class, "is_active": 1},
            fields=["name", "student_name", "user_id"]
        )
        
        student_emails = [s.user_id for s in students if s.user_id]
        
        if student_emails:
            frappe.sendmail(
                recipients=student_emails,
                subject=_("Assessment Scheduled: {0} - {1}").format(self.subject, self.assessment_type),
                message=self.get_student_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def create_calendar_event(self):
        """Create calendar event for assessment."""
        if self.planned_date and self.teacher:
            event_doc = frappe.get_doc({
                "doctype": "Event",
                "subject": _("Assessment: {0}").format(self.assessment_plan_name),
                "starts_on": self.planned_date,
                "event_type": "Private",
                "ref_type": self.doctype,
                "ref_name": self.name,
                "description": self.get_event_description()
            })
            
            # Add teacher as participant
            event_doc.append("event_participants", {
                "reference_doctype": "User",
                "reference_docname": self.teacher
            })
            
            event_doc.insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def schedule_assessment(self):
        """Schedule the assessment."""
        if self.status != "Draft":
            frappe.throw(_("Only draft assessments can be scheduled"))
        
        if not self.planned_date:
            frappe.throw(_("Planned date is required to schedule assessment"))
        
        self.status = "Scheduled"
        self.save()
        
        frappe.msgprint(_("Assessment scheduled successfully"))
        return self
    
    @frappe.whitelist()
    def conduct_assessment(self):
        """Mark assessment as conducted."""
        if self.status != "Scheduled":
            frappe.throw(_("Only scheduled assessments can be conducted"))
        
        self.status = "Conducted"
        self.save()
        
        # Create assessment record for grading
        self.create_assessment_record()
        
        frappe.msgprint(_("Assessment marked as conducted"))
        return self
    
    def create_assessment_record(self):
        """Create assessment record for student grading."""
        assessment_doc = frappe.get_doc({
            "doctype": "Assessment",
            "assessment_plan": self.name,
            "assessment_name": self.assessment_plan_name,
            "academic_year": self.academic_year,
            "academic_term": self.academic_term,
            "school_class": self.school_class,
            "subject": self.subject,
            "teacher": self.teacher,
            "assessment_date": self.planned_date,
            "total_marks": self.total_marks,
            "passing_marks": self.passing_marks,
            "grading_scale": self.get_grading_scale()
        })
        
        # Add students to assessment
        students = frappe.get_all("Student", 
            filters={"school_class": self.school_class, "is_active": 1},
            fields=["name", "student_name"]
        )
        
        for student in students:
            assessment_doc.append("students", {
                "student": student.name,
                "student_name": student.student_name
            })
        
        assessment_doc.insert(ignore_permissions=True)
        return assessment_doc.name
    
    def get_grading_scale(self):
        """Get appropriate grading scale."""
        # Try to get grading scale for the class or subject
        grading_scale = frappe.db.get_value("School Class", self.school_class, "grading_scale")
        
        if not grading_scale:
            grading_scale = frappe.db.get_value("Subject", self.subject, "grading_scale")
        
        if not grading_scale:
            # Get default grading scale
            grading_scale = frappe.db.get_single_value("School Settings", "default_grading_scale")
        
        return grading_scale
    
    def get_teacher_notification_message(self):
        """Get notification message for teacher."""
        return _("""
        Assessment Scheduled
        
        Assessment: {assessment_name}
        Class: {school_class}
        Subject: {subject}
        Type: {assessment_type}
        Date: {planned_date}
        Duration: {duration} minutes
        Total Marks: {total_marks}
        
        Syllabus Coverage:
        {syllabus_coverage}
        
        Learning Objectives:
        {learning_objectives}
        
        Please ensure all preparations are completed before the assessment date.
        """).format(
            assessment_name=self.assessment_plan_name,
            school_class=self.school_class,
            subject=self.subject,
            assessment_type=self.assessment_type,
            planned_date=self.planned_date,
            duration=self.duration_minutes or "Not specified",
            total_marks=self.total_marks,
            syllabus_coverage=self.syllabus_coverage or "Not specified",
            learning_objectives=self.learning_objectives or "Not specified"
        )
    
    def get_student_notification_message(self):
        """Get notification message for students."""
        return _("""
        Assessment Notification
        
        Subject: {subject}
        Assessment Type: {assessment_type}
        Date: {planned_date}
        Duration: {duration} minutes
        Total Marks: {total_marks}
        Passing Marks: {passing_marks}
        
        Syllabus Coverage:
        {syllabus_coverage}
        
        Instructions:
        {instructions}
        
        Materials Required:
        {materials_required}
        
        Please prepare accordingly and arrive on time.
        """).format(
            subject=self.subject,
            assessment_type=self.assessment_type,
            planned_date=self.planned_date,
            duration=self.duration_minutes or "Not specified",
            total_marks=self.total_marks,
            passing_marks=self.passing_marks,
            syllabus_coverage=self.syllabus_coverage or "As per curriculum",
            instructions=self.instructions or "Follow standard assessment guidelines",
            materials_required=self.materials_required or "Standard writing materials"
        )
    
    def get_event_description(self):
        """Get description for calendar event."""
        return _("""
        Assessment: {assessment_name}
        Class: {school_class}
        Subject: {subject}
        Type: {assessment_type}
        Total Marks: {total_marks}
        Duration: {duration} minutes
        """).format(
            assessment_name=self.assessment_plan_name,
            school_class=self.school_class,
            subject=self.subject,
            assessment_type=self.assessment_type,
            total_marks=self.total_marks,
            duration=self.duration_minutes or "Not specified"
        )
