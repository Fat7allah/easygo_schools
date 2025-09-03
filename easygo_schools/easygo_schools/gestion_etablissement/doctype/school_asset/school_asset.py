"""School Asset DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, add_months, flt


class SchoolAsset(Document):
    """School Asset management."""
    
    def validate(self):
        """Validate school asset data."""
        self.validate_dates()
        self.validate_cost()
        self.calculate_warranty_expiry()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate asset dates."""
        if self.purchase_date and getdate(self.purchase_date) > getdate():
            frappe.throw(_("Purchase date cannot be in the future"))
        
        if self.warranty_expiry and self.purchase_date:
            if getdate(self.warranty_expiry) < getdate(self.purchase_date):
                frappe.throw(_("Warranty expiry cannot be before purchase date"))
    
    def validate_cost(self):
        """Validate purchase cost."""
        if self.purchase_cost and flt(self.purchase_cost) < 0:
            frappe.throw(_("Purchase cost cannot be negative"))
    
    def calculate_warranty_expiry(self):
        """Calculate warranty expiry date."""
        if self.purchase_date and self.warranty_period and not self.warranty_expiry:
            self.warranty_expiry = add_months(getdate(self.purchase_date), self.warranty_period)
    
    def set_defaults(self):
        """Set default values."""
        if not self.asset_type:
            self.asset_type = "Fixed Asset"
        
        if not self.condition_status:
            self.condition_status = "Good"
        
        if not self.status:
            self.status = "Active"
    
    def on_update(self):
        """Actions after update."""
        self.check_maintenance_due()
        self.check_warranty_expiry()
        self.update_asset_value()
    
    def check_maintenance_due(self):
        """Check if maintenance is due."""
        if self.next_maintenance_date and getdate() >= getdate(self.next_maintenance_date):
            self.create_maintenance_alert()
    
    def check_warranty_expiry(self):
        """Check warranty expiry."""
        if self.warranty_expiry:
            days_to_expiry = (getdate(self.warranty_expiry) - getdate()).days
            
            if days_to_expiry <= 30 and days_to_expiry > 0:
                self.create_warranty_alert()
            elif days_to_expiry <= 0:
                frappe.msgprint(_("Warning: Warranty has expired for asset {0}").format(self.asset_name), alert=True)
    
    def create_maintenance_alert(self):
        """Create maintenance due alert."""
        existing_alert = frappe.db.exists("Asset Alert", {
            "asset": self.name,
            "alert_type": "Maintenance Due",
            "status": "Open"
        })
        
        if not existing_alert:
            alert_doc = frappe.get_doc({
                "doctype": "Asset Alert",
                "asset": self.name,
                "asset_name": self.asset_name,
                "alert_type": "Maintenance Due",
                "message": f"Maintenance is due for asset {self.asset_name}",
                "due_date": self.next_maintenance_date,
                "status": "Open",
                "alert_date": getdate()
            })
            
            alert_doc.insert(ignore_permissions=True)
            
            # Notify asset manager
            self.notify_asset_manager("maintenance_due")
    
    def create_warranty_alert(self):
        """Create warranty expiry alert."""
        existing_alert = frappe.db.exists("Asset Alert", {
            "asset": self.name,
            "alert_type": "Warranty Expiring",
            "status": "Open"
        })
        
        if not existing_alert:
            days_to_expiry = (getdate(self.warranty_expiry) - getdate()).days
            
            alert_doc = frappe.get_doc({
                "doctype": "Asset Alert",
                "asset": self.name,
                "asset_name": self.asset_name,
                "alert_type": "Warranty Expiring",
                "message": f"Warranty expires in {days_to_expiry} days for asset {self.asset_name}",
                "due_date": self.warranty_expiry,
                "status": "Open",
                "alert_date": getdate()
            })
            
            alert_doc.insert(ignore_permissions=True)
            
            # Notify asset manager
            self.notify_asset_manager("warranty_expiring")
    
    @frappe.whitelist()
    def create_maintenance_request(self, maintenance_type, description, priority="Medium"):
        """Create maintenance request for the asset."""
        maintenance_request = frappe.get_doc({
            "doctype": "Maintenance Request",
            "asset": self.name,
            "asset_name": self.asset_name,
            "maintenance_type": maintenance_type,
            "description": description,
            "priority": priority,
            "requested_by": frappe.session.user,
            "request_date": getdate(),
            "status": "Open"
        })
        
        maintenance_request.insert()
        
        frappe.msgprint(_("Maintenance request created: {0}").format(maintenance_request.name))
        return maintenance_request.name
    
    @frappe.whitelist()
    def transfer_asset(self, new_location, new_assignee=None, transfer_reason=None):
        """Transfer asset to new location or assignee."""
        old_location = self.current_location
        old_assignee = self.assigned_to
        
        self.current_location = new_location
        if new_assignee:
            self.assigned_to = new_assignee
        
        # Create transfer log
        transfer_log = frappe.get_doc({
            "doctype": "Asset Transfer Log",
            "asset": self.name,
            "from_location": old_location,
            "to_location": new_location,
            "from_assignee": old_assignee,
            "to_assignee": new_assignee,
            "transfer_reason": transfer_reason,
            "transfer_date": getdate(),
            "transferred_by": frappe.session.user
        })
        
        transfer_log.insert(ignore_permissions=True)
        
        self.save()
        
        # Notify involved parties
        self.notify_asset_transfer(old_assignee, new_assignee, transfer_reason)
        
        frappe.msgprint(_("Asset transferred successfully"))
        return self
    
    @frappe.whitelist()
    def update_condition(self, new_condition, inspection_notes=None):
        """Update asset condition status."""
        old_condition = self.condition_status
        self.condition_status = new_condition
        
        # Create condition log
        condition_log = frappe.get_doc({
            "doctype": "Asset Condition Log",
            "asset": self.name,
            "old_condition": old_condition,
            "new_condition": new_condition,
            "inspection_notes": inspection_notes,
            "inspection_date": getdate(),
            "inspected_by": frappe.session.user
        })
        
        condition_log.insert(ignore_permissions=True)
        
        # Update status based on condition
        if new_condition in ["Poor", "Damaged"]:
            self.status = "Under Maintenance"
        elif new_condition in ["Excellent", "Good", "Fair"]:
            self.status = "Active"
        
        self.save()
        
        frappe.msgprint(_("Asset condition updated successfully"))
        return self
    
    def update_asset_value(self):
        """Update asset value based on depreciation."""
        if not self.purchase_cost or not self.purchase_date:
            return
        
        if self.depreciation_method == "Straight Line":
            self.calculate_straight_line_depreciation()
    
    def calculate_straight_line_depreciation(self):
        """Calculate straight line depreciation."""
        # Assume 5-year useful life for simplicity
        useful_life_years = 5
        annual_depreciation = flt(self.purchase_cost) / useful_life_years
        
        # Calculate years since purchase
        years_since_purchase = (getdate() - getdate(self.purchase_date)).days / 365.25
        
        total_depreciation = annual_depreciation * years_since_purchase
        current_value = max(0, flt(self.purchase_cost) - total_depreciation)
        
        return {
            "current_value": current_value,
            "total_depreciation": total_depreciation,
            "annual_depreciation": annual_depreciation
        }
    
    @frappe.whitelist()
    def generate_asset_qr_code(self):
        """Generate QR code for asset."""
        if not self.qr_code:
            import json
            qr_data = {
                "asset_code": self.asset_code,
                "asset_name": self.asset_name,
                "location": self.current_location,
                "assigned_to": self.assigned_to,
                "status": self.status
            }
            
            self.qr_code = json.dumps(qr_data)
            self.save()
        
        return self.qr_code
    
    @frappe.whitelist()
    def get_maintenance_history(self):
        """Get maintenance history for the asset."""
        return frappe.get_all("Maintenance Request",
            filters={"asset": self.name},
            fields=["name", "maintenance_type", "description", "status", "request_date", "completion_date"],
            order_by="request_date desc"
        )
    
    @frappe.whitelist()
    def get_asset_utilization(self, from_date=None, to_date=None):
        """Get asset utilization data."""
        # This would integrate with booking/scheduling systems
        utilization_data = {
            "total_bookings": 0,
            "total_hours_booked": 0,
            "utilization_percentage": 0,
            "most_frequent_user": None
        }
        
        # Placeholder for actual utilization calculation
        return utilization_data
    
    def notify_asset_manager(self, alert_type):
        """Notify asset manager about alerts."""
        asset_manager = frappe.db.get_single_value("School Settings", "asset_manager")
        
        if asset_manager:
            if alert_type == "maintenance_due":
                subject = _("Maintenance Due: {0}").format(self.asset_name)
                message = self.get_maintenance_due_message()
            elif alert_type == "warranty_expiring":
                subject = _("Warranty Expiring: {0}").format(self.asset_name)
                message = self.get_warranty_expiring_message()
            else:
                return
            
            frappe.sendmail(
                recipients=[asset_manager],
                subject=subject,
                message=message,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def notify_asset_transfer(self, old_assignee, new_assignee, reason):
        """Notify about asset transfer."""
        recipients = []
        
        if old_assignee:
            recipients.append(old_assignee)
        if new_assignee:
            recipients.append(new_assignee)
        
        asset_manager = frappe.db.get_single_value("School Settings", "asset_manager")
        if asset_manager:
            recipients.append(asset_manager)
        
        if recipients:
            frappe.sendmail(
                recipients=list(set(recipients)),  # Remove duplicates
                subject=_("Asset Transfer: {0}").format(self.asset_name),
                message=self.get_transfer_message(old_assignee, new_assignee, reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_maintenance_due_message(self):
        """Get maintenance due notification message."""
        return _("""
        Asset Maintenance Due
        
        Asset: {asset_name} ({asset_code})
        Category: {asset_category}
        Location: {current_location}
        Assigned To: {assigned_to}
        
        Next Maintenance Date: {next_maintenance_date}
        Last Maintenance: {last_maintenance_date}
        
        Please schedule maintenance for this asset.
        """).format(
            asset_name=self.asset_name,
            asset_code=self.asset_code,
            asset_category=self.asset_category,
            current_location=self.current_location or "Not specified",
            assigned_to=self.assigned_to or "Not assigned",
            next_maintenance_date=self.next_maintenance_date,
            last_maintenance_date=self.last_maintenance_date or "Never"
        )
    
    def get_warranty_expiring_message(self):
        """Get warranty expiring notification message."""
        days_to_expiry = (getdate(self.warranty_expiry) - getdate()).days
        
        return _("""
        Asset Warranty Expiring
        
        Asset: {asset_name} ({asset_code})
        Category: {asset_category}
        Supplier: {supplier}
        
        Warranty Expiry Date: {warranty_expiry}
        Days Remaining: {days_remaining}
        
        Please consider extending warranty or preparing for post-warranty maintenance.
        """).format(
            asset_name=self.asset_name,
            asset_code=self.asset_code,
            asset_category=self.asset_category,
            supplier=self.supplier or "Not specified",
            warranty_expiry=self.warranty_expiry,
            days_remaining=days_to_expiry
        )
    
    def get_transfer_message(self, old_assignee, new_assignee, reason):
        """Get asset transfer notification message."""
        return _("""
        Asset Transfer Notification
        
        Asset: {asset_name} ({asset_code})
        Category: {asset_category}
        
        From: {old_assignee}
        To: {new_assignee}
        New Location: {current_location}
        
        Transfer Reason: {reason}
        Transfer Date: {transfer_date}
        
        Please update your records accordingly.
        """).format(
            asset_name=self.asset_name,
            asset_code=self.asset_code,
            asset_category=self.asset_category,
            old_assignee=old_assignee or "Unassigned",
            new_assignee=new_assignee or "Unassigned",
            current_location=self.current_location or "Not specified",
            reason=reason or "Not specified",
            transfer_date=getdate()
        )
    
    def get_asset_summary(self):
        """Get asset summary for reporting."""
        depreciation_info = self.calculate_straight_line_depreciation() if self.purchase_cost else {}
        
        return {
            "asset_code": self.asset_code,
            "asset_name": self.asset_name,
            "category": self.asset_category,
            "status": self.status,
            "condition": self.condition_status,
            "location": self.current_location,
            "assigned_to": self.assigned_to,
            "purchase_cost": self.purchase_cost,
            "current_value": depreciation_info.get("current_value"),
            "warranty_status": "Active" if self.warranty_expiry and getdate(self.warranty_expiry) > getdate() else "Expired",
            "maintenance_due": self.next_maintenance_date and getdate(self.next_maintenance_date) <= getdate()
        }
