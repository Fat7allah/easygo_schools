"""Budget Line DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, flt


class BudgetLine(Document):
    """Budget Line management."""
    
    def validate(self):
        """Validate budget line data."""
        self.validate_dates()
        self.validate_amounts()
        self.calculate_remaining_amount()
        self.update_status()
    
    def validate_dates(self):
        """Validate start and end dates."""
        if self.start_date and self.end_date:
            if getdate(self.start_date) >= getdate(self.end_date):
                frappe.throw(_("End date must be after start date"))
    
    def validate_amounts(self):
        """Validate budget amounts."""
        if flt(self.allocated_amount) <= 0:
            frappe.throw(_("Allocated amount must be greater than zero"))
        
        if self.overspend_limit and flt(self.overspend_limit) < 0:
            frappe.throw(_("Overspend limit cannot be negative"))
    
    def calculate_remaining_amount(self):
        """Calculate remaining budget amount."""
        self.remaining_amount = flt(self.allocated_amount) - flt(self.consumed_amount)
        
        # Calculate percentage consumed
        if flt(self.allocated_amount) > 0:
            self.percentage_consumed = (flt(self.consumed_amount) / flt(self.allocated_amount)) * 100
    
    def update_status(self):
        """Update budget line status based on consumption."""
        if not self.is_active:
            self.status = "Inactive"
            return
        
        consumed_pct = flt(self.percentage_consumed)
        
        if consumed_pct >= 100:
            if consumed_pct > 100:
                self.status = "Overspent"
            else:
                self.status = "Exhausted"
        else:
            self.status = "Active"
    
    def on_update(self):
        """Actions after update."""
        self.check_budget_alerts()
    
    def check_budget_alerts(self):
        """Check for budget alerts and notifications."""
        consumed_pct = flt(self.percentage_consumed)
        
        # Alert thresholds
        if consumed_pct >= 90:
            self.create_budget_alert("Critical", "Budget line is 90% consumed")
        elif consumed_pct >= 75:
            self.create_budget_alert("Warning", "Budget line is 75% consumed")
        elif consumed_pct >= 50:
            self.create_budget_alert("Info", "Budget line is 50% consumed")
    
    def create_budget_alert(self, alert_type, message):
        """Create budget alert."""
        existing_alert = frappe.db.exists("Budget Alert", {
            "budget_line": self.name,
            "alert_type": alert_type,
            "status": "Open"
        })
        
        if not existing_alert:
            alert_doc = frappe.get_doc({
                "doctype": "Budget Alert",
                "budget_line": self.name,
                "budget": self.budget,
                "account": self.account,
                "alert_type": alert_type,
                "message": message,
                "consumed_percentage": self.percentage_consumed,
                "status": "Open",
                "alert_date": getdate()
            })
            
            alert_doc.insert(ignore_permissions=True)
            
            # Notify budget manager
            self.notify_budget_manager(alert_type, message)
    
    @frappe.whitelist()
    def update_consumed_amount(self):
        """Update consumed amount from expense entries."""
        total_expenses = frappe.db.sql("""
            SELECT SUM(amount)
            FROM `tabExpense Entry`
            WHERE budget_line = %s
            AND docstatus = 1
        """, [self.name], as_list=True)
        
        self.consumed_amount = total_expenses[0][0] if total_expenses and total_expenses[0][0] else 0
        self.calculate_remaining_amount()
        self.update_status()
        self.save()
        
        return self.consumed_amount
    
    @frappe.whitelist()
    def check_availability(self, amount):
        """Check if amount is available in budget."""
        available_amount = flt(self.remaining_amount)
        
        if self.allow_overspend and self.overspend_limit:
            available_amount += flt(self.overspend_limit)
        
        return {
            "available": flt(amount) <= available_amount,
            "available_amount": available_amount,
            "requested_amount": flt(amount),
            "shortage": max(0, flt(amount) - available_amount)
        }
    
    @frappe.whitelist()
    def get_expense_history(self, from_date=None, to_date=None):
        """Get expense history for this budget line."""
        conditions = ""
        if from_date:
            conditions += f" AND expense_date >= '{from_date}'"
        if to_date:
            conditions += f" AND expense_date <= '{to_date}'"
        
        expenses = frappe.db.sql(f"""
            SELECT 
                name,
                expense_title,
                amount,
                expense_date,
                status,
                requested_by
            FROM `tabExpense Entry`
            WHERE budget_line = %s
            AND docstatus = 1
            {conditions}
            ORDER BY expense_date DESC
        """, [self.name], as_dict=True)
        
        return expenses
    
    @frappe.whitelist()
    def get_monthly_consumption(self):
        """Get monthly consumption pattern."""
        monthly_data = frappe.db.sql("""
            SELECT 
                DATE_FORMAT(expense_date, '%Y-%m') as month,
                SUM(amount) as total_amount,
                COUNT(*) as expense_count
            FROM `tabExpense Entry`
            WHERE budget_line = %s
            AND docstatus = 1
            AND expense_date BETWEEN %s AND %s
            GROUP BY DATE_FORMAT(expense_date, '%Y-%m')
            ORDER BY month
        """, [self.name, self.start_date, self.end_date], as_dict=True)
        
        return monthly_data
    
    def notify_budget_manager(self, alert_type, message):
        """Notify budget manager about alerts."""
        budget_manager = frappe.db.get_single_value("School Settings", "budget_manager")
        
        if budget_manager:
            subject = _("Budget Alert ({0}): {1}").format(alert_type, self.budget_line_name)
            email_message = self.get_alert_message(alert_type, message)
            
            frappe.sendmail(
                recipients=[budget_manager],
                subject=subject,
                message=email_message,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_alert_message(self, alert_type, message):
        """Get alert notification message."""
        return _("""
        Budget Line Alert
        
        Budget: {budget}
        Budget Line: {budget_line_name}
        Account: {account}
        
        Alert Type: {alert_type}
        Message: {message}
        
        Budget Details:
        - Allocated Amount: {allocated_amount}
        - Consumed Amount: {consumed_amount}
        - Remaining Amount: {remaining_amount}
        - Percentage Consumed: {percentage_consumed}%
        
        Period: {start_date} to {end_date}
        
        Please review the budget consumption and take necessary action.
        """).format(
            budget=self.budget,
            budget_line_name=self.budget_line_name,
            account=self.account,
            alert_type=alert_type,
            message=message,
            allocated_amount=self.allocated_amount,
            consumed_amount=self.consumed_amount,
            remaining_amount=self.remaining_amount,
            percentage_consumed=round(self.percentage_consumed, 1),
            start_date=self.start_date,
            end_date=self.end_date
        )
    
    @frappe.whitelist()
    def reallocate_budget(self, new_amount, reason=None):
        """Reallocate budget amount."""
        if flt(new_amount) <= 0:
            frappe.throw(_("New allocation amount must be greater than zero"))
        
        old_amount = self.allocated_amount
        self.allocated_amount = flt(new_amount)
        
        # Recalculate remaining amount and status
        self.calculate_remaining_amount()
        self.update_status()
        
        # Log the reallocation
        reallocation_log = frappe.get_doc({
            "doctype": "Budget Reallocation Log",
            "budget_line": self.name,
            "old_amount": old_amount,
            "new_amount": new_amount,
            "difference": flt(new_amount) - flt(old_amount),
            "reason": reason,
            "reallocated_by": frappe.session.user,
            "reallocation_date": getdate()
        })
        
        reallocation_log.insert(ignore_permissions=True)
        
        self.save()
        
        frappe.msgprint(_("Budget reallocated successfully"))
        return self
    
    @frappe.whitelist()
    def freeze_budget_line(self, reason=None):
        """Freeze budget line to prevent further expenses."""
        self.is_active = 0
        self.status = "Inactive"
        
        if reason:
            self.description = (self.description or "") + f"\n\nFrozen: {reason}"
        
        self.save()
        
        # Notify relevant users
        self.notify_budget_freeze(reason)
        
        frappe.msgprint(_("Budget line frozen successfully"))
        return self
    
    def notify_budget_freeze(self, reason):
        """Notify about budget line freeze."""
        budget_manager = frappe.db.get_single_value("School Settings", "budget_manager")
        
        if budget_manager:
            frappe.sendmail(
                recipients=[budget_manager],
                subject=_("Budget Line Frozen: {0}").format(self.budget_line_name),
                message=_("""
                Budget Line Frozen
                
                Budget Line: {budget_line_name}
                Budget: {budget}
                Account: {account}
                
                Reason: {reason}
                
                This budget line has been frozen and no further expenses can be charged against it.
                """).format(
                    budget_line_name=self.budget_line_name,
                    budget=self.budget,
                    account=self.account,
                    reason=reason or _("No reason provided")
                ),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_budget_utilization_report(self):
        """Get budget utilization report data."""
        return {
            "budget_line": self.budget_line_name,
            "budget": self.budget,
            "account": self.account,
            "allocated_amount": self.allocated_amount,
            "consumed_amount": self.consumed_amount,
            "remaining_amount": self.remaining_amount,
            "percentage_consumed": self.percentage_consumed,
            "status": self.status,
            "period": f"{self.start_date} to {self.end_date}",
            "is_active": self.is_active,
            "allow_overspend": self.allow_overspend,
            "overspend_limit": self.overspend_limit
        }
