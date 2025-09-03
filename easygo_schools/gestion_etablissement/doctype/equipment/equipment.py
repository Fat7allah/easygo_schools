"""Equipment doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate, add_days, date_diff
from dateutil.relativedelta import relativedelta


class Equipment(Document):
    """Equipment doctype controller."""
    
    def validate(self):
        """Validate equipment data."""
        self.validate_dates()
        self.calculate_next_maintenance()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate purchase and maintenance dates."""
        if self.purchase_date and self.warranty_expiry:
            if getdate(self.warranty_expiry) <= getdate(self.purchase_date):
                frappe.throw(_("Warranty expiry must be after purchase date"))
        
        if self.last_maintenance and self.next_maintenance:
            if getdate(self.next_maintenance) <= getdate(self.last_maintenance):
                frappe.throw(_("Next maintenance must be after last maintenance"))
    
    def calculate_next_maintenance(self):
        """Calculate next maintenance date based on frequency."""
        if self.maintenance_frequency and self.last_maintenance:
            last_date = getdate(self.last_maintenance)
            
            if self.maintenance_frequency == "Weekly":
                self.next_maintenance = add_days(last_date, 7)
            elif self.maintenance_frequency == "Monthly":
                self.next_maintenance = last_date + relativedelta(months=1)
            elif self.maintenance_frequency == "Quarterly":
                self.next_maintenance = last_date + relativedelta(months=3)
            elif self.maintenance_frequency == "Semi-Annual":
                self.next_maintenance = last_date + relativedelta(months=6)
            elif self.maintenance_frequency == "Annual":
                self.next_maintenance = last_date + relativedelta(years=1)
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
    
    @frappe.whitelist()
    def schedule_maintenance(self, maintenance_date, notes=None):
        """Schedule maintenance for this equipment."""
        maintenance_doc = frappe.get_doc({
            "doctype": "Equipment Maintenance",
            "equipment": self.name,
            "maintenance_date": maintenance_date,
            "maintenance_type": "Scheduled",
            "notes": notes or "",
            "status": "Scheduled"
        })
        
        maintenance_doc.insert()
        
        # Update equipment status
        self.status = "Under Maintenance"
        self.save()
        
        return maintenance_doc.name
    
    @frappe.whitelist()
    def report_issue(self, issue_description, priority="Medium"):
        """Report an issue with this equipment."""
        issue_doc = frappe.get_doc({
            "doctype": "Equipment Issue",
            "equipment": self.name,
            "issue_description": issue_description,
            "priority": priority,
            "reported_by": frappe.session.user,
            "status": "Open"
        })
        
        issue_doc.insert()
        
        # Update equipment issues
        current_issues = self.issues_reported or ""
        new_issue = f"\n{getdate()}: {issue_description}"
        self.issues_reported = current_issues + new_issue
        
        # Update status if critical
        if priority == "Critical":
            self.status = "Out of Order"
        
        self.save()
        
        return issue_doc.name
    
    @frappe.whitelist()
    def get_maintenance_history(self):
        """Get maintenance history for this equipment."""
        history = frappe.get_list("Equipment Maintenance",
            filters={"equipment": self.name},
            fields=["maintenance_date", "maintenance_type", "status", "notes", "cost"],
            order_by="maintenance_date desc"
        )
        
        return history
    
    @frappe.whitelist()
    def get_utilization_stats(self):
        """Get utilization statistics."""
        # This would integrate with booking/usage tracking
        stats = {
            "total_bookings": 0,
            "hours_used": 0,
            "utilization_rate": 0,
            "last_used": None,
            "most_frequent_user": None
        }
        
        return stats
    
    @frappe.whitelist()
    def check_warranty_status(self):
        """Check warranty status."""
        if not self.warranty_expiry:
            return {"status": "No warranty info", "days_remaining": None}
        
        today = getdate()
        warranty_date = getdate(self.warranty_expiry)
        
        if warranty_date < today:
            return {"status": "Expired", "days_remaining": 0}
        
        days_remaining = date_diff(warranty_date, today)
        
        if days_remaining <= 30:
            return {"status": "Expiring Soon", "days_remaining": days_remaining}
        
        return {"status": "Active", "days_remaining": days_remaining}
