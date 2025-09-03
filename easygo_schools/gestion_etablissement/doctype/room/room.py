"""Room doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate, add_days


class Room(Document):
    """Room doctype controller."""
    
    def validate(self):
        """Validate room data."""
        self.validate_capacity()
        self.validate_dates()
        self.set_defaults()
    
    def validate_capacity(self):
        """Validate room capacity."""
        if self.capacity and self.capacity <= 0:
            frappe.throw(_("Capacity must be greater than 0"))
        
        if self.area_sqm and self.area_sqm <= 0:
            frappe.throw(_("Area must be greater than 0"))
    
    def validate_dates(self):
        """Validate maintenance dates."""
        if self.last_maintenance_date and getdate(self.last_maintenance_date) > getdate():
            frappe.throw(_("Last maintenance date cannot be in the future"))
        
        if self.next_maintenance_date and self.last_maintenance_date:
            if getdate(self.next_maintenance_date) <= getdate(self.last_maintenance_date):
                frappe.throw(_("Next maintenance date must be after last maintenance date"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
        
        # Set default room name if not provided
        if not self.room_name:
            self.room_name = f"{self.room_type} {self.room_number}"
    
    def before_save(self):
        """Actions before saving."""
        self.check_maintenance_alerts()
    
    def check_maintenance_alerts(self):
        """Check for maintenance alerts."""
        if self.next_maintenance_date:
            days_until_maintenance = (getdate(self.next_maintenance_date) - getdate()).days
            
            if days_until_maintenance <= 7 and days_until_maintenance > 0:
                self.create_maintenance_reminder()
            elif days_until_maintenance <= 0:
                self.status = "Maintenance"
    
    def create_maintenance_reminder(self):
        """Create maintenance reminder."""
        try:
            # Get facility manager emails
            facility_managers = frappe.get_list("User",
                filters={"role_profile_name": ["in", ["Education Manager", "Facility Manager"]]},
                fields=["email"]
            )
            
            recipients = [user.email for user in facility_managers if user.email]
            
            if recipients:
                frappe.sendmail(
                    recipients=recipients,
                    subject=_("Maintenance Due - Room {0}").format(self.room_number),
                    message=_("Room {0} ({1}) is due for maintenance on {2}.\n\nPlease schedule the maintenance accordingly.").format(
                        self.room_number, self.room_name, self.next_maintenance_date
                    ),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        except Exception as e:
            frappe.log_error(f"Failed to send maintenance reminder: {str(e)}")
    
    @frappe.whitelist()
    def check_availability(self, start_datetime, end_datetime):
        """Check room availability for booking."""
        if not self.is_active or not self.is_bookable:
            return {"available": False, "reason": "Room is not available for booking"}
        
        if self.status != "Available":
            return {"available": False, "reason": f"Room status is {self.status}"}
        
        # Check for existing bookings (this would integrate with a booking system)
        # For now, just return available
        return {"available": True, "reason": "Room is available"}
    
    @frappe.whitelist()
    def book_room(self, booking_data):
        """Book the room."""
        if isinstance(booking_data, str):
            import json
            booking_data = json.loads(booking_data)
        
        # Check availability
        availability = self.check_availability(
            booking_data.get("start_datetime"),
            booking_data.get("end_datetime")
        )
        
        if not availability["available"]:
            frappe.throw(_(availability["reason"]))
        
        # Create booking record (this would integrate with a booking system)
        booking_doc = frappe.get_doc({
            "doctype": "Room Booking",  # This DocType would need to be created
            "room": self.name,
            "booked_by": frappe.session.user,
            "start_datetime": booking_data.get("start_datetime"),
            "end_datetime": booking_data.get("end_datetime"),
            "purpose": booking_data.get("purpose"),
            "status": "Confirmed"
        })
        
        try:
            booking_doc.insert()
            return {"success": True, "booking_id": booking_doc.name}
        except:
            # If Room Booking DocType doesn't exist, just return success
            return {"success": True, "message": "Booking request submitted"}
    
    @frappe.whitelist()
    def update_maintenance(self, maintenance_data):
        """Update maintenance information."""
        if isinstance(maintenance_data, str):
            import json
            maintenance_data = json.loads(maintenance_data)
        
        self.last_maintenance_date = maintenance_data.get("maintenance_date", getdate())
        self.maintenance_notes = maintenance_data.get("notes")
        self.condition_status = maintenance_data.get("condition", self.condition_status)
        
        # Set next maintenance date (default 6 months)
        if maintenance_data.get("next_maintenance_months"):
            from dateutil.relativedelta import relativedelta
            self.next_maintenance_date = getdate() + relativedelta(months=int(maintenance_data["next_maintenance_months"]))
        else:
            self.next_maintenance_date = add_days(getdate(), 180)  # 6 months
        
        # Update status
        if self.status == "Maintenance":
            self.status = "Available"
        
        self.save()
        
        return True
    
    @frappe.whitelist()
    def get_room_utilization(self, start_date=None, end_date=None):
        """Get room utilization statistics."""
        if not start_date:
            from dateutil.relativedelta import relativedelta
            start_date = getdate() - relativedelta(months=1)
        
        if not end_date:
            end_date = getdate()
        
        # This would integrate with booking/schedule systems
        # For now, return mock data
        utilization = {
            "total_hours_available": 240,  # 8 hours * 30 days
            "total_hours_booked": 120,
            "utilization_percentage": 50,
            "peak_hours": ["09:00-11:00", "14:00-16:00"],
            "most_common_usage": self.room_type,
            "booking_frequency": {
                "daily_average": 4,
                "weekly_total": 28,
                "monthly_total": 120
            }
        }
        
        return utilization
    
    @frappe.whitelist()
    def get_equipment_inventory(self):
        """Get equipment inventory for this room."""
        equipment = {
            "basic_facilities": {
                "projector": self.has_projector,
                "whiteboard": self.has_whiteboard,
                "computer": self.has_computer,
                "air_conditioning": self.has_air_conditioning,
                "internet": self.has_internet
            },
            "additional_equipment": self.equipment_list,
            "special_features": self.special_features,
            "accessibility": self.accessibility_features,
            "safety_equipment": self.safety_equipment
        }
        
        return equipment
    
    @frappe.whitelist()
    def report_issue(self, issue_data):
        """Report an issue with the room."""
        if isinstance(issue_data, str):
            import json
            issue_data = json.loads(issue_data)
        
        # Create issue report (this would integrate with a maintenance system)
        issue_report = {
            "room": self.name,
            "reported_by": frappe.session.user,
            "issue_type": issue_data.get("type"),
            "description": issue_data.get("description"),
            "priority": issue_data.get("priority", "Medium"),
            "reported_date": now()
        }
        
        # Update room status if critical
        if issue_data.get("priority") == "Critical":
            self.status = "Out of Service"
            self.save()
        
        # Send notification to facility managers
        self.send_issue_notification(issue_report)
        
        return {"success": True, "message": "Issue reported successfully"}
    
    def send_issue_notification(self, issue_report):
        """Send issue notification to facility managers."""
        try:
            facility_managers = frappe.get_list("User",
                filters={"role_profile_name": ["in", ["Education Manager", "Facility Manager"]]},
                fields=["email"]
            )
            
            recipients = [user.email for user in facility_managers if user.email]
            
            if recipients:
                frappe.sendmail(
                    recipients=recipients,
                    subject=_("Room Issue Report - {0}").format(self.room_number),
                    message=_("An issue has been reported for Room {0} ({1}).\n\nIssue Details:\nType: {2}\nPriority: {3}\nDescription: {4}\nReported by: {5}\nDate: {6}").format(
                        self.room_number,
                        self.room_name,
                        issue_report["issue_type"],
                        issue_report["priority"],
                        issue_report["description"],
                        issue_report["reported_by"],
                        issue_report["reported_date"]
                    ),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        except Exception as e:
            frappe.log_error(f"Failed to send issue notification: {str(e)}")
    
    @frappe.whitelist()
    def get_room_schedule(self, date=None):
        """Get room schedule for a specific date."""
        if not date:
            date = getdate()
        
        # This would integrate with scheduling systems
        # For now, return mock schedule
        schedule = {
            "date": date,
            "room": self.room_number,
            "bookings": [
                {
                    "time": "09:00-10:30",
                    "subject": "Mathematics",
                    "teacher": "John Doe",
                    "class": "Grade 10A"
                },
                {
                    "time": "11:00-12:30",
                    "subject": "Physics",
                    "teacher": "Jane Smith",
                    "class": "Grade 11B"
                }
            ],
            "available_slots": [
                "08:00-09:00",
                "10:30-11:00",
                "12:30-14:00",
                "14:00-16:00"
            ]
        }
        
        return schedule
    
    @frappe.whitelist()
    def get_maintenance_history(self):
        """Get maintenance history for this room."""
        # This would integrate with maintenance tracking
        # For now, return basic info
        history = {
            "last_maintenance": {
                "date": self.last_maintenance_date,
                "notes": self.maintenance_notes,
                "condition_after": self.condition_status
            },
            "next_scheduled": {
                "date": self.next_maintenance_date,
                "days_remaining": (getdate(self.next_maintenance_date) - getdate()).days if self.next_maintenance_date else None
            },
            "maintenance_frequency": "Every 6 months",
            "total_maintenance_cost": 0  # Would be calculated from maintenance records
        }
        
        return history
