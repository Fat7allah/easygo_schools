"""Vaccination Record DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, add_days


class VaccinationRecord(Document):
    """Vaccination Record management."""
    
    def validate(self):
        """Validate vaccination record data."""
        self.validate_dates()
        self.validate_dose_number()
        self.validate_expiry_date()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate vaccination dates."""
        if self.vaccination_date and getdate(self.vaccination_date) > getdate():
            frappe.throw(_("Vaccination date cannot be in the future"))
        
        if self.next_dose_due and self.vaccination_date:
            if getdate(self.next_dose_due) <= getdate(self.vaccination_date):
                frappe.throw(_("Next dose due date must be after vaccination date"))
    
    def validate_dose_number(self):
        """Validate dose number sequence."""
        if self.dose_number and self.dose_number < 1:
            frappe.throw(_("Dose number must be greater than 0"))
        
        # Check for previous doses
        if self.dose_number and self.dose_number > 1:
            previous_dose = frappe.db.exists("Vaccination Record", {
                "student": self.student,
                "vaccine_name": self.vaccine_name,
                "dose_number": self.dose_number - 1,
                "name": ["!=", self.name]
            })
            
            if not previous_dose:
                frappe.msgprint(_("Warning: Previous dose {0} not found for {1}").format(
                    self.dose_number - 1, self.vaccine_name
                ), alert=True)
    
    def validate_expiry_date(self):
        """Validate vaccine expiry date."""
        if self.expiry_date and self.vaccination_date:
            if getdate(self.expiry_date) < getdate(self.vaccination_date):
                frappe.throw(_("Vaccine was expired on vaccination date"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.vaccine_type:
            self.vaccine_type = "Routine"
        
        if not self.dose_number:
            self.dose_number = 1
    
    def on_insert(self):
        """Actions after insert."""
        self.update_health_record()
        self.schedule_next_dose_reminder()
    
    def on_update(self):
        """Actions after update."""
        if self.adverse_reactions and self.has_value_changed("adverse_reactions"):
            self.notify_healthcare_team()
    
    def update_health_record(self):
        """Update student's health record."""
        health_record = frappe.db.exists("Health Record", {"student": self.student})
        
        if health_record:
            health_doc = frappe.get_doc("Health Record", health_record)
            
            # Add vaccination to immunization history
            vaccination_entry = f"{self.vaccine_name} - Dose {self.dose_number} ({self.vaccination_date})"
            
            if health_doc.immunization_history:
                health_doc.immunization_history += f"\n{vaccination_entry}"
            else:
                health_doc.immunization_history = vaccination_entry
            
            health_doc.save(ignore_permissions=True)
    
    def schedule_next_dose_reminder(self):
        """Schedule reminder for next dose."""
        if self.next_dose_due and not self.vaccination_series_complete:
            # Create a reminder event
            reminder_date = add_days(self.next_dose_due, -7)  # Remind 1 week before
            
            event_doc = frappe.get_doc({
                "doctype": "Event",
                "subject": _("Vaccination Reminder: {0} - Dose {1}").format(
                    self.vaccine_name, (self.dose_number or 0) + 1
                ),
                "starts_on": reminder_date,
                "event_type": "Private",
                "ref_type": self.doctype,
                "ref_name": self.name,
                "description": _("Next dose due for {0}").format(self.student_name)
            })
            
            # Add school nurse or health coordinator
            health_coordinator = frappe.db.get_single_value("School Settings", "health_coordinator")
            if health_coordinator:
                event_doc.append("event_participants", {
                    "reference_doctype": "User",
                    "reference_docname": health_coordinator
                })
            
            event_doc.insert(ignore_permissions=True)
    
    def notify_healthcare_team(self):
        """Notify healthcare team about adverse reactions."""
        if not self.adverse_reactions:
            return
        
        # Get healthcare team members
        healthcare_team = frappe.get_all("Employee", 
            filters={"department": "Healthcare"},
            fields=["name", "user_id", "employee_name"]
        )
        
        recipients = [emp.user_id for emp in healthcare_team if emp.user_id]
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Adverse Reaction Reported: {0}").format(self.student_name),
                message=self.get_adverse_reaction_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    @frappe.whitelist()
    def mark_series_complete(self):
        """Mark vaccination series as complete."""
        self.vaccination_series_complete = 1
        self.next_dose_due = None
        self.save()
        
        frappe.msgprint(_("Vaccination series marked as complete"))
        return self
    
    @frappe.whitelist()
    def schedule_next_dose(self, next_dose_date, dose_number=None):
        """Schedule next dose."""
        if not next_dose_date:
            frappe.throw(_("Next dose date is required"))
        
        next_dose_doc = frappe.get_doc({
            "doctype": "Vaccination Record",
            "student": self.student,
            "vaccine_name": self.vaccine_name,
            "vaccine_type": self.vaccine_type,
            "manufacturer": self.manufacturer,
            "dose_number": dose_number or (self.dose_number + 1),
            "vaccination_date": next_dose_date,
            "administered_by": self.administered_by,
            "health_facility": self.health_facility
        })
        
        next_dose_doc.insert()
        
        frappe.msgprint(_("Next dose scheduled: {0}").format(next_dose_doc.name))
        return next_dose_doc.name
    
    def get_adverse_reaction_message(self):
        """Get formatted message for adverse reaction notification."""
        return _("""
        Adverse Reaction Report
        
        Student: {student_name}
        Class: {school_class}
        Vaccine: {vaccine_name}
        Dose Number: {dose_number}
        Vaccination Date: {vaccination_date}
        
        Adverse Reactions:
        {adverse_reactions}
        
        Severity: {reaction_severity}
        Medical Attention Required: {medical_attention}
        
        Administered By: {administered_by}
        Health Facility: {health_facility}
        
        Please review and take appropriate action if necessary.
        """).format(
            student_name=self.student_name,
            school_class=self.school_class,
            vaccine_name=self.vaccine_name,
            dose_number=self.dose_number,
            vaccination_date=self.vaccination_date,
            adverse_reactions=self.adverse_reactions,
            reaction_severity=self.reaction_severity or "Not specified",
            medical_attention="Yes" if self.medical_attention_required else "No",
            administered_by=self.administered_by,
            health_facility=self.health_facility or "Not specified"
        )
    
    def get_vaccination_certificate_data(self):
        """Get data for vaccination certificate."""
        return {
            "student_name": self.student_name,
            "student_id": self.student,
            "vaccine_name": self.vaccine_name,
            "manufacturer": self.manufacturer,
            "batch_number": self.batch_number,
            "vaccination_date": self.vaccination_date,
            "dose_number": self.dose_number,
            "administered_by": self.administered_by,
            "health_facility": self.health_facility,
            "next_dose_due": self.next_dose_due,
            "series_complete": self.vaccination_series_complete
        }
    
    @frappe.whitelist()
    def get_vaccination_history(self):
        """Get complete vaccination history for the student."""
        history = frappe.get_all("Vaccination Record",
            filters={"student": self.student},
            fields=[
                "name", "vaccine_name", "dose_number", "vaccination_date",
                "administered_by", "health_facility", "adverse_reactions",
                "vaccination_series_complete", "next_dose_due"
            ],
            order_by="vaccination_date desc"
        )
        
        return history
    
    def check_vaccination_schedule_compliance(self):
        """Check if vaccination is on schedule."""
        # This would implement logic to check against standard vaccination schedules
        # For now, return a simple compliance status
        if self.next_dose_due and getdate(self.next_dose_due) < getdate():
            return {
                "status": "Overdue",
                "message": _("Next dose is overdue by {0} days").format(
                    (getdate() - getdate(self.next_dose_due)).days
                )
            }
        elif self.vaccination_series_complete:
            return {
                "status": "Complete",
                "message": _("Vaccination series is complete")
            }
        else:
            return {
                "status": "On Schedule",
                "message": _("Vaccination is on schedule")
            }
