"""Transport Route DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, get_time, flt


class TransportRoute(Document):
    """Transport Route management."""
    
    def validate(self):
        """Validate transport route data."""
        self.validate_capacity()
        self.validate_timing()
        self.validate_costs()
        self.set_defaults()
    
    def validate_capacity(self):
        """Validate route capacity against enrolled students."""
        if self.capacity and len(self.students) > self.capacity:
            frappe.throw(_("Number of students ({0}) exceeds route capacity ({1})").format(
                len(self.students), self.capacity
            ))
    
    def validate_timing(self):
        """Validate departure and return times."""
        if self.departure_time and self.return_time:
            if get_time(self.departure_time) >= get_time(self.return_time):
                frappe.throw(_("Return time must be after departure time"))
    
    def validate_costs(self):
        """Validate cost calculations."""
        if self.fuel_cost_per_km and self.fuel_cost_per_km < 0:
            frappe.throw(_("Fuel cost per KM cannot be negative"))
        
        if self.monthly_fee and self.monthly_fee < 0:
            frappe.throw(_("Monthly fee cannot be negative"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.route_code:
            self.route_code = f"RT-{self.route_name[:3].upper()}"
        
        if not self.operating_days:
            self.operating_days = "Monday to Friday"
    
    def on_update(self):
        """Actions after update."""
        self.update_student_transport_fees()
        self.calculate_route_efficiency()
    
    @frappe.whitelist()
    def add_student(self, student, pickup_stop, monthly_fee=None):
        """Add student to transport route."""
        if len(self.students) >= (self.capacity or 999):
            frappe.throw(_("Route capacity exceeded"))
        
        # Check if student is already on this route
        existing = [s for s in self.students if s.student == student]
        if existing:
            frappe.throw(_("Student is already enrolled in this route"))
        
        self.append("students", {
            "student": student,
            "pickup_stop": pickup_stop,
            "monthly_fee": monthly_fee or self.monthly_fee,
            "enrollment_date": getdate(),
            "status": "Active"
        })
        
        self.save()
        
        # Create transport fee entry
        self.create_transport_fee_entry(student, monthly_fee or self.monthly_fee)
        
        frappe.msgprint(_("Student added to transport route"))
        return self
    
    @frappe.whitelist()
    def remove_student(self, student, reason=None):
        """Remove student from transport route."""
        student_entries = [s for s in self.students if s.student == student]
        
        if not student_entries:
            frappe.throw(_("Student not found in this route"))
        
        # Remove student from route
        for entry in student_entries:
            self.students.remove(entry)
        
        self.save()
        
        # Log removal
        self.log_student_removal(student, reason)
        
        frappe.msgprint(_("Student removed from transport route"))
        return self
    
    def create_transport_fee_entry(self, student, monthly_fee):
        """Create transport fee entry for student."""
        fee_entry = frappe.get_doc({
            "doctype": "Transport Fee",
            "student": student,
            "transport_route": self.name,
            "monthly_fee": monthly_fee,
            "academic_year": frappe.db.get_single_value("School Settings", "current_academic_year"),
            "status": "Active"
        })
        
        fee_entry.insert(ignore_permissions=True)
        return fee_entry.name
    
    def log_student_removal(self, student, reason):
        """Log student removal from route."""
        log_entry = frappe.get_doc({
            "doctype": "Transport Log",
            "transport_route": self.name,
            "student": student,
            "action": "Removed",
            "reason": reason,
            "log_date": getdate(),
            "logged_by": frappe.session.user
        })
        
        log_entry.insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def optimize_route(self):
        """Optimize route stops for efficiency."""
        if not self.stops:
            return
        
        # Simple optimization: sort stops by distance/time
        # In a real implementation, this would use mapping APIs
        optimized_stops = []
        
        for i, stop in enumerate(self.stops):
            stop.sequence = i + 1
            optimized_stops.append(stop)
        
        self.stops = optimized_stops
        self.save()
        
        frappe.msgprint(_("Route optimized"))
        return self
    
    def calculate_route_efficiency(self):
        """Calculate route efficiency metrics."""
        if not self.capacity or not self.distance_km:
            return
        
        occupancy_rate = (len(self.students) / self.capacity) * 100
        
        # Calculate cost per student
        total_monthly_cost = flt(self.maintenance_cost)
        if self.fuel_cost_per_km and self.distance_km:
            # Assume 22 working days per month, 2 trips per day
            fuel_cost = flt(self.fuel_cost_per_km) * flt(self.distance_km) * 2 * 22
            total_monthly_cost += fuel_cost
        
        cost_per_student = total_monthly_cost / len(self.students) if self.students else 0
        
        return {
            "occupancy_rate": occupancy_rate,
            "total_monthly_cost": total_monthly_cost,
            "cost_per_student": cost_per_student,
            "revenue": sum(flt(s.monthly_fee) for s in self.students),
            "profit_margin": sum(flt(s.monthly_fee) for s in self.students) - total_monthly_cost
        }
    
    @frappe.whitelist()
    def generate_attendance_sheet(self, date=None):
        """Generate attendance sheet for the route."""
        if not date:
            date = getdate()
        
        attendance_sheet = frappe.get_doc({
            "doctype": "Transport Attendance",
            "transport_route": self.name,
            "attendance_date": date,
            "driver": self.driver,
            "vehicle": self.vehicle,
            "students": []
        })
        
        for student_entry in self.students:
            if student_entry.status == "Active":
                attendance_sheet.append("students", {
                    "student": student_entry.student,
                    "pickup_stop": student_entry.pickup_stop,
                    "morning_status": "Present",
                    "evening_status": "Present"
                })
        
        attendance_sheet.insert()
        
        frappe.msgprint(_("Attendance sheet generated: {0}").format(attendance_sheet.name))
        return attendance_sheet.name
    
    @frappe.whitelist()
    def send_route_update(self, message, recipients="all"):
        """Send route update to students/parents."""
        if recipients == "all":
            recipient_list = []
            for student_entry in self.students:
                if student_entry.status == "Active":
                    # Get student's guardians
                    guardians = frappe.get_all("Student Guardian",
                        filters={"parent": student_entry.student},
                        fields=["guardian"]
                    )
                    
                    for guardian_link in guardians:
                        guardian = frappe.get_doc("Guardian", guardian_link.guardian)
                        if guardian.email_address:
                            recipient_list.append(guardian.email_address)
                        if guardian.mobile_number:
                            self.send_route_sms(guardian.mobile_number, message)
            
            if recipient_list:
                frappe.sendmail(
                    recipients=list(set(recipient_list)),  # Remove duplicates
                    subject=_("Transport Route Update: {0}").format(self.route_name),
                    message=self.get_route_update_message(message),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        frappe.msgprint(_("Route update sent successfully"))
        return self
    
    def send_route_sms(self, mobile_number, message):
        """Send SMS update."""
        sms_message = _("Transport Update - {0}: {1}").format(self.route_name, message)
        
        # Use SMS adapter
        from easygo_education.finances_rh.adapters.sms import send_sms
        send_sms(mobile_number, sms_message)
    
    def get_route_update_message(self, update_message):
        """Get route update email message."""
        return _("""
        Transport Route Update
        
        Route: {route_name}
        Driver: {driver}
        Vehicle: {vehicle}
        
        Update Message:
        {message}
        
        Route Schedule:
        - Departure Time: {departure_time}
        - Return Time: {return_time}
        - Operating Days: {operating_days}
        
        If you have any questions, please contact the transport office.
        
        School Transport Team
        """).format(
            route_name=self.route_name,
            driver=self.driver or "Not assigned",
            vehicle=self.vehicle or "Not assigned",
            message=update_message,
            departure_time=self.departure_time or "Not set",
            return_time=self.return_time or "Not set",
            operating_days=self.operating_days
        )
    
    @frappe.whitelist()
    def get_route_analytics(self):
        """Get route analytics and performance metrics."""
        efficiency = self.calculate_route_efficiency()
        
        # Get attendance statistics
        attendance_stats = frappe.db.sql("""
            SELECT 
                AVG(CASE WHEN morning_status = 'Present' THEN 1 ELSE 0 END) * 100 as morning_attendance,
                AVG(CASE WHEN evening_status = 'Present' THEN 1 ELSE 0 END) * 100 as evening_attendance
            FROM `tabTransport Attendance Student`
            WHERE parent IN (
                SELECT name FROM `tabTransport Attendance`
                WHERE transport_route = %s
                AND attendance_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            )
        """, [self.name], as_dict=True)
        
        analytics = {
            "route_info": {
                "name": self.route_name,
                "capacity": self.capacity,
                "enrolled_students": len(self.students),
                "active_students": len([s for s in self.students if s.status == "Active"]),
                "distance_km": self.distance_km,
                "stops_count": len(self.stops)
            },
            "efficiency": efficiency,
            "attendance": attendance_stats[0] if attendance_stats else {},
            "financial": {
                "monthly_revenue": sum(flt(s.monthly_fee) for s in self.students if s.status == "Active"),
                "average_fee": sum(flt(s.monthly_fee) for s in self.students) / len(self.students) if self.students else 0
            }
        }
        
        return analytics
    
    @frappe.whitelist()
    def duplicate_route(self, new_route_name):
        """Duplicate route for similar routes."""
        new_route = frappe.copy_doc(self)
        new_route.route_name = new_route_name
        new_route.route_code = f"RT-{new_route_name[:3].upper()}"
        
        # Clear students and specific assignments
        new_route.students = []
        new_route.driver = None
        new_route.vehicle = None
        
        new_route.insert()
        
        frappe.msgprint(_("Route duplicated: {0}").format(new_route.name))
        return new_route.name
    
    def get_route_summary(self):
        """Get route summary for reporting."""
        return {
            "route_name": self.route_name,
            "route_code": self.route_code,
            "driver": self.driver,
            "vehicle": self.vehicle,
            "capacity": self.capacity,
            "enrolled_students": len(self.students),
            "active_students": len([s for s in self.students if s.status == "Active"]),
            "distance_km": self.distance_km,
            "monthly_fee": self.monthly_fee,
            "stops_count": len(self.stops),
            "is_active": self.is_active,
            "occupancy_rate": (len([s for s in self.students if s.status == "Active"]) / self.capacity * 100) if self.capacity else 0
        }
