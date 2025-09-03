"""Student Follow-up DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, add_days


class StudentFollowUp(Document):
    """Student Follow-up management."""
    
    def validate(self):
        """Validate student follow-up data."""
        self.validate_dates()
        self.validate_student_class()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate follow-up dates."""
        if self.next_follow_up_date and self.follow_up_date:
            if getdate(self.next_follow_up_date) <= getdate(self.follow_up_date):
                frappe.throw(_("Next follow-up date must be after current follow-up date"))
        
        if self.notification_date and self.follow_up_date:
            if getdate(self.notification_date) < getdate(self.follow_up_date):
                frappe.throw(_("Notification date cannot be before follow-up date"))
    
    def validate_student_class(self):
        """Validate student and class consistency."""
        if self.student:
            student_doc = frappe.get_doc("Student", self.student)
            if self.school_class and self.school_class != student_doc.school_class:
                frappe.throw(_("Selected class does not match student's current class"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.priority:
            self.priority = "Medium"
        
        if not self.status:
            self.status = "Open"
        
        # Auto-set next follow-up date based on priority
        if not self.next_follow_up_date and self.follow_up_date:
            days_to_add = {
                "Urgent": 1,
                "High": 3,
                "Medium": 7,
                "Low": 14
            }
            self.next_follow_up_date = add_days(self.follow_up_date, days_to_add.get(self.priority, 7))
    
    def on_update(self):
        """Actions after update."""
        self.notify_assigned_user()
        self.create_calendar_event()
    
    def notify_assigned_user(self):
        """Notify assigned user of follow-up."""
        if self.assigned_to and self.has_value_changed("assigned_to"):
            frappe.sendmail(
                recipients=[self.assigned_to],
                subject=_("Student Follow-up Assigned: {0}").format(self.student_name),
                message=_("You have been assigned a student follow-up for {0}. Priority: {1}").format(
                    self.student_name, self.priority
                ),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def create_calendar_event(self):
        """Create calendar event for next follow-up."""
        if self.next_follow_up_date and self.assigned_to:
            # Check if event already exists
            existing_event = frappe.db.exists("Event", {
                "ref_type": self.doctype,
                "ref_name": self.name
            })
            
            if not existing_event:
                event_doc = frappe.get_doc({
                    "doctype": "Event",
                    "subject": _("Follow-up: {0}").format(self.student_name),
                    "starts_on": self.next_follow_up_date,
                    "event_type": "Private",
                    "ref_type": self.doctype,
                    "ref_name": self.name,
                    "description": self.recommendations or self.description
                })
                
                # Add assigned user as participant
                event_doc.append("event_participants", {
                    "reference_doctype": "User",
                    "reference_docname": self.assigned_to
                })
                
                event_doc.insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def mark_resolved(self):
        """Mark follow-up as resolved."""
        self.status = "Resolved"
        self.save()
        
        frappe.msgprint(_("Follow-up marked as resolved"))
        return self
    
    @frappe.whitelist()
    def create_next_follow_up(self):
        """Create next follow-up based on recommendations."""
        if not self.next_follow_up_date:
            frappe.throw(_("Next follow-up date is required"))
        
        next_follow_up = frappe.get_doc({
            "doctype": "Student Follow-up",
            "student": self.student,
            "follow_up_date": self.next_follow_up_date,
            "follow_up_type": self.follow_up_type,
            "subject": self.subject,
            "description": self.recommendations or _("Follow-up from {0}").format(self.name),
            "assigned_to": self.assigned_to,
            "priority": self.priority
        })
        
        next_follow_up.insert()
        
        # Update current follow-up
        self.status = "Closed"
        self.save()
        
        frappe.msgprint(_("Next follow-up created: {0}").format(next_follow_up.name))
        return next_follow_up.name
    
    @frappe.whitelist()
    def notify_parent(self):
        """Send notification to parent."""
        if not self.student:
            frappe.throw(_("Student is required"))
        
        # Get parent contact details
        parent_contacts = frappe.get_all("Guardian", 
            filters={"student": self.student},
            fields=["guardian_name", "email_address", "mobile_number"]
        )
        
        if not parent_contacts:
            frappe.throw(_("No parent/guardian contact found for student"))
        
        for parent in parent_contacts:
            if parent.email_address:
                frappe.sendmail(
                    recipients=[parent.email_address],
                    subject=_("Student Follow-up: {0}").format(self.student_name),
                    message=self.get_parent_notification_message(parent.guardian_name),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        # Update notification status
        self.parent_notified = 1
        self.notification_date = getdate()
        self.save()
        
        frappe.msgprint(_("Parent notification sent successfully"))
    
    def get_parent_notification_message(self, parent_name):
        """Get formatted message for parent notification."""
        return _("""
        Dear {parent_name},
        
        This is to inform you about a follow-up regarding your child {student_name}.
        
        Follow-up Type: {follow_up_type}
        Date: {follow_up_date}
        
        Details:
        {description}
        
        {action_section}
        
        {recommendations_section}
        
        If you have any questions or concerns, please contact the school.
        
        Best regards,
        School Administration
        """).format(
            parent_name=parent_name,
            student_name=self.student_name,
            follow_up_type=self.follow_up_type,
            follow_up_date=self.follow_up_date,
            description=self.description,
            action_section=_("Action Taken:\n{0}").format(self.action_taken) if self.action_taken else "",
            recommendations_section=_("Recommendations:\n{0}").format(self.recommendations) if self.recommendations else ""
        )
    
    def get_student_performance_summary(self):
        """Get student performance summary for context."""
        # Get recent grades
        recent_grades = frappe.get_all("Grade",
            filters={
                "student": self.student,
                "creation": [">=", add_days(getdate(), -30)]
            },
            fields=["subject", "grade", "percentage", "assessment_date"],
            order_by="assessment_date desc",
            limit=5
        )
        
        # Get attendance summary
        attendance_summary = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_days,
                COUNT(CASE WHEN status = 'Present' THEN 1 END) as present_days,
                COUNT(CASE WHEN status = 'Absent' THEN 1 END) as absent_days
            FROM `tabStudent Attendance`
            WHERE student = %s 
            AND attendance_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        """, [self.student], as_dict=True)
        
        return {
            "recent_grades": recent_grades,
            "attendance_summary": attendance_summary[0] if attendance_summary else {}
        }
