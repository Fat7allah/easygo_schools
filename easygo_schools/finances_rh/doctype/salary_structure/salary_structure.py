"""Salary Structure DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, flt


class SalaryStructure(Document):
    """Salary Structure management."""
    
    def validate(self):
        """Validate salary structure data."""
        self.validate_dates()
        self.validate_employee()
        self.calculate_totals()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate effective dates."""
        if self.effective_from and self.effective_to:
            if getdate(self.effective_from) >= getdate(self.effective_to):
                frappe.throw(_("Effective To date must be after Effective From date"))
    
    def validate_employee(self):
        """Validate employee and check for overlapping structures."""
        if self.employee and self.effective_from:
            # Check for overlapping salary structures
            overlapping = frappe.db.sql("""
                SELECT name
                FROM `tabSalary Structure`
                WHERE employee = %s
                AND is_active = 1
                AND name != %s
                AND (
                    (effective_from <= %s AND (effective_to IS NULL OR effective_to >= %s))
                    OR (effective_from <= %s AND (effective_to IS NULL OR effective_to >= %s))
                    OR (effective_from >= %s AND effective_from <= %s)
                )
            """, [
                self.employee, self.name or "",
                self.effective_from, self.effective_from,
                self.effective_to or "2099-12-31", self.effective_to or "2099-12-31",
                self.effective_from, self.effective_to or "2099-12-31"
            ])
            
            if overlapping:
                frappe.throw(_("Overlapping salary structure found: {0}").format(overlapping[0][0]))
    
    def calculate_totals(self):
        """Calculate total earnings, deductions, and net salary."""
        total_earnings = flt(self.base_salary)
        total_deductions = 0
        
        # Calculate earnings
        for earning in self.earnings:
            if earning.component_type == "Fixed":
                total_earnings += flt(earning.amount)
            elif earning.component_type == "Percentage":
                total_earnings += (flt(self.base_salary) * flt(earning.percentage)) / 100
        
        # Calculate deductions
        for deduction in self.deductions:
            if deduction.component_type == "Fixed":
                total_deductions += flt(deduction.amount)
            elif deduction.component_type == "Percentage":
                total_deductions += (total_earnings * flt(deduction.percentage)) / 100
        
        self.total_earnings = total_earnings
        self.total_deductions = total_deductions
        self.net_salary = total_earnings - total_deductions
    
    def set_defaults(self):
        """Set default values."""
        if not self.currency:
            self.currency = frappe.db.get_single_value("School Settings", "default_currency") or "MAD"
        
        if not self.salary_frequency:
            self.salary_frequency = "Monthly"
    
    def on_update(self):
        """Actions after update."""
        if self.is_active:
            self.deactivate_other_structures()
    
    def deactivate_other_structures(self):
        """Deactivate other active salary structures for the same employee."""
        frappe.db.sql("""
            UPDATE `tabSalary Structure`
            SET is_active = 0
            WHERE employee = %s
            AND name != %s
            AND is_active = 1
        """, [self.employee, self.name])
    
    @frappe.whitelist()
    def create_salary_slip(self, payroll_date=None):
        """Create salary slip based on this structure."""
        if not payroll_date:
            payroll_date = getdate()
        
        # Check if salary slip already exists for this period
        existing_slip = frappe.db.exists("Salary Slip", {
            "employee": self.employee,
            "salary_structure": self.name,
            "payroll_date": payroll_date
        })
        
        if existing_slip:
            frappe.throw(_("Salary slip already exists for this period: {0}").format(existing_slip))
        
        salary_slip = frappe.get_doc({
            "doctype": "Salary Slip",
            "employee": self.employee,
            "employee_name": self.employee_name,
            "salary_structure": self.name,
            "payroll_date": payroll_date,
            "base_salary": self.base_salary,
            "total_earnings": self.total_earnings,
            "total_deductions": self.total_deductions,
            "net_salary": self.net_salary,
            "currency": self.currency,
            "earnings": self.get_earnings_for_slip(),
            "deductions": self.get_deductions_for_slip()
        })
        
        salary_slip.insert()
        
        frappe.msgprint(_("Salary slip created: {0}").format(salary_slip.name))
        return salary_slip.name
    
    def get_earnings_for_slip(self):
        """Get earnings components for salary slip."""
        earnings_list = []
        
        # Add base salary
        earnings_list.append({
            "component": "Base Salary",
            "component_type": "Fixed",
            "amount": self.base_salary
        })
        
        # Add other earnings
        for earning in self.earnings:
            amount = 0
            if earning.component_type == "Fixed":
                amount = flt(earning.amount)
            elif earning.component_type == "Percentage":
                amount = (flt(self.base_salary) * flt(earning.percentage)) / 100
            
            earnings_list.append({
                "component": earning.component,
                "component_type": earning.component_type,
                "amount": amount,
                "percentage": earning.percentage if earning.component_type == "Percentage" else 0
            })
        
        return earnings_list
    
    def get_deductions_for_slip(self):
        """Get deduction components for salary slip."""
        deductions_list = []
        
        for deduction in self.deductions:
            amount = 0
            if deduction.component_type == "Fixed":
                amount = flt(deduction.amount)
            elif deduction.component_type == "Percentage":
                amount = (flt(self.total_earnings) * flt(deduction.percentage)) / 100
            
            deductions_list.append({
                "component": deduction.component,
                "component_type": deduction.component_type,
                "amount": amount,
                "percentage": deduction.percentage if deduction.component_type == "Percentage" else 0
            })
        
        return deductions_list
    
    @frappe.whitelist()
    def duplicate_structure(self, new_employee, new_effective_from):
        """Duplicate salary structure for another employee."""
        new_structure = frappe.copy_doc(self)
        new_structure.employee = new_employee
        new_structure.effective_from = new_effective_from
        new_structure.effective_to = None
        new_structure.salary_structure_name = f"{new_employee}_{new_effective_from}"
        
        # Get employee name
        employee_name = frappe.db.get_value("Employee", new_employee, "employee_name")
        new_structure.employee_name = employee_name
        
        new_structure.insert()
        
        frappe.msgprint(_("Salary structure duplicated: {0}").format(new_structure.name))
        return new_structure.name
    
    @frappe.whitelist()
    def approve_structure(self):
        """Approve salary structure."""
        if self.approved_by:
            frappe.throw(_("Salary structure is already approved"))
        
        self.approved_by = frappe.session.user
        self.approval_date = getdate()
        self.save()
        
        # Notify employee
        self.notify_employee()
        
        frappe.msgprint(_("Salary structure approved successfully"))
        return self
    
    def notify_employee(self):
        """Notify employee about salary structure approval."""
        employee_user = frappe.db.get_value("Employee", self.employee, "user_id")
        
        if employee_user:
            frappe.sendmail(
                recipients=[employee_user],
                subject=_("Salary Structure Approved: {0}").format(self.salary_structure_name),
                message=self.get_approval_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_approval_message(self):
        """Get salary structure approval message."""
        return _("""
        Salary Structure Approved
        
        Employee: {employee_name}
        Salary Structure: {salary_structure_name}
        Effective From: {effective_from}
        Effective To: {effective_to}
        
        Salary Details:
        - Base Salary: {base_salary} {currency}
        - Total Earnings: {total_earnings} {currency}
        - Total Deductions: {total_deductions} {currency}
        - Net Salary: {net_salary} {currency}
        
        Approved By: {approved_by}
        Approval Date: {approval_date}
        
        Your salary structure has been approved and is now active.
        """).format(
            employee_name=self.employee_name,
            salary_structure_name=self.salary_structure_name,
            effective_from=self.effective_from,
            effective_to=self.effective_to or "Ongoing",
            base_salary=self.base_salary,
            currency=self.currency,
            total_earnings=self.total_earnings,
            total_deductions=self.total_deductions,
            net_salary=self.net_salary,
            approved_by=self.approved_by,
            approval_date=self.approval_date
        )
    
    @frappe.whitelist()
    def get_salary_breakdown(self):
        """Get detailed salary breakdown."""
        breakdown = {
            "base_salary": self.base_salary,
            "earnings": [],
            "deductions": [],
            "totals": {
                "total_earnings": self.total_earnings,
                "total_deductions": self.total_deductions,
                "net_salary": self.net_salary
            }
        }
        
        # Add earnings breakdown
        for earning in self.earnings:
            amount = 0
            if earning.component_type == "Fixed":
                amount = flt(earning.amount)
            elif earning.component_type == "Percentage":
                amount = (flt(self.base_salary) * flt(earning.percentage)) / 100
            
            breakdown["earnings"].append({
                "component": earning.component,
                "type": earning.component_type,
                "amount": amount,
                "percentage": earning.percentage if earning.component_type == "Percentage" else None
            })
        
        # Add deductions breakdown
        for deduction in self.deductions:
            amount = 0
            if deduction.component_type == "Fixed":
                amount = flt(deduction.amount)
            elif deduction.component_type == "Percentage":
                amount = (flt(self.total_earnings) * flt(deduction.percentage)) / 100
            
            breakdown["deductions"].append({
                "component": deduction.component,
                "type": deduction.component_type,
                "amount": amount,
                "percentage": deduction.percentage if deduction.component_type == "Percentage" else None
            })
        
        return breakdown
    
    @frappe.whitelist()
    def get_annual_cost(self):
        """Calculate annual cost for this salary structure."""
        monthly_cost = flt(self.net_salary)
        
        if self.salary_frequency == "Monthly":
            annual_cost = monthly_cost * 12
        elif self.salary_frequency == "Bi-weekly":
            annual_cost = monthly_cost * 26
        elif self.salary_frequency == "Weekly":
            annual_cost = monthly_cost * 52
        elif self.salary_frequency == "Daily":
            annual_cost = monthly_cost * 365
        else:
            annual_cost = monthly_cost * 12  # Default to monthly
        
        return {
            "monthly_cost": monthly_cost,
            "annual_cost": annual_cost,
            "frequency": self.salary_frequency
        }
    
    def get_structure_summary(self):
        """Get salary structure summary for reporting."""
        return {
            "structure_name": self.salary_structure_name,
            "employee": self.employee_name,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "base_salary": self.base_salary,
            "total_earnings": self.total_earnings,
            "total_deductions": self.total_deductions,
            "net_salary": self.net_salary,
            "currency": self.currency,
            "frequency": self.salary_frequency,
            "is_active": self.is_active,
            "approved": bool(self.approved_by),
            "approval_date": self.approval_date
        }
