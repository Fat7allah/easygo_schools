import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, add_days, getdate, date_diff
from frappe import _


class Contract(Document):
    def validate(self):
        self.validate_dates()
        self.set_employee_details()
        self.validate_salary()
        self.check_overlapping_contracts()
        
    def validate_dates(self):
        """Validate contract dates"""
        if self.end_date and self.start_date:
            if getdate(self.end_date) <= getdate(self.start_date):
                frappe.throw(_("End date must be after start date"))
                
    def set_employee_details(self):
        """Set employee details from Employee master"""
        if self.employee:
            employee = frappe.get_doc("Employee", self.employee)
            self.employee_name = employee.employee_name
            if not self.department:
                self.department = employee.department
                
    def validate_salary(self):
        """Validate salary structure"""
        if self.basic_salary <= 0:
            frappe.throw(_("Basic salary must be greater than 0"))
            
    def check_overlapping_contracts(self):
        """Check for overlapping active contracts"""
        if self.status == "Active":
            overlapping = frappe.db.sql("""
                SELECT name FROM `tabContract`
                WHERE employee = %s AND status = 'Active'
                AND name != %s
                AND (
                    (start_date <= %s AND (end_date IS NULL OR end_date >= %s))
                    OR (start_date <= %s AND (end_date IS NULL OR end_date >= %s))
                    OR (start_date >= %s AND start_date <= %s)
                )
            """, (self.employee, self.name, self.start_date, self.start_date,
                  self.end_date or '2099-12-31', self.end_date or '2099-12-31',
                  self.start_date, self.end_date or '2099-12-31'))
                  
            if overlapping:
                frappe.throw(_("Employee {0} already has an active contract: {1}").format(
                    self.employee, overlapping[0][0]))
                    
    def on_submit(self):
        if self.status == "Draft":
            self.status = "Active"
        self.update_employee_contract()
        self.send_contract_notification()
        
    def on_cancel(self):
        self.status = "Terminated"
        self.update_employee_contract()
        
    def update_employee_contract(self):
        """Update employee's current contract reference"""
        if self.status == "Active":
            frappe.db.set_value("Employee", self.employee, "current_contract", self.name)
        elif self.status == "Terminated":
            current_contract = frappe.db.get_value("Employee", self.employee, "current_contract")
            if current_contract == self.name:
                frappe.db.set_value("Employee", self.employee, "current_contract", None)
                
    def send_contract_notification(self):
        """Send contract notification to employee"""
        employee_email = frappe.db.get_value("Employee", self.employee, "user_id")
        if employee_email:
            frappe.sendmail(
                recipients=[employee_email],
                subject=f"Contract {self.status}: {self.name}",
                message=f"""
                <p>Dear {self.employee_name},</p>
                <p>Your employment contract has been {self.status.lower()}:</p>
                <p><strong>Contract:</strong> {self.name}</p>
                <p><strong>Position:</strong> {self.position}</p>
                <p><strong>Contract Type:</strong> {self.contract_type}</p>
                <p><strong>Start Date:</strong> {self.start_date}</p>
                {f'<p><strong>End Date:</strong> {self.end_date}</p>' if self.end_date else ''}
                <p><strong>Basic Salary:</strong> {frappe.format_value(self.basic_salary, 'Currency')}</p>
                <p>Please review the contract details in the system.</p>
                """,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
            
    @frappe.whitelist()
    def renew_contract(self, new_end_date=None, new_salary=None):
        """Renew contract"""
        if self.status != "Active":
            frappe.throw(_("Only active contracts can be renewed"))
            
        # Create new contract
        new_contract = frappe.copy_doc(self)
        new_contract.start_date = self.end_date if self.end_date else add_days(nowdate(), 1)
        new_contract.end_date = new_end_date
        new_contract.status = "Draft"
        
        if new_salary:
            new_contract.basic_salary = new_salary
            
        new_contract.insert()
        
        # Mark current contract as renewed
        self.status = "Renewed"
        self.save()
        
        frappe.msgprint(_("New contract {0} created for renewal").format(new_contract.name))
        return new_contract.name
        
    @frappe.whitelist()
    def terminate_contract(self, termination_date=None, reason=None):
        """Terminate contract"""
        if self.status not in ["Active"]:
            frappe.throw(_("Only active contracts can be terminated"))
            
        self.status = "Terminated"
        if termination_date:
            self.end_date = termination_date
        if reason:
            self.termination_clause = (self.termination_clause or "") + f"\nTermination Reason: {reason}"
            
        self.save()
        self.update_employee_contract()
        
        frappe.msgprint(_("Contract terminated"))
        
    def check_contract_expiry(self):
        """Check if contract is expiring soon"""
        if self.end_date and self.status == "Active":
            days_to_expiry = date_diff(self.end_date, nowdate())
            if days_to_expiry <= 30 and days_to_expiry > 0:
                return {
                    "expiring": True,
                    "days_remaining": days_to_expiry,
                    "end_date": self.end_date
                }
        return {"expiring": False}


@frappe.whitelist()
def get_expiring_contracts(days=30):
    """Get contracts expiring within specified days"""
    expiry_date = add_days(nowdate(), days)
    
    return frappe.get_all("Contract", 
        filters={
            "status": "Active",
            "end_date": ["between", [nowdate(), expiry_date]]
        },
        fields=["name", "employee", "employee_name", "position", "end_date", "contract_type"],
        order_by="end_date asc"
    )


@frappe.whitelist()
def get_contract_analytics():
    """Get contract analytics"""
    return {
        "total_contracts": frappe.db.count("Contract", {"docstatus": 1}),
        "active_contracts": frappe.db.count("Contract", {
            "status": "Active", "docstatus": 1
        }),
        "expiring_soon": frappe.db.count("Contract", {
            "status": "Active",
            "end_date": ["between", [nowdate(), add_days(nowdate(), 30)]],
            "docstatus": 1
        }),
        "by_type": frappe.db.sql("""
            SELECT contract_type, COUNT(*) as count
            FROM `tabContract`
            WHERE docstatus = 1
            GROUP BY contract_type
        """, as_dict=True),
        "by_status": frappe.db.sql("""
            SELECT status, COUNT(*) as count
            FROM `tabContract`
            WHERE docstatus = 1
            GROUP BY status
        """, as_dict=True),
        "average_salary": frappe.db.sql("""
            SELECT AVG(basic_salary) as avg_salary
            FROM `tabContract`
            WHERE status = 'Active' AND docstatus = 1
        """)[0][0] or 0
    }


# Scheduled job to check contract expiry
def check_contract_expiry_daily():
    """Daily job to check contract expiry and send notifications"""
    expiring_contracts = get_expiring_contracts(30)
    
    if expiring_contracts:
        # Notify HR Manager
        hr_managers = frappe.get_all("User", {
            "role_profile_name": "HR Manager",
            "enabled": 1
        }, ["email"])
        
        if hr_managers:
            recipient_emails = [user.email for user in hr_managers if user.email]
            
            contract_list = ""
            for contract in expiring_contracts:
                days_remaining = date_diff(contract.end_date, nowdate())
                contract_list += f"<li>{contract.employee_name} ({contract.position}) - Expires in {days_remaining} days</li>"
                
            frappe.sendmail(
                recipients=recipient_emails,
                subject="Contracts Expiring Soon",
                message=f"""
                <p>The following contracts are expiring within the next 30 days:</p>
                <ul>{contract_list}</ul>
                <p>Please review and take necessary action for contract renewals.</p>
                """
            )
