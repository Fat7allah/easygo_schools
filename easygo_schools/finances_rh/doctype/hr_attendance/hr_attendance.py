import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, get_datetime, time_diff_in_hours, flt
from frappe import _
from datetime import datetime, timedelta


class HRAttendance(Document):
    def validate(self):
        self.validate_employee()
        self.validate_duplicate()
        self.set_employee_name()
        self.calculate_working_hours()
        self.check_late_early()
        
    def validate_employee(self):
        """Validate employee exists and is active"""
        if not frappe.db.exists("Employee", self.employee):
            frappe.throw(_("Employee {0} does not exist").format(self.employee))
            
        employee_status = frappe.db.get_value("Employee", self.employee, "status")
        if employee_status != "Active":
            frappe.throw(_("Employee {0} is not active").format(self.employee))
            
    def validate_duplicate(self):
        """Check for duplicate attendance on same date"""
        existing = frappe.db.exists("HR Attendance", {
            "employee": self.employee,
            "attendance_date": self.attendance_date,
            "name": ["!=", self.name],
            "docstatus": ["!=", 2]
        })
        
        if existing:
            frappe.throw(_("Attendance already marked for {0} on {1}").format(
                self.employee, self.attendance_date))
                
    def set_employee_name(self):
        """Set employee name from Employee master"""
        if self.employee:
            self.employee_name = frappe.db.get_value("Employee", self.employee, "employee_name")
            
    def calculate_working_hours(self):
        """Calculate working hours based on in/out time"""
        if self.in_time and self.out_time and self.status == "Present":
            # Convert to datetime objects for calculation
            in_datetime = get_datetime(self.in_time)
            out_datetime = get_datetime(self.out_time)
            
            if out_datetime > in_datetime:
                total_hours = time_diff_in_hours(out_datetime, in_datetime)
                break_hours = flt(self.break_hours) or 0
                self.working_hours = total_hours - break_hours
                
                # Calculate overtime (assuming 8 hours standard)
                standard_hours = 8.0
                if self.working_hours > standard_hours:
                    self.overtime_hours = self.working_hours - standard_hours
                else:
                    self.overtime_hours = 0
            else:
                frappe.throw(_("Out time cannot be before in time"))
        else:
            self.working_hours = 0
            self.overtime_hours = 0
            
    def check_late_early(self):
        """Check for late entry and early exit"""
        if self.in_time and self.status == "Present":
            # Get standard shift timings (can be customized)
            standard_in_time = "09:00:00"
            standard_out_time = "17:00:00"
            
            in_time = get_datetime(self.in_time).time()
            standard_in = datetime.strptime(standard_in_time, "%H:%M:%S").time()
            
            if in_time > standard_in:
                self.late_entry = 1
                
        if self.out_time and self.status == "Present":
            out_time = get_datetime(self.out_time).time()
            standard_out = datetime.strptime(standard_out_time, "%H:%M:%S").time()
            
            if out_time < standard_out:
                self.early_exit = 1
                
    def on_submit(self):
        self.update_monthly_summary()
        self.send_attendance_notification()
        
    def update_monthly_summary(self):
        """Update monthly attendance summary"""
        month = self.attendance_date.strftime("%Y-%m")
        
        # This would typically update a monthly summary document
        # Implementation depends on specific requirements
        pass
        
    def send_attendance_notification(self):
        """Send attendance notification if required"""
        if self.late_entry or self.early_exit or self.status == "Absent":
            # Notify HR and manager
            employee_doc = frappe.get_doc("Employee", self.employee)
            recipients = []
            
            # Add HR Manager
            hr_managers = frappe.get_all("User", {
                "role_profile_name": "HR Manager",
                "enabled": 1
            }, ["email"])
            recipients.extend([user.email for user in hr_managers if user.email])
            
            # Add reporting manager
            if employee_doc.reports_to:
                manager_email = frappe.db.get_value("Employee", employee_doc.reports_to, "user_id")
                if manager_email:
                    recipients.append(manager_email)
                    
            if recipients:
                subject = f"Attendance Alert: {self.employee_name}"
                message = f"""
                <p>Attendance alert for {self.employee_name}:</p>
                <p><strong>Date:</strong> {self.attendance_date}</p>
                <p><strong>Status:</strong> {self.status}</p>
                """
                
                if self.late_entry:
                    message += f"<p><strong>Late Entry:</strong> In time {self.in_time}</p>"
                if self.early_exit:
                    message += f"<p><strong>Early Exit:</strong> Out time {self.out_time}</p>"
                if self.remarks:
                    message += f"<p><strong>Remarks:</strong> {self.remarks}</p>"
                    
                frappe.sendmail(
                    recipients=recipients,
                    subject=subject,
                    message=message,
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
                
    @frappe.whitelist()
    def approve_attendance(self):
        """Approve attendance record"""
        if not frappe.has_permission(self.doctype, "write"):
            frappe.throw(_("Not permitted to approve"))
            
        self.approval_status = "Approved"
        self.approved_by = frappe.session.user
        self.approval_date = nowdate()
        self.save()
        
        frappe.msgprint(_("Attendance approved"))
        
    @frappe.whitelist()
    def reject_attendance(self, reason=None):
        """Reject attendance record"""
        if not frappe.has_permission(self.doctype, "write"):
            frappe.throw(_("Not permitted to reject"))
            
        self.approval_status = "Rejected"
        self.approved_by = frappe.session.user
        self.approval_date = nowdate()
        if reason:
            self.remarks = (self.remarks or "") + f"\nRejection Reason: {reason}"
        self.save()
        
        frappe.msgprint(_("Attendance rejected"))


@frappe.whitelist()
def mark_bulk_attendance(employees, attendance_date, status, remarks=None):
    """Mark attendance for multiple employees"""
    created_records = []
    
    for employee in employees:
        # Check if attendance already exists
        existing = frappe.db.exists("HR Attendance", {
            "employee": employee,
            "attendance_date": attendance_date
        })
        
        if not existing:
            attendance = frappe.new_doc("HR Attendance")
            attendance.employee = employee
            attendance.attendance_date = attendance_date
            attendance.status = status
            if remarks:
                attendance.remarks = remarks
            attendance.insert()
            attendance.submit()
            created_records.append(attendance.name)
            
    return created_records


@frappe.whitelist()
def get_attendance_summary(employee=None, from_date=None, to_date=None):
    """Get attendance summary for employee(s)"""
    conditions = ["docstatus = 1"]
    values = []
    
    if employee:
        conditions.append("employee = %s")
        values.append(employee)
        
    if from_date:
        conditions.append("attendance_date >= %s")
        values.append(from_date)
        
    if to_date:
        conditions.append("attendance_date <= %s")
        values.append(to_date)
        
    return frappe.db.sql(f"""
        SELECT 
            employee,
            employee_name,
            COUNT(*) as total_days,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
            SUM(CASE WHEN status = 'Half Day' THEN 1 ELSE 0 END) as half_days,
            SUM(CASE WHEN status = 'On Leave' THEN 1 ELSE 0 END) as leave_days,
            SUM(CASE WHEN late_entry = 1 THEN 1 ELSE 0 END) as late_entries,
            SUM(CASE WHEN early_exit = 1 THEN 1 ELSE 0 END) as early_exits,
            SUM(working_hours) as total_working_hours,
            SUM(overtime_hours) as total_overtime_hours
        FROM `tabHR Attendance`
        WHERE {' AND '.join(conditions)}
        GROUP BY employee, employee_name
        ORDER BY employee_name
    """, values, as_dict=True)


@frappe.whitelist()
def get_attendance_analytics():
    """Get attendance analytics"""
    today = nowdate()
    
    return {
        "today_present": frappe.db.count("HR Attendance", {
            "attendance_date": today,
            "status": "Present",
            "docstatus": 1
        }),
        "today_absent": frappe.db.count("HR Attendance", {
            "attendance_date": today,
            "status": "Absent",
            "docstatus": 1
        }),
        "today_late": frappe.db.count("HR Attendance", {
            "attendance_date": today,
            "late_entry": 1,
            "docstatus": 1
        }),
        "pending_approval": frappe.db.count("HR Attendance", {
            "approval_status": "Pending",
            "docstatus": 1
        }),
        "monthly_stats": frappe.db.sql("""
            SELECT 
                status,
                COUNT(*) as count,
                AVG(working_hours) as avg_hours
            FROM `tabHR Attendance`
            WHERE MONTH(attendance_date) = MONTH(CURDATE())
            AND YEAR(attendance_date) = YEAR(CURDATE())
            AND docstatus = 1
            GROUP BY status
        """, as_dict=True)
    }


# Scheduled job for daily attendance processing
def process_daily_attendance():
    """Process daily attendance - mark absent for employees without attendance"""
    yesterday = (datetime.now() - timedelta(days=1)).date()
    
    # Get all active employees
    active_employees = frappe.get_all("Employee", 
        filters={"status": "Active"},
        fields=["name", "employee_name"]
    )
    
    for employee in active_employees:
        # Check if attendance exists for yesterday
        existing = frappe.db.exists("HR Attendance", {
            "employee": employee.name,
            "attendance_date": yesterday
        })
        
        if not existing:
            # Mark as absent
            attendance = frappe.new_doc("HR Attendance")
            attendance.employee = employee.name
            attendance.attendance_date = yesterday
            attendance.status = "Absent"
            attendance.remarks = "Auto-marked absent - no attendance record"
            attendance.insert()
            attendance.submit()
