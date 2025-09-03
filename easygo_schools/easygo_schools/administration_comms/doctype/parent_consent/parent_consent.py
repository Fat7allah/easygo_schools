"""Parent Consent doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate, add_days


class ParentConsent(Document):
    """Parent Consent doctype controller."""
    
    def validate(self):
        """Validate parent consent data."""
        self.validate_dates()
        self.validate_consent_requirements()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate consent and expiry dates."""
        if self.consent_date and getdate(self.consent_date) > getdate():
            frappe.throw(_("Consent date cannot be in the future"))
        
        if self.expiry_date and self.consent_date:
            if getdate(self.expiry_date) <= getdate(self.consent_date):
                frappe.throw(_("Expiry date must be after consent date"))
    
    def validate_consent_requirements(self):
        """Validate consent requirements based on type."""
        if self.consent_given and not self.signature_date:
            frappe.throw(_("Signature date is required when consent is given"))
        
        # Check if guardian is authorized for this student
        if self.student and self.guardian:
            guardian_exists = frappe.db.exists("Student Guardian", {
                "student": self.student,
                "guardian": self.guardian
            })
            
            if not guardian_exists:
                frappe.throw(_("Selected guardian is not authorized for this student"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
        
        # Fetch student and guardian names
        if self.student and not self.student_name:
            self.student_name = frappe.db.get_value("Student", self.student, "student_name")
        
        if self.guardian and not self.guardian_name:
            guardian_doc = frappe.get_doc("Guardian", self.guardian)
            self.guardian_name = f"{guardian_doc.first_name} {guardian_doc.last_name}"
        
        # Set default expiry date (1 year from consent date)
        if self.consent_date and not self.expiry_date:
            self.expiry_date = add_days(self.consent_date, 365)
    
    def before_save(self):
        """Actions before saving."""
        self.update_status()
    
    def update_status(self):
        """Update consent status based on conditions."""
        if self.consent_given and self.signature_date:
            if self.status == "Pending":
                self.status = "Approved"
        
        # Check if consent has expired
        if self.expiry_date and getdate(self.expiry_date) < getdate():
            self.status = "Expired"
    
    def on_update(self):
        """Actions after update."""
        if self.status == "Approved" and self.consent_given:
            self.send_consent_confirmation()
    
    def send_consent_confirmation(self):
        """Send consent confirmation to relevant parties."""
        try:
            # Get guardian email
            guardian_email = frappe.db.get_value("Guardian", self.guardian, "email_address")
            
            recipients = []
            if guardian_email:
                recipients.append(guardian_email)
            
            # Get school admin emails
            admin_emails = frappe.get_list("User",
                filters={"role_profile_name": ["in", ["Education Manager", "Administrator"]]},
                fields=["email"]
            )
            
            for admin in admin_emails:
                if admin.email:
                    recipients.append(admin.email)
            
            if recipients:
                frappe.sendmail(
                    recipients=recipients,
                    subject=_("Consent Confirmation - {0}").format(self.activity_event or self.consent_type),
                    message=_("Consent has been provided for {0}.\n\nDetails:\nStudent: {1}\nGuardian: {2}\nActivity: {3}\nConsent Type: {4}\nDate: {5}").format(
                        self.activity_event or self.consent_type,
                        self.student_name,
                        self.guardian_name,
                        self.activity_event or "N/A",
                        self.consent_type,
                        self.consent_date
                    ),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        except Exception as e:
            frappe.log_error(f"Failed to send consent confirmation: {str(e)}")
    
    @frappe.whitelist()
    def revoke_consent(self, reason=None):
        """Revoke the consent."""
        if self.status == "Revoked":
            frappe.throw(_("Consent is already revoked"))
        
        self.status = "Revoked"
        self.consent_given = 0
        
        if reason:
            self.remarks = (self.remarks or "") + f"\nRevoked: {reason} (Date: {now()})"
        
        self.save()
        self.send_revocation_notice()
        
        return True
    
    def send_revocation_notice(self):
        """Send consent revocation notice."""
        try:
            # Get relevant parties
            recipients = []
            
            # Guardian email
            guardian_email = frappe.db.get_value("Guardian", self.guardian, "email_address")
            if guardian_email:
                recipients.append(guardian_email)
            
            # School admin emails
            admin_emails = frappe.get_list("User",
                filters={"role_profile_name": ["in", ["Education Manager", "Teacher"]]},
                fields=["email"]
            )
            
            for admin in admin_emails:
                if admin.email:
                    recipients.append(admin.email)
            
            if recipients:
                frappe.sendmail(
                    recipients=recipients,
                    subject=_("Consent Revoked - {0}").format(self.activity_event or self.consent_type),
                    message=_("Consent has been revoked for {0}.\n\nDetails:\nStudent: {1}\nGuardian: {2}\nActivity: {3}\nRevocation Date: {4}").format(
                        self.activity_event or self.consent_type,
                        self.student_name,
                        self.guardian_name,
                        self.activity_event or "N/A",
                        now()
                    ),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        except Exception as e:
            frappe.log_error(f"Failed to send revocation notice: {str(e)}")
    
    @frappe.whitelist()
    def get_consent_history(self):
        """Get consent history for this student."""
        consents = frappe.get_list("Parent Consent",
            filters={"student": self.student},
            fields=[
                "name", "consent_type", "activity_event", "consent_date",
                "expiry_date", "status", "guardian_name"
            ],
            order_by="consent_date desc"
        )
        
        return consents
    
    @frappe.whitelist()
    def check_consent_validity(self):
        """Check if consent is still valid."""
        if self.status != "Approved":
            return {"valid": False, "reason": f"Consent status is {self.status}"}
        
        if not self.consent_given:
            return {"valid": False, "reason": "Consent not given"}
        
        if self.expiry_date and getdate(self.expiry_date) < getdate():
            return {"valid": False, "reason": "Consent has expired"}
        
        return {"valid": True, "reason": "Consent is valid"}
    
    @frappe.whitelist()
    def generate_consent_form(self):
        """Generate consent form data for printing."""
        form_data = {
            "consent_info": {
                "reference": self.name,
                "student_name": self.student_name,
                "guardian_name": self.guardian_name,
                "consent_type": self.consent_type,
                "activity_event": self.activity_event,
                "consent_date": self.consent_date,
                "expiry_date": self.expiry_date
            },
            "activity_details": {
                "description": self.activity_description,
                "risks": self.risks_involved,
                "instructions": self.special_instructions,
                "emergency_contact": self.emergency_contact,
                "conditions": self.consent_conditions
            },
            "medical_info": {
                "conditions": self.medical_conditions,
                "medications": self.medications,
                "allergies": self.allergies,
                "dietary_restrictions": self.dietary_restrictions
            },
            "approval": {
                "consent_given": self.consent_given,
                "signature_date": self.signature_date,
                "digital_signature": self.digital_signature,
                "witness": self.witness_name
            }
        }
        
        return form_data
