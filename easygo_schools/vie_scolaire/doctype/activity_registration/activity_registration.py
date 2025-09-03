"""Activity Registration DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, flt, cint


class ActivityRegistration(Document):
    """Activity Registration management."""
    
    def validate(self):
        """Validate activity registration data."""
        self.validate_activity_capacity()
        self.validate_guardian_consent()
        self.validate_registration_period()
        self.set_defaults()
    
    def validate_activity_capacity(self):
        """Validate activity capacity limits."""
        if self.activity:
            activity_doc = frappe.get_doc("Extracurricular Activity", self.activity)
            
            # Count current active registrations
            current_registrations = frappe.db.count("Activity Registration", {
                "activity": self.activity,
                "status": ["in", ["Approved", "Active"]],
                "name": ["!=", self.name or ""]
            })
            
            if current_registrations >= activity_doc.max_participants:
                if self.status not in ["Waitlisted", "Withdrawn"]:
                    self.status = "Waitlisted"
                    frappe.msgprint(_("Activity is at full capacity. Registration added to waitlist."))
    
    def validate_guardian_consent(self):
        """Validate guardian consent requirements."""
        if self.guardian_consent and not self.consent_date:
            self.consent_date = getdate()
        
        if not self.guardian_consent and self.status in ["Approved", "Active"]:
            frappe.throw(_("Guardian consent is required before approval"))
    
    def validate_registration_period(self):
        """Validate registration timing."""
        if self.activity:
            activity_doc = frappe.get_doc("Extracurricular Activity", self.activity)
            
            if activity_doc.registration_start_date and self.registration_date < activity_doc.registration_start_date:
                frappe.throw(_("Registration period has not started yet"))
            
            if activity_doc.registration_end_date and self.registration_date > activity_doc.registration_end_date:
                frappe.throw(_("Registration period has ended"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.registration_date:
            self.registration_date = getdate()
        
        if self.activity:
            activity_doc = frappe.get_doc("Extracurricular Activity", self.activity)
            
            if not self.start_date and activity_doc.start_date:
                self.start_date = activity_doc.start_date
            
            if not self.end_date and activity_doc.end_date:
                self.end_date = activity_doc.end_date
            
            if activity_doc.fees_applicable and not self.fees_applicable:
                self.fees_applicable = 1
                self.registration_fee = activity_doc.registration_fee
        
        # Set emergency contact from student guardian
        if self.student and not self.emergency_contact:
            guardian = frappe.db.get_value("Student Guardian", 
                {"parent": self.student, "is_primary_contact": 1}, 
                ["guardian", "guardian_name"])
            
            if guardian:
                self.emergency_contact = guardian[1] if isinstance(guardian, tuple) else guardian
                guardian_doc = frappe.get_doc("Guardian", guardian[0] if isinstance(guardian, tuple) else guardian)
                if guardian_doc.mobile_number:
                    self.emergency_phone = guardian_doc.mobile_number
    
    def on_submit(self):
        """Actions on submit."""
        if self.status == "Pending":
            self.process_registration()
        
        self.send_registration_confirmation()
        self.create_payment_entry()
    
    def process_registration(self):
        """Process the registration based on capacity."""
        activity_doc = frappe.get_doc("Extracurricular Activity", self.activity)
        
        # Check if approval is required
        if activity_doc.requires_approval:
            self.status = "Pending"
            self.send_approval_request()
        else:
            # Auto-approve if capacity allows
            current_registrations = frappe.db.count("Activity Registration", {
                "activity": self.activity,
                "status": ["in", ["Approved", "Active"]]
            })
            
            if current_registrations < activity_doc.max_participants:
                self.status = "Approved"
                self.approved_by = frappe.session.user
                self.approval_date = getdate()
            else:
                self.status = "Waitlisted"
    
    def send_approval_request(self):
        """Send approval request to activities coordinator."""
        coordinator = frappe.db.get_single_value("School Settings", "activities_coordinator")
        
        if coordinator:
            frappe.sendmail(
                recipients=[coordinator],
                subject=_("Activity Registration Approval Required - {0}").format(self.name),
                message=self.get_approval_request_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_approval_request_message(self):
        """Get approval request message."""
        return _("""
        A new activity registration requires your approval:
        
        Registration: {registration_name}
        Student: {student_name}
        Activity: {activity_name}
        Registration Date: {registration_date}
        
        Student Information:
        - Skill Level: {skill_level}
        - Previous Experience: {previous_experience}
        - Special Requirements: {special_requirements}
        
        Guardian Consent: {consent_status}
        Medical Clearance: {medical_status}
        
        Please review and approve/reject this registration.
        """).format(
            registration_name=self.name,
            student_name=self.student_name,
            activity_name=self.activity_name,
            registration_date=frappe.format(self.registration_date, "Date"),
            skill_level=self.skill_level or "Not specified",
            previous_experience=self.previous_experience or "None",
            special_requirements=self.special_requirements or "None",
            consent_status="Given" if self.guardian_consent else "Pending",
            medical_status="Required" if self.medical_clearance else "Not required"
        )
    
    def send_registration_confirmation(self):
        """Send registration confirmation to student and guardians."""
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
                subject=_("Activity Registration Confirmation - {0}").format(self.activity_name),
                message=self.get_registration_confirmation_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_registration_confirmation_message(self):
        """Get registration confirmation message."""
        return _("""
        Dear Student/Guardian,
        
        Thank you for registering for the extracurricular activity.
        
        Registration Details:
        - Registration Number: {registration_name}
        - Student: {student_name}
        - Activity: {activity_name}
        - Status: {status}
        
        Activity Period:
        - Start Date: {start_date}
        - End Date: {end_date}
        
        {payment_info}
        
        {status_message}
        
        If you have any questions, please contact the Activities Coordinator.
        
        Activities Team
        """).format(
            registration_name=self.name,
            student_name=self.student_name,
            activity_name=self.activity_name,
            status=self.status,
            start_date=frappe.format(self.start_date, "Date") if self.start_date else "TBA",
            end_date=frappe.format(self.end_date, "Date") if self.end_date else "TBA",
            payment_info=self.get_payment_info_message(),
            status_message=self.get_status_message()
        )
    
    def get_payment_info_message(self):
        """Get payment information message."""
        if self.fees_applicable:
            return f"""
        Payment Information:
        - Registration Fee: {frappe.format_value(self.registration_fee, "Currency")}
        - Payment Status: {self.payment_status}
        {f"- Payment Reference: {self.payment_reference}" if self.payment_reference else ""}
        """
        return "No fees applicable for this activity."
    
    def get_status_message(self):
        """Get status-specific message."""
        if self.status == "Pending":
            return "Your registration is pending approval. You will be notified once it's reviewed."
        elif self.status == "Approved":
            return "Your registration has been approved! You will receive activity schedules soon."
        elif self.status == "Waitlisted":
            return "The activity is currently full. You have been added to the waitlist and will be notified if a spot becomes available."
        elif self.status == "Active":
            return "Your registration is active. Please attend scheduled sessions regularly."
        return ""
    
    def create_payment_entry(self):
        """Create payment entry if fees are applicable."""
        if self.fees_applicable and self.registration_fee and self.payment_status == "Unpaid":
            payment_request = frappe.get_doc({
                "doctype": "Payment Request",
                "payment_request_type": "Inward",
                "party_type": "Student",
                "party": self.student,
                "reference_doctype": self.doctype,
                "reference_name": self.name,
                "grand_total": self.registration_fee,
                "currency": frappe.defaults.get_global_default("currency"),
                "subject": f"Activity Registration Fee - {self.activity_name}"
            })
            payment_request.insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def approve_registration(self, approval_notes=None):
        """Approve the registration."""
        if self.status != "Pending":
            frappe.throw(_("Only pending registrations can be approved"))
        
        # Check capacity again
        activity_doc = frappe.get_doc("Extracurricular Activity", self.activity)
        current_registrations = frappe.db.count("Activity Registration", {
            "activity": self.activity,
            "status": ["in", ["Approved", "Active"]]
        })
        
        if current_registrations >= activity_doc.max_participants:
            frappe.throw(_("Activity is at full capacity"))
        
        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approval_date = getdate()
        
        if approval_notes:
            self.add_comment("Comment", f"Approved: {approval_notes}")
        
        self.save()
        
        # Send approval notification
        self.send_approval_notification()
        
        frappe.msgprint(_("Registration approved successfully"))
        return self
    
    def send_approval_notification(self):
        """Send approval notification."""
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
                subject=_("Activity Registration Approved - {0}").format(self.activity_name),
                message=self.get_approval_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_approval_notification_message(self):
        """Get approval notification message."""
        return _("""
        Dear Student/Guardian,
        
        Great news! Your activity registration has been approved.
        
        Registration: {registration_name}
        Activity: {activity_name}
        Approved By: {approved_by}
        Approval Date: {approval_date}
        
        Next Steps:
        1. Complete payment if applicable
        2. Attend orientation session (if scheduled)
        3. Prepare required equipment/materials
        4. Check activity schedules regularly
        
        Welcome to {activity_name}!
        
        Activities Team
        """).format(
            registration_name=self.name,
            activity_name=self.activity_name,
            approved_by=self.approved_by,
            approval_date=frappe.format(self.approval_date, "Date")
        )
    
    @frappe.whitelist()
    def reject_registration(self, rejection_reason):
        """Reject the registration."""
        if self.status != "Pending":
            frappe.throw(_("Only pending registrations can be rejected"))
        
        self.status = "Withdrawn"
        self.withdrawal_date = getdate()
        self.withdrawal_reason = rejection_reason
        
        self.add_comment("Comment", f"Rejected: {rejection_reason}")
        self.save()
        
        # Send rejection notification
        self.send_rejection_notification(rejection_reason)
        
        frappe.msgprint(_("Registration rejected"))
        return self
    
    def send_rejection_notification(self, reason):
        """Send rejection notification."""
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
                subject=_("Activity Registration Update - {0}").format(self.activity_name),
                message=self.get_rejection_notification_message(reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_rejection_notification_message(self, reason):
        """Get rejection notification message."""
        return _("""
        Dear Student/Guardian,
        
        We regret to inform you that your activity registration could not be approved at this time.
        
        Registration: {registration_name}
        Activity: {activity_name}
        
        Reason:
        {reason}
        
        You are welcome to apply again in the future or explore other available activities.
        
        Activities Team
        """).format(
            registration_name=self.name,
            activity_name=self.activity_name,
            reason=reason
        )
    
    @frappe.whitelist()
    def activate_registration(self):
        """Activate approved registration."""
        if self.status != "Approved":
            frappe.throw(_("Only approved registrations can be activated"))
        
        # Check payment if fees applicable
        if self.fees_applicable and self.payment_status != "Paid":
            frappe.throw(_("Payment must be completed before activation"))
        
        self.status = "Active"
        self.save()
        
        # Update session counts
        self.update_session_counts()
        
        frappe.msgprint(_("Registration activated"))
        return self
    
    def update_session_counts(self):
        """Update total sessions count."""
        if self.activity:
            # Count scheduled sessions for this activity
            total_sessions = frappe.db.count("Activity Schedule", {
                "activity": self.activity,
                "schedule_date": ["between", [self.start_date, self.end_date]],
                "status": ["!=", "Cancelled"]
            })
            
            self.total_sessions = total_sessions
            
            # Count attended sessions
            attended_sessions = frappe.db.count("Activity Attendance", {
                "student": self.student,
                "activity_schedule": ["in", frappe.get_all("Activity Schedule", 
                    filters={"activity": self.activity}, pluck="name")],
                "status": "Present"
            })
            
            self.sessions_attended = attended_sessions
            self.save()
    
    @frappe.whitelist()
    def withdraw_registration(self, withdrawal_reason):
        """Withdraw from activity."""
        if self.status in ["Withdrawn", "Completed"]:
            frappe.throw(_("Cannot withdraw from {0} registration").format(self.status.lower()))
        
        self.status = "Withdrawn"
        self.withdrawal_date = getdate()
        self.withdrawal_reason = withdrawal_reason
        
        # Process refund if applicable
        if self.fees_applicable and self.payment_status == "Paid":
            self.calculate_refund()
        
        self.save()
        
        # Send withdrawal confirmation
        self.send_withdrawal_confirmation()
        
        # Move waitlisted student up if any
        self.promote_waitlisted_student()
        
        frappe.msgprint(_("Registration withdrawn successfully"))
        return self
    
    def calculate_refund(self):
        """Calculate refund amount based on withdrawal timing."""
        if not self.start_date:
            return
        
        days_before_start = (getdate(self.start_date) - getdate()).days
        
        # Refund policy based on withdrawal timing
        if days_before_start >= 7:
            refund_percentage = 100  # Full refund
        elif days_before_start >= 3:
            refund_percentage = 50   # 50% refund
        else:
            refund_percentage = 0    # No refund
        
        self.refund_amount = flt(self.registration_fee) * refund_percentage / 100
        
        if self.refund_amount > 0:
            self.refund_status = "Pending"
            self.process_refund()
    
    def process_refund(self):
        """Process refund payment."""
        if self.refund_amount > 0:
            # Create refund entry
            refund_entry = frappe.get_doc({
                "doctype": "Payment Entry",
                "payment_type": "Pay",
                "party_type": "Student",
                "party": self.student,
                "paid_amount": self.refund_amount,
                "received_amount": self.refund_amount,
                "reference_no": f"Refund-{self.name}",
                "reference_date": getdate(),
                "remarks": f"Activity registration refund for {self.name}"
            })
            
            refund_entry.insert(ignore_permissions=True)
            refund_entry.submit()
            
            self.refund_status = "Processed"
            self.payment_status = "Refunded"
    
    def promote_waitlisted_student(self):
        """Promote next waitlisted student."""
        waitlisted = frappe.get_all("Activity Registration",
            filters={
                "activity": self.activity,
                "status": "Waitlisted"
            },
            fields=["name", "student_name"],
            order_by="registration_date asc",
            limit=1
        )
        
        if waitlisted:
            waitlisted_reg = frappe.get_doc("Activity Registration", waitlisted[0].name)
            waitlisted_reg.status = "Approved"
            waitlisted_reg.approved_by = "System"
            waitlisted_reg.approval_date = getdate()
            waitlisted_reg.save()
            
            # Send promotion notification
            waitlisted_reg.send_waitlist_promotion_notification()
    
    def send_waitlist_promotion_notification(self):
        """Send waitlist promotion notification."""
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
                subject=_("Waitlist Update - Spot Available for {0}").format(self.activity_name),
                message=self.get_waitlist_promotion_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_waitlist_promotion_message(self):
        """Get waitlist promotion message."""
        return _("""
        Dear Student/Guardian,
        
        Great news! A spot has become available in the activity you were waitlisted for.
        
        Activity: {activity_name}
        Registration: {registration_name}
        
        Your registration has been automatically approved. Please complete the following steps:
        
        1. Complete payment if applicable
        2. Confirm your participation
        3. Prepare for the activity
        
        Please respond within 48 hours to confirm your participation, or the spot will be offered to the next person on the waitlist.
        
        Activities Team
        """).format(
            activity_name=self.activity_name,
            registration_name=self.name
        )
    
    def send_withdrawal_confirmation(self):
        """Send withdrawal confirmation."""
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
                subject=_("Activity Registration Withdrawal Confirmation - {0}").format(self.activity_name),
                message=self.get_withdrawal_confirmation_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_withdrawal_confirmation_message(self):
        """Get withdrawal confirmation message."""
        refund_info = ""
        if self.refund_amount > 0:
            refund_info = f"""
        Refund Information:
        - Refund Amount: {frappe.format_value(self.refund_amount, "Currency")}
        - Refund Status: {self.refund_status}
        """
        
        return _("""
        Dear Student/Guardian,
        
        Your withdrawal from the activity has been processed.
        
        Registration: {registration_name}
        Activity: {activity_name}
        Withdrawal Date: {withdrawal_date}
        Reason: {withdrawal_reason}
        
        {refund_info}
        
        Thank you for your participation. You are welcome to register for other activities.
        
        Activities Team
        """).format(
            registration_name=self.name,
            activity_name=self.activity_name,
            withdrawal_date=frappe.format(self.withdrawal_date, "Date"),
            withdrawal_reason=self.withdrawal_reason,
            refund_info=refund_info
        )
    
    @frappe.whitelist()
    def get_registration_analytics(self):
        """Get registration analytics and insights."""
        # Get attendance statistics
        attendance_stats = frappe.db.sql("""
            SELECT 
                aa.status,
                COUNT(*) as count
            FROM `tabActivity Attendance` aa
            JOIN `tabActivity Schedule` acs ON aa.activity_schedule = acs.name
            WHERE acs.activity = %s AND aa.student = %s
            GROUP BY aa.status
        """, [self.activity, self.student], as_dict=True)
        
        # Calculate attendance rate
        attendance_rate = (self.sessions_attended / self.total_sessions * 100) if self.total_sessions else 0
        
        # Get activity progress
        activity_doc = frappe.get_doc("Extracurricular Activity", self.activity)
        
        return {
            "registration_info": {
                "name": self.name,
                "student": self.student_name,
                "activity": self.activity_name,
                "status": self.status,
                "registration_date": self.registration_date
            },
            "participation": {
                "sessions_attended": self.sessions_attended,
                "total_sessions": self.total_sessions,
                "attendance_rate": attendance_rate,
                "skill_level": self.skill_level
            },
            "attendance_breakdown": attendance_stats,
            "payment_info": {
                "fees_applicable": self.fees_applicable,
                "registration_fee": self.registration_fee,
                "payment_status": self.payment_status,
                "refund_amount": self.refund_amount
            },
            "activity_details": {
                "start_date": self.start_date,
                "end_date": self.end_date,
                "category": activity_doc.category,
                "difficulty_level": activity_doc.difficulty_level
            }
        }
    
    def get_registration_summary(self):
        """Get registration summary for reporting."""
        return {
            "registration_name": self.name,
            "student": self.student_name,
            "activity": self.activity_name,
            "registration_date": self.registration_date,
            "status": self.status,
            "approval_date": self.approval_date,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "sessions_attended": self.sessions_attended,
            "total_sessions": self.total_sessions,
            "attendance_rate": (self.sessions_attended / self.total_sessions * 100) if self.total_sessions else 0,
            "fees_applicable": self.fees_applicable,
            "registration_fee": self.registration_fee,
            "payment_status": self.payment_status,
            "guardian_consent": self.guardian_consent,
            "skill_level": self.skill_level
        }
