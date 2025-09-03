"""Accident Report DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, get_datetime, now_datetime, add_days


class AccidentReport(Document):
    """Accident Report management."""
    
    def validate(self):
        """Validate accident report data."""
        self.validate_dates()
        self.validate_severity_requirements()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate incident and follow-up dates."""
        if self.incident_date and self.incident_date > getdate():
            frappe.throw(_("Incident date cannot be in the future"))
        
        if self.follow_up_date and self.follow_up_date < getdate():
            frappe.throw(_("Follow-up date cannot be in the past"))
        
        if self.investigation_date and self.incident_date and self.investigation_date < self.incident_date:
            frappe.throw(_("Investigation date cannot be before incident date"))
    
    def validate_severity_requirements(self):
        """Validate requirements based on severity level."""
        if self.severity_level in ["Severe", "Critical"]:
            if not self.medical_attention_required:
                frappe.throw(_("Medical attention is required for {0} incidents").format(self.severity_level))
            
            if not self.parent_notified:
                frappe.throw(_("Parent notification is mandatory for {0} incidents").format(self.severity_level))
        
        if self.medical_attention_required and not self.doctor_name:
            frappe.msgprint(_("Please specify the doctor's name for medical attention"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.reported_by:
            self.reported_by = frappe.session.user
        
        if not self.status:
            self.status = "Open"
        
        # Auto-set follow-up requirements for severe cases
        if self.severity_level in ["Severe", "Critical"] and not self.follow_up_required:
            self.follow_up_required = 1
            if not self.follow_up_date:
                self.follow_up_date = add_days(getdate(), 3)
    
    def on_submit(self):
        """Actions on submit."""
        self.notify_stakeholders()
        self.create_follow_up_tasks()
        self.update_student_health_record()
    
    def notify_stakeholders(self):
        """Notify relevant stakeholders."""
        # Notify parents/guardians
        if self.severity_level in ["Moderate", "Severe", "Critical"]:
            self.send_parent_notification()
        
        # Notify school management for severe cases
        if self.severity_level in ["Severe", "Critical"]:
            self.send_management_notification()
        
        # Notify healthcare team
        self.send_healthcare_notification()
    
    def send_parent_notification(self):
        """Send notification to parents/guardians."""
        student = frappe.get_doc("Student", self.student)
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            
            if guardian.email_address:
                frappe.sendmail(
                    recipients=[guardian.email_address],
                    subject=_("Accident Report - {0}").format(self.student_name),
                    message=self.get_parent_notification_message(),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
            
            if guardian.mobile_number:
                self.send_parent_sms(guardian.mobile_number)
    
    def send_parent_sms(self, mobile_number):
        """Send SMS to parent."""
        message = _("School Alert: {0} had a {1} incident on {2}. Please contact school for details.").format(
            self.student_name,
            self.severity_level.lower(),
            frappe.format(self.incident_date, "Date")
        )
        
        # Use SMS adapter
        from easygo_education.finances_rh.adapters.sms import send_sms
        send_sms(mobile_number, message)
    
    def send_management_notification(self):
        """Send notification to school management."""
        management_emails = frappe.db.get_single_value("School Settings", "management_emails")
        
        if management_emails:
            email_list = [email.strip() for email in management_emails.split(",")]
            
            frappe.sendmail(
                recipients=email_list,
                subject=_("Urgent: {0} Accident Report - {1}").format(self.severity_level, self.student_name),
                message=self.get_management_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def send_healthcare_notification(self):
        """Send notification to healthcare team."""
        healthcare_practitioners = frappe.get_all("Healthcare Practitioner",
            filters={"department": "School Health"},
            fields=["name", "user_id"]
        )
        
        for practitioner in healthcare_practitioners:
            if practitioner.user_id:
                frappe.get_doc({
                    "doctype": "Notification Log",
                    "subject": _("New Accident Report: {0}").format(self.student_name),
                    "email_content": self.get_healthcare_notification_message(),
                    "for_user": practitioner.user_id,
                    "type": "Alert",
                    "document_type": self.doctype,
                    "document_name": self.name
                }).insert(ignore_permissions=True)
    
    def get_parent_notification_message(self):
        """Get parent notification message."""
        return _("""
        Dear Parent/Guardian,
        
        We are writing to inform you about an incident involving your child {student_name} that occurred at school.
        
        Incident Details:
        - Date: {incident_date}
        - Time: {incident_time}
        - Location: {incident_location}
        - Type: {incident_type}
        - Severity: {severity_level}
        
        Description:
        {incident_description}
        
        Medical Attention: {medical_attention}
        First Aid Given: {first_aid}
        
        We have taken all necessary precautions and your child is being well cared for. 
        
        Please contact the school office at your earliest convenience to discuss this matter further.
        
        School Health Team
        """).format(
            student_name=self.student_name,
            incident_date=frappe.format(self.incident_date, "Date"),
            incident_time=self.incident_time or "Not specified",
            incident_location=self.incident_location,
            incident_type=self.incident_type,
            severity_level=self.severity_level,
            incident_description=self.incident_description,
            medical_attention="Yes" if self.medical_attention_required else "No",
            first_aid="Yes" if self.first_aid_given else "No"
        )
    
    def get_management_notification_message(self):
        """Get management notification message."""
        return _("""
        Urgent Accident Report Notification
        
        Student: {student_name}
        Incident Date: {incident_date}
        Severity: {severity_level}
        Location: {incident_location}
        Type: {incident_type}
        
        Description:
        {incident_description}
        
        Medical Attention Required: {medical_attention}
        Parent Notified: {parent_notified}
        
        Reported By: {reported_by}
        Report ID: {report_id}
        
        Please review this report and take necessary actions.
        """).format(
            student_name=self.student_name,
            incident_date=frappe.format(self.incident_date, "Date"),
            severity_level=self.severity_level,
            incident_location=self.incident_location,
            incident_type=self.incident_type,
            incident_description=self.incident_description,
            medical_attention="Yes" if self.medical_attention_required else "No",
            parent_notified="Yes" if self.parent_notified else "No",
            reported_by=self.reported_by,
            report_id=self.name
        )
    
    def get_healthcare_notification_message(self):
        """Get healthcare notification message."""
        return _("""
        New Accident Report Submitted
        
        Student: {student_name}
        Incident: {incident_type} - {severity_level}
        Date: {incident_date}
        Location: {incident_location}
        
        Injury: {injury_type}
        Body Parts: {body_parts}
        
        Medical Attention: {medical_attention}
        Follow-up Required: {follow_up}
        
        Please review and take appropriate action.
        """).format(
            student_name=self.student_name,
            incident_type=self.incident_type,
            severity_level=self.severity_level,
            incident_date=frappe.format(self.incident_date, "Date"),
            incident_location=self.incident_location,
            injury_type=self.injury_type or "Not specified",
            body_parts=self.body_parts_affected or "Not specified",
            medical_attention="Yes" if self.medical_attention_required else "No",
            follow_up="Yes" if self.follow_up_required else "No"
        )
    
    def create_follow_up_tasks(self):
        """Create follow-up tasks."""
        if self.follow_up_required and self.follow_up_date:
            # Create task for healthcare team
            task = frappe.get_doc({
                "doctype": "Task",
                "subject": _("Follow-up: Accident Report - {0}").format(self.student_name),
                "description": _("Follow-up required for accident report {0}").format(self.name),
                "priority": "High" if self.severity_level in ["Severe", "Critical"] else "Medium",
                "status": "Open",
                "exp_start_date": self.follow_up_date,
                "exp_end_date": self.follow_up_date,
                "reference_type": self.doctype,
                "reference_name": self.name
            })
            
            # Assign to healthcare practitioners
            healthcare_users = frappe.get_all("Healthcare Practitioner",
                filters={"department": "School Health"},
                fields=["user_id"]
            )
            
            for practitioner in healthcare_users:
                if practitioner.user_id:
                    task.append("assigned_to", {"assigned_to": practitioner.user_id})
            
            task.insert(ignore_permissions=True)
    
    def update_student_health_record(self):
        """Update student health record."""
        # Check if student has a health record
        health_record = frappe.db.exists("Student Health Record", {"student": self.student})
        
        if health_record:
            health_doc = frappe.get_doc("Student Health Record", health_record)
        else:
            health_doc = frappe.get_doc({
                "doctype": "Student Health Record",
                "student": self.student,
                "student_name": self.student_name
            })
        
        # Add accident to health history
        health_doc.append("health_history", {
            "date": self.incident_date,
            "condition": f"Accident: {self.incident_type}",
            "description": self.incident_description,
            "severity": self.severity_level,
            "treatment": self.first_aid_by if self.first_aid_given else "None",
            "reference_document": self.name
        })
        
        # Update medical conditions if injury is significant
        if self.severity_level in ["Severe", "Critical"] and self.injury_type:
            existing_conditions = health_doc.medical_conditions or ""
            if self.injury_type not in existing_conditions:
                health_doc.medical_conditions = f"{existing_conditions}\n{self.injury_type} (from accident {self.name})"
        
        health_doc.save(ignore_permissions=True)
    
    @frappe.whitelist()
    def mark_parent_notified(self, notification_method, contacted_by):
        """Mark parent as notified."""
        self.parent_notified = 1
        self.parent_notification_time = now_datetime()
        self.notification_method = notification_method
        self.parent_contacted_by = contacted_by
        self.save()
        
        frappe.msgprint(_("Parent notification recorded"))
        return self
    
    @frappe.whitelist()
    def update_investigation(self, notes, investigated_by=None):
        """Update investigation details."""
        self.investigation_notes = notes
        self.investigated_by = investigated_by or frappe.session.user
        self.investigation_date = getdate()
        self.status = "Under Investigation"
        self.save()
        
        frappe.msgprint(_("Investigation details updated"))
        return self
    
    @frappe.whitelist()
    def close_case(self, closing_notes=None):
        """Close the accident case."""
        if self.status == "Closed":
            frappe.throw(_("Case is already closed"))
        
        self.status = "Closed"
        self.case_closed_date = getdate()
        
        if closing_notes:
            current_notes = self.investigation_notes or ""
            self.investigation_notes = f"{current_notes}\n\nCase Closure Notes ({getdate()}):\n{closing_notes}"
        
        self.save()
        
        # Notify stakeholders about case closure
        self.send_case_closure_notification()
        
        frappe.msgprint(_("Accident case closed"))
        return self
    
    def send_case_closure_notification(self):
        """Send case closure notification."""
        # Notify parents for severe cases
        if self.severity_level in ["Severe", "Critical"]:
            student = frappe.get_doc("Student", self.student)
            guardians = frappe.get_all("Student Guardian",
                filters={"parent": self.student},
                fields=["guardian"]
            )
            
            for guardian_link in guardians:
                guardian = frappe.get_doc("Guardian", guardian_link.guardian)
                
                if guardian.email_address:
                    frappe.sendmail(
                        recipients=[guardian.email_address],
                        subject=_("Accident Case Closed - {0}").format(self.student_name),
                        message=self.get_case_closure_message(),
                        reference_doctype=self.doctype,
                        reference_name=self.name
                    )
    
    def get_case_closure_message(self):
        """Get case closure message."""
        return _("""
        Dear Parent/Guardian,
        
        We are writing to inform you that the accident case involving {student_name} has been officially closed.
        
        Case Details:
        - Incident Date: {incident_date}
        - Case Closed Date: {case_closed_date}
        - Final Status: Resolved
        
        All necessary follow-up actions have been completed, and we are satisfied that appropriate measures have been taken.
        
        If you have any questions or concerns, please do not hesitate to contact us.
        
        Thank you for your cooperation throughout this process.
        
        School Administration
        """).format(
            student_name=self.student_name,
            incident_date=frappe.format(self.incident_date, "Date"),
            case_closed_date=frappe.format(self.case_closed_date, "Date")
        )
    
    @frappe.whitelist()
    def get_accident_statistics(self):
        """Get accident statistics for reporting."""
        # Get school-wide accident statistics
        total_accidents = frappe.db.count("Accident Report")
        
        # Get accidents by severity
        severity_stats = frappe.db.sql("""
            SELECT severity_level, COUNT(*) as count
            FROM `tabAccident Report`
            GROUP BY severity_level
        """, as_dict=True)
        
        # Get accidents by location
        location_stats = frappe.db.sql("""
            SELECT incident_location, COUNT(*) as count
            FROM `tabAccident Report`
            GROUP BY incident_location
            ORDER BY count DESC
        """, as_dict=True)
        
        # Get monthly trend
        monthly_trend = frappe.db.sql("""
            SELECT 
                DATE_FORMAT(incident_date, '%Y-%m') as month,
                COUNT(*) as count
            FROM `tabAccident Report`
            WHERE incident_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(incident_date, '%Y-%m')
            ORDER BY month
        """, as_dict=True)
        
        return {
            "total_accidents": total_accidents,
            "severity_breakdown": severity_stats,
            "location_breakdown": location_stats,
            "monthly_trend": monthly_trend,
            "current_case": {
                "name": self.name,
                "student": self.student_name,
                "severity": self.severity_level,
                "status": self.status,
                "incident_date": self.incident_date
            }
        }
    
    def get_accident_summary(self):
        """Get accident summary for reporting."""
        return {
            "report_id": self.name,
            "student": self.student_name,
            "incident_date": self.incident_date,
            "incident_type": self.incident_type,
            "severity_level": self.severity_level,
            "location": self.incident_location,
            "medical_attention": self.medical_attention_required,
            "parent_notified": self.parent_notified,
            "status": self.status,
            "reported_by": self.reported_by,
            "follow_up_required": self.follow_up_required
        }
