"""Activity Schedule DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, get_time, now_datetime, add_days, add_weeks, add_months


class ActivitySchedule(Document):
    """Activity Schedule management."""
    
    def validate(self):
        """Validate activity schedule data."""
        self.validate_timing()
        self.validate_venue_availability()
        self.validate_instructor_availability()
        self.set_defaults()
    
    def validate_timing(self):
        """Validate schedule timing."""
        if self.start_time and self.end_time:
            if get_time(self.start_time) >= get_time(self.end_time):
                frappe.throw(_("End time must be after start time"))
        
        if self.schedule_date and self.schedule_date < getdate():
            frappe.msgprint(_("Warning: Scheduling activity for a past date"))
        
        if self.is_recurring and self.end_recurrence_date:
            if self.end_recurrence_date <= self.schedule_date:
                frappe.throw(_("End recurrence date must be after schedule date"))
    
    def validate_venue_availability(self):
        """Validate venue availability."""
        if self.venue and self.schedule_date and self.start_time and self.end_time:
            # Check for conflicting schedules
            conflicts = frappe.db.sql("""
                SELECT name FROM `tabActivity Schedule`
                WHERE venue = %s 
                AND schedule_date = %s
                AND name != %s
                AND status NOT IN ('Cancelled', 'Completed')
                AND (
                    (start_time <= %s AND end_time > %s) OR
                    (start_time < %s AND end_time >= %s) OR
                    (start_time >= %s AND end_time <= %s)
                )
            """, [self.venue, self.schedule_date, self.name or "", 
                  self.start_time, self.start_time, self.end_time, self.end_time,
                  self.start_time, self.end_time])
            
            if conflicts:
                frappe.throw(_("Venue {0} is not available at the scheduled time").format(self.venue))
    
    def validate_instructor_availability(self):
        """Validate instructor availability."""
        if self.instructor and self.schedule_date and self.start_time and self.end_time:
            # Check for conflicting instructor schedules
            conflicts = frappe.db.sql("""
                SELECT name FROM `tabActivity Schedule`
                WHERE instructor = %s 
                AND schedule_date = %s
                AND name != %s
                AND status NOT IN ('Cancelled', 'Completed')
                AND (
                    (start_time <= %s AND end_time > %s) OR
                    (start_time < %s AND end_time >= %s) OR
                    (start_time >= %s AND end_time <= %s)
                )
            """, [self.instructor, self.schedule_date, self.name or "",
                  self.start_time, self.start_time, self.end_time, self.end_time,
                  self.start_time, self.end_time])
            
            if conflicts:
                frappe.throw(_("Instructor is not available at the scheduled time"))
    
    def set_defaults(self):
        """Set default values."""
        if self.activity:
            activity_doc = frappe.get_doc("Extracurricular Activity", self.activity)
            
            if not self.instructor and activity_doc.default_instructor:
                self.instructor = activity_doc.default_instructor
            
            if not self.venue and activity_doc.default_venue:
                self.venue = activity_doc.default_venue
            
            if not self.max_participants:
                self.max_participants = activity_doc.max_participants
    
    def on_submit(self):
        """Actions on submit."""
        self.create_recurring_schedules()
        self.send_schedule_notifications()
        self.update_activity_registrations()
    
    def create_recurring_schedules(self):
        """Create recurring schedules if specified."""
        if not self.is_recurring or not self.recurrence_pattern:
            return
        
        current_date = self.schedule_date
        end_date = self.end_recurrence_date or add_months(current_date, 3)  # Default 3 months
        
        while current_date < end_date:
            # Calculate next occurrence
            if self.recurrence_pattern == "Daily":
                current_date = add_days(current_date, 1)
            elif self.recurrence_pattern == "Weekly":
                current_date = add_weeks(current_date, 1)
            elif self.recurrence_pattern == "Bi-weekly":
                current_date = add_weeks(current_date, 2)
            elif self.recurrence_pattern == "Monthly":
                current_date = add_months(current_date, 1)
            
            if current_date >= end_date:
                break
            
            # Create new schedule
            new_schedule = frappe.copy_doc(self)
            new_schedule.schedule_date = current_date
            new_schedule.is_recurring = 0  # Prevent infinite recursion
            new_schedule.registered_participants = 0
            new_schedule.attendance_taken = 0
            new_schedule.attendance_count = 0
            
            try:
                new_schedule.insert()
            except Exception as e:
                frappe.log_error(f"Failed to create recurring schedule: {str(e)}")
                break
    
    def send_schedule_notifications(self):
        """Send schedule notifications to registered participants."""
        # Get registered students for this activity
        registrations = frappe.get_all("Activity Registration",
            filters={"activity": self.activity, "status": "Active"},
            fields=["student", "student_name"]
        )
        
        for registration in registrations:
            self.send_student_notification(registration.student, registration.student_name)
    
    def send_student_notification(self, student, student_name):
        """Send notification to individual student."""
        student_doc = frappe.get_doc("Student", student)
        recipients = []
        
        # Get guardian emails
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": student},
            fields=["guardian"]
        )
        
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            if guardian.email_address:
                recipients.append(guardian.email_address)
        
        # Add student email if available
        if student_doc.student_email_id:
            recipients.append(student_doc.student_email_id)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Activity Schedule - {0}").format(self.activity_name),
                message=self.get_schedule_notification_message(student_name),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_schedule_notification_message(self, student_name):
        """Get schedule notification message."""
        return _("""
        Dear Student/Guardian,
        
        A new session has been scheduled for the activity {student_name} is registered in.
        
        Activity Details:
        - Activity: {activity_name}
        - Date: {schedule_date}
        - Time: {start_time} - {end_time}
        - Venue: {venue}
        - Instructor: {instructor}
        
        Requirements:
        {requirements}
        
        Equipment Needed:
        {equipment}
        
        Special Instructions:
        {instructions}
        
        Please ensure {student_name} attends on time with all required equipment.
        
        Activities Team
        """).format(
            student_name=student_name,
            activity_name=self.activity_name,
            schedule_date=frappe.format(self.schedule_date, "Date"),
            start_time=self.start_time,
            end_time=self.end_time,
            venue=self.venue or "TBA",
            instructor=self.instructor or "TBA",
            requirements=self.requirements or "None",
            equipment=self.equipment_needed or "None",
            instructions=self.special_instructions or "None"
        )
    
    def update_activity_registrations(self):
        """Update registered participants count."""
        registration_count = frappe.db.count("Activity Registration", {
            "activity": self.activity,
            "status": "Active"
        })
        
        self.registered_participants = registration_count
        self.save()
    
    @frappe.whitelist()
    def mark_in_progress(self):
        """Mark activity as in progress."""
        if self.status != "Scheduled":
            frappe.throw(_("Can only start scheduled activities"))
        
        self.status = "In Progress"
        self.save()
        
        frappe.msgprint(_("Activity marked as in progress"))
        return self
    
    @frappe.whitelist()
    def mark_completed(self):
        """Mark activity as completed."""
        if self.status != "In Progress":
            frappe.throw(_("Activity must be in progress to complete"))
        
        self.status = "Completed"
        self.save()
        
        # Create completion records for registered students
        self.create_completion_records()
        
        frappe.msgprint(_("Activity marked as completed"))
        return self
    
    def create_completion_records(self):
        """Create completion records for students."""
        registrations = frappe.get_all("Activity Registration",
            filters={"activity": self.activity, "status": "Active"},
            fields=["student", "student_name"]
        )
        
        for registration in registrations:
            completion = frappe.get_doc({
                "doctype": "Activity Completion",
                "student": registration.student,
                "activity": self.activity,
                "schedule": self.name,
                "completion_date": self.schedule_date,
                "instructor": self.instructor,
                "status": "Completed"
            })
            
            completion.insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def cancel_schedule(self, reason=None):
        """Cancel the activity schedule."""
        if self.status in ["Completed", "Cancelled"]:
            frappe.throw(_("Cannot cancel {0} activity").format(self.status.lower()))
        
        self.status = "Cancelled"
        self.cancelled_reason = reason
        self.save()
        
        # Send cancellation notifications
        self.send_cancellation_notifications(reason)
        
        frappe.msgprint(_("Activity schedule cancelled"))
        return self
    
    def send_cancellation_notifications(self, reason):
        """Send cancellation notifications."""
        registrations = frappe.get_all("Activity Registration",
            filters={"activity": self.activity, "status": "Active"},
            fields=["student", "student_name"]
        )
        
        for registration in registrations:
            self.send_cancellation_notification(registration.student, registration.student_name, reason)
    
    def send_cancellation_notification(self, student, student_name, reason):
        """Send cancellation notification to student."""
        student_doc = frappe.get_doc("Student", student)
        recipients = []
        
        # Get guardian emails
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": student},
            fields=["guardian"]
        )
        
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            if guardian.email_address:
                recipients.append(guardian.email_address)
        
        if student_doc.student_email_id:
            recipients.append(student_doc.student_email_id)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Activity Cancelled - {0}").format(self.activity_name),
                message=self.get_cancellation_message(student_name, reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_cancellation_message(self, student_name, reason):
        """Get cancellation message."""
        return _("""
        Dear Student/Guardian,
        
        We regret to inform you that the following activity session has been cancelled:
        
        Activity: {activity_name}
        Date: {schedule_date}
        Time: {start_time} - {end_time}
        
        Reason for Cancellation:
        {reason}
        
        We apologize for any inconvenience caused. We will notify you of any rescheduled sessions.
        
        Activities Team
        """).format(
            activity_name=self.activity_name,
            schedule_date=frappe.format(self.schedule_date, "Date"),
            start_time=self.start_time,
            end_time=self.end_time,
            reason=reason or "Not specified"
        )
    
    @frappe.whitelist()
    def reschedule_activity(self, new_date, new_start_time, new_end_time, reason=None):
        """Reschedule the activity."""
        if self.status in ["Completed", "Cancelled"]:
            frappe.throw(_("Cannot reschedule {0} activity").format(self.status.lower()))
        
        # Create new schedule
        new_schedule = frappe.copy_doc(self)
        new_schedule.schedule_date = new_date
        new_schedule.start_time = new_start_time
        new_schedule.end_time = new_end_time
        new_schedule.status = "Scheduled"
        
        new_schedule.insert()
        
        # Update current schedule
        self.status = "Rescheduled"
        self.rescheduled_to = new_schedule.name
        self.save()
        
        # Send reschedule notifications
        self.send_reschedule_notifications(new_schedule, reason)
        
        frappe.msgprint(_("Activity rescheduled to {0}").format(new_schedule.name))
        return new_schedule.name
    
    def send_reschedule_notifications(self, new_schedule, reason):
        """Send reschedule notifications."""
        registrations = frappe.get_all("Activity Registration",
            filters={"activity": self.activity, "status": "Active"},
            fields=["student", "student_name"]
        )
        
        for registration in registrations:
            self.send_reschedule_notification(registration.student, registration.student_name, new_schedule, reason)
    
    def send_reschedule_notification(self, student, student_name, new_schedule, reason):
        """Send reschedule notification to student."""
        student_doc = frappe.get_doc("Student", student)
        recipients = []
        
        # Get guardian emails
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": student},
            fields=["guardian"]
        )
        
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            if guardian.email_address:
                recipients.append(guardian.email_address)
        
        if student_doc.student_email_id:
            recipients.append(student_doc.student_email_id)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Activity Rescheduled - {0}").format(self.activity_name),
                message=self.get_reschedule_message(student_name, new_schedule, reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_reschedule_message(self, student_name, new_schedule, reason):
        """Get reschedule message."""
        return _("""
        Dear Student/Guardian,
        
        The following activity session has been rescheduled:
        
        Original Schedule:
        - Date: {old_date}
        - Time: {old_time}
        
        New Schedule:
        - Date: {new_date}
        - Time: {new_time}
        - Venue: {venue}
        
        Reason for Rescheduling:
        {reason}
        
        Please make note of the new schedule. We apologize for any inconvenience.
        
        Activities Team
        """).format(
            old_date=frappe.format(self.schedule_date, "Date"),
            old_time=f"{self.start_time} - {self.end_time}",
            new_date=frappe.format(new_schedule.schedule_date, "Date"),
            new_time=f"{new_schedule.start_time} - {new_schedule.end_time}",
            venue=new_schedule.venue or "TBA",
            reason=reason or "Not specified"
        )
    
    @frappe.whitelist()
    def take_attendance(self, attendance_data):
        """Take attendance for the activity."""
        if self.status != "In Progress":
            frappe.throw(_("Can only take attendance for activities in progress"))
        
        attendance_count = 0
        
        for student_data in attendance_data:
            student = student_data.get("student")
            status = student_data.get("status", "Present")
            
            # Create attendance record
            attendance = frappe.get_doc({
                "doctype": "Activity Attendance",
                "activity_schedule": self.name,
                "student": student,
                "attendance_date": self.schedule_date,
                "status": status,
                "marked_by": frappe.session.user,
                "marked_time": now_datetime()
            })
            
            attendance.insert(ignore_permissions=True)
            
            if status == "Present":
                attendance_count += 1
        
        self.attendance_taken = 1
        self.attendance_count = attendance_count
        self.save()
        
        frappe.msgprint(_("Attendance recorded for {0} students").format(attendance_count))
        return self
    
    @frappe.whitelist()
    def get_schedule_analytics(self):
        """Get schedule analytics and insights."""
        # Get attendance statistics
        attendance_stats = frappe.db.sql("""
            SELECT 
                status,
                COUNT(*) as count
            FROM `tabActivity Attendance`
            WHERE activity_schedule = %s
            GROUP BY status
        """, [self.name], as_dict=True)
        
        # Get activity performance metrics
        total_registrations = frappe.db.count("Activity Registration", {
            "activity": self.activity,
            "status": "Active"
        })
        
        # Calculate utilization rate
        utilization_rate = (self.attendance_count / self.max_participants * 100) if self.max_participants else 0
        
        return {
            "schedule_info": {
                "name": self.name,
                "activity": self.activity_name,
                "date": self.schedule_date,
                "status": self.status,
                "venue": self.venue,
                "instructor": self.instructor
            },
            "participation": {
                "max_participants": self.max_participants,
                "registered_participants": self.registered_participants,
                "attendance_count": self.attendance_count,
                "utilization_rate": utilization_rate
            },
            "attendance_breakdown": attendance_stats,
            "performance_metrics": {
                "registration_rate": (self.registered_participants / total_registrations * 100) if total_registrations else 0,
                "attendance_rate": (self.attendance_count / self.registered_participants * 100) if self.registered_participants else 0
            }
        }
    
    def get_schedule_summary(self):
        """Get schedule summary for reporting."""
        return {
            "schedule_name": self.name,
            "activity": self.activity_name,
            "schedule_date": self.schedule_date,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "venue": self.venue,
            "instructor": self.instructor,
            "max_participants": self.max_participants,
            "registered_participants": self.registered_participants,
            "attendance_count": self.attendance_count,
            "status": self.status,
            "is_recurring": self.is_recurring,
            "attendance_taken": self.attendance_taken
        }
