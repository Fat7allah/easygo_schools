"""Maintenance Request doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate


class MaintenanceRequest(Document):
    """Maintenance Request doctype controller."""
    
    def validate(self):
        """Validate maintenance request data."""
        self.validate_assignment()
        self.validate_dates()
        self.set_defaults()
    
    def validate_assignment(self):
        """Validate assignment details."""
        if self.status == "Assigned" and not self.assigned_to:
            frappe.throw(_("Assigned To is required when status is Assigned"))
        
        if self.assigned_to and not self.assigned_date:
            self.assigned_date = getdate()
    
    def validate_dates(self):
        """Validate work dates."""
        if self.work_started and self.work_completed:
            if self.work_completed <= self.work_started:
                frappe.throw(_("Work completed time must be after work started time"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.requested_by:
            self.requested_by = frappe.session.user
        
        if not self.request_date:
            self.request_date = getdate()
    
    def on_update(self):
        """Actions on document update."""
        self.send_status_notifications()
        self.update_equipment_status()
    
    def send_status_notifications(self):
        """Send notifications based on status changes."""
        if self.has_value_changed("status"):
            recipients = [self.requested_by]
            if self.assigned_to:
                recipients.append(self.assigned_to)
            
            subject = f"Maintenance Request {self.name} - Status Updated"
            message = f"""
            Maintenance Request: {self.request_title}
            Status: {self.status}
            Priority: {self.priority}
            
            Description: {self.description}
            """
            
            for recipient in recipients:
                try:
                    frappe.sendmail(
                        recipients=[recipient],
                        subject=subject,
                        message=message
                    )
                except Exception as e:
                    frappe.log_error(f"Failed to send notification: {str(e)}")
    
    def update_equipment_status(self):
        """Update equipment status based on request status."""
        if self.equipment:
            equipment_doc = frappe.get_doc("Equipment", self.equipment)
            
            if self.status == "In Progress" and self.request_type in ["Repair", "Maintenance"]:
                equipment_doc.status = "Under Maintenance"
            elif self.status == "Completed":
                equipment_doc.status = "Active"
                # Update last maintenance date if it's maintenance
                if self.request_type == "Maintenance":
                    equipment_doc.last_maintenance = getdate()
            
            equipment_doc.save(ignore_permissions=True)
    
    @frappe.whitelist()
    def assign_request(self, assigned_to, estimated_cost=None, estimated_duration=None):
        """Assign request to a user."""
        self.assigned_to = assigned_to
        self.assigned_date = getdate()
        self.status = "Assigned"
        
        if estimated_cost:
            self.estimated_cost = estimated_cost
        
        if estimated_duration:
            self.estimated_duration = estimated_duration
        
        self.save()
        
        return True
    
    @frappe.whitelist()
    def start_work(self):
        """Mark work as started."""
        if self.status not in ["Assigned", "Open"]:
            frappe.throw(_("Cannot start work on request with status: {0}").format(self.status))
        
        self.work_started = now()
        self.status = "In Progress"
        self.save()
        
        return True
    
    @frappe.whitelist()
    def complete_work(self, completion_notes=None, actual_cost=None):
        """Mark work as completed."""
        if self.status != "In Progress":
            frappe.throw(_("Cannot complete work on request with status: {0}").format(self.status))
        
        self.work_completed = now()
        self.status = "Completed"
        
        if completion_notes:
            self.completion_notes = completion_notes
        
        if actual_cost:
            self.actual_cost = actual_cost
        
        self.save()
        
        return True
    
    @frappe.whitelist()
    def get_request_analytics(self):
        """Get analytics for this request."""
        analytics = {
            "response_time": None,
            "completion_time": None,
            "cost_variance": 0,
            "duration_actual": None
        }
        
        if self.assigned_date and self.request_date:
            response_days = (getdate(self.assigned_date) - getdate(self.request_date)).days
            analytics["response_time"] = f"{response_days} days"
        
        if self.work_completed and self.work_started:
            from frappe.utils import time_diff_in_hours
            duration_hours = time_diff_in_hours(self.work_completed, self.work_started)
            analytics["duration_actual"] = f"{duration_hours:.1f} hours"
        
        if self.estimated_cost and self.actual_cost:
            variance = ((self.actual_cost - self.estimated_cost) / self.estimated_cost) * 100
            analytics["cost_variance"] = f"{variance:.1f}%"
        
        return analytics
