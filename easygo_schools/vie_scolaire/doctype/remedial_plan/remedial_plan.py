"""Remedial Plan DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, flt, cint, add_days, date_diff


class RemedialPlan(Document):
    """Remedial Plan management for student support."""
    
    def validate(self):
        """Validate remedial plan data."""
        self.validate_dates()
        self.validate_team_assignment()
        self.calculate_duration()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate plan dates."""
        if self.start_date and self.target_completion_date:
            if self.start_date > self.target_completion_date:
                frappe.throw(_("Start date cannot be after target completion date"))
        
        if self.actual_completion_date and self.start_date:
            if self.actual_completion_date < self.start_date:
                frappe.throw(_("Actual completion date cannot be before start date"))
    
    def validate_team_assignment(self):
        """Validate team member assignments."""
        if not self.assigned_counselor:
            # Auto-assign based on student's counselor or default
            student_counselor = frappe.db.get_value("Student Counselor Assignment", 
                {"student": self.student, "status": "Active"}, "counselor")
            
            if student_counselor:
                self.assigned_counselor = student_counselor
            else:
                # Get default counselor from settings
                default_counselor = frappe.db.get_single_value("School Settings", "default_counselor")
                if default_counselor:
                    self.assigned_counselor = default_counselor
        
        # Set class teacher if not provided
        if not self.class_teacher and self.student:
            student_group = frappe.db.get_value("Student", self.student, "student_group")
            if student_group:
                instructor = frappe.db.get_value("Student Group", student_group, "instructor")
                if instructor:
                    self.class_teacher = instructor
    
    def calculate_duration(self):
        """Calculate plan duration in weeks."""
        if self.start_date and self.target_completion_date:
            days = date_diff(self.target_completion_date, self.start_date)
            self.duration_weeks = max(1, round(days / 7))
    
    def set_defaults(self):
        """Set default values."""
        if not self.identification_date:
            self.identification_date = getdate()
        
        if not self.identified_by:
            self.identified_by = frappe.session.user
        
        if not self.review_frequency:
            self.review_frequency = "Weekly"
        
        if not self.next_review_date and self.start_date:
            self.set_next_review_date()
    
    def set_next_review_date(self):
        """Set next review date based on frequency."""
        if not self.start_date:
            return
        
        days_to_add = {
            "Daily": 1,
            "Weekly": 7,
            "Bi-weekly": 14,
            "Monthly": 30
        }
        
        days = days_to_add.get(self.review_frequency, 7)
        self.next_review_date = add_days(self.start_date, days)
    
    def on_submit(self):
        """Actions on submit."""
        self.status = "Active"
        self.send_plan_notifications()
        self.create_intervention_sessions()
        self.schedule_reviews()
    
    def send_plan_notifications(self):
        """Send notifications to all stakeholders."""
        # Notify assigned counselor
        if self.assigned_counselor:
            self.send_counselor_notification()
        
        # Notify class teacher
        if self.class_teacher:
            self.send_teacher_notification()
        
        # Notify parent/guardian
        if self.parent_guardian:
            self.send_guardian_notification()
        
        # Notify student if appropriate
        self.send_student_notification()
    
    def send_counselor_notification(self):
        """Send notification to assigned counselor."""
        counselor = frappe.get_doc("Employee", self.assigned_counselor)
        
        if counselor.user_id:
            frappe.sendmail(
                recipients=[counselor.user_id],
                subject=_("New Remedial Plan Assignment - {0}").format(self.student_name),
                message=self.get_counselor_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_counselor_notification_message(self):
        """Get counselor notification message."""
        return _("""
        You have been assigned a new remedial plan:
        
        Plan: {plan_name}
        Student: {student_name}
        Plan Type: {plan_type}
        Priority: {priority}
        
        Plan Details:
        {description}
        
        Objectives:
        {objectives}
        
        Timeline:
        - Start Date: {start_date}
        - Target Completion: {target_completion_date}
        - Duration: {duration_weeks} weeks
        
        Review Frequency: {review_frequency}
        Next Review: {next_review_date}
        
        Please review the plan and begin implementation.
        
        Academic Support Team
        """).format(
            plan_name=self.name,
            student_name=self.student_name,
            plan_type=self.plan_type,
            priority=self.priority,
            description=self.description or "Not specified",
            objectives=self.objectives or "Not specified",
            start_date=frappe.format(self.start_date, "Date"),
            target_completion_date=frappe.format(self.target_completion_date, "Date"),
            duration_weeks=self.duration_weeks,
            review_frequency=self.review_frequency,
            next_review_date=frappe.format(self.next_review_date, "Date")
        )
    
    def send_teacher_notification(self):
        """Send notification to class teacher."""
        teacher = frappe.get_doc("Employee", self.class_teacher)
        
        if teacher.user_id:
            frappe.sendmail(
                recipients=[teacher.user_id],
                subject=_("Student Remedial Plan - {0}").format(self.student_name),
                message=self.get_teacher_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_teacher_notification_message(self):
        """Get teacher notification message."""
        return _("""
        A remedial plan has been created for your student:
        
        Student: {student_name}
        Plan Type: {plan_type}
        Priority: {priority}
        Assigned Counselor: {counselor_name}
        
        Plan Overview:
        {description}
        
        Your Role:
        - Monitor student progress in class
        - Provide feedback to the counselor
        - Implement classroom accommodations as needed
        - Report any concerns or improvements
        
        Please coordinate with the assigned counselor for effective implementation.
        
        Academic Support Team
        """).format(
            student_name=self.student_name,
            plan_type=self.plan_type,
            priority=self.priority,
            counselor_name=frappe.get_value("Employee", self.assigned_counselor, "employee_name") if self.assigned_counselor else "Not assigned",
            description=self.description or "See full plan for details"
        )
    
    def send_guardian_notification(self):
        """Send notification to parent/guardian."""
        if self.parent_guardian:
            guardian = frappe.get_doc("Guardian", self.parent_guardian)
            
            if guardian.email_address:
                frappe.sendmail(
                    recipients=[guardian.email_address],
                    subject=_("Student Support Plan - {0}").format(self.student_name),
                    message=self.get_guardian_notification_message(),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
    
    def get_guardian_notification_message(self):
        """Get guardian notification message."""
        return _("""
        Dear Parent/Guardian,
        
        We have developed a support plan for {student_name} to help with their academic progress.
        
        Plan Details:
        - Type: {plan_type}
        - Duration: {duration_weeks} weeks
        - Start Date: {start_date}
        
        Objectives:
        {objectives}
        
        Support Team:
        - Counselor: {counselor_name}
        - Class Teacher: {teacher_name}
        
        Your involvement is crucial for the success of this plan. We will keep you updated on progress and may request your support with home-based activities.
        
        {consent_required}
        
        If you have any questions or concerns, please contact the assigned counselor.
        
        Best regards,
        Academic Support Team
        """).format(
            student_name=self.student_name,
            plan_type=self.plan_type,
            duration_weeks=self.duration_weeks,
            start_date=frappe.format(self.start_date, "Date"),
            objectives=self.objectives or "Detailed objectives will be shared separately",
            counselor_name=frappe.get_value("Employee", self.assigned_counselor, "employee_name") if self.assigned_counselor else "TBA",
            teacher_name=frappe.get_value("Employee", self.class_teacher, "employee_name") if self.class_teacher else "TBA",
            consent_required="Please provide your consent for this plan if you haven't already." if not self.guardian_consent else ""
        )
    
    def send_student_notification(self):
        """Send age-appropriate notification to student."""
        student = frappe.get_doc("Student", self.student)
        
        if student.student_email_id:
            frappe.sendmail(
                recipients=[student.student_email_id],
                subject=_("Your Personal Learning Plan"),
                message=self.get_student_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_student_notification_message(self):
        """Get student notification message."""
        return _("""
        Hi {student_name},
        
        We've created a special learning plan just for you to help you succeed!
        
        Your Support Team:
        - Counselor: {counselor_name}
        - Teacher: {teacher_name}
        
        What this means:
        - You'll get extra support in areas where you need it
        - We'll work together to reach your goals
        - You'll have regular check-ins to see how you're doing
        
        Remember, asking for help is a sign of strength, and we're here to support you every step of the way!
        
        If you have any questions, feel free to talk to your counselor or teacher.
        
        You've got this!
        Your Support Team
        """).format(
            student_name=self.student_name,
            counselor_name=frappe.get_value("Employee", self.assigned_counselor, "employee_name") if self.assigned_counselor else "Your counselor",
            teacher_name=frappe.get_value("Employee", self.class_teacher, "employee_name") if self.class_teacher else "Your teacher"
        )
    
    def create_intervention_sessions(self):
        """Create intervention sessions based on plan interventions."""
        for intervention in self.interventions:
            if intervention.create_session:
                session = frappe.get_doc({
                    "doctype": "Intervention Session",
                    "student": self.student,
                    "remedial_plan": self.name,
                    "intervention_type": intervention.intervention_type,
                    "session_description": intervention.description,
                    "assigned_counselor": self.assigned_counselor,
                    "scheduled_date": intervention.target_date,
                    "duration_minutes": intervention.duration_minutes or 60,
                    "status": "Scheduled"
                })
                
                session.insert(ignore_permissions=True)
    
    def schedule_reviews(self):
        """Schedule regular review meetings."""
        if self.review_frequency and self.next_review_date:
            # Create initial review task
            review_task = frappe.get_doc({
                "doctype": "ToDo",
                "description": f"Review remedial plan: {self.name} for {self.student_name}",
                "reference_type": self.doctype,
                "reference_name": self.name,
                "assigned_by": frappe.session.user,
                "owner": self.assigned_counselor or frappe.session.user,
                "date": self.next_review_date,
                "priority": "Medium" if self.priority == "Medium" else "High"
            })
            
            review_task.insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def update_progress(self, completion_percentage, progress_notes, challenges=None):
        """Update plan progress."""
        self.completion_percentage = flt(completion_percentage)
        
        if progress_notes:
            current_notes = self.progress_notes or ""
            timestamp = now_datetime().strftime("%Y-%m-%d %H:%M")
            new_note = f"\n[{timestamp}] {progress_notes}"
            self.progress_notes = current_notes + new_note
        
        if challenges:
            self.challenges_faced = challenges
        
        # Update next review date
        self.set_next_review_date()
        
        self.save()
        
        # Send progress update notifications
        self.send_progress_notifications()
        
        # Check if plan should be completed
        if self.completion_percentage >= 100:
            self.complete_plan()
        
        frappe.msgprint(_("Progress updated successfully"))
        return self
    
    def send_progress_notifications(self):
        """Send progress update notifications."""
        # Notify stakeholders about progress
        recipients = []
        
        if self.assigned_counselor:
            counselor = frappe.get_doc("Employee", self.assigned_counselor)
            if counselor.user_id:
                recipients.append(counselor.user_id)
        
        if self.class_teacher:
            teacher = frappe.get_doc("Employee", self.class_teacher)
            if teacher.user_id:
                recipients.append(teacher.user_id)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Progress Update - {0}").format(self.name),
                message=self.get_progress_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_progress_notification_message(self):
        """Get progress notification message."""
        return _("""
        Progress Update for Remedial Plan
        
        Plan: {plan_name}
        Student: {student_name}
        
        Current Progress: {completion_percentage}%
        
        Latest Notes:
        {latest_notes}
        
        {challenges_info}
        
        Next Review: {next_review_date}
        
        Academic Support Team
        """).format(
            plan_name=self.name,
            student_name=self.student_name,
            completion_percentage=self.completion_percentage,
            latest_notes=self.get_latest_progress_note(),
            challenges_info=f"Challenges: {self.challenges_faced}" if self.challenges_faced else "",
            next_review_date=frappe.format(self.next_review_date, "Date") if self.next_review_date else "TBA"
        )
    
    def get_latest_progress_note(self):
        """Get the most recent progress note."""
        if not self.progress_notes:
            return "No notes available"
        
        notes = self.progress_notes.split('\n')
        # Return the last non-empty note
        for note in reversed(notes):
            if note.strip():
                return note.strip()
        
        return "No notes available"
    
    @frappe.whitelist()
    def complete_plan(self, effectiveness_rating=None, completion_notes=None):
        """Mark plan as completed."""
        if self.status == "Completed":
            frappe.throw(_("Plan is already completed"))
        
        self.status = "Completed"
        self.actual_completion_date = getdate()
        self.completion_percentage = 100
        
        if effectiveness_rating:
            self.effectiveness_rating = cint(effectiveness_rating)
        
        if completion_notes:
            current_notes = self.progress_notes or ""
            timestamp = now_datetime().strftime("%Y-%m-%d %H:%M")
            completion_note = f"\n[{timestamp}] COMPLETED: {completion_notes}"
            self.progress_notes = current_notes + completion_note
        
        self.save()
        
        # Send completion notifications
        self.send_completion_notifications()
        
        # Create follow-up tasks if needed
        self.create_follow_up_tasks()
        
        frappe.msgprint(_("Plan marked as completed"))
        return self
    
    def send_completion_notifications(self):
        """Send plan completion notifications."""
        # Notify all stakeholders
        recipients = []
        
        if self.assigned_counselor:
            counselor = frappe.get_doc("Employee", self.assigned_counselor)
            if counselor.user_id:
                recipients.append(counselor.user_id)
        
        if self.class_teacher:
            teacher = frappe.get_doc("Employee", self.class_teacher)
            if teacher.user_id:
                recipients.append(teacher.user_id)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Remedial Plan Completed - {0}").format(self.student_name),
                message=self.get_completion_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
        
        # Notify guardian
        if self.parent_guardian:
            guardian = frappe.get_doc("Guardian", self.parent_guardian)
            if guardian.email_address:
                frappe.sendmail(
                    recipients=[guardian.email_address],
                    subject=_("Support Plan Completed - {0}").format(self.student_name),
                    message=self.get_guardian_completion_message(),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
    
    def get_completion_notification_message(self):
        """Get completion notification message."""
        return _("""
        Remedial Plan Completed
        
        Plan: {plan_name}
        Student: {student_name}
        Completion Date: {completion_date}
        
        Plan Summary:
        - Type: {plan_type}
        - Duration: {actual_duration} weeks
        - Effectiveness Rating: {effectiveness_rating}/5
        
        Final Progress: {completion_percentage}%
        
        {final_notes}
        
        Thank you for your dedication to student success!
        
        Academic Support Team
        """).format(
            plan_name=self.name,
            student_name=self.student_name,
            completion_date=frappe.format(self.actual_completion_date, "Date"),
            plan_type=self.plan_type,
            actual_duration=date_diff(self.actual_completion_date, self.start_date) // 7 if self.actual_completion_date and self.start_date else self.duration_weeks,
            effectiveness_rating=self.effectiveness_rating or "Not rated",
            completion_percentage=self.completion_percentage,
            final_notes=self.get_latest_progress_note()
        )
    
    def get_guardian_completion_message(self):
        """Get guardian completion notification message."""
        return _("""
        Dear Parent/Guardian,
        
        We're pleased to inform you that {student_name}'s support plan has been successfully completed!
        
        Plan Summary:
        - Duration: {actual_duration} weeks
        - Final Progress: {completion_percentage}%
        - Effectiveness: {effectiveness_rating}/5
        
        Your child has made excellent progress, and we're proud of their hard work and dedication.
        
        We will continue to monitor their progress and provide support as needed.
        
        Thank you for your support throughout this process!
        
        Best regards,
        Academic Support Team
        """).format(
            student_name=self.student_name,
            actual_duration=date_diff(self.actual_completion_date, self.start_date) // 7 if self.actual_completion_date and self.start_date else self.duration_weeks,
            completion_percentage=self.completion_percentage,
            effectiveness_rating=self.effectiveness_rating or "Not rated"
        )
    
    def create_follow_up_tasks(self):
        """Create follow-up tasks after plan completion."""
        # Create follow-up monitoring task
        follow_up_date = add_days(self.actual_completion_date, 30)  # 30-day follow-up
        
        follow_up_task = frappe.get_doc({
            "doctype": "ToDo",
            "description": f"Follow-up monitoring for completed remedial plan: {self.name}",
            "reference_type": self.doctype,
            "reference_name": self.name,
            "assigned_by": frappe.session.user,
            "owner": self.assigned_counselor or frappe.session.user,
            "date": follow_up_date,
            "priority": "Low"
        })
        
        follow_up_task.insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def put_on_hold(self, hold_reason):
        """Put plan on hold."""
        if self.status in ["Completed", "Cancelled"]:
            frappe.throw(_("Cannot put {0} plan on hold").format(self.status.lower()))
        
        self.status = "On Hold"
        
        # Add hold reason to progress notes
        current_notes = self.progress_notes or ""
        timestamp = now_datetime().strftime("%Y-%m-%d %H:%M")
        hold_note = f"\n[{timestamp}] ON HOLD: {hold_reason}"
        self.progress_notes = current_notes + hold_note
        
        self.save()
        
        frappe.msgprint(_("Plan put on hold"))
        return self
    
    @frappe.whitelist()
    def resume_plan(self, resume_notes=None):
        """Resume plan from hold."""
        if self.status != "On Hold":
            frappe.throw(_("Can only resume plans that are on hold"))
        
        self.status = "Active"
        
        # Update next review date
        self.set_next_review_date()
        
        if resume_notes:
            current_notes = self.progress_notes or ""
            timestamp = now_datetime().strftime("%Y-%m-%d %H:%M")
            resume_note = f"\n[{timestamp}] RESUMED: {resume_notes}"
            self.progress_notes = current_notes + resume_note
        
        self.save()
        
        frappe.msgprint(_("Plan resumed"))
        return self
    
    @frappe.whitelist()
    def cancel_plan(self, cancellation_reason):
        """Cancel the plan."""
        if self.status in ["Completed", "Cancelled"]:
            frappe.throw(_("Cannot cancel {0} plan").format(self.status.lower()))
        
        self.status = "Cancelled"
        
        # Add cancellation reason to progress notes
        current_notes = self.progress_notes or ""
        timestamp = now_datetime().strftime("%Y-%m-%d %H:%M")
        cancel_note = f"\n[{timestamp}] CANCELLED: {cancellation_reason}"
        self.progress_notes = current_notes + cancel_note
        
        self.save()
        
        # Send cancellation notifications
        self.send_cancellation_notifications(cancellation_reason)
        
        frappe.msgprint(_("Plan cancelled"))
        return self
    
    def send_cancellation_notifications(self, reason):
        """Send plan cancellation notifications."""
        recipients = []
        
        if self.assigned_counselor:
            counselor = frappe.get_doc("Employee", self.assigned_counselor)
            if counselor.user_id:
                recipients.append(counselor.user_id)
        
        if self.class_teacher:
            teacher = frappe.get_doc("Employee", self.class_teacher)
            if teacher.user_id:
                recipients.append(teacher.user_id)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Remedial Plan Cancelled - {0}").format(self.student_name),
                message=self.get_cancellation_notification_message(reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_cancellation_notification_message(self, reason):
        """Get cancellation notification message."""
        return _("""
        Remedial Plan Cancelled
        
        Plan: {plan_name}
        Student: {student_name}
        
        Cancellation Reason:
        {reason}
        
        Progress at Cancellation: {completion_percentage}%
        
        Please consider alternative support strategies if needed.
        
        Academic Support Team
        """).format(
            plan_name=self.name,
            student_name=self.student_name,
            reason=reason,
            completion_percentage=self.completion_percentage
        )
    
    @frappe.whitelist()
    def get_plan_analytics(self):
        """Get plan analytics and insights."""
        # Calculate time metrics
        days_elapsed = date_diff(getdate(), self.start_date) if self.start_date else 0
        total_planned_days = date_diff(self.target_completion_date, self.start_date) if self.start_date and self.target_completion_date else 0
        
        # Get intervention sessions
        sessions = frappe.get_all("Intervention Session",
            filters={"remedial_plan": self.name},
            fields=["status", "session_date", "effectiveness_rating"]
        )
        
        completed_sessions = len([s for s in sessions if s.status == "Completed"])
        total_sessions = len(sessions)
        
        # Calculate progress rate
        progress_rate = (self.completion_percentage / days_elapsed) if days_elapsed > 0 else 0
        
        return {
            "plan_info": {
                "name": self.name,
                "student": self.student_name,
                "plan_type": self.plan_type,
                "priority": self.priority,
                "status": self.status
            },
            "timeline": {
                "start_date": self.start_date,
                "target_completion_date": self.target_completion_date,
                "actual_completion_date": self.actual_completion_date,
                "days_elapsed": days_elapsed,
                "total_planned_days": total_planned_days,
                "duration_weeks": self.duration_weeks
            },
            "progress": {
                "completion_percentage": self.completion_percentage,
                "progress_rate": progress_rate,
                "effectiveness_rating": self.effectiveness_rating
            },
            "interventions": {
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
                "session_completion_rate": (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
            },
            "team": {
                "assigned_counselor": self.assigned_counselor,
                "class_teacher": self.class_teacher,
                "guardian_consent": self.guardian_consent
            }
        }
    
    def get_plan_summary(self):
        """Get plan summary for reporting."""
        return {
            "plan_name": self.name,
            "student": self.student_name,
            "plan_type": self.plan_type,
            "priority": self.priority,
            "status": self.status,
            "start_date": self.start_date,
            "target_completion_date": self.target_completion_date,
            "actual_completion_date": self.actual_completion_date,
            "duration_weeks": self.duration_weeks,
            "completion_percentage": self.completion_percentage,
            "effectiveness_rating": self.effectiveness_rating,
            "assigned_counselor": self.assigned_counselor,
            "guardian_consent": self.guardian_consent,
            "trigger_rule": self.trigger_rule,
            "intervention_count": len(self.interventions) if self.interventions else 0
        }
