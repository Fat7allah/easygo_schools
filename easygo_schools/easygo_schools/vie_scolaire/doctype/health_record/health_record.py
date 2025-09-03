"""Health Record doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate, flt


class HealthRecord(Document):
    """Health Record doctype controller."""
    
    def validate(self):
        """Validate health record data."""
        self.validate_measurements()
        self.calculate_bmi()
        self.validate_dates()
        self.set_defaults()
    
    def validate_measurements(self):
        """Validate height and weight measurements."""
        if self.height and (self.height < 50 or self.height > 250):
            frappe.throw(_("Height must be between 50 and 250 cm"))
        
        if self.weight and (self.weight < 10 or self.weight > 200):
            frappe.throw(_("Weight must be between 10 and 200 kg"))
    
    def calculate_bmi(self):
        """Calculate BMI from height and weight."""
        if self.height and self.weight:
            height_m = self.height / 100  # Convert cm to meters
            self.bmi = round(self.weight / (height_m * height_m), 2)
    
    def validate_dates(self):
        """Validate dates."""
        if self.record_date and getdate(self.record_date) > getdate():
            frappe.throw(_("Record date cannot be in the future"))
        
        if self.incident_date and getdate(self.incident_date) > getdate():
            frappe.throw(_("Incident date cannot be in the future"))
        
        if self.clearance_expiry and self.record_date:
            if getdate(self.clearance_expiry) <= getdate(self.record_date):
                frappe.throw(_("Clearance expiry must be after record date"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.last_updated:
            self.last_updated = now()
        
        # Fetch student details
        if self.student and not self.student_name:
            self.student_name = frappe.db.get_value("Student", self.student, "student_name")
        
        # Set current academic year if not specified
        if not self.academic_year:
            current_year = frappe.db.get_single_value("School Settings", "current_academic_year")
            if current_year:
                self.academic_year = current_year
    
    def before_save(self):
        """Actions before saving."""
        self.last_updated = now()
        self.check_vaccination_alerts()
        self.check_clearance_expiry()
    
    def check_vaccination_alerts(self):
        """Check for vaccination alerts."""
        if self.next_vaccination_due:
            days_until_due = (getdate(self.next_vaccination_due) - getdate()).days
            
            if days_until_due <= 30 and days_until_due > 0:
                self.create_vaccination_reminder()
    
    def check_clearance_expiry(self):
        """Check medical clearance expiry."""
        if self.clearance_expiry:
            days_until_expiry = (getdate(self.clearance_expiry) - getdate()).days
            
            if days_until_expiry <= 30 and days_until_expiry > 0:
                self.create_clearance_reminder()
    
    def create_vaccination_reminder(self):
        """Create vaccination reminder."""
        try:
            # Get guardian emails
            guardian_emails = frappe.db.sql("""
                SELECT g.email_address
                FROM `tabGuardian` g
                INNER JOIN `tabStudent Guardian` sg ON g.name = sg.guardian
                WHERE sg.student = %s AND g.email_address IS NOT NULL
            """, (self.student,))
            
            recipients = [email[0] for email in guardian_emails if email[0]]
            
            if recipients:
                frappe.sendmail(
                    recipients=recipients,
                    subject=_("Vaccination Reminder - {0}").format(self.student_name),
                    message=_("This is a reminder that {0} has a vaccination due on {1}. Please schedule an appointment with your healthcare provider.").format(
                        self.student_name, self.next_vaccination_due
                    ),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        except Exception as e:
            frappe.log_error(f"Failed to send vaccination reminder: {str(e)}")
    
    def create_clearance_reminder(self):
        """Create medical clearance reminder."""
        try:
            # Get guardian emails
            guardian_emails = frappe.db.sql("""
                SELECT g.email_address
                FROM `tabGuardian` g
                INNER JOIN `tabStudent Guardian` sg ON g.name = sg.guardian
                WHERE sg.student = %s AND g.email_address IS NOT NULL
            """, (self.student,))
            
            recipients = [email[0] for email in guardian_emails if email[0]]
            
            if recipients:
                frappe.sendmail(
                    recipients=recipients,
                    subject=_("Medical Clearance Expiry - {0}").format(self.student_name),
                    message=_("The medical clearance for {0} will expire on {1}. Please renew the clearance to continue participation in activities.").format(
                        self.student_name, self.clearance_expiry
                    ),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        except Exception as e:
            frappe.log_error(f"Failed to send clearance reminder: {str(e)}")
    
    @frappe.whitelist()
    def add_health_incident(self, incident_data):
        """Add a health incident."""
        if isinstance(incident_data, str):
            import json
            incident_data = json.loads(incident_data)
        
        self.incident_date = incident_data.get("date")
        self.incident_type = incident_data.get("type")
        self.incident_description = incident_data.get("description")
        self.action_taken = incident_data.get("action_taken")
        self.follow_up_required = incident_data.get("follow_up_required", 0)
        
        self.save()
        
        # Send incident notification
        self.send_incident_notification(incident_data)
        
        return True
    
    def send_incident_notification(self, incident_data):
        """Send health incident notification."""
        try:
            # Get guardian emails
            guardian_emails = frappe.db.sql("""
                SELECT g.email_address
                FROM `tabGuardian` g
                INNER JOIN `tabStudent Guardian` sg ON g.name = sg.guardian
                WHERE sg.student = %s AND g.email_address IS NOT NULL
            """, (self.student,))
            
            recipients = [email[0] for email in guardian_emails if email[0]]
            
            if recipients:
                frappe.sendmail(
                    recipients=recipients,
                    subject=_("Health Incident Report - {0}").format(self.student_name),
                    message=_("A health incident has been reported for {0}.\n\nIncident Details:\nDate: {1}\nType: {2}\nDescription: {3}\nAction Taken: {4}").format(
                        self.student_name,
                        incident_data.get("date"),
                        incident_data.get("type"),
                        incident_data.get("description"),
                        incident_data.get("action_taken")
                    ),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        except Exception as e:
            frappe.log_error(f"Failed to send incident notification: {str(e)}")
    
    @frappe.whitelist()
    def update_medical_clearance(self, clearance_data):
        """Update medical clearance status."""
        if isinstance(clearance_data, str):
            import json
            clearance_data = json.loads(clearance_data)
        
        self.cleared_for_sports = clearance_data.get("sports", 0)
        self.cleared_for_field_trips = clearance_data.get("field_trips", 0)
        self.medical_restrictions = clearance_data.get("restrictions")
        self.clearance_expiry = clearance_data.get("expiry_date")
        
        self.save()
        
        return True
    
    @frappe.whitelist()
    def get_health_summary(self):
        """Get health summary for this student."""
        summary = {
            "basic_info": {
                "height": self.height,
                "weight": self.weight,
                "bmi": self.bmi,
                "blood_type": self.blood_type
            },
            "medical_conditions": {
                "chronic_conditions": self.chronic_conditions,
                "allergies": self.allergies,
                "medications": self.current_medications,
                "dietary_restrictions": self.dietary_restrictions,
                "physical_limitations": self.physical_limitations
            },
            "vaccination_status": {
                "status": self.vaccination_status,
                "next_due": self.next_vaccination_due,
                "exemptions": self.vaccination_exemptions
            },
            "clearances": {
                "sports": self.cleared_for_sports,
                "field_trips": self.cleared_for_field_trips,
                "restrictions": self.medical_restrictions,
                "expiry": self.clearance_expiry
            },
            "emergency_contacts": {
                "name": self.emergency_contact_name,
                "phone": self.emergency_contact_phone,
                "relation": self.emergency_contact_relation,
                "doctor": self.family_doctor,
                "doctor_phone": self.family_doctor_phone
            }
        }
        
        return summary
    
    @frappe.whitelist()
    def get_bmi_category(self):
        """Get BMI category based on age and BMI value."""
        if not self.bmi:
            return "Unknown"
        
        # Get student's age
        student_doc = frappe.get_doc("Student", self.student)
        if not student_doc.date_of_birth:
            return "Unknown"
        
        from dateutil.relativedelta import relativedelta
        age = relativedelta(getdate(), getdate(student_doc.date_of_birth)).years
        
        # BMI categories for children and adults
        if age < 18:
            # Simplified pediatric BMI categories
            if self.bmi < 18.5:
                return "Underweight"
            elif self.bmi < 25:
                return "Normal"
            elif self.bmi < 30:
                return "Overweight"
            else:
                return "Obese"
        else:
            # Adult BMI categories
            if self.bmi < 18.5:
                return "Underweight"
            elif self.bmi < 25:
                return "Normal"
            elif self.bmi < 30:
                return "Overweight"
            else:
                return "Obese"
    
    @frappe.whitelist()
    def check_activity_eligibility(self, activity_type):
        """Check if student is eligible for specific activity."""
        eligibility = {
            "eligible": True,
            "restrictions": [],
            "notes": []
        }
        
        # Check clearance expiry
        if self.clearance_expiry and getdate(self.clearance_expiry) < getdate():
            eligibility["eligible"] = False
            eligibility["restrictions"].append("Medical clearance expired")
        
        # Check activity-specific clearances
        if activity_type == "sports" and not self.cleared_for_sports:
            eligibility["eligible"] = False
            eligibility["restrictions"].append("Not cleared for sports activities")
        
        if activity_type == "field_trip" and not self.cleared_for_field_trips:
            eligibility["eligible"] = False
            eligibility["restrictions"].append("Not cleared for field trips")
        
        # Add medical restrictions
        if self.medical_restrictions:
            eligibility["notes"].append(f"Medical restrictions: {self.medical_restrictions}")
        
        # Add allergy warnings
        if self.allergies:
            eligibility["notes"].append(f"Allergies: {self.allergies}")
        
        return eligibility
