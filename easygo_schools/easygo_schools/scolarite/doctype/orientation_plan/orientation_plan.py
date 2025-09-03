"""Orientation Plan DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, flt, cint, add_days


class OrientationPlan(Document):
    """Orientation Plan management for student career guidance."""
    
    def validate(self):
        """Validate orientation plan data."""
        self.validate_dates()
        self.validate_team_assignment()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate plan dates."""
        if self.orientation_date and self.orientation_date < getdate():
            frappe.msgprint(_("Warning: Orientation date is in the past"))
        
        if self.next_review_date and self.orientation_date:
            if self.next_review_date <= self.orientation_date:
                frappe.throw(_("Next review date must be after orientation date"))
    
    def validate_team_assignment(self):
        """Validate team member assignments."""
        if not self.orientation_counselor:
            # Auto-assign based on student's counselor or default
            student_counselor = frappe.db.get_value("Student Counselor Assignment", 
                {"student": self.student, "status": "Active"}, "counselor")
            
            if student_counselor:
                self.orientation_counselor = student_counselor
            else:
                # Get default orientation counselor from settings
                default_counselor = frappe.db.get_single_value("School Settings", "orientation_counselor")
                if default_counselor:
                    self.orientation_counselor = default_counselor
        
        # Set class teacher if not provided
        if not self.class_teacher and self.student:
            student_group = frappe.db.get_value("Student", self.student, "student_group")
            if student_group:
                instructor = frappe.db.get_value("Student Group", student_group, "instructor")
                if instructor:
                    self.class_teacher = instructor
    
    def set_defaults(self):
        """Set default values."""
        if not self.orientation_date:
            self.orientation_date = getdate()
        
        if not self.follow_up_schedule:
            self.follow_up_schedule = "Quarterly"
        
        if not self.priority:
            self.priority = "Medium"
        
        # Set next review date based on follow-up schedule
        if not self.next_review_date and self.orientation_date:
            self.set_next_review_date()
    
    def set_next_review_date(self):
        """Set next review date based on follow-up schedule."""
        days_to_add = {
            "Monthly": 30,
            "Quarterly": 90,
            "Bi-annual": 180,
            "Annual": 365,
            "As Needed": 90  # Default to quarterly
        }
        
        days = days_to_add.get(self.follow_up_schedule, 90)
        self.next_review_date = add_days(self.orientation_date, days)
    
    def on_submit(self):
        """Actions on submit."""
        self.status = "In Progress"
        self.send_plan_notifications()
        self.schedule_orientation_meeting()
        self.create_follow_up_tasks()
    
    def send_plan_notifications(self):
        """Send notifications to all stakeholders."""
        # Notify orientation counselor
        if self.orientation_counselor:
            self.send_counselor_notification()
        
        # Notify class teacher
        if self.class_teacher:
            self.send_teacher_notification()
        
        # Notify parent/guardian
        if self.parent_guardian:
            self.send_guardian_notification()
        
        # Notify student
        self.send_student_notification()
    
    def send_counselor_notification(self):
        """Send notification to orientation counselor."""
        counselor = frappe.get_doc("Employee", self.orientation_counselor)
        
        if counselor.user_id:
            frappe.sendmail(
                recipients=[counselor.user_id],
                subject=_("New Orientation Plan Assignment - {0}").format(self.student_name),
                message=self.get_counselor_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_counselor_notification_message(self):
        """Get counselor notification message."""
        return _("""
        You have been assigned a new orientation plan:
        
        Plan: {plan_name}
        Student: {student_name}
        Current Grade: {current_grade}
        Priority: {priority}
        
        Student Assessment:
        Academic Performance: {academic_performance}
        Career Aspirations: {career_aspirations}
        
        Action Plan:
        {action_plan}
        
        Timeline: {timeline}
        Follow-up Schedule: {follow_up_schedule}
        Next Review: {next_review_date}
        
        Please review the plan and begin implementation.
        
        Academic Guidance Team
        """).format(
            plan_name=self.name,
            student_name=self.student_name,
            current_grade=self.current_grade or "Not specified",
            priority=self.priority,
            academic_performance=self.academic_performance or "To be assessed",
            career_aspirations=self.career_aspirations or "To be explored",
            action_plan=self.action_plan or "To be developed",
            timeline=self.timeline or "To be determined",
            follow_up_schedule=self.follow_up_schedule,
            next_review_date=frappe.format(self.next_review_date, "Date") if self.next_review_date else "TBA"
        )
    
    def send_teacher_notification(self):
        """Send notification to class teacher."""
        teacher = frappe.get_doc("Employee", self.class_teacher)
        
        if teacher.user_id:
            frappe.sendmail(
                recipients=[teacher.user_id],
                subject=_("Student Orientation Plan - {0}").format(self.student_name),
                message=self.get_teacher_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_teacher_notification_message(self):
        """Get teacher notification message."""
        return _("""
        An orientation plan has been created for your student:
        
        Student: {student_name}
        Orientation Counselor: {counselor_name}
        Priority: {priority}
        
        Your Role:
        - Provide academic performance insights
        - Support subject selection guidance
        - Monitor student progress
        - Coordinate with the orientation counselor
        
        Recommended Streams:
        {recommended_streams}
        
        Please coordinate with the orientation counselor for effective implementation.
        
        Academic Guidance Team
        """).format(
            student_name=self.student_name,
            counselor_name=frappe.get_value("Employee", self.orientation_counselor, "employee_name") if self.orientation_counselor else "Not assigned",
            priority=self.priority,
            recommended_streams=self.get_recommended_streams_text()
        )
    
    def get_recommended_streams_text(self):
        """Get recommended streams as text."""
        if not self.recommended_streams:
            return "To be determined"
        
        streams = []
        for stream in self.recommended_streams:
            streams.append(f"- {stream.stream_name}: {stream.recommendation_reason}")
        
        return "\n".join(streams) if streams else "To be determined"
    
    def send_guardian_notification(self):
        """Send notification to parent/guardian."""
        if self.parent_guardian:
            guardian = frappe.get_doc("Guardian", self.parent_guardian)
            
            if guardian.email_address:
                frappe.sendmail(
                    recipients=[guardian.email_address],
                    subject=_("Academic Orientation Plan - {0}").format(self.student_name),
                    message=self.get_guardian_notification_message(),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
    
    def get_guardian_notification_message(self):
        """Get guardian notification message."""
        return _("""
        Dear Parent/Guardian,
        
        We have developed an academic orientation plan for {student_name} to help guide their educational path.
        
        Plan Overview:
        - Orientation Date: {orientation_date}
        - Counselor: {counselor_name}
        - Priority: {priority}
        
        Assessment Areas:
        - Academic Performance
        - Interests & Aptitudes
        - Career Aspirations
        - Strengths & Areas for Improvement
        
        Recommended Streams:
        {recommended_streams}
        
        {meeting_info}
        
        Your involvement is crucial for the success of this orientation plan. We will keep you updated on progress and may request your input on important decisions.
        
        If you have any questions or concerns, please contact the orientation counselor.
        
        Best regards,
        Academic Guidance Team
        """).format(
            student_name=self.student_name,
            orientation_date=frappe.format(self.orientation_date, "Date"),
            counselor_name=frappe.get_value("Employee", self.orientation_counselor, "employee_name") if self.orientation_counselor else "TBA",
            priority=self.priority,
            recommended_streams=self.get_recommended_streams_text(),
            meeting_info="A meeting will be scheduled to discuss the plan in detail." if self.meeting_scheduled else "Please contact us to schedule a discussion meeting."
        )
    
    def send_student_notification(self):
        """Send age-appropriate notification to student."""
        student = frappe.get_doc("Student", self.student)
        
        if student.student_email_id:
            frappe.sendmail(
                recipients=[student.student_email_id],
                subject=_("Your Academic Guidance Plan"),
                message=self.get_student_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_student_notification_message(self):
        """Get student notification message."""
        return _("""
        Hi {student_name},
        
        We've created a special academic guidance plan to help you explore your future education and career options!
        
        Your Guidance Team:
        - Orientation Counselor: {counselor_name}
        - Class Teacher: {teacher_name}
        
        What this means for you:
        - We'll explore your interests and strengths
        - Discuss different academic streams and career paths
        - Help you make informed decisions about your future
        - Provide ongoing support and guidance
        
        Areas we'll explore together:
        - Your academic strengths
        - What subjects interest you most
        - Career fields you might enjoy
        - Educational paths that match your goals
        
        Remember, this is about discovering your potential and finding the path that's right for YOU!
        
        If you have any questions or want to discuss anything, feel free to talk to your counselor or teacher.
        
        Your future is bright!
        Academic Guidance Team
        """).format(
            student_name=self.student_name,
            counselor_name=frappe.get_value("Employee", self.orientation_counselor, "employee_name") if self.orientation_counselor else "Your counselor",
            teacher_name=frappe.get_value("Employee", self.class_teacher, "employee_name") if self.class_teacher else "Your teacher"
        )
    
    def schedule_orientation_meeting(self):
        """Schedule orientation meeting if required."""
        if self.meeting_scheduled and self.parent_guardian:
            meeting = frappe.get_doc({
                "doctype": "Meeting Request",
                "student": self.student,
                "meeting_type": "Orientation Meeting",
                "priority": self.priority,
                "requested_by": self.orientation_counselor,
                "subject": f"Academic orientation discussion for {self.student_name}",
                "description": f"Meeting to discuss orientation plan: {self.name}",
                "attendees": [
                    {"attendee_type": "Guardian", "attendee": self.parent_guardian},
                    {"attendee_type": "Employee", "attendee": self.orientation_counselor}
                ],
                "status": "Requested"
            })
            
            meeting.insert(ignore_permissions=True)
    
    def create_follow_up_tasks(self):
        """Create follow-up tasks for the orientation plan."""
        if self.next_review_date:
            # Create review task
            review_task = frappe.get_doc({
                "doctype": "ToDo",
                "description": f"Review orientation plan: {self.name} for {self.student_name}",
                "reference_type": self.doctype,
                "reference_name": self.name,
                "assigned_by": frappe.session.user,
                "owner": frappe.get_value("Employee", self.orientation_counselor, "user_id") if self.orientation_counselor else frappe.session.user,
                "date": self.next_review_date,
                "priority": "Medium" if self.priority == "Medium" else "High"
            })
            
            review_task.insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def update_assessment(self, academic_performance, interests_aptitudes, career_aspirations, strengths_weaknesses):
        """Update student assessment information."""
        self.academic_performance = academic_performance
        self.interests_aptitudes = interests_aptitudes
        self.career_aspirations = career_aspirations
        self.strengths_weaknesses = strengths_weaknesses
        
        self.save()
        
        # Send assessment update notifications
        self.send_assessment_update_notifications()
        
        frappe.msgprint(_("Assessment updated successfully"))
        return self
    
    def send_assessment_update_notifications(self):
        """Send assessment update notifications."""
        # Notify guardian
        if self.parent_guardian:
            guardian = frappe.get_doc("Guardian", self.parent_guardian)
            if guardian.email_address:
                frappe.sendmail(
                    recipients=[guardian.email_address],
                    subject=_("Assessment Update - {0}").format(self.student_name),
                    message=self.get_assessment_update_message(),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
    
    def get_assessment_update_message(self):
        """Get assessment update message."""
        return _("""
        Dear Parent/Guardian,
        
        We have updated the academic assessment for {student_name}.
        
        Assessment Summary:
        
        Academic Performance:
        {academic_performance}
        
        Interests & Aptitudes:
        {interests_aptitudes}
        
        Career Aspirations:
        {career_aspirations}
        
        Strengths & Areas for Improvement:
        {strengths_weaknesses}
        
        Based on this assessment, we will refine our recommendations and guidance approach.
        
        Academic Guidance Team
        """).format(
            student_name=self.student_name,
            academic_performance=self.academic_performance or "To be assessed",
            interests_aptitudes=self.interests_aptitudes or "To be explored",
            career_aspirations=self.career_aspirations or "To be discussed",
            strengths_weaknesses=self.strengths_weaknesses or "To be identified"
        )
    
    @frappe.whitelist()
    def add_stream_recommendation(self, stream_name, recommendation_reason, priority_level, required_subjects):
        """Add stream recommendation to the plan."""
        # Add to recommended streams table
        self.append("recommended_streams", {
            "stream_name": stream_name,
            "recommendation_reason": recommendation_reason,
            "priority_level": priority_level,
            "required_subjects": required_subjects
        })
        
        self.save()
        
        frappe.msgprint(_("Stream recommendation added"))
        return self
    
    @frappe.whitelist()
    def complete_plan(self, completion_notes, effectiveness_rating, student_feedback=None, parent_feedback=None):
        """Complete the orientation plan."""
        if self.status == "Completed":
            frappe.throw(_("Plan is already completed"))
        
        self.status = "Completed"
        self.completion_date = getdate()
        self.effectiveness_rating = cint(effectiveness_rating)
        
        if student_feedback:
            self.student_feedback = student_feedback
        
        if parent_feedback:
            self.parent_feedback = parent_feedback
        
        # Add completion notes to counselor notes
        current_notes = self.counselor_notes or ""
        timestamp = now_datetime().strftime("%Y-%m-%d %H:%M")
        completion_note = f"\n[{timestamp}] COMPLETED: {completion_notes}"
        self.counselor_notes = current_notes + completion_note
        
        self.save()
        
        # Send completion notifications
        self.send_completion_notifications()
        
        # Create follow-up monitoring task
        self.create_follow_up_monitoring()
        
        frappe.msgprint(_("Orientation plan completed"))
        return self
    
    def send_completion_notifications(self):
        """Send plan completion notifications."""
        # Notify all stakeholders
        recipients = []
        
        if self.orientation_counselor:
            counselor = frappe.get_doc("Employee", self.orientation_counselor)
            if counselor.user_id:
                recipients.append(counselor.user_id)
        
        if self.class_teacher:
            teacher = frappe.get_doc("Employee", self.class_teacher)
            if teacher.user_id:
                recipients.append(teacher.user_id)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Orientation Plan Completed - {0}").format(self.student_name),
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
                    subject=_("Orientation Plan Completed - {0}").format(self.student_name),
                    message=self.get_guardian_completion_message(),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
    
    def get_completion_notification_message(self):
        """Get completion notification message."""
        return _("""
        Orientation Plan Completed
        
        Plan: {plan_name}
        Student: {student_name}
        Completion Date: {completion_date}
        
        Plan Summary:
        - Effectiveness Rating: {effectiveness_rating}/5
        - Recommended Streams: {stream_count}
        
        Final Recommendations:
        {recommended_streams}
        
        Student Feedback: {student_feedback}
        Parent Feedback: {parent_feedback}
        
        Thank you for your dedication to student guidance!
        
        Academic Guidance Team
        """).format(
            plan_name=self.name,
            student_name=self.student_name,
            completion_date=frappe.format(self.completion_date, "Date"),
            effectiveness_rating=self.effectiveness_rating or "Not rated",
            stream_count=len(self.recommended_streams) if self.recommended_streams else 0,
            recommended_streams=self.get_recommended_streams_text(),
            student_feedback=self.student_feedback or "No feedback provided",
            parent_feedback=self.parent_feedback or "No feedback provided"
        )
    
    def get_guardian_completion_message(self):
        """Get guardian completion notification message."""
        return _("""
        Dear Parent/Guardian,
        
        We're pleased to inform you that {student_name}'s academic orientation plan has been successfully completed!
        
        Plan Summary:
        - Completion Date: {completion_date}
        - Effectiveness Rating: {effectiveness_rating}/5
        
        Final Recommendations:
        {recommended_streams}
        
        Alternative Options:
        {alternative_options}
        
        Next Steps:
        - Review the recommendations with your child
        - Consider the suggested academic streams
        - Plan for subject selections
        - Continue monitoring academic progress
        
        We will continue to provide guidance and support as needed for {student_name}'s academic journey.
        
        Thank you for your cooperation throughout this process!
        
        Best regards,
        Academic Guidance Team
        """).format(
            student_name=self.student_name,
            completion_date=frappe.format(self.completion_date, "Date"),
            effectiveness_rating=self.effectiveness_rating or "Not rated",
            recommended_streams=self.get_recommended_streams_text(),
            alternative_options=self.alternative_options or "None specified"
        )
    
    def create_follow_up_monitoring(self):
        """Create follow-up monitoring task after plan completion."""
        # Create follow-up monitoring task for 6 months later
        follow_up_date = add_days(self.completion_date, 180)
        
        follow_up_task = frappe.get_doc({
            "doctype": "ToDo",
            "description": f"Follow-up monitoring for completed orientation plan: {self.name}",
            "reference_type": self.doctype,
            "reference_name": self.name,
            "assigned_by": frappe.session.user,
            "owner": frappe.get_value("Employee", self.orientation_counselor, "user_id") if self.orientation_counselor else frappe.session.user,
            "date": follow_up_date,
            "priority": "Low"
        })
        
        follow_up_task.insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def put_on_hold(self, hold_reason):
        """Put plan on hold."""
        if self.status in ["Completed", "On Hold"]:
            frappe.throw(_("Cannot put {0} plan on hold").format(self.status.lower()))
        
        self.status = "On Hold"
        
        # Add hold reason to counselor notes
        current_notes = self.counselor_notes or ""
        timestamp = now_datetime().strftime("%Y-%m-%d %H:%M")
        hold_note = f"\n[{timestamp}] ON HOLD: {hold_reason}"
        self.counselor_notes = current_notes + hold_note
        
        self.save()
        
        frappe.msgprint(_("Plan put on hold"))
        return self
    
    @frappe.whitelist()
    def resume_plan(self, resume_notes=None):
        """Resume plan from hold."""
        if self.status != "On Hold":
            frappe.throw(_("Can only resume plans that are on hold"))
        
        self.status = "In Progress"
        
        # Update next review date
        self.set_next_review_date()
        
        if resume_notes:
            current_notes = self.counselor_notes or ""
            timestamp = now_datetime().strftime("%Y-%m-%d %H:%M")
            resume_note = f"\n[{timestamp}] RESUMED: {resume_notes}"
            self.counselor_notes = current_notes + resume_note
        
        self.save()
        
        frappe.msgprint(_("Plan resumed"))
        return self
    
    @frappe.whitelist()
    def request_revision(self, revision_reason):
        """Request plan revision."""
        if self.status in ["Completed", "Revision Required"]:
            frappe.throw(_("Cannot request revision for {0} plan").format(self.status.lower()))
        
        self.status = "Revision Required"
        
        # Add revision request to counselor notes
        current_notes = self.counselor_notes or ""
        timestamp = now_datetime().strftime("%Y-%m-%d %H:%M")
        revision_note = f"\n[{timestamp}] REVISION REQUESTED: {revision_reason}"
        self.counselor_notes = current_notes + revision_note
        
        self.save()
        
        # Send revision request notification
        self.send_revision_request_notification(revision_reason)
        
        frappe.msgprint(_("Revision requested"))
        return self
    
    def send_revision_request_notification(self, reason):
        """Send revision request notification."""
        if self.orientation_counselor:
            counselor = frappe.get_doc("Employee", self.orientation_counselor)
            if counselor.user_id:
                frappe.sendmail(
                    recipients=[counselor.user_id],
                    subject=_("Plan Revision Required - {0}").format(self.student_name),
                    message=self.get_revision_request_message(reason),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
    
    def get_revision_request_message(self, reason):
        """Get revision request message."""
        return _("""
        Orientation Plan Revision Required
        
        Plan: {plan_name}
        Student: {student_name}
        
        Revision Reason:
        {reason}
        
        Please review the plan and make necessary revisions.
        
        Academic Guidance Team
        """).format(
            plan_name=self.name,
            student_name=self.student_name,
            reason=reason
        )
    
    @frappe.whitelist()
    def get_plan_analytics(self):
        """Get plan analytics and insights."""
        # Get student's orientation history
        orientation_history = frappe.get_all("Orientation Plan",
            filters={"student": self.student, "status": "Completed"},
            fields=["orientation_date", "effectiveness_rating", "completion_date"],
            order_by="orientation_date desc",
            limit=5
        )
        
        # Calculate plan duration
        plan_duration = None
        if self.completion_date and self.orientation_date:
            plan_duration = (self.completion_date - self.orientation_date).days
        
        # Get stream recommendation statistics
        stream_stats = {}
        if self.recommended_streams:
            for stream in self.recommended_streams:
                priority = stream.priority_level
                if priority not in stream_stats:
                    stream_stats[priority] = 0
                stream_stats[priority] += 1
        
        return {
            "current_plan": {
                "name": self.name,
                "status": self.status,
                "orientation_date": self.orientation_date,
                "completion_date": self.completion_date,
                "plan_duration": plan_duration
            },
            "student_statistics": {
                "total_completed_plans": len(orientation_history),
                "average_effectiveness": sum(flt(p.effectiveness_rating) for p in orientation_history if p.effectiveness_rating) / max(1, len([p for p in orientation_history if p.effectiveness_rating])),
                "stream_recommendations": len(self.recommended_streams) if self.recommended_streams else 0
            },
            "stream_distribution": stream_stats,
            "recent_plans": orientation_history,
            "team": {
                "orientation_counselor": self.orientation_counselor,
                "class_teacher": self.class_teacher,
                "meeting_scheduled": self.meeting_scheduled
            }
        }
    
    def get_plan_summary(self):
        """Get plan summary for reporting."""
        return {
            "plan_name": self.name,
            "student": self.student_name,
            "current_grade": self.current_grade,
            "status": self.status,
            "priority": self.priority,
            "orientation_date": self.orientation_date,
            "completion_date": self.completion_date,
            "effectiveness_rating": self.effectiveness_rating,
            "orientation_counselor": self.orientation_counselor,
            "meeting_scheduled": self.meeting_scheduled,
            "stream_recommendations": len(self.recommended_streams) if self.recommended_streams else 0,
            "follow_up_schedule": self.follow_up_schedule,
            "next_review_date": self.next_review_date,
            "academic_year": self.academic_year
        }
