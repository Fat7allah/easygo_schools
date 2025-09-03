"""Leave Application DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, flt, cint, date_diff, add_days


class LeaveApplication(Document):
    """Employee leave application management."""
    
    def validate(self):
        """Validate leave application data."""
        self.validate_dates()
        self.validate_leave_balance()
        self.validate_overlapping_applications()
        self.calculate_total_days()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate leave dates."""
        if self.from_date and self.to_date:
            if getdate(self.from_date) > getdate(self.to_date):
                frappe.throw(_("To Date cannot be before From Date"))
            
            if getdate(self.from_date) < getdate():
                frappe.msgprint(_("Warning: Leave start date is in the past"))
        
        if self.half_day and not self.half_day_date:
            frappe.throw(_("Half Day Date is required when Half Day is checked"))
        
        if self.half_day_date:
            if not (getdate(self.from_date) <= getdate(self.half_day_date) <= getdate(self.to_date)):
                frappe.throw(_("Half Day Date must be between From Date and To Date"))
    
    def validate_leave_balance(self):
        """Validate available leave balance."""
        if not self.leave_type or not self.employee:
            return
        
        # Get current leave balance
        leave_balance = self.get_leave_balance()
        self.leave_balance_before = leave_balance
        
        # Calculate total leave days
        total_days = self.get_total_leave_days()
        
        # Check if sufficient balance
        if leave_balance < total_days:
            leave_type_doc = frappe.get_doc("Leave Type", self.leave_type)
            if not leave_type_doc.allow_negative_balance:
                frappe.throw(_("Insufficient leave balance. Available: {0}, Requested: {1}").format(
                    leave_balance, total_days
                ))
        
        self.leave_balance_after = leave_balance - total_days
    
    def get_leave_balance(self):
        """Get current leave balance for employee and leave type."""
        # Get leave allocation
        allocation = frappe.db.get_value("Leave Allocation",
            {
                "employee": self.employee,
                "leave_type": self.leave_type,
                "docstatus": 1,
                "from_date": ["<=", self.from_date],
                "to_date": [">=", self.to_date]
            },
            "total_leaves_allocated"
        )
        
        if not allocation:
            return 0
        
        # Get used leaves
        used_leaves = frappe.db.sql("""
            SELECT SUM(total_leave_days)
            FROM `tabLeave Application`
            WHERE employee = %s
            AND leave_type = %s
            AND status = 'Approved'
            AND docstatus = 1
            AND name != %s
        """, (self.employee, self.leave_type, self.name or ""))[0][0] or 0
        
        return flt(allocation) - flt(used_leaves)
    
    def validate_overlapping_applications(self):
        """Check for overlapping leave applications."""
        overlapping = frappe.db.sql("""
            SELECT name
            FROM `tabLeave Application`
            WHERE employee = %s
            AND docstatus = 1
            AND status IN ('Open', 'Approved')
            AND name != %s
            AND (
                (from_date <= %s AND to_date >= %s) OR
                (from_date <= %s AND to_date >= %s) OR
                (from_date >= %s AND to_date <= %s)
            )
        """, (
            self.employee, self.name or "",
            self.from_date, self.from_date,
            self.to_date, self.to_date,
            self.from_date, self.to_date
        ))
        
        if overlapping:
            frappe.throw(_("Leave application overlaps with existing application: {0}").format(overlapping[0][0]))
    
    def calculate_total_days(self):
        """Calculate total leave days."""
        self.total_leave_days = self.get_total_leave_days()
    
    def get_total_leave_days(self):
        """Get total leave days including half day consideration."""
        if not self.from_date or not self.to_date:
            return 0
        
        total_days = date_diff(self.to_date, self.from_date) + 1
        
        # Exclude weekends and holidays
        working_days = self.get_working_days(self.from_date, self.to_date)
        
        if self.half_day:
            working_days -= 0.5
        
        return working_days
    
    def get_working_days(self, start_date, end_date):
        """Calculate working days excluding weekends and holidays."""
        # Get holiday list
        holiday_list = frappe.db.get_value("Employee", self.employee, "holiday_list")
        
        if not holiday_list:
            holiday_list = frappe.db.get_single_value("HR Settings", "default_holiday_list")
        
        working_days = 0
        current_date = getdate(start_date)
        end_date = getdate(end_date)
        
        while current_date <= end_date:
            # Check if it's a working day
            if self.is_working_day(current_date, holiday_list):
                working_days += 1
            current_date = add_days(current_date, 1)
        
        return working_days
    
    def is_working_day(self, date, holiday_list):
        """Check if date is a working day."""
        # Check if it's a weekend (assuming Saturday-Sunday)
        weekday = date.weekday()
        if weekday >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check if it's a holiday
        if holiday_list:
            is_holiday = frappe.db.exists("Holiday",
                {"parent": holiday_list, "holiday_date": date}
            )
            if is_holiday:
                return False
        
        return True
    
    def set_defaults(self):
        """Set default values."""
        if not self.posting_date:
            self.posting_date = getdate()
        
        if not self.leave_approver:
            # Get default approver
            approver = frappe.db.get_value("Employee", self.employee, "leave_approver")
            if approver:
                self.leave_approver = approver
            else:
                # Get department head or HR manager
                dept_head = frappe.db.get_value("Department", self.department, "leave_approver")
                if dept_head:
                    self.leave_approver = dept_head
    
    def on_submit(self):
        """Actions on submit."""
        self.send_leave_notifications()
        self.create_approval_task()
    
    def send_leave_notifications(self):
        """Send leave application notifications."""
        # Notify leave approver
        if self.leave_approver:
            self.send_approver_notification()
        
        # Notify HR team
        self.send_hr_notification()
        
        # Send confirmation to employee
        self.send_employee_confirmation()
    
    def send_approver_notification(self):
        """Send notification to leave approver."""
        frappe.sendmail(
            recipients=[self.leave_approver],
            subject=_("Leave Application for Approval - {0}").format(self.employee_name),
            message=self.get_approver_notification_message(),
            reference_doctype=self.doctype,
            reference_name=self.name
        )
    
    def get_approver_notification_message(self):
        """Get approver notification message."""
        return _("""
        Leave Application Pending Approval
        
        Employee: {employee_name} ({employee})
        Department: {department}
        Leave Type: {leave_type}
        
        Leave Period: {from_date} to {to_date}
        Total Days: {total_days}
        Half Day: {half_day_status}
        
        Reason: {reason}
        
        Current Leave Balance: {leave_balance}
        Balance After Leave: {balance_after}
        
        Please review and approve/reject this application.
        
        HR Management System
        """).format(
            employee_name=self.employee_name,
            employee=self.employee,
            department=self.department or "Not specified",
            leave_type=self.leave_type,
            from_date=frappe.format(self.from_date, "Date"),
            to_date=frappe.format(self.to_date, "Date"),
            total_days=self.total_leave_days,
            half_day_status="Yes" if self.half_day else "No",
            reason=self.reason,
            leave_balance=self.leave_balance_before,
            balance_after=self.leave_balance_after
        )
    
    def send_hr_notification(self):
        """Send notification to HR team."""
        hr_users = frappe.get_all("Has Role",
            filters={"role": "HR Manager"},
            fields=["parent"]
        )
        
        if hr_users:
            recipients = [user.parent for user in hr_users]
            
            frappe.sendmail(
                recipients=recipients,
                subject=_("New Leave Application - {0}").format(self.employee_name),
                message=self.get_hr_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_hr_notification_message(self):
        """Get HR notification message."""
        return _("""
        New Leave Application Submitted
        
        Employee: {employee_name}
        Department: {department}
        Designation: {designation}
        Leave Type: {leave_type}
        
        Leave Details:
        - From: {from_date}
        - To: {to_date}
        - Total Days: {total_days}
        - Reason: {reason}
        
        Leave Balance:
        - Before: {leave_balance_before}
        - After: {leave_balance_after}
        
        Approver: {leave_approver}
        Status: {status}
        
        HR Management System
        """).format(
            employee_name=self.employee_name,
            department=self.department or "Not specified",
            designation=self.designation or "Not specified",
            leave_type=self.leave_type,
            from_date=frappe.format(self.from_date, "Date"),
            to_date=frappe.format(self.to_date, "Date"),
            total_days=self.total_leave_days,
            reason=self.reason,
            leave_balance_before=self.leave_balance_before,
            leave_balance_after=self.leave_balance_after,
            leave_approver=frappe.get_value("User", self.leave_approver, "full_name") if self.leave_approver else "Not assigned",
            status=self.status
        )
    
    def send_employee_confirmation(self):
        """Send confirmation to employee."""
        employee = frappe.get_doc("Employee", self.employee)
        
        if employee.user_id:
            frappe.sendmail(
                recipients=[employee.user_id],
                subject=_("Leave Application Submitted"),
                message=self.get_employee_confirmation_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_employee_confirmation_message(self):
        """Get employee confirmation message."""
        return _("""
        Dear {employee_name},
        
        Your leave application has been successfully submitted.
        
        Application Details:
        - Application Number: {application_number}
        - Leave Type: {leave_type}
        - From: {from_date}
        - To: {to_date}
        - Total Days: {total_days}
        
        Your application is now pending approval from {approver_name}.
        
        You will be notified once your application is reviewed.
        
        Thank you,
        HR Team
        """).format(
            employee_name=self.employee_name,
            application_number=self.name,
            leave_type=self.leave_type,
            from_date=frappe.format(self.from_date, "Date"),
            to_date=frappe.format(self.to_date, "Date"),
            total_days=self.total_leave_days,
            approver_name=frappe.get_value("User", self.leave_approver, "full_name") if self.leave_approver else "your manager"
        )
    
    def create_approval_task(self):
        """Create approval task for leave approver."""
        if self.leave_approver:
            frappe.get_doc({
                "doctype": "ToDo",
                "description": f"Approve leave application: {self.name} for {self.employee_name}",
                "reference_type": self.doctype,
                "reference_name": self.name,
                "assigned_by": frappe.session.user,
                "owner": self.leave_approver,
                "date": add_days(getdate(), 2),  # 2 days to approve
                "priority": "Medium"
            }).insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def approve_leave(self, approval_notes=None):
        """Approve leave application."""
        if self.status == "Approved":
            frappe.throw(_("Leave application is already approved"))
        
        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approved_on = getdate()
        
        if approval_notes:
            self.description = (self.description or "") + f"\nApproval Notes: {approval_notes}"
        
        self.save()
        
        # Send approval notifications
        self.send_approval_notifications()
        
        # Create calendar events
        self.create_leave_calendar_events()
        
        frappe.msgprint(_("Leave application approved"))
        return self
    
    def send_approval_notifications(self):
        """Send approval notifications."""
        # Notify employee
        employee = frappe.get_doc("Employee", self.employee)
        if employee.user_id:
            frappe.sendmail(
                recipients=[employee.user_id],
                subject=_("Leave Application Approved"),
                message=self.get_approval_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
        
        # Notify HR team
        hr_users = frappe.get_all("Has Role",
            filters={"role": "HR Manager"},
            fields=["parent"]
        )
        
        if hr_users:
            recipients = [user.parent for user in hr_users]
            frappe.sendmail(
                recipients=recipients,
                subject=_("Leave Approved - {0}").format(self.employee_name),
                message=self.get_hr_approval_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_approval_notification_message(self):
        """Get approval notification message for employee."""
        return _("""
        Dear {employee_name},
        
        Great news! Your leave application has been approved.
        
        Approved Leave Details:
        - Leave Type: {leave_type}
        - From: {from_date}
        - To: {to_date}
        - Total Days: {total_days}
        - Approved By: {approved_by}
        - Approved On: {approved_on}
        
        Please ensure proper handover of your responsibilities before going on leave.
        
        Enjoy your time off!
        
        HR Team
        """).format(
            employee_name=self.employee_name,
            leave_type=self.leave_type,
            from_date=frappe.format(self.from_date, "Date"),
            to_date=frappe.format(self.to_date, "Date"),
            total_days=self.total_leave_days,
            approved_by=frappe.get_value("User", self.approved_by, "full_name") if self.approved_by else "Manager",
            approved_on=frappe.format(self.approved_on, "Date")
        )
    
    def get_hr_approval_message(self):
        """Get HR approval notification message."""
        return _("""
        Leave Application Approved
        
        Employee: {employee_name}
        Application: {application_name}
        Leave Type: {leave_type}
        Period: {from_date} to {to_date}
        Total Days: {total_days}
        
        Approved By: {approved_by}
        Approved On: {approved_on}
        
        Updated Leave Balance: {balance_after}
        
        HR Management System
        """).format(
            employee_name=self.employee_name,
            application_name=self.name,
            leave_type=self.leave_type,
            from_date=frappe.format(self.from_date, "Date"),
            to_date=frappe.format(self.to_date, "Date"),
            total_days=self.total_leave_days,
            approved_by=frappe.get_value("User", self.approved_by, "full_name") if self.approved_by else "Manager",
            approved_on=frappe.format(self.approved_on, "Date"),
            balance_after=self.leave_balance_after
        )
    
    def create_leave_calendar_events(self):
        """Create calendar events for approved leave."""
        # Create event for the employee
        frappe.get_doc({
            "doctype": "Event",
            "subject": f"Leave - {self.leave_type}",
            "starts_on": f"{self.from_date} 00:00:00",
            "ends_on": f"{self.to_date} 23:59:59",
            "all_day": 1,
            "event_type": "Private",
            "description": f"Leave Application: {self.name}\nReason: {self.reason}",
            "color": "#ff6b6b"
        }).insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def reject_leave(self, rejection_reason):
        """Reject leave application."""
        if self.status == "Rejected":
            frappe.throw(_("Leave application is already rejected"))
        
        self.status = "Rejected"
        self.rejected_by = frappe.session.user
        self.rejected_on = getdate()
        
        self.description = (self.description or "") + f"\nRejection Reason: {rejection_reason}"
        
        self.save()
        
        # Send rejection notification
        self.send_rejection_notification(rejection_reason)
        
        frappe.msgprint(_("Leave application rejected"))
        return self
    
    def send_rejection_notification(self, reason):
        """Send rejection notification to employee."""
        employee = frappe.get_doc("Employee", self.employee)
        
        if employee.user_id:
            frappe.sendmail(
                recipients=[employee.user_id],
                subject=_("Leave Application Rejected"),
                message=self.get_rejection_notification_message(reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_rejection_notification_message(self, reason):
        """Get rejection notification message."""
        return _("""
        Dear {employee_name},
        
        We regret to inform you that your leave application has been rejected.
        
        Application Details:
        - Leave Type: {leave_type}
        - From: {from_date}
        - To: {to_date}
        - Total Days: {total_days}
        
        Rejection Reason:
        {rejection_reason}
        
        Rejected By: {rejected_by}
        Rejected On: {rejected_on}
        
        If you have any questions, please contact your manager or HR department.
        
        HR Team
        """).format(
            employee_name=self.employee_name,
            leave_type=self.leave_type,
            from_date=frappe.format(self.from_date, "Date"),
            to_date=frappe.format(self.to_date, "Date"),
            total_days=self.total_leave_days,
            rejection_reason=reason,
            rejected_by=frappe.get_value("User", self.rejected_by, "full_name") if self.rejected_by else "Manager",
            rejected_on=frappe.format(self.rejected_on, "Date")
        )
    
    @frappe.whitelist()
    def cancel_leave(self, cancellation_reason):
        """Cancel leave application."""
        if self.status == "Cancelled":
            frappe.throw(_("Leave application is already cancelled"))
        
        self.status = "Cancelled"
        self.description = (self.description or "") + f"\nCancellation Reason: {cancellation_reason}"
        
        self.save()
        
        # Send cancellation notification
        self.send_cancellation_notification(cancellation_reason)
        
        frappe.msgprint(_("Leave application cancelled"))
        return self
    
    def send_cancellation_notification(self, reason):
        """Send cancellation notification."""
        # Notify approver and HR
        recipients = []
        
        if self.leave_approver:
            recipients.append(self.leave_approver)
        
        hr_users = frappe.get_all("Has Role",
            filters={"role": "HR Manager"},
            fields=["parent"]
        )
        
        recipients.extend([user.parent for user in hr_users])
        
        if recipients:
            frappe.sendmail(
                recipients=list(set(recipients)),
                subject=_("Leave Application Cancelled - {0}").format(self.employee_name),
                message=self.get_cancellation_notification_message(reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_cancellation_notification_message(self, reason):
        """Get cancellation notification message."""
        return _("""
        Leave Application Cancelled
        
        Employee: {employee_name}
        Application: {application_name}
        Leave Type: {leave_type}
        Period: {from_date} to {to_date}
        
        Cancellation Reason:
        {cancellation_reason}
        
        The leave application has been cancelled and will not affect the employee's leave balance.
        
        HR Management System
        """).format(
            employee_name=self.employee_name,
            application_name=self.name,
            leave_type=self.leave_type,
            from_date=frappe.format(self.from_date, "Date"),
            to_date=frappe.format(self.to_date, "Date"),
            cancellation_reason=reason
        )
    
    @frappe.whitelist()
    def get_leave_analytics(self):
        """Get leave analytics for employee."""
        # Get employee's leave history
        leave_history = frappe.get_all("Leave Application",
            filters={"employee": self.employee, "docstatus": 1},
            fields=["leave_type", "total_leave_days", "status", "from_date"],
            order_by="from_date desc",
            limit=10
        )
        
        # Get leave type balances
        leave_balances = {}
        leave_types = frappe.get_all("Leave Type", fields=["name"])
        
        for leave_type in leave_types:
            balance = frappe.db.get_value("Leave Allocation",
                {
                    "employee": self.employee,
                    "leave_type": leave_type.name,
                    "docstatus": 1
                },
                "total_leaves_allocated"
            ) or 0
            
            used = frappe.db.sql("""
                SELECT SUM(total_leave_days)
                FROM `tabLeave Application`
                WHERE employee = %s
                AND leave_type = %s
                AND status = 'Approved'
                AND docstatus = 1
            """, (self.employee, leave_type.name))[0][0] or 0
            
            leave_balances[leave_type.name] = {
                "allocated": balance,
                "used": used,
                "remaining": balance - used
            }
        
        return {
            "current_application": {
                "name": self.name,
                "leave_type": self.leave_type,
                "total_days": self.total_leave_days,
                "status": self.status
            },
            "leave_balances": leave_balances,
            "recent_applications": leave_history,
            "employee_info": {
                "name": self.employee_name,
                "department": self.department,
                "designation": self.designation
            }
        }
