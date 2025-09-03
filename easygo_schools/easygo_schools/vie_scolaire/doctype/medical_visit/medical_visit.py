"""Medical Visit DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, get_time, flt


class MedicalVisit(Document):
    """Medical Visit management."""
    
    def validate(self):
        """Validate medical visit data."""
        self.validate_vital_signs()
        self.validate_follow_up()
        self.set_defaults()
    
    def validate_vital_signs(self):
        """Validate vital signs ranges."""
        if self.temperature and (flt(self.temperature) < 35 or flt(self.temperature) > 42):
            frappe.msgprint(_("Warning: Temperature reading seems unusual"), alert=True)
        
        if self.pulse_rate and (self.pulse_rate < 40 or self.pulse_rate > 200):
            frappe.msgprint(_("Warning: Pulse rate reading seems unusual"), alert=True)
        
        if self.respiratory_rate and (self.respiratory_rate < 8 or self.respiratory_rate > 40):
            frappe.msgprint(_("Warning: Respiratory rate reading seems unusual"), alert=True)
    
    def validate_follow_up(self):
        """Validate follow-up requirements."""
        if self.follow_up_required and not self.follow_up_date:
            frappe.throw(_("Follow-up date is required when follow-up is needed"))
        
        if self.follow_up_date and getdate(self.follow_up_date) <= getdate(self.visit_date):
            frappe.throw(_("Follow-up date must be after visit date"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.healthcare_provider:
            self.healthcare_provider = frappe.session.user
        
        if not self.visit_time:
            self.visit_time = get_time()
        
        if not self.status:
            self.status = "In Progress"
    
    def on_update(self):
        """Actions after update."""
        if self.status == "Completed":
            self.update_health_record()
            if self.parent_notified:
                self.notify_parents()
            if self.follow_up_required:
                self.schedule_follow_up()
    
    def update_health_record(self):
        """Update student's health record."""
        health_record = frappe.db.exists("Health Record", {"student": self.student})
        
        if health_record:
            health_doc = frappe.get_doc("Health Record", health_record)
        else:
            health_doc = frappe.get_doc({
                "doctype": "Health Record",
                "student": self.student,
                "student_name": self.student_name
            })
            health_doc.insert(ignore_permissions=True)
        
        # Update latest measurements
        if self.weight:
            health_doc.current_weight = self.weight
        if self.height:
            health_doc.current_height = self.height
        
        # Add visit to medical history
        health_doc.append("medical_history", {
            "visit_date": self.visit_date,
            "visit_type": self.visit_type,
            "diagnosis": self.diagnosis,
            "treatment": self.treatment_given,
            "healthcare_provider": self.healthcare_provider
        })
        
        health_doc.save(ignore_permissions=True)
    
    @frappe.whitelist()
    def complete_visit(self):
        """Complete the medical visit."""
        if self.status == "Completed":
            frappe.throw(_("Visit is already completed"))
        
        if not self.diagnosis:
            frappe.throw(_("Diagnosis is required to complete the visit"))
        
        self.status = "Completed"
        self.save()
        
        frappe.msgprint(_("Medical visit completed successfully"))
        return self
    
    @frappe.whitelist()
    def prescribe_medication(self, medication, dosage, frequency, duration, instructions=None):
        """Prescribe medication during visit."""
        self.append("medications_prescribed", {
            "medication": medication,
            "dosage": dosage,
            "frequency": frequency,
            "duration": duration,
            "instructions": instructions
        })
        
        self.save()
        
        frappe.msgprint(_("Medication prescribed: {0}").format(medication))
        return self
    
    @frappe.whitelist()
    def refer_student(self, specialist, reason, urgency="Normal"):
        """Refer student to specialist."""
        self.referred_to = specialist
        self.referral_reason = reason
        
        # Create referral document
        referral = frappe.get_doc({
            "doctype": "Medical Referral",
            "student": self.student,
            "student_name": self.student_name,
            "medical_visit": self.name,
            "referred_to": specialist,
            "referral_reason": reason,
            "urgency": urgency,
            "referring_provider": self.healthcare_provider,
            "referral_date": getdate(),
            "status": "Pending"
        })
        
        referral.insert(ignore_permissions=True)
        
        self.save()
        
        # Notify parents about referral
        self.notify_parents_referral(specialist, reason)
        
        frappe.msgprint(_("Student referred to {0}").format(specialist))
        return referral.name
    
    def schedule_follow_up(self):
        """Schedule follow-up appointment."""
        if not self.follow_up_date:
            return
        
        follow_up = frappe.get_doc({
            "doctype": "Medical Visit",
            "student": self.student,
            "student_name": self.student_name,
            "visit_date": self.follow_up_date,
            "visit_type": "Follow-up",
            "status": "Scheduled",
            "healthcare_provider": self.healthcare_provider,
            "chief_complaint": f"Follow-up for: {self.diagnosis}",
            "visit_notes": f"Follow-up visit for medical visit: {self.name}"
        })
        
        follow_up.insert(ignore_permissions=True)
        
        # Notify healthcare provider
        self.notify_follow_up_scheduled(follow_up.name)
        
        return follow_up.name
    
    def notify_parents(self):
        """Notify parents about medical visit."""
        # Get student's guardians
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            
            if guardian.email_address:
                frappe.sendmail(
                    recipients=[guardian.email_address],
                    subject=_("Medical Visit Update: {0}").format(self.student_name),
                    message=self.get_parent_notification_message(),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
            
            if guardian.mobile_number and self.notification_method == "SMS":
                self.send_parent_sms(guardian.mobile_number)
    
    def notify_parents_referral(self, specialist, reason):
        """Notify parents about medical referral."""
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            
            if guardian.email_address:
                frappe.sendmail(
                    recipients=[guardian.email_address],
                    subject=_("Medical Referral: {0}").format(self.student_name),
                    message=self.get_referral_message(specialist, reason),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
    
    def notify_follow_up_scheduled(self, follow_up_name):
        """Notify about scheduled follow-up."""
        if self.healthcare_provider:
            frappe.sendmail(
                recipients=[self.healthcare_provider],
                subject=_("Follow-up Scheduled: {0}").format(self.student_name),
                message=self.get_follow_up_message(follow_up_name),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_parent_notification_message(self):
        """Get parent notification message."""
        return _("""
        Medical Visit Update
        
        Student: {student_name}
        Visit Date: {visit_date}
        Visit Type: {visit_type}
        Healthcare Provider: {healthcare_provider}
        
        Chief Complaint: {chief_complaint}
        Diagnosis: {diagnosis}
        
        Treatment Given:
        {treatment_given}
        
        Recommendations:
        {recommendations}
        
        {follow_up_info}
        
        If you have any questions, please contact the school health office.
        
        School Health Team
        """).format(
            student_name=self.student_name,
            visit_date=self.visit_date,
            visit_type=self.visit_type,
            healthcare_provider=self.healthcare_provider,
            chief_complaint=self.chief_complaint,
            diagnosis=self.diagnosis or "Not specified",
            treatment_given=self.treatment_given or "None",
            recommendations=self.recommendations or "None",
            follow_up_info=f"Follow-up required on: {self.follow_up_date}" if self.follow_up_required else "No follow-up required"
        )
    
    def get_referral_message(self, specialist, reason):
        """Get referral notification message."""
        return _("""
        Medical Referral Notice
        
        Student: {student_name}
        Visit Date: {visit_date}
        Healthcare Provider: {healthcare_provider}
        
        Your child has been referred to: {specialist}
        Reason for Referral: {reason}
        
        Please contact the specialist to schedule an appointment.
        
        If you have any questions, please contact the school health office.
        
        School Health Team
        """).format(
            student_name=self.student_name,
            visit_date=self.visit_date,
            healthcare_provider=self.healthcare_provider,
            specialist=specialist,
            reason=reason
        )
    
    def get_follow_up_message(self, follow_up_name):
        """Get follow-up notification message."""
        return _("""
        Follow-up Appointment Scheduled
        
        Student: {student_name}
        Original Visit: {visit_date}
        Follow-up Date: {follow_up_date}
        Follow-up Visit ID: {follow_up_name}
        
        Reason for Follow-up: {diagnosis}
        
        Please ensure the student attends the follow-up appointment.
        """).format(
            student_name=self.student_name,
            visit_date=self.visit_date,
            follow_up_date=self.follow_up_date,
            follow_up_name=follow_up_name,
            diagnosis=self.diagnosis
        )
    
    def send_parent_sms(self, mobile_number):
        """Send SMS to parent."""
        message = _("Medical visit update for {0} on {1}. Please check your email for details. School: {2}").format(
            self.student_name,
            self.visit_date,
            frappe.db.get_single_value("School Settings", "school_name")
        )
        
        # Use SMS adapter
        from easygo_education.finances_rh.adapters.sms import send_sms
        send_sms(mobile_number, message)
    
    @frappe.whitelist()
    def get_student_medical_history(self):
        """Get student's medical history."""
        return frappe.get_all("Medical Visit",
            filters={"student": self.student},
            fields=["name", "visit_date", "visit_type", "diagnosis", "healthcare_provider"],
            order_by="visit_date desc",
            limit=10
        )
    
    @frappe.whitelist()
    def calculate_bmi(self):
        """Calculate BMI if height and weight are available."""
        if self.height and self.weight:
            height_m = flt(self.height) / 100  # Convert cm to meters
            bmi = flt(self.weight) / (height_m * height_m)
            
            # BMI categories for children (simplified)
            if bmi < 18.5:
                category = "Underweight"
            elif bmi < 25:
                category = "Normal weight"
            elif bmi < 30:
                category = "Overweight"
            else:
                category = "Obese"
            
            return {
                "bmi": round(bmi, 1),
                "category": category
            }
        
        return None
    
    @frappe.whitelist()
    def generate_medical_report(self):
        """Generate comprehensive medical report."""
        bmi_data = self.calculate_bmi()
        
        report = {
            "visit_info": {
                "visit_id": self.name,
                "student": self.student_name,
                "date": self.visit_date,
                "time": self.visit_time,
                "type": self.visit_type,
                "provider": self.healthcare_provider
            },
            "vital_signs": {
                "temperature": self.temperature,
                "blood_pressure": self.blood_pressure,
                "pulse_rate": self.pulse_rate,
                "respiratory_rate": self.respiratory_rate,
                "weight": self.weight,
                "height": self.height,
                "bmi": bmi_data
            },
            "clinical_info": {
                "chief_complaint": self.chief_complaint,
                "examination_findings": self.examination_findings,
                "diagnosis": self.diagnosis,
                "treatment": self.treatment_given,
                "recommendations": self.recommendations
            },
            "follow_up": {
                "required": self.follow_up_required,
                "date": self.follow_up_date,
                "referral": self.referred_to,
                "referral_reason": self.referral_reason
            },
            "medications": [
                {
                    "medication": med.medication,
                    "dosage": med.dosage,
                    "frequency": med.frequency,
                    "duration": med.duration
                } for med in self.medications_prescribed
            ]
        }
        
        return report
    
    def get_visit_summary(self):
        """Get visit summary for reporting."""
        return {
            "visit_id": self.name,
            "student": self.student_name,
            "visit_date": self.visit_date,
            "visit_type": self.visit_type,
            "chief_complaint": self.chief_complaint,
            "diagnosis": self.diagnosis,
            "treatment_given": bool(self.treatment_given),
            "medications_prescribed": len(self.medications_prescribed),
            "follow_up_required": self.follow_up_required,
            "referred": bool(self.referred_to),
            "status": self.status,
            "healthcare_provider": self.healthcare_provider
        }
