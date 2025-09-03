"""Disciplinary Action doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate, date_diff


class DisciplinaryAction(Document):
    """Disciplinary Action doctype controller."""
    
    def validate(self):
        """Validate disciplinary action data."""
        self.validate_dates()
        self.calculate_duration()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate incident and action dates."""
        if self.incident_date and getdate(self.incident_date) > getdate():
            frappe.throw(_("Incident date cannot be in the future"))
        
        if self.start_date and self.end_date:
            if getdate(self.start_date) > getdate(self.end_date):
                frappe.throw(_("Action start date cannot be after end date"))
        
        if self.follow_up_date and self.incident_date:
            if getdate(self.follow_up_date) <= getdate(self.incident_date):
                frappe.throw(_("Follow-up date must be after incident date"))
    
    def calculate_duration(self):
        """Calculate action duration in days."""
        if self.start_date and self.end_date:
            self.duration_days = date_diff(self.end_date, self.start_date) + 1
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
        
        if not self.reported_by:
            self.reported_by = frappe.session.user
        
        # Fetch student details
        if self.student and not self.student_name:
            self.student_name = frappe.db.get_value("Student", self.student, "student_name")
        
        # Set current academic year if not specified
        if not self.academic_year:
            current_year = frappe.db.get_single_value("School Settings", "current_academic_year")
            if current_year:
                self.academic_year = current_year
    
    def on_update(self):
        """Actions after update."""
        if self.parent_notified and not self.parent_notification_date:
            self.parent_notification_date = now()
            self.save()
        
        if self.status == "In Progress" and not self.parent_notified:
            self.send_parent_notification()
    
    def send_parent_notification(self):
        """Send notification to parents about disciplinary action."""
        try:
            # Get guardian emails
            guardian_emails = frappe.db.sql("""
                SELECT g.email_address, g.first_name, g.last_name
                FROM `tabGuardian` g
                INNER JOIN `tabStudent Guardian` sg ON g.name = sg.guardian
                WHERE sg.student = %s AND g.email_address IS NOT NULL
            """, (self.student,), as_dict=True)
            
            if guardian_emails:
                for guardian in guardian_emails:
                    frappe.sendmail(
                        recipients=[guardian.email_address],
                        subject=_("Disciplinary Action Notice - {0}").format(self.student_name),
                        message=self.get_notification_message(guardian),
                        reference_doctype=self.doctype,
                        reference_name=self.name
                    )
                
                self.parent_notified = 1
                self.parent_notification_date = now()
                self.save()
        
        except Exception as e:
            frappe.log_error(f"Failed to send parent notification: {str(e)}")
    
    def get_notification_message(self, guardian):
        """Get notification message for parents."""
        message = _("""Dear {0},

We are writing to inform you about a disciplinary incident involving your child, {1}.

Incident Details:
- Date: {2}
- Type: {3}
- Severity: {4}
- Location: {5}

Description:
{6}

Action Taken:
- Action Type: {7}
- Description: {8}

{9}

If you have any questions or would like to discuss this matter, please contact the school administration.

Best regards,
School Administration""").format(
            f"{guardian.first_name} {guardian.last_name}",
            self.student_name,
            self.incident_date,
            self.incident_type,
            self.severity_level,
            self.location or "N/A",
            self.incident_description,
            self.action_type or "To be determined",
            self.action_description or "Details to follow",
            self.get_meeting_notice()
        )
        
        return message
    
    def get_meeting_notice(self):
        """Get parent meeting notice if required."""
        if self.parent_meeting_required:
            return _("\nIMPORTANT: A parent meeting is required. Please contact the school to schedule an appointment.")
        return ""
    
    @frappe.whitelist()
    def resolve_action(self, resolution_notes=None):
        """Resolve the disciplinary action."""
        if self.status == "Resolved":
            frappe.throw(_("Action is already resolved"))
        
        self.status = "Resolved"
        self.resolved_date = getdate()
        self.resolved_by = frappe.session.user
        
        if resolution_notes:
            self.resolution_notes = resolution_notes
        
        self.save()
        
        # Send resolution notification
        self.send_resolution_notification()
        
        return True
    
    def send_resolution_notification(self):
        """Send resolution notification to parents."""
        try:
            guardian_emails = frappe.db.sql("""
                SELECT g.email_address, g.first_name, g.last_name
                FROM `tabGuardian` g
                INNER JOIN `tabStudent Guardian` sg ON g.name = sg.guardian
                WHERE sg.student = %s AND g.email_address IS NOT NULL
            """, (self.student,), as_dict=True)
            
            if guardian_emails:
                for guardian in guardian_emails:
                    frappe.sendmail(
                        recipients=[guardian.email_address],
                        subject=_("Disciplinary Action Resolved - {0}").format(self.student_name),
                        message=_("""Dear {0},

We are pleased to inform you that the disciplinary action for {1} has been resolved.

Resolution Details:
- Resolved Date: {2}
- Resolution Notes: {3}

Thank you for your cooperation in addressing this matter.

Best regards,
School Administration""").format(
                            f"{guardian.first_name} {guardian.last_name}",
                            self.student_name,
                            self.resolved_date,
                            self.resolution_notes or "No additional notes"
                        ),
                        reference_doctype=self.doctype,
                        reference_name=self.name
                    )
        
        except Exception as e:
            frappe.log_error(f"Failed to send resolution notification: {str(e)}")
    
    @frappe.whitelist()
    def schedule_follow_up(self, follow_up_date, notes=None):
        """Schedule follow-up for this disciplinary action."""
        self.follow_up_required = 1
        self.follow_up_date = follow_up_date
        
        if notes:
            self.follow_up_notes = notes
        
        self.save()
        
        # Create follow-up reminder
        self.create_follow_up_reminder()
        
        return True
    
    def create_follow_up_reminder(self):
        """Create follow-up reminder task."""
        try:
            # This would integrate with a task/reminder system
            # For now, just log the follow-up requirement
            frappe.log_error(f"Follow-up required for disciplinary action {self.name} on {self.follow_up_date}")
        
        except Exception as e:
            frappe.log_error(f"Failed to create follow-up reminder: {str(e)}")
    
    @frappe.whitelist()
    def get_student_disciplinary_history(self):
        """Get disciplinary history for this student."""
        history = frappe.get_list("Disciplinary Action",
            filters={"student": self.student},
            fields=[
                "name", "incident_date", "incident_type", "severity_level",
                "action_type", "status", "resolved_date"
            ],
            order_by="incident_date desc"
        )
        
        return history
    
    @frappe.whitelist()
    def get_behavior_trend(self):
        """Get behavior trend analysis for this student."""
        # Get incidents in the last 12 months
        from dateutil.relativedelta import relativedelta
        start_date = getdate() - relativedelta(months=12)
        
        incidents = frappe.db.sql("""
            SELECT 
                incident_type,
                severity_level,
                incident_date,
                status
            FROM `tabDisciplinary Action`
            WHERE student = %s 
                AND incident_date >= %s
            ORDER BY incident_date
        """, (self.student, start_date), as_dict=True)
        
        # Analyze trends
        trend_analysis = {
            "total_incidents": len(incidents),
            "resolved_incidents": len([i for i in incidents if i.status == "Resolved"]),
            "severity_breakdown": {},
            "type_breakdown": {},
            "monthly_trend": {}
        }
        
        for incident in incidents:
            # Severity breakdown
            severity = incident.severity_level
            trend_analysis["severity_breakdown"][severity] = trend_analysis["severity_breakdown"].get(severity, 0) + 1
            
            # Type breakdown
            incident_type = incident.incident_type
            trend_analysis["type_breakdown"][incident_type] = trend_analysis["type_breakdown"].get(incident_type, 0) + 1
            
            # Monthly trend
            month_key = incident.incident_date.strftime("%Y-%m")
            trend_analysis["monthly_trend"][month_key] = trend_analysis["monthly_trend"].get(month_key, 0) + 1
        
        return trend_analysis
    
    @frappe.whitelist()
    def create_improvement_plan(self, plan_details):
        """Create behavior improvement plan."""
        if isinstance(plan_details, str):
            import json
            plan_details = json.loads(plan_details)
        
        self.improvement_plan = plan_details.get("plan_text")
        self.behavioral_notes = (self.behavioral_notes or "") + f"\nImprovement Plan Created: {now()}"
        
        # Set follow-up if specified
        if plan_details.get("follow_up_weeks"):
            from dateutil.relativedelta import relativedelta
            follow_up_date = getdate() + relativedelta(weeks=int(plan_details["follow_up_weeks"]))
            self.follow_up_required = 1
            self.follow_up_date = follow_up_date
        
        self.save()
        
        # Notify parents about improvement plan
        self.send_improvement_plan_notification()
        
        return True
    
    def send_improvement_plan_notification(self):
        """Send improvement plan notification to parents."""
        try:
            guardian_emails = frappe.db.sql("""
                SELECT g.email_address, g.first_name, g.last_name
                FROM `tabGuardian` g
                INNER JOIN `tabStudent Guardian` sg ON g.name = sg.guardian
                WHERE sg.student = %s AND g.email_address IS NOT NULL
            """, (self.student,), as_dict=True)
            
            if guardian_emails:
                for guardian in guardian_emails:
                    frappe.sendmail(
                        recipients=[guardian.email_address],
                        subject=_("Behavior Improvement Plan - {0}").format(self.student_name),
                        message=_("""Dear {0},

We have developed a behavior improvement plan for {1} to help address recent disciplinary concerns.

Improvement Plan:
{2}

{3}

We look forward to working together to support {1}'s positive behavior development.

Best regards,
School Administration""").format(
                            f"{guardian.first_name} {guardian.last_name}",
                            self.student_name,
                            self.improvement_plan,
                            f"Follow-up scheduled for: {self.follow_up_date}" if self.follow_up_date else ""
                        ),
                        reference_doctype=self.doctype,
                        reference_name=self.name
                    )
        
        except Exception as e:
            frappe.log_error(f"Failed to send improvement plan notification: {str(e)}")
    
    @frappe.whitelist()
    def appeal_action(self, appeal_reason):
        """Appeal the disciplinary action."""
        if self.status == "Appealed":
            frappe.throw(_("Action is already under appeal"))
        
        self.status = "Appealed"
        self.behavioral_notes = (self.behavioral_notes or "") + f"\nAppeal Filed: {now()}\nReason: {appeal_reason}"
        
        self.save()
        
        # Notify administration about appeal
        self.send_appeal_notification(appeal_reason)
        
        return True
    
    def send_appeal_notification(self, appeal_reason):
        """Send appeal notification to administration."""
        try:
            # Get education manager emails
            admin_emails = frappe.get_list("User",
                filters={"role_profile_name": "Education Manager"},
                fields=["email"]
            )
            
            recipients = [admin.email for admin in admin_emails if admin.email]
            
            if recipients:
                frappe.sendmail(
                    recipients=recipients,
                    subject=_("Disciplinary Action Appeal - {0}").format(self.student_name),
                    message=_("""A disciplinary action has been appealed.

Student: {0}
Action: {1}
Original Date: {2}
Appeal Reason: {3}

Please review the appeal and take appropriate action.

Reference: {4}""").format(
                        self.student_name,
                        self.name,
                        self.incident_date,
                        appeal_reason,
                        self.name
                    ),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        except Exception as e:
            frappe.log_error(f"Failed to send appeal notification: {str(e)}")
