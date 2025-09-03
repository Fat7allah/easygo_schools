"""Orientation Choice DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, flt, cint, add_days


class OrientationChoice(Document):
    """Student orientation choice management for academic stream selection."""
    
    def validate(self):
        """Validate orientation choice data."""
        self.validate_choices()
        self.validate_prerequisites()
        self.validate_guardian_consent()
        self.set_defaults()
    
    def validate_choices(self):
        """Validate stream choices."""
        choices = [self.first_choice_stream, self.second_choice_stream, self.third_choice_stream]
        unique_choices = [choice for choice in choices if choice]
        
        if len(unique_choices) != len(set(unique_choices)):
            frappe.throw(_("Stream choices must be unique"))
        
        # Validate first choice is provided
        if not self.first_choice_stream:
            frappe.throw(_("First choice stream is required"))
        
        # Check stream availability for the academic year
        self.validate_stream_availability()
    
    def validate_stream_availability(self):
        """Validate stream availability."""
        for stream_field in ['first_choice_stream', 'second_choice_stream', 'third_choice_stream']:
            stream = getattr(self, stream_field)
            if stream:
                # Check if stream is active
                stream_doc = frappe.get_doc("Academic Stream", stream)
                if not stream_doc.is_active:
                    frappe.throw(_("Stream {0} is not currently available").format(stream))
                
                # Check capacity if defined
                if stream_doc.max_capacity:
                    current_enrollment = frappe.db.count("Orientation Choice", {
                        "final_decision": stream,
                        "status": "Approved",
                        "academic_year": self.academic_year
                    })
                    
                    if current_enrollment >= stream_doc.max_capacity:
                        frappe.msgprint(_("Warning: Stream {0} is at full capacity").format(stream))
    
    def validate_prerequisites(self):
        """Validate subject prerequisites."""
        if self.first_choice_stream:
            stream_doc = frappe.get_doc("Academic Stream", self.first_choice_stream)
            
            # Get student's academic performance
            student_grades = self.get_student_grades()
            
            # Check prerequisites for the stream
            if hasattr(stream_doc, 'prerequisites') and stream_doc.prerequisites:
                for prereq in stream_doc.prerequisites:
                    subject = prereq.subject
                    min_grade = flt(prereq.minimum_grade)
                    
                    student_grade = student_grades.get(subject, 0)
                    if student_grade < min_grade:
                        frappe.msgprint(_("Warning: Student grade in {0} ({1}) is below minimum requirement ({2})").format(
                            subject, student_grade, min_grade
                        ))
    
    def get_student_grades(self):
        """Get student's latest grades."""
        # Get latest assessment results for the student
        assessments = frappe.get_all("Assessment Result",
            filters={
                "student": self.student,
                "academic_year": self.academic_year
            },
            fields=["subject", "grade", "assessment_date"],
            order_by="assessment_date desc"
        )
        
        # Get the latest grade for each subject
        grades = {}
        for assessment in assessments:
            if assessment.subject not in grades:
                grades[assessment.subject] = flt(assessment.grade)
        
        return grades
    
    def validate_guardian_consent(self):
        """Validate guardian consent requirements."""
        if self.parent_guardian and not self.guardian_consent:
            if self.status in ["Submitted", "Under Review"]:
                frappe.throw(_("Guardian consent is required before submission"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.choice_date:
            self.choice_date = getdate()
        
        if not self.counselor and self.orientation_plan:
            # Get counselor from orientation plan
            plan_counselor = frappe.db.get_value("Orientation Plan", self.orientation_plan, "orientation_counselor")
            if plan_counselor:
                self.counselor = plan_counselor
        
        if not self.counselor:
            # Get default counselor from student assignment
            student_counselor = frappe.db.get_value("Student Counselor Assignment", 
                {"student": self.student, "status": "Active"}, "counselor")
            if student_counselor:
                self.counselor = student_counselor
    
    def on_submit(self):
        """Actions on submit."""
        self.status = "Submitted"
        self.submission_date = now_datetime()
        self.send_submission_notifications()
        self.create_review_tasks()
    
    def send_submission_notifications(self):
        """Send submission notifications."""
        # Notify counselor
        if self.counselor:
            self.send_counselor_notification()
        
        # Notify guardian
        if self.parent_guardian:
            self.send_guardian_notification()
        
        # Send confirmation to student
        self.send_student_confirmation()
    
    def send_counselor_notification(self):
        """Send notification to counselor."""
        counselor = frappe.get_doc("Employee", self.counselor)
        
        if counselor.user_id:
            frappe.sendmail(
                recipients=[counselor.user_id],
                subject=_("New Orientation Choice Submission - {0}").format(self.student_name),
                message=self.get_counselor_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_counselor_notification_message(self):
        """Get counselor notification message."""
        return _("""
        New Orientation Choice Submitted for Review
        
        Student: {student_name}
        Current Grade: {current_grade}
        Submission Date: {submission_date}
        
        Stream Choices:
        1st Choice: {first_choice} - {first_reason}
        2nd Choice: {second_choice} - {second_reason}
        3rd Choice: {third_choice} - {third_reason}
        
        Career Goals: {career_goals}
        University Aspirations: {university_aspirations}
        
        Student Confidence Level: {confidence}/5
        Guardian Consent: {consent_status}
        
        Student Comments:
        {student_comments}
        
        Please review and provide your recommendation.
        
        Academic Guidance Team
        """).format(
            student_name=self.student_name,
            current_grade=self.current_grade or "Not specified",
            submission_date=frappe.format(self.submission_date, "Datetime"),
            first_choice=self.first_choice_stream or "Not specified",
            first_reason=self.first_choice_reason or "No reason provided",
            second_choice=self.second_choice_stream or "Not specified",
            second_reason=self.second_choice_reason or "No reason provided",
            third_choice=self.third_choice_stream or "Not specified",
            third_reason=self.third_choice_reason or "No reason provided",
            career_goals=self.career_goals or "Not specified",
            university_aspirations=self.university_aspirations or "Not specified",
            confidence=self.student_confidence_level or "Not rated",
            consent_status="Given" if self.guardian_consent else "Pending",
            student_comments=self.student_comments or "No comments provided"
        )
    
    def send_guardian_notification(self):
        """Send notification to guardian."""
        guardian = frappe.get_doc("Guardian", self.parent_guardian)
        
        if guardian.email_address:
            frappe.sendmail(
                recipients=[guardian.email_address],
                subject=_("Orientation Choice Submitted - {0}").format(self.student_name),
                message=self.get_guardian_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_guardian_notification_message(self):
        """Get guardian notification message."""
        return _("""
        Dear Parent/Guardian,
        
        {student_name} has submitted their academic stream choices for review.
        
        Submission Summary:
        - Submission Date: {submission_date}
        - First Choice: {first_choice}
        - Second Choice: {second_choice}
        - Third Choice: {third_choice}
        
        Career Aspirations:
        {career_goals}
        
        University Plans:
        {university_aspirations}
        
        Your Consent Status: {consent_status}
        
        Next Steps:
        1. The orientation counselor will review the choices
        2. You may be contacted for additional input
        3. Final approval will be communicated to you
        4. Stream placement will be confirmed before the new academic year
        
        If you have any questions or concerns, please contact the orientation counselor.
        
        Thank you for your involvement in {student_name}'s academic journey.
        
        Best regards,
        Academic Guidance Team
        """).format(
            student_name=self.student_name,
            submission_date=frappe.format(self.submission_date, "Datetime"),
            first_choice=self.first_choice_stream or "Not specified",
            second_choice=self.second_choice_stream or "Not specified",
            third_choice=self.third_choice_stream or "Not specified",
            career_goals=self.career_goals or "Not specified",
            university_aspirations=self.university_aspirations or "Not specified",
            consent_status="Given" if self.guardian_consent else "Pending - Please provide consent"
        )
    
    def send_student_confirmation(self):
        """Send confirmation to student."""
        student = frappe.get_doc("Student", self.student)
        
        if student.student_email_id:
            frappe.sendmail(
                recipients=[student.student_email_id],
                subject=_("Your Stream Choices Have Been Submitted"),
                message=self.get_student_confirmation_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_student_confirmation_message(self):
        """Get student confirmation message."""
        return _("""
        Hi {student_name},
        
        Great news! Your academic stream choices have been successfully submitted.
        
        Your Choices:
        🥇 First Choice: {first_choice}
        🥈 Second Choice: {second_choice}
        🥉 Third Choice: {third_choice}
        
        What happens next:
        1. Your counselor will review your choices
        2. They may discuss your options with you
        3. Your parents/guardians will be involved in the final decision
        4. You'll receive confirmation of your stream placement
        
        Your confidence level: {confidence}/5 ⭐
        
        Remember, this is an important step in your academic journey, and we're here to support you every step of the way!
        
        If you have any questions or want to discuss your choices, don't hesitate to talk to your counselor.
        
        Best of luck!
        Academic Guidance Team
        """).format(
            student_name=self.student_name,
            first_choice=self.first_choice_stream or "Not specified",
            second_choice=self.second_choice_stream or "Not specified",
            third_choice=self.third_choice_stream or "Not specified",
            confidence=self.student_confidence_level or "Not rated"
        )
    
    def create_review_tasks(self):
        """Create review tasks for counselor."""
        # Create counselor review task
        review_task = frappe.get_doc({
            "doctype": "ToDo",
            "description": f"Review orientation choice: {self.name} for {self.student_name}",
            "reference_type": self.doctype,
            "reference_name": self.name,
            "assigned_by": frappe.session.user,
            "owner": frappe.get_value("Employee", self.counselor, "user_id") if self.counselor else frappe.session.user,
            "date": add_days(getdate(), 3),  # 3 days to review
            "priority": "Medium"
        })
        
        review_task.insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def approve_choice(self, recommendation, counselor_notes=None, final_decision=None):
        """Approve the orientation choice."""
        if self.status != "Under Review":
            self.status = "Under Review"
        
        self.counselor_recommendation = recommendation
        
        if counselor_notes:
            current_notes = self.counselor_notes or ""
            timestamp = now_datetime().strftime("%Y-%m-%d %H:%M")
            new_note = f"\n[{timestamp}] COUNSELOR REVIEW: {counselor_notes}"
            self.counselor_notes = current_notes + new_note
        
        if final_decision:
            self.final_decision = final_decision
        
        if recommendation in ["Strongly Recommend", "Recommend"]:
            self.approval_status = "Approved by Counselor"
            if self.guardian_consent:
                self.approval_status = "Fully Approved"
                self.status = "Approved"
                self.approval_date = getdate()
        elif recommendation == "Recommend with Conditions":
            self.approval_status = "Conditional Approval"
        else:
            self.approval_status = "Rejected"
            self.status = "Rejected"
        
        self.save()
        
        # Send approval notifications
        self.send_approval_notifications()
        
        frappe.msgprint(_("Choice reviewed and recommendation recorded"))
        return self
    
    def send_approval_notifications(self):
        """Send approval/rejection notifications."""
        # Notify student
        self.send_student_decision_notification()
        
        # Notify guardian
        if self.parent_guardian:
            self.send_guardian_decision_notification()
    
    def send_student_decision_notification(self):
        """Send decision notification to student."""
        student = frappe.get_doc("Student", self.student)
        
        if student.student_email_id:
            frappe.sendmail(
                recipients=[student.student_email_id],
                subject=_("Update on Your Stream Choice"),
                message=self.get_student_decision_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_student_decision_message(self):
        """Get student decision message."""
        if self.status == "Approved":
            return _("""
            Hi {student_name},
            
            Excellent news! Your stream choice has been approved! 🎉
            
            Final Decision: {final_decision}
            Counselor Recommendation: {recommendation}
            Approval Date: {approval_date}
            
            What this means:
            - You're all set for the {final_decision} stream
            - You can start preparing for your new academic path
            - Subject registration will open soon
            
            Congratulations on this important milestone in your academic journey!
            
            If you have any questions about your new stream, feel free to reach out to your counselor.
            
            Best wishes,
            Academic Guidance Team
            """).format(
                student_name=self.student_name,
                final_decision=self.final_decision or self.first_choice_stream,
                recommendation=self.counselor_recommendation,
                approval_date=frappe.format(self.approval_date, "Date")
            )
        elif self.approval_status == "Conditional Approval":
            return _("""
            Hi {student_name},
            
            Your stream choice has been reviewed with some conditions.
            
            Counselor Recommendation: {recommendation}
            
            Next Steps:
            - Meet with your counselor to discuss the conditions
            - Address any requirements or concerns
            - Finalize your stream selection
            
            Don't worry - this is just to ensure you're fully prepared for success in your chosen stream!
            
            Please schedule a meeting with your counselor to move forward.
            
            Academic Guidance Team
            """).format(
                student_name=self.student_name,
                recommendation=self.counselor_recommendation
            )
        else:
            return _("""
            Hi {student_name},
            
            Thank you for submitting your stream choices. After careful review, we need to discuss alternative options.
            
            Counselor Recommendation: {recommendation}
            
            This doesn't mean your goals aren't achievable - we just want to find the best path for your success!
            
            Next Steps:
            - Schedule a meeting with your counselor
            - Explore alternative streams that match your interests
            - Consider additional preparation options
            - Resubmit your choices when ready
            
            Remember, there are many paths to success, and we're here to help you find yours.
            
            Academic Guidance Team
            """).format(
                student_name=self.student_name,
                recommendation=self.counselor_recommendation
            )
    
    def send_guardian_decision_notification(self):
        """Send decision notification to guardian."""
        guardian = frappe.get_doc("Guardian", self.parent_guardian)
        
        if guardian.email_address:
            frappe.sendmail(
                recipients=[guardian.email_address],
                subject=_("Stream Choice Decision - {0}").format(self.student_name),
                message=self.get_guardian_decision_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_guardian_decision_message(self):
        """Get guardian decision message."""
        return _("""
        Dear Parent/Guardian,
        
        We have completed the review of {student_name}'s stream choice submission.
        
        Decision Summary:
        - Status: {status}
        - Counselor Recommendation: {recommendation}
        - Final Decision: {final_decision}
        
        Original Choices:
        1st Choice: {first_choice}
        2nd Choice: {second_choice}
        3rd Choice: {third_choice}
        
        {decision_details}
        
        If you have any questions or would like to discuss this decision, please contact the orientation counselor.
        
        Thank you for your continued involvement in {student_name}'s education.
        
        Best regards,
        Academic Guidance Team
        """).format(
            student_name=self.student_name,
            status=self.status,
            recommendation=self.counselor_recommendation or "Pending",
            final_decision=self.final_decision or "To be determined",
            first_choice=self.first_choice_stream,
            second_choice=self.second_choice_stream or "None",
            third_choice=self.third_choice_stream or "None",
            decision_details=self.get_decision_details_for_guardian()
        )
    
    def get_decision_details_for_guardian(self):
        """Get decision details for guardian message."""
        if self.status == "Approved":
            return _("""
            Great news! {student_name}'s choice has been approved. They will be placed in the {final_decision} stream for the upcoming academic year.
            
            Next steps:
            - Subject registration will begin soon
            - Orientation sessions will be scheduled
            - Academic requirements will be communicated
            """).format(
                student_name=self.student_name,
                final_decision=self.final_decision or self.first_choice_stream
            )
        elif self.approval_status == "Conditional Approval":
            return _("""
            The choice requires some additional considerations. Please schedule a meeting with the counselor to discuss the conditions and next steps.
            """)
        else:
            return _("""
            Alternative options need to be explored. The counselor will work with you and {student_name} to find the best academic path forward.
            """).format(student_name=self.student_name)
    
    @frappe.whitelist()
    def request_revision(self, revision_reason):
        """Request revision of the choice."""
        if self.status in ["Approved", "Rejected"]:
            frappe.throw(_("Cannot request revision for {0} choice").format(self.status.lower()))
        
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
        # Notify student
        student = frappe.get_doc("Student", self.student)
        if student.student_email_id:
            frappe.sendmail(
                recipients=[student.student_email_id],
                subject=_("Please Revise Your Stream Choice"),
                message=self.get_revision_request_message(reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
        
        # Notify guardian
        if self.parent_guardian:
            guardian = frappe.get_doc("Guardian", self.parent_guardian)
            if guardian.email_address:
                frappe.sendmail(
                    recipients=[guardian.email_address],
                    subject=_("Stream Choice Revision Required - {0}").format(self.student_name),
                    message=self.get_guardian_revision_message(reason),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
    
    def get_revision_request_message(self, reason):
        """Get revision request message for student."""
        return _("""
        Hi {student_name},
        
        Your counselor has reviewed your stream choices and would like you to make some revisions.
        
        Reason for Revision:
        {reason}
        
        What you need to do:
        1. Review your current choices
        2. Consider the feedback provided
        3. Make necessary changes to your submission
        4. Resubmit your updated choices
        
        Don't worry - this is a normal part of the process to ensure you make the best choice for your future!
        
        If you need help or have questions, please talk to your counselor.
        
        Academic Guidance Team
        """).format(
            student_name=self.student_name,
            reason=reason
        )
    
    def get_guardian_revision_message(self, reason):
        """Get revision request message for guardian."""
        return _("""
        Dear Parent/Guardian,
        
        The counselor has requested revisions to {student_name}'s stream choice submission.
        
        Reason for Revision:
        {reason}
        
        Please discuss this with {student_name} and help them make any necessary adjustments to their choices.
        
        If you have any questions, please contact the orientation counselor.
        
        Thank you for your cooperation.
        
        Academic Guidance Team
        """).format(
            student_name=self.student_name,
            reason=reason
        )
    
    @frappe.whitelist()
    def provide_guardian_consent(self, consent_comments=None):
        """Provide guardian consent."""
        if not self.parent_guardian:
            frappe.throw(_("No guardian assigned to provide consent"))
        
        self.guardian_consent = 1
        
        if consent_comments:
            self.parent_comments = consent_comments
        
        # Update approval status if counselor has already approved
        if self.approval_status == "Approved by Counselor":
            self.approval_status = "Fully Approved"
            self.status = "Approved"
            self.approval_date = getdate()
        
        self.save()
        
        # Send consent confirmation
        self.send_consent_confirmation()
        
        frappe.msgprint(_("Guardian consent provided"))
        return self
    
    def send_consent_confirmation(self):
        """Send consent confirmation notifications."""
        # Notify counselor
        if self.counselor:
            counselor = frappe.get_doc("Employee", self.counselor)
            if counselor.user_id:
                frappe.sendmail(
                    recipients=[counselor.user_id],
                    subject=_("Guardian Consent Provided - {0}").format(self.student_name),
                    message=self.get_consent_confirmation_message(),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        # Notify student
        student = frappe.get_doc("Student", self.student)
        if student.student_email_id:
            frappe.sendmail(
                recipients=[student.student_email_id],
                subject=_("Guardian Consent Received"),
                message=self.get_student_consent_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_consent_confirmation_message(self):
        """Get consent confirmation message for counselor."""
        return _("""
        Guardian Consent Received
        
        Student: {student_name}
        Choice: {choice_name}
        Guardian: {guardian_name}
        
        Guardian Comments:
        {guardian_comments}
        
        Current Status: {status}
        Approval Status: {approval_status}
        
        {next_steps}
        
        Academic Guidance Team
        """).format(
            student_name=self.student_name,
            choice_name=self.name,
            guardian_name=frappe.get_value("Guardian", self.parent_guardian, "guardian_name") if self.parent_guardian else "Not specified",
            guardian_comments=self.parent_comments or "No comments provided",
            status=self.status,
            approval_status=self.approval_status,
            next_steps="The choice is now fully approved." if self.status == "Approved" else "Please complete your review and approval."
        )
    
    def get_student_consent_message(self):
        """Get consent confirmation message for student."""
        return _("""
        Hi {student_name},
        
        Great news! Your parent/guardian has provided consent for your stream choice.
        
        Current Status: {status}
        
        {status_message}
        
        Academic Guidance Team
        """).format(
            student_name=self.student_name,
            status=self.status,
            status_message="Your choice is now fully approved! 🎉" if self.status == "Approved" else "Your submission is being processed."
        )
    
    @frappe.whitelist()
    def get_choice_analytics(self):
        """Get choice analytics and insights."""
        # Get student's academic performance
        student_grades = self.get_student_grades()
        
        # Get stream statistics
        stream_stats = {}
        for stream_field in ['first_choice_stream', 'second_choice_stream', 'third_choice_stream']:
            stream = getattr(self, stream_field)
            if stream:
                # Get stream enrollment statistics
                total_choices = frappe.db.count("Orientation Choice", {
                    stream_field: stream,
                    "academic_year": self.academic_year
                })
                
                approved_choices = frappe.db.count("Orientation Choice", {
                    "final_decision": stream,
                    "status": "Approved",
                    "academic_year": self.academic_year
                })
                
                stream_stats[stream] = {
                    "total_applications": total_choices,
                    "approved_applications": approved_choices,
                    "choice_rank": stream_field.replace('_choice_stream', '').replace('_', ' ').title()
                }
        
        # Get counselor's recommendation history
        counselor_stats = {}
        if self.counselor:
            counselor_recommendations = frappe.get_all("Orientation Choice",
                filters={"counselor": self.counselor, "academic_year": self.academic_year},
                fields=["counselor_recommendation"],
                group_by="counselor_recommendation"
            )
            
            for rec in counselor_recommendations:
                recommendation = rec.counselor_recommendation
                if recommendation:
                    count = frappe.db.count("Orientation Choice", {
                        "counselor": self.counselor,
                        "counselor_recommendation": recommendation,
                        "academic_year": self.academic_year
                    })
                    counselor_stats[recommendation] = count
        
        return {
            "choice_summary": {
                "name": self.name,
                "student": self.student_name,
                "status": self.status,
                "approval_status": self.approval_status,
                "submission_date": self.submission_date,
                "approval_date": self.approval_date
            },
            "student_performance": {
                "current_grades": student_grades,
                "confidence_level": self.student_confidence_level,
                "parent_satisfaction": self.parent_satisfaction
            },
            "stream_statistics": stream_stats,
            "counselor_statistics": counselor_stats,
            "choices": {
                "first_choice": {
                    "stream": self.first_choice_stream,
                    "reason": self.first_choice_reason
                },
                "second_choice": {
                    "stream": self.second_choice_stream,
                    "reason": self.second_choice_reason
                },
                "third_choice": {
                    "stream": self.third_choice_stream,
                    "reason": self.third_choice_reason
                }
            },
            "final_outcome": {
                "final_decision": self.final_decision,
                "counselor_recommendation": self.counselor_recommendation,
                "follow_up_required": self.follow_up_required
            }
        }
    
    def get_choice_summary(self):
        """Get choice summary for reporting."""
        return {
            "choice_name": self.name,
            "student": self.student_name,
            "current_grade": self.current_grade,
            "status": self.status,
            "approval_status": self.approval_status,
            "first_choice": self.first_choice_stream,
            "second_choice": self.second_choice_stream,
            "third_choice": self.third_choice_stream,
            "final_decision": self.final_decision,
            "counselor_recommendation": self.counselor_recommendation,
            "submission_date": self.submission_date,
            "approval_date": self.approval_date,
            "guardian_consent": self.guardian_consent,
            "student_confidence": self.student_confidence_level,
            "parent_satisfaction": self.parent_satisfaction,
            "follow_up_required": self.follow_up_required,
            "academic_year": self.academic_year
        }
