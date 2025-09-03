"""School Account DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class SchoolAccount(Document):
    """School Account management."""
    
    def validate(self):
        """Validate account data."""
        self.validate_parent_account()
        self.validate_account_hierarchy()
        self.validate_bank_details()
        self.set_defaults()
    
    def validate_parent_account(self):
        """Validate parent account relationship."""
        if self.parent_account:
            if self.parent_account == self.name:
                frappe.throw(_("Account cannot be its own parent"))
            
            parent_doc = frappe.get_doc("School Account", self.parent_account)
            if not parent_doc.is_group:
                frappe.throw(_("Parent account must be a group account"))
    
    def validate_account_hierarchy(self):
        """Validate account hierarchy rules."""
        if self.is_group and self.account_type in ["Bank", "Cash"]:
            frappe.throw(_("Bank and Cash accounts cannot be group accounts"))
        
        # Check for circular reference
        if self.parent_account:
            self.check_circular_reference()
    
    def check_circular_reference(self):
        """Check for circular reference in account hierarchy."""
        visited = set()
        current = self.parent_account
        
        while current:
            if current in visited or current == self.name:
                frappe.throw(_("Circular reference detected in account hierarchy"))
            
            visited.add(current)
            parent_account = frappe.db.get_value("School Account", current, "parent_account")
            current = parent_account
    
    def validate_bank_details(self):
        """Validate bank account details."""
        if self.account_type == "Bank":
            if not self.bank_name:
                frappe.throw(_("Bank name is required for bank accounts"))
            
            if self.iban and len(self.iban) < 15:
                frappe.throw(_("Invalid IBAN format"))
    
    def set_defaults(self):
        """Set default values."""
        if not self.account_currency:
            self.account_currency = "MAD"
        
        if not self.balance_date and self.opening_balance:
            self.balance_date = getdate()
    
    def on_update(self):
        """Actions after update."""
        self.update_budget_summary()
    
    def update_budget_summary(self):
        """Update budget allocation and consumption."""
        if self.is_group:
            return
        
        # Get budget allocation
        budget_allocated = frappe.db.sql("""
            SELECT SUM(allocated_amount)
            FROM `tabBudget Line`
            WHERE account = %s
            AND parent IN (
                SELECT name FROM `tabBudget`
                WHERE docstatus = 1
                AND %s BETWEEN from_date AND to_date
            )
        """, [self.name, getdate()], as_list=True)
        
        self.budget_allocated = budget_allocated[0][0] if budget_allocated and budget_allocated[0][0] else 0
        
        # Get budget consumption
        budget_consumed = frappe.db.sql("""
            SELECT SUM(amount)
            FROM `tabExpense Entry`
            WHERE account = %s
            AND docstatus = 1
            AND expense_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
        """, [self.name], as_list=True)
        
        self.budget_consumed = budget_consumed[0][0] if budget_consumed and budget_consumed[0][0] else 0
        self.budget_remaining = flt(self.budget_allocated) - flt(self.budget_consumed)
    
    @frappe.whitelist()
    def get_account_balance(self, as_on_date=None):
        """Get current account balance."""
        if not as_on_date:
            as_on_date = getdate()
        
        # Calculate balance based on transactions
        balance = flt(self.opening_balance or 0)
        
        # Add income transactions
        income = frappe.db.sql("""
            SELECT SUM(amount)
            FROM `tabPayment Entry`
            WHERE account = %s
            AND payment_date <= %s
            AND docstatus = 1
        """, [self.name, as_on_date], as_list=True)
        
        if income and income[0][0]:
            balance += flt(income[0][0])
        
        # Subtract expense transactions
        expenses = frappe.db.sql("""
            SELECT SUM(amount)
            FROM `tabExpense Entry`
            WHERE account = %s
            AND expense_date <= %s
            AND docstatus = 1
        """, [self.name, as_on_date], as_list=True)
        
        if expenses and expenses[0][0]:
            balance -= flt(expenses[0][0])
        
        return balance
    
    @frappe.whitelist()
    def get_child_accounts(self):
        """Get all child accounts."""
        return frappe.get_all("School Account",
            filters={"parent_account": self.name, "is_active": 1},
            fields=["name", "account_name", "account_type", "is_group"],
            order_by="account_name"
        )
    
    @frappe.whitelist()
    def get_account_statement(self, from_date, to_date):
        """Get account statement for a period."""
        transactions = []
        
        # Get payment entries
        payments = frappe.db.sql("""
            SELECT 
                payment_date as date,
                'Payment Entry' as voucher_type,
                name as voucher_no,
                student_name as party,
                amount as credit,
                0 as debit,
                remarks
            FROM `tabPayment Entry`
            WHERE account = %s
            AND payment_date BETWEEN %s AND %s
            AND docstatus = 1
            ORDER BY payment_date
        """, [self.name, from_date, to_date], as_dict=True)
        
        transactions.extend(payments)
        
        # Get expense entries
        expenses = frappe.db.sql("""
            SELECT 
                expense_date as date,
                'Expense Entry' as voucher_type,
                name as voucher_no,
                expense_category as party,
                0 as credit,
                amount as debit,
                description as remarks
            FROM `tabExpense Entry`
            WHERE account = %s
            AND expense_date BETWEEN %s AND %s
            AND docstatus = 1
            ORDER BY expense_date
        """, [self.name, from_date, to_date], as_dict=True)
        
        transactions.extend(expenses)
        
        # Sort by date
        transactions.sort(key=lambda x: x['date'])
        
        # Calculate running balance
        opening_balance = self.get_account_balance(from_date)
        running_balance = opening_balance
        
        for transaction in transactions:
            running_balance += flt(transaction['credit']) - flt(transaction['debit'])
            transaction['balance'] = running_balance
        
        return {
            "opening_balance": opening_balance,
            "transactions": transactions,
            "closing_balance": running_balance
        }
    
    def get_account_hierarchy(self):
        """Get complete account hierarchy."""
        hierarchy = []
        current = self
        
        while current:
            hierarchy.insert(0, {
                "name": current.name,
                "account_name": current.account_name,
                "account_type": current.account_type
            })
            
            if current.parent_account:
                current = frappe.get_doc("School Account", current.parent_account)
            else:
                break
        
        return hierarchy
    
    @frappe.whitelist()
    def freeze_account(self):
        """Freeze account to prevent transactions."""
        self.is_active = 0
        self.save()
        
        frappe.msgprint(_("Account {0} has been frozen").format(self.account_name))
        return self
    
    @frappe.whitelist()
    def unfreeze_account(self):
        """Unfreeze account to allow transactions."""
        self.is_active = 1
        self.save()
        
        frappe.msgprint(_("Account {0} has been unfrozen").format(self.account_name))
        return self
    
    def get_budget_utilization(self):
        """Get budget utilization percentage."""
        if not self.budget_allocated or self.budget_allocated == 0:
            return 0
        
        return (flt(self.budget_consumed) / flt(self.budget_allocated)) * 100
    
    def check_budget_exceeded(self):
        """Check if budget is exceeded."""
        return flt(self.budget_consumed) > flt(self.budget_allocated)
    
    @frappe.whitelist()
    def create_budget_alert(self):
        """Create budget alert if threshold exceeded."""
        utilization = self.get_budget_utilization()
        
        if utilization >= 90:  # Alert at 90% utilization
            alert_doc = frappe.get_doc({
                "doctype": "Budget Alert",
                "account": self.name,
                "alert_type": "Budget Exceeded" if utilization >= 100 else "Budget Warning",
                "utilization_percentage": utilization,
                "budget_allocated": self.budget_allocated,
                "budget_consumed": self.budget_consumed,
                "alert_date": getdate()
            })
            
            alert_doc.insert(ignore_permissions=True)
            
            # Notify account manager
            if self.account_manager:
                frappe.sendmail(
                    recipients=[self.account_manager],
                    subject=_("Budget Alert: {0}").format(self.account_name),
                    message=_("Budget utilization for account {0} is at {1}%").format(
                        self.account_name, utilization
                    ),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
