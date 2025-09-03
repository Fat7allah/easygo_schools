"""Salary Slip DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, flt, cint, add_days, get_first_day, get_last_day


class SalarySlip(Document):
    """Employee salary slip management."""
    
    def validate(self):
        """Validate salary slip data."""
        self.validate_employee()
        self.validate_salary_structure()
        self.calculate_salary_components()
        self.calculate_totals()
        self.set_defaults()
    
    def validate_employee(self):
        """Validate employee details."""
        if not self.employee:
            frappe.throw(_("Employee is required"))
        
        employee = frappe.get_doc("Employee", self.employee)
        
        # Check if employee is active
        if employee.status != "Active":
            frappe.throw(_("Cannot create salary slip for inactive employee"))
        
        # Validate employment dates
        if employee.relieving_date and getdate(employee.relieving_date) < getdate():
            frappe.msgprint(_("Warning: Employee has been relieved"))
    
    def validate_salary_structure(self):
        """Validate salary structure assignment."""
        if not self.salary_structure:
            # Auto-assign current salary structure
            current_structure = frappe.db.get_value("Salary Structure Assignment",
                {"employee": self.employee, "docstatus": 1},
                "salary_structure",
                order_by="from_date desc"
            )
            
            if current_structure:
                self.salary_structure = current_structure
            else:
                frappe.throw(_("No active salary structure found for employee {0}").format(self.employee_name))
    
    def calculate_salary_components(self):
        """Calculate earnings and deductions."""
        if not self.salary_structure:
            return
        
        structure = frappe.get_doc("Salary Structure", self.salary_structure)
        
        # Clear existing components
        self.earnings = []
        self.deductions = []
        
        # Calculate earnings
        for earning in structure.earnings:
            amount = self.calculate_component_amount(earning)
            if amount > 0:
                self.append("earnings", {
                    "salary_component": earning.salary_component,
                    "amount": amount,
                    "formula": earning.formula,
                    "condition": earning.condition
                })
        
        # Calculate deductions
        for deduction in structure.deductions:
            amount = self.calculate_component_amount(deduction)
            if amount > 0:
                self.append("deductions", {
                    "salary_component": deduction.salary_component,
                    "amount": amount,
                    "formula": deduction.formula,
                    "condition": deduction.condition
                })
    
    def calculate_component_amount(self, component):
        """Calculate individual component amount."""
        # Check condition if specified
        if component.condition:
            try:
                condition_result = eval(component.condition, {"doc": self})
                if not condition_result:
                    return 0
            except:
                return 0
        
        # Calculate amount based on formula
        if component.formula:
            try:
                amount = eval(component.formula, {"doc": self, "basic_salary": self.basic_salary or 0})
                return flt(amount, 2)
            except:
                return flt(component.amount or 0, 2)
        
        return flt(component.amount or 0, 2)
    
    def calculate_totals(self):
        """Calculate salary totals."""
        # Calculate gross salary
        total_earnings = sum(flt(earning.amount) for earning in self.earnings)
        self.gross_salary = flt(self.basic_salary or 0) + total_earnings
        
        # Calculate total deductions
        self.total_deductions = sum(flt(deduction.amount) for deduction in self.deductions)
        
        # Calculate net salary
        self.net_salary = self.gross_salary - self.total_deductions
        
        if self.net_salary < 0:
            frappe.msgprint(_("Warning: Net salary is negative"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.processed_date and self.status == "Processed":
            self.processed_date = getdate()
        
        if not self.processed_by and self.status == "Processed":
            self.processed_by = frappe.session.user
        
        # Set attendance details if not provided
        if not self.working_days:
            self.set_attendance_details()
    
    def set_attendance_details(self):
        """Set attendance details from attendance records."""
        if not self.payroll_cycle:
            return
        
        cycle = frappe.get_doc("Payroll Cycle", self.payroll_cycle)
        
        # Get attendance records for the period
        attendance_records = frappe.get_all("Attendance",
            filters={
                "employee": self.employee,
                "attendance_date": ["between", [cycle.start_date, cycle.end_date]]
            },
            fields=["status", "attendance_date"]
        )
        
        # Calculate attendance days
        present_days = len([a for a in attendance_records if a.status == "Present"])
        absent_days = len([a for a in attendance_records if a.status == "Absent"])
        
        # Get leave days
        leave_days = frappe.db.sql("""
            SELECT SUM(total_leave_days) as leave_days
            FROM `tabLeave Application`
            WHERE employee = %s
            AND status = 'Approved'
            AND from_date <= %s
            AND to_date >= %s
        """, (self.employee, cycle.end_date, cycle.start_date))[0][0] or 0
        
        # Calculate working days (excluding weekends and holidays)
        total_days = (getdate(cycle.end_date) - getdate(cycle.start_date)).days + 1
        working_days = total_days - self.get_weekend_holidays(cycle.start_date, cycle.end_date)
        
        self.attendance_days = present_days
        self.working_days = working_days
        self.leave_days = flt(leave_days)
        self.absent_days = absent_days
    
    def get_weekend_holidays(self, start_date, end_date):
        """Calculate weekend and holiday days."""
        # This is a simplified calculation
        # In practice, you'd check holiday lists and weekend settings
        total_days = (getdate(end_date) - getdate(start_date)).days + 1
        weekend_days = (total_days // 7) * 2  # Assuming Sat-Sun weekends
        
        return weekend_days
    
    def on_submit(self):
        """Actions on submit."""
        self.status = "Processed"
        self.processed_date = getdate()
        self.processed_by = frappe.session.user
        
        # Send notifications
        self.send_salary_slip_notifications()
        
        # Create payment entry if auto-payment is enabled
        if frappe.db.get_single_value("HR Settings", "auto_create_payment_entry"):
            self.create_payment_entry()
    
    def send_salary_slip_notifications(self):
        """Send salary slip notifications."""
        # Notify employee
        self.send_employee_notification()
        
        # Notify HR manager
        self.send_hr_notification()
        
        # Notify accounts team
        self.send_accounts_notification()
    
    def send_employee_notification(self):
        """Send notification to employee."""
        employee = frappe.get_doc("Employee", self.employee)
        
        if employee.user_id:
            frappe.sendmail(
                recipients=[employee.user_id],
                subject=_("Salary Slip Generated - {0}").format(self.pay_period),
                message=self.get_employee_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_employee_notification_message(self):
        """Get employee notification message."""
        return _("""
        Dear {employee_name},
        
        Your salary slip for {pay_period} has been generated.
        
        Salary Summary:
        - Basic Salary: {basic_salary}
        - Gross Salary: {gross_salary}
        - Total Deductions: {total_deductions}
        - Net Salary: {net_salary}
        
        Attendance Details:
        - Working Days: {working_days}
        - Attendance Days: {attendance_days}
        - Leave Days: {leave_days}
        - Absent Days: {absent_days}
        
        Payment Details:
        - Payment Method: {payment_method}
        - Expected Payment Date: {payment_date}
        
        You can view and download your detailed salary slip from the employee portal.
        
        If you have any questions, please contact the HR department.
        
        Best regards,
        HR Team
        """).format(
            employee_name=self.employee_name,
            pay_period=self.pay_period,
            basic_salary=frappe.format(self.basic_salary, "Currency"),
            gross_salary=frappe.format(self.gross_salary, "Currency"),
            total_deductions=frappe.format(self.total_deductions, "Currency"),
            net_salary=frappe.format(self.net_salary, "Currency"),
            working_days=self.working_days,
            attendance_days=self.attendance_days,
            leave_days=self.leave_days,
            absent_days=self.absent_days,
            payment_method=self.payment_method,
            payment_date=frappe.format(self.payment_date, "Date") if self.payment_date else "TBA"
        )
    
    def send_hr_notification(self):
        """Send notification to HR manager."""
        hr_managers = frappe.get_all("Has Role",
            filters={"role": "HR Manager"},
            fields=["parent"]
        )
        
        if hr_managers:
            recipients = [user.parent for user in hr_managers]
            
            frappe.sendmail(
                recipients=recipients,
                subject=_("Salary Slip Processed - {0}").format(self.employee_name),
                message=self.get_hr_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_hr_notification_message(self):
        """Get HR notification message."""
        return _("""
        Salary Slip Processed
        
        Employee: {employee_name} ({employee})
        Department: {department}
        Designation: {designation}
        Pay Period: {pay_period}
        
        Salary Details:
        - Net Salary: {net_salary}
        - Payment Method: {payment_method}
        - Status: {status}
        
        Attendance Summary:
        - Attendance: {attendance_days}/{working_days} days
        - Leave Days: {leave_days}
        - Absent Days: {absent_days}
        
        Next Steps:
        - Review and approve for payment
        - Process payment through {payment_method}
        - Update payment status
        
        HR Management System
        """).format(
            employee_name=self.employee_name,
            employee=self.employee,
            department=self.department or "Not specified",
            designation=self.designation or "Not specified",
            pay_period=self.pay_period,
            net_salary=frappe.format(self.net_salary, "Currency"),
            payment_method=self.payment_method,
            status=self.status,
            attendance_days=self.attendance_days,
            working_days=self.working_days,
            leave_days=self.leave_days,
            absent_days=self.absent_days
        )
    
    def send_accounts_notification(self):
        """Send notification to accounts team."""
        accounts_managers = frappe.get_all("Has Role",
            filters={"role": "Accounts Manager"},
            fields=["parent"]
        )
        
        if accounts_managers:
            recipients = [user.parent for user in accounts_managers]
            
            frappe.sendmail(
                recipients=recipients,
                subject=_("Payment Required - Salary Slip {0}").format(self.name),
                message=self.get_accounts_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_accounts_notification_message(self):
        """Get accounts notification message."""
        return _("""
        Payment Required for Salary Slip
        
        Employee: {employee_name}
        Salary Slip: {slip_name}
        Pay Period: {pay_period}
        
        Payment Details:
        - Amount: {net_salary}
        - Payment Method: {payment_method}
        - Bank Account: {bank_account}
        - Due Date: {payment_date}
        
        Please process the payment and update the payment status.
        
        Accounts Team
        """).format(
            employee_name=self.employee_name,
            slip_name=self.name,
            pay_period=self.pay_period,
            net_salary=frappe.format(self.net_salary, "Currency"),
            payment_method=self.payment_method,
            bank_account=self.bank_account or "Not specified",
            payment_date=frappe.format(self.payment_date, "Date") if self.payment_date else "Not specified"
        )
    
    def create_payment_entry(self):
        """Create payment entry for salary."""
        if self.net_salary <= 0:
            return
        
        payment_entry = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Pay",
            "party_type": "Employee",
            "party": self.employee,
            "paid_amount": self.net_salary,
            "received_amount": self.net_salary,
            "reference_no": self.name,
            "reference_date": getdate(),
            "remarks": f"Salary payment for {self.pay_period}",
            "mode_of_payment": self.payment_method,
            "status": "Draft"
        })
        
        payment_entry.insert(ignore_permissions=True)
        
        # Link payment entry to salary slip
        self.payment_reference = payment_entry.name
        self.save()
    
    @frappe.whitelist()
    def approve_salary_slip(self, approval_notes=None):
        """Approve salary slip for payment."""
        if self.approval_status == "Approved":
            frappe.throw(_("Salary slip is already approved"))
        
        self.approval_status = "Approved"
        self.approved_by = frappe.session.user
        self.approval_date = getdate()
        
        if approval_notes:
            self.remarks = (self.remarks or "") + f"\nApproval Notes: {approval_notes}"
        
        self.save()
        
        # Send approval notification
        self.send_approval_notification()
        
        frappe.msgprint(_("Salary slip approved"))
        return self
    
    def send_approval_notification(self):
        """Send approval notification."""
        # Notify accounts team
        accounts_managers = frappe.get_all("Has Role",
            filters={"role": "Accounts Manager"},
            fields=["parent"]
        )
        
        if accounts_managers:
            recipients = [user.parent for user in accounts_managers]
            
            frappe.sendmail(
                recipients=recipients,
                subject=_("Salary Slip Approved - {0}").format(self.employee_name),
                message=self.get_approval_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_approval_notification_message(self):
        """Get approval notification message."""
        return _("""
        Salary Slip Approved for Payment
        
        Employee: {employee_name}
        Salary Slip: {slip_name}
        Approved By: {approved_by}
        Approval Date: {approval_date}
        
        Payment Details:
        - Net Amount: {net_salary}
        - Payment Method: {payment_method}
        - Bank Account: {bank_account}
        
        Please proceed with payment processing.
        
        HR Management System
        """).format(
            employee_name=self.employee_name,
            slip_name=self.name,
            approved_by=frappe.get_value("User", self.approved_by, "full_name") if self.approved_by else "System",
            approval_date=frappe.format(self.approval_date, "Date"),
            net_salary=frappe.format(self.net_salary, "Currency"),
            payment_method=self.payment_method,
            bank_account=self.bank_account or "Not specified"
        )
    
    @frappe.whitelist()
    def mark_as_paid(self, payment_reference=None, payment_date=None):
        """Mark salary slip as paid."""
        if self.status == "Paid":
            frappe.throw(_("Salary slip is already marked as paid"))
        
        self.status = "Paid"
        self.payment_status = "Completed"
        
        if payment_reference:
            self.payment_reference = payment_reference
        
        if payment_date:
            self.payment_date = getdate(payment_date)
        else:
            self.payment_date = getdate()
        
        self.save()
        
        # Send payment confirmation
        self.send_payment_confirmation()
        
        frappe.msgprint(_("Salary slip marked as paid"))
        return self
    
    def send_payment_confirmation(self):
        """Send payment confirmation to employee."""
        employee = frappe.get_doc("Employee", self.employee)
        
        if employee.user_id:
            frappe.sendmail(
                recipients=[employee.user_id],
                subject=_("Salary Payment Processed - {0}").format(self.pay_period),
                message=self.get_payment_confirmation_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_payment_confirmation_message(self):
        """Get payment confirmation message."""
        return _("""
        Dear {employee_name},
        
        Your salary for {pay_period} has been successfully processed and paid.
        
        Payment Details:
        - Net Salary: {net_salary}
        - Payment Method: {payment_method}
        - Payment Date: {payment_date}
        - Payment Reference: {payment_reference}
        
        The amount should reflect in your account within the next 1-2 business days.
        
        If you have any questions or concerns about your salary payment, please contact the HR department.
        
        Thank you for your continued service.
        
        Best regards,
        HR Team
        """).format(
            employee_name=self.employee_name,
            pay_period=self.pay_period,
            net_salary=frappe.format(self.net_salary, "Currency"),
            payment_method=self.payment_method,
            payment_date=frappe.format(self.payment_date, "Date"),
            payment_reference=self.payment_reference or "N/A"
        )
    
    @frappe.whitelist()
    def get_salary_slip_analytics(self):
        """Get salary slip analytics."""
        # Get employee's salary history
        salary_history = frappe.get_all("Salary Slip",
            filters={"employee": self.employee, "docstatus": 1},
            fields=["pay_period", "net_salary", "payment_date"],
            order_by="payment_date desc",
            limit=12
        )
        
        # Calculate averages
        avg_net_salary = sum(flt(s.net_salary) for s in salary_history) / max(1, len(salary_history))
        
        # Get department statistics
        dept_avg = frappe.db.sql("""
            SELECT AVG(net_salary) as avg_salary
            FROM `tabSalary Slip`
            WHERE department = %s
            AND docstatus = 1
            AND pay_period = %s
        """, (self.department, self.pay_period))[0][0] or 0
        
        return {
            "current_slip": {
                "name": self.name,
                "employee": self.employee_name,
                "pay_period": self.pay_period,
                "net_salary": self.net_salary,
                "status": self.status
            },
            "employee_statistics": {
                "average_salary": avg_net_salary,
                "salary_history_count": len(salary_history),
                "attendance_percentage": (self.attendance_days / max(1, self.working_days)) * 100 if self.working_days else 0
            },
            "department_comparison": {
                "department": self.department,
                "department_average": dept_avg,
                "variance_from_dept_avg": self.net_salary - dept_avg if dept_avg else 0
            },
            "salary_breakdown": {
                "basic_salary": self.basic_salary,
                "total_earnings": sum(flt(e.amount) for e in self.earnings),
                "total_deductions": self.total_deductions,
                "net_salary": self.net_salary
            },
            "attendance_summary": {
                "working_days": self.working_days,
                "attendance_days": self.attendance_days,
                "leave_days": self.leave_days,
                "absent_days": self.absent_days
            }
        }
    
    def get_salary_slip_summary(self):
        """Get salary slip summary for reporting."""
        return {
            "slip_name": self.name,
            "employee": self.employee_name,
            "department": self.department,
            "designation": self.designation,
            "pay_period": self.pay_period,
            "basic_salary": self.basic_salary,
            "gross_salary": self.gross_salary,
            "total_deductions": self.total_deductions,
            "net_salary": self.net_salary,
            "attendance_days": self.attendance_days,
            "working_days": self.working_days,
            "status": self.status,
            "approval_status": self.approval_status,
            "payment_status": self.payment_status,
            "payment_date": self.payment_date,
            "processed_date": self.processed_date
        }
