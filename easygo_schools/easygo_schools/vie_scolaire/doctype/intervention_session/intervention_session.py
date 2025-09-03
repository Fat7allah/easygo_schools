"""Intervention Session DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, flt, cint, add_days


class InterventionSession(Document):
    """Intervention Session management for student support."""
    
    def validate(self):
        """Validate intervention session data."""
        self.validate_session_timing()
        self.validate_counselor_availability()
        self.set_defaults()
    
    def validate_session_timing(self):
        """Validate session timing."""
        if self.session_date and self.session_date < getdate():
            frappe.msgprint(_("Warning: Scheduling session for a past date"))
        
        if self.next_session_date and self.session_date:
            if self.next_session_date <= self.session_date:
                frappe.throw(_("Next session date must be after current session date"))
    
    def validate_counselor_availability(self):
        """Validate counselor availability for the session."""
        if self.assigned_counselor and self.session_date:
            # Check for conflicting sessions
            conflicts = frappe.db.sql("""
                SELECT name FROM `tabIntervention Session`
                WHERE assigned_counselor = %s 
                AND session_date = %s
                AND name != %s
                AND status NOT IN ('Cancelled', 'Completed')
            """, [self.assigned_counselor, self.session_date, self.name or ""])
            
            if conflicts:
                frappe.msgprint(_("Warning: Counselor has other sessions scheduled on this date"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.duration_minutes:
            self.duration_minutes = 60
        
        if not self.session_mode:
            self.session_mode = "In-Person"
        
        if not self.priority:
            self.priority = "Medium"
        
        # Set counselor from remedial plan if available
        if self.remedial_plan and not self.assigned_counselor:
            plan_counselor = frappe.db.get_value("Remedial Plan", self.remedial_plan, "assigned_counselor")
            if plan_counselor:
                self.assigned_counselor = plan_counselor
    
    def on_submit(self):
        """Actions on submit."""
        self.send_session_notifications()
        self.create_calendar_event()
    
    def send_session_notifications(self):
        """Send session notifications to relevant parties."""
        # Notify counselor
        if self.assigned_counselor:
            self.send_counselor_notification()
        
        # Notify student and guardian
        self.send_student_notification()
        
        # Notify teacher if required
        if self.teacher_notified:
            self.send_teacher_notification()
    
    def send_counselor_notification(self):
        """Send notification to assigned counselor."""
        counselor = frappe.get_doc("Employee", self.assigned_counselor)
        
        if counselor.user_id:
            frappe.sendmail(
                recipients=[counselor.user_id],
                subject=_("Intervention Session Scheduled - {0}").format(self.student_name),
                message=self.get_counselor_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_counselor_notification_message(self):
        """Get counselor notification message."""
        return _("""
        New Intervention Session Scheduled
        
        Session: {session_name}
        Student: {student_name}
        Type: {intervention_type}
        Date: {session_date}
        Duration: {duration} minutes
        Location: {location}
        Mode: {session_mode}
        
        Session Details:
        Reason: {session_reason}
        Objectives: {objectives}
        
        {remedial_plan_info}
        
        Please prepare for the session and review any relevant student information.
        
        Academic Support Team
        """).format(
            session_name=self.name,
            student_name=self.student_name,
            intervention_type=self.intervention_type,
            session_date=frappe.format(self.session_date, "Date"),
            duration=self.duration_minutes,
            location=self.session_location or "TBA",
            session_mode=self.session_mode,
            session_reason=self.session_reason or "Not specified",
            objectives=self.objectives or "See session description",
            remedial_plan_info=f"Related Remedial Plan: {self.remedial_plan}" if self.remedial_plan else ""
        )
    
    def send_student_notification(self):
        """Send notification to student and guardian."""
        student = frappe.get_doc("Student", self.student)
        recipients = []
        
        # Get guardian emails
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            if guardian.email_address:
                recipients.append(guardian.email_address)
        
        # Add student email if available
        if student.student_email_id:
            recipients.append(student.student_email_id)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Support Session Scheduled - {0}").format(self.student_name),
                message=self.get_student_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_student_notification_message(self):
        """Get student notification message."""
        return _("""
        Dear Student/Guardian,
        
        A support session has been scheduled for {student_name}.
        
        Session Details:
        - Date: {session_date}
        - Time: As scheduled with counselor
        - Duration: {duration} minutes
        - Location: {location}
        - Counselor: {counselor_name}
        - Type: {intervention_type}
        
        Purpose:
        {session_reason}
        
        Please ensure {student_name} attends the session on time. This session is designed to provide personalized support and guidance.
        
        If you need to reschedule, please contact the counselor as soon as possible.
        
        Academic Support Team
        """).format(
            student_name=self.student_name,
            session_date=frappe.format(self.session_date, "Date"),
            duration=self.duration_minutes,
            location=self.session_location or "Counselor's office",
            counselor_name=frappe.get_value("Employee", self.assigned_counselor, "employee_name") if self.assigned_counselor else "TBA",
            intervention_type=self.intervention_type,
            session_reason=self.session_reason or "Academic and personal support"
        )
    
    def send_teacher_notification(self):
        """Send notification to class teacher."""
        if self.student:
            student_group = frappe.db.get_value("Student", self.student, "student_group")
            if student_group:
                instructor = frappe.db.get_value("Student Group", student_group, "instructor")
                if instructor:
                    teacher = frappe.get_doc("Employee", instructor)
                    if teacher.user_id:
                        frappe.sendmail(
                            recipients=[teacher.user_id],
                            subject=_("Student Intervention Session - {0}").format(self.student_name),
                            message=self.get_teacher_notification_message(),
                            reference_doctype=self.doctype,
                            reference_name=self.name
                        )
    
    def get_teacher_notification_message(self):
        """Get teacher notification message."""
        return _("""
        Student Intervention Session Notification
        
        Student: {student_name}
        Session Date: {session_date}
        Intervention Type: {intervention_type}
        Counselor: {counselor_name}
        
        Please be aware that this student has a scheduled intervention session. You may notice them being called out of class or arriving late.
        
        If you have any observations or concerns about the student that might be relevant to the session, please coordinate with the counselor.
        
        Academic Support Team
        """).format(
            student_name=self.student_name,
            session_date=frappe.format(self.session_date, "Date"),
            intervention_type=self.intervention_type,
            counselor_name=frappe.get_value("Employee", self.assigned_counselor, "employee_name") if self.assigned_counselor else "TBA"
        )
    
    def create_calendar_event(self):
        """Create calendar event for the session."""
        if self.assigned_counselor:
            counselor = frappe.get_doc("Employee", self.assigned_counselor)
            if counselor.user_id:
                event = frappe.get_doc({
                    "doctype": "Event",
                    "subject": f"Intervention Session - {self.student_name}",
                    "event_type": "Private",
                    "starts_on": f"{self.session_date} 09:00:00",  # Default time
                    "ends_on": f"{self.session_date} {self.get_end_time()}",
                    "description": f"Intervention session with {self.student_name}\nType: {self.intervention_type}",
                    "owner": counselor.user_id,
                    "event_participants": [{"reference_doctype": "User", "reference_docname": counselor.user_id}]
                })
                
                event.insert(ignore_permissions=True)
    
    def get_end_time(self):
        """Calculate session end time."""
        # Simple calculation - add duration to 9:00 AM
        start_hour = 9
        start_minute = 0
        
        total_minutes = start_minute + self.duration_minutes
        end_hour = start_hour + (total_minutes // 60)
        end_minute = total_minutes % 60
        
        return f"{end_hour:02d}:{end_minute:02d}:00"
    
    @frappe.whitelist()
    def start_session(self):
        """Mark session as started."""
        if self.status != "Scheduled":
            frappe.throw(_("Can only start scheduled sessions"))
        
        self.status = "In Progress"
        self.session_start_time = now_datetime()
        self.attendance_status = "Present"
        self.save()
        
        frappe.msgprint(_("Session started"))
        return self
    
    @frappe.whitelist()
    def complete_session(self, session_notes, outcomes_achieved, effectiveness_rating, student_response, student_engagement):
        """Complete the session with documentation."""
        if self.status != "In Progress":
            frappe.throw(_("Session must be in progress to complete"))
        
        self.status = "Completed"
        self.session_notes = session_notes
        self.outcomes_achieved = outcomes_achieved
        self.effectiveness_rating = cint(effectiveness_rating)
        self.student_response = student_response
        self.student_engagement = student_engagement
        
        self.save()
        
        # Update remedial plan progress if linked
        if self.remedial_plan:
            self.update_remedial_plan_progress()
        
        # Send completion notifications
        self.send_completion_notifications()
        
        # Schedule follow-up if required
        if self.follow_up_required and self.next_session_date:
            self.schedule_follow_up_session()
        
        frappe.msgprint(_("Session completed successfully"))
        return self
    
    def update_remedial_plan_progress(self):
        """Update related remedial plan progress."""
        if self.remedial_plan:
            plan = frappe.get_doc("Remedial Plan", self.remedial_plan)
            
            # Add session completion note to plan
            progress_note = f"Intervention session completed: {self.intervention_type} - Rating: {self.effectiveness_rating}/5"
            plan.update_progress(
                completion_percentage=plan.completion_percentage + 10,  # Increment by 10%
                progress_notes=progress_note
            )
    
    def send_completion_notifications(self):
        """Send session completion notifications."""
        # Notify parent if requested
        if self.parent_informed:
            self.send_parent_completion_notification()
        
        # Notify teacher if coordination required
        if self.teacher_notified and self.coordination_notes:
            self.send_teacher_completion_notification()
    
    def send_parent_completion_notification(self):
        """Send completion notification to parent."""
        student = frappe.get_doc("Student", self.student)
        
        # Get guardian emails
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        recipients = []
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            if guardian.email_address:
                recipients.append(guardian.email_address)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Session Update - {0}").format(self.student_name),
                message=self.get_parent_completion_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_parent_completion_message(self):
        """Get parent completion notification message."""
        return _("""
        Dear Parent/Guardian,
        
        {student_name} has completed their intervention session today.
        
        Session Summary:
        - Date: {session_date}
        - Type: {intervention_type}
        - Duration: {duration} minutes
        - Counselor: {counselor_name}
        
        Session Outcomes:
        {outcomes_achieved}
        
        Student Engagement: {student_engagement}
        
        {homework_info}
        
        {follow_up_info}
        
        If you have any questions or would like to discuss the session further, please feel free to contact the counselor.
        
        Academic Support Team
        """).format(
            student_name=self.student_name,
            session_date=frappe.format(self.session_date, "Date"),
            intervention_type=self.intervention_type,
            duration=self.duration_minutes,
            counselor_name=frappe.get_value("Employee", self.assigned_counselor, "employee_name") if self.assigned_counselor else "Counselor",
            outcomes_achieved=self.outcomes_achieved or "Session objectives were addressed",
            student_engagement=self.student_engagement or "Good",
            homework_info=f"Tasks assigned: {self.homework_assigned}" if self.homework_assigned else "",
            follow_up_info=f"Next session scheduled: {frappe.format(self.next_session_date, 'Date')}" if self.follow_up_required and self.next_session_date else "No immediate follow-up required"
        )
    
    def send_teacher_completion_notification(self):
        """Send completion notification to teacher."""
        if self.student:
            student_group = frappe.db.get_value("Student", self.student, "student_group")
            if student_group:
                instructor = frappe.db.get_value("Student Group", student_group, "instructor")
                if instructor:
                    teacher = frappe.get_doc("Employee", instructor)
                    if teacher.user_id:
                        frappe.sendmail(
                            recipients=[teacher.user_id],
                            subject=_("Session Coordination - {0}").format(self.student_name),
                            message=self.get_teacher_completion_message(),
                            reference_doctype=self.doctype,
                            reference_name=self.name
                        )
    
    def get_teacher_completion_message(self):
        """Get teacher completion notification message."""
        return _("""
        Session Coordination Update
        
        Student: {student_name}
        Session Type: {intervention_type}
        Date: {session_date}
        
        Coordination Notes:
        {coordination_notes}
        
        Student Engagement: {student_engagement}
        
        Please consider these points in your interactions with the student and coordinate with the counselor as needed.
        
        Academic Support Team
        """).format(
            student_name=self.student_name,
            intervention_type=self.intervention_type,
            session_date=frappe.format(self.session_date, "Date"),
            coordination_notes=self.coordination_notes or "General coordination required",
            student_engagement=self.student_engagement or "Good"
        )
    
    def schedule_follow_up_session(self):
        """Schedule follow-up session."""
        if self.next_session_date:
            follow_up = frappe.get_doc({
                "doctype": "Intervention Session",
                "student": self.student,
                "remedial_plan": self.remedial_plan,
                "intervention_type": self.intervention_type,
                "session_date": self.next_session_date,
                "assigned_counselor": self.assigned_counselor,
                "session_location": self.session_location,
                "duration_minutes": self.duration_minutes,
                "session_mode": self.session_mode,
                "session_reason": f"Follow-up to session {self.name}",
                "priority": self.priority,
                "status": "Scheduled"
            })
            
            follow_up.insert(ignore_permissions=True)
            
            frappe.msgprint(_("Follow-up session scheduled: {0}").format(follow_up.name))
    
    @frappe.whitelist()
    def mark_no_show(self, no_show_reason=None):
        """Mark session as no show."""
        if self.status not in ["Scheduled", "In Progress"]:
            frappe.throw(_("Can only mark scheduled or in-progress sessions as no show"))
        
        self.status = "No Show"
        self.attendance_status = "Absent"
        
        if no_show_reason:
            self.session_notes = f"No Show - Reason: {no_show_reason}"
        
        self.save()
        
        # Send no show notifications
        self.send_no_show_notifications()
        
        # Suggest rescheduling
        self.suggest_reschedule()
        
        frappe.msgprint(_("Session marked as no show"))
        return self
    
    def send_no_show_notifications(self):
        """Send no show notifications."""
        # Notify counselor
        if self.assigned_counselor:
            counselor = frappe.get_doc("Employee", self.assigned_counselor)
            if counselor.user_id:
                frappe.sendmail(
                    recipients=[counselor.user_id],
                    subject=_("Student No Show - {0}").format(self.student_name),
                    message=self.get_no_show_notification_message(),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        # Notify guardian
        student = frappe.get_doc("Student", self.student)
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        recipients = []
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            if guardian.email_address:
                recipients.append(guardian.email_address)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Missed Session - {0}").format(self.student_name),
                message=self.get_guardian_no_show_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_no_show_notification_message(self):
        """Get no show notification message."""
        return _("""
        Student No Show Alert
        
        Session: {session_name}
        Student: {student_name}
        Scheduled Date: {session_date}
        Type: {intervention_type}
        
        The student did not attend the scheduled intervention session.
        
        Recommended Actions:
        1. Contact the student/guardian to understand the reason
        2. Reschedule the session if appropriate
        3. Update the remedial plan if necessary
        4. Consider alternative intervention strategies
        
        Academic Support Team
        """).format(
            session_name=self.name,
            student_name=self.student_name,
            session_date=frappe.format(self.session_date, "Date"),
            intervention_type=self.intervention_type
        )
    
    def get_guardian_no_show_message(self):
        """Get guardian no show notification message."""
        return _("""
        Dear Parent/Guardian,
        
        {student_name} did not attend their scheduled support session today.
        
        Session Details:
        - Date: {session_date}
        - Type: {intervention_type}
        - Counselor: {counselor_name}
        
        Please contact the school counselor to:
        1. Explain the absence
        2. Reschedule the session if needed
        3. Discuss any concerns or barriers
        
        These sessions are important for {student_name}'s academic and personal development.
        
        Academic Support Team
        """).format(
            student_name=self.student_name,
            session_date=frappe.format(self.session_date, "Date"),
            intervention_type=self.intervention_type,
            counselor_name=frappe.get_value("Employee", self.assigned_counselor, "employee_name") if self.assigned_counselor else "Counselor"
        )
    
    def suggest_reschedule(self):
        """Suggest rescheduling the session."""
        # Create a task for the counselor to reschedule
        if self.assigned_counselor:
            task = frappe.get_doc({
                "doctype": "ToDo",
                "description": f"Reschedule missed intervention session for {self.student_name}",
                "reference_type": self.doctype,
                "reference_name": self.name,
                "assigned_by": frappe.session.user,
                "owner": frappe.get_value("Employee", self.assigned_counselor, "user_id"),
                "date": add_days(getdate(), 1),
                "priority": "Medium"
            })
            
            task.insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def cancel_session(self, cancellation_reason):
        """Cancel the session."""
        if self.status in ["Completed", "Cancelled"]:
            frappe.throw(_("Cannot cancel {0} session").format(self.status.lower()))
        
        self.status = "Cancelled"
        self.session_notes = f"Cancelled - Reason: {cancellation_reason}"
        self.save()
        
        # Send cancellation notifications
        self.send_cancellation_notifications(cancellation_reason)
        
        frappe.msgprint(_("Session cancelled"))
        return self
    
    def send_cancellation_notifications(self, reason):
        """Send session cancellation notifications."""
        # Notify student and guardian
        student = frappe.get_doc("Student", self.student)
        recipients = []
        
        # Get guardian emails
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            if guardian.email_address:
                recipients.append(guardian.email_address)
        
        if student.student_email_id:
            recipients.append(student.student_email_id)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Session Cancelled - {0}").format(self.student_name),
                message=self.get_cancellation_message(reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_cancellation_message(self, reason):
        """Get cancellation notification message."""
        return _("""
        Dear Student/Guardian,
        
        The scheduled intervention session for {student_name} has been cancelled.
        
        Session Details:
        - Date: {session_date}
        - Type: {intervention_type}
        - Counselor: {counselor_name}
        
        Cancellation Reason:
        {reason}
        
        We will contact you to reschedule the session at a more convenient time.
        
        Academic Support Team
        """).format(
            student_name=self.student_name,
            session_date=frappe.format(self.session_date, "Date"),
            intervention_type=self.intervention_type,
            counselor_name=frappe.get_value("Employee", self.assigned_counselor, "employee_name") if self.assigned_counselor else "Counselor",
            reason=reason
        )
    
    @frappe.whitelist()
    def reschedule_session(self, new_date, reschedule_reason):
        """Reschedule the session."""
        if self.status in ["Completed", "Cancelled"]:
            frappe.throw(_("Cannot reschedule {0} session").format(self.status.lower()))
        
        # Create new session
        new_session = frappe.copy_doc(self)
        new_session.session_date = new_date
        new_session.status = "Scheduled"
        new_session.session_notes = f"Rescheduled from {self.session_date} - Reason: {reschedule_reason}"
        
        new_session.insert(ignore_permissions=True)
        
        # Update current session
        self.status = "Rescheduled"
        self.session_notes = f"Rescheduled to {new_date} - Reason: {reschedule_reason}"
        self.save()
        
        # Send reschedule notifications
        self.send_reschedule_notifications(new_session, reschedule_reason)
        
        frappe.msgprint(_("Session rescheduled to {0}").format(new_session.name))
        return new_session.name
    
    def send_reschedule_notifications(self, new_session, reason):
        """Send reschedule notifications."""
        student = frappe.get_doc("Student", self.student)
        recipients = []
        
        # Get guardian emails
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            if guardian.email_address:
                recipients.append(guardian.email_address)
        
        if student.student_email_id:
            recipients.append(student.student_email_id)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Session Rescheduled - {0}").format(self.student_name),
                message=self.get_reschedule_message(new_session, reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_reschedule_message(self, new_session, reason):
        """Get reschedule notification message."""
        return _("""
        Dear Student/Guardian,
        
        The intervention session for {student_name} has been rescheduled.
        
        Original Session:
        - Date: {old_date}
        
        New Session:
        - Date: {new_date}
        - Type: {intervention_type}
        - Counselor: {counselor_name}
        
        Reason for Rescheduling:
        {reason}
        
        Please make note of the new date and ensure attendance.
        
        Academic Support Team
        """).format(
            student_name=self.student_name,
            old_date=frappe.format(self.session_date, "Date"),
            new_date=frappe.format(new_session.session_date, "Date"),
            intervention_type=self.intervention_type,
            counselor_name=frappe.get_value("Employee", self.assigned_counselor, "employee_name") if self.assigned_counselor else "Counselor",
            reason=reason
        )
    
    @frappe.whitelist()
    def get_session_analytics(self):
        """Get session analytics and insights."""
        # Get student's session history
        session_history = frappe.get_all("Intervention Session",
            filters={"student": self.student, "status": "Completed"},
            fields=["session_date", "intervention_type", "effectiveness_rating", "student_engagement"],
            order_by="session_date desc",
            limit=10
        )
        
        # Calculate statistics
        total_sessions = len(session_history)
        avg_effectiveness = sum(flt(s.effectiveness_rating) for s in session_history if s.effectiveness_rating) / max(1, len([s for s in session_history if s.effectiveness_rating]))
        
        # Get intervention type distribution
        type_stats = {}
        for session in session_history:
            intervention_type = session.intervention_type
            if intervention_type not in type_stats:
                type_stats[intervention_type] = 0
            type_stats[intervention_type] += 1
        
        return {
            "current_session": {
                "name": self.name,
                "status": self.status,
                "intervention_type": self.intervention_type,
                "session_date": self.session_date
            },
            "student_statistics": {
                "total_completed_sessions": total_sessions,
                "average_effectiveness": avg_effectiveness,
                "intervention_types": type_stats
            },
            "recent_sessions": session_history,
            "remedial_plan": self.remedial_plan
        }
    
    def get_session_summary(self):
        """Get session summary for reporting."""
        return {
            "session_name": self.name,
            "student": self.student_name,
            "intervention_type": self.intervention_type,
            "session_date": self.session_date,
            "status": self.status,
            "assigned_counselor": self.assigned_counselor,
            "duration_minutes": self.duration_minutes,
            "effectiveness_rating": self.effectiveness_rating,
            "student_engagement": self.student_engagement,
            "attendance_status": self.attendance_status,
            "follow_up_required": self.follow_up_required,
            "remedial_plan": self.remedial_plan,
            "priority": self.priority
        }
