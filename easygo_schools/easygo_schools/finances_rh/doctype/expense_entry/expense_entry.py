"""Expense Entry DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, flt


class ExpenseEntry(Document):
    """Expense Entry management."""
    
    def validate(self):
        """Validate expense entry data."""
        self.validate_amount()
        self.validate_dates()
        self.validate_budget_availability()
        self.set_defaults()
    
    def validate_amount(self):
        """Validate expense amount."""
        if self.amount <= 0:
            frappe.throw(_("Expense amount must be greater than zero"))
    
    def validate_dates(self):
        """Validate expense dates."""
        if self.expense_date and getdate(self.expense_date) > getdate():
            frappe.throw(_("Expense date cannot be in the future"))
        
        if self.approval_date and self.expense_date:
            if getdate(self.approval_date) < getdate(self.expense_date):
                frappe.throw(_("Approval date cannot be before expense date"))
    
    def validate_budget_availability(self):
        """Validate budget availability."""
        if self.budget_line:
            budget_line_doc = frappe.get_doc("Budget Line", self.budget_line)
            
            # Get total expenses against this budget line
            total_expenses = frappe.db.sql("""
                SELECT SUM(amount)
                FROM `tabExpense Entry`
                WHERE budget_line = %s
                AND docstatus = 1
                AND name != %s
            """, [self.budget_line, self.name or ""], as_list=True)
            
            current_expenses = total_expenses[0][0] if total_expenses and total_expenses[0][0] else 0
            available_budget = flt(budget_line_doc.allocated_amount) - flt(current_expenses)
            
            if flt(self.amount) > available_budget:
                frappe.msgprint(_("Warning: Expense amount ({0}) exceeds available budget ({1})").format(
                    self.amount, available_budget
                ), alert=True)
    
    def set_defaults(self):
        """Set default values."""
        if not self.requested_by:
            self.requested_by = frappe.session.user
        
        if not self.expense_date:
            self.expense_date = getdate()
        
        if not self.status:
            self.status = "Draft"
        
        if not self.payment_status:
            self.payment_status = "Unpaid"
    
    def on_submit(self):
        """Actions on submit."""
        self.update_account_balance()
        self.update_budget_consumption()
        self.create_payment_request()
    
    def on_cancel(self):
        """Actions on cancel."""
        self.reverse_account_balance()
        self.reverse_budget_consumption()
    
    def update_account_balance(self):
        """Update account balance after expense."""
        if self.account:
            account_doc = frappe.get_doc("School Account", self.account)
            account_doc.update_budget_summary()
    
    def reverse_account_balance(self):
        """Reverse account balance on cancellation."""
        if self.account:
            account_doc = frappe.get_doc("School Account", self.account)
            account_doc.update_budget_summary()
    
    def update_budget_consumption(self):
        """Update budget consumption."""
        if self.budget_line:
            budget_line_doc = frappe.get_doc("Budget Line", self.budget_line)
            
            # Recalculate consumed amount
            total_expenses = frappe.db.sql("""
                SELECT SUM(amount)
                FROM `tabExpense Entry`
                WHERE budget_line = %s
                AND docstatus = 1
            """, [self.budget_line], as_list=True)
            
            consumed_amount = total_expenses[0][0] if total_expenses and total_expenses[0][0] else 0
            budget_line_doc.consumed_amount = consumed_amount
            budget_line_doc.remaining_amount = flt(budget_line_doc.allocated_amount) - flt(consumed_amount)
            budget_line_doc.save()
    
    def reverse_budget_consumption(self):
        """Reverse budget consumption on cancellation."""
        if self.budget_line:
            self.update_budget_consumption()
    
    def create_payment_request(self):
        """Create payment request for approved expenses."""
        if self.status == "Approved" and self.payment_status == "Unpaid":
            payment_request_doc = frappe.get_doc({
                "doctype": "Payment Request",
                "expense_entry": self.name,
                "vendor": self.vendor,
                "amount": self.amount,
                "payment_method": self.payment_method,
                "account": self.account,
                "description": self.description,
                "requested_by": self.requested_by,
                "status": "Pending"
            })
            
            payment_request_doc.insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def submit_for_approval(self):
        """Submit expense for approval."""
        if self.status != "Draft":
            frappe.throw(_("Only draft expenses can be submitted for approval"))
        
        self.status = "Pending Approval"
        self.save()
        
        # Notify approver
        self.notify_approver()
        
        frappe.msgprint(_("Expense submitted for approval"))
        return self
    
    @frappe.whitelist()
    def approve_expense(self):
        """Approve the expense."""
        if self.status != "Pending Approval":
            frappe.throw(_("Only pending expenses can be approved"))
        
        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approval_date = getdate()
        self.save()
        
        # Submit the document
        self.submit()
        
        # Notify requester
        self.notify_requester("approved")
        
        frappe.msgprint(_("Expense approved successfully"))
        return self
    
    @frappe.whitelist()
    def reject_expense(self, rejection_reason=None):
        """Reject the expense."""
        if self.status != "Pending Approval":
            frappe.throw(_("Only pending expenses can be rejected"))
        
        self.status = "Rejected"
        self.approved_by = frappe.session.user
        self.approval_date = getdate()
        
        if rejection_reason:
            self.justification = (self.justification or "") + f"\n\nRejection Reason: {rejection_reason}"
        
        self.save()
        
        # Notify requester
        self.notify_requester("rejected", rejection_reason)
        
        frappe.msgprint(_("Expense rejected"))
        return self
    
    @frappe.whitelist()
    def mark_as_paid(self, paid_date=None):
        """Mark expense as paid."""
        if self.status != "Approved":
            frappe.throw(_("Only approved expenses can be marked as paid"))
        
        self.payment_status = "Paid"
        self.paid_date = paid_date or getdate()
        self.status = "Paid"
        self.save()
        
        frappe.msgprint(_("Expense marked as paid"))
        return self
    
    def notify_approver(self):
        """Notify approver about pending expense."""
        # Get approver based on amount or category
        approver = self.get_approver()
        
        if approver:
            frappe.sendmail(
                recipients=[approver],
                subject=_("Expense Approval Required: {0}").format(self.expense_title),
                message=self.get_approval_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def notify_requester(self, action, reason=None):
        """Notify requester about expense status."""
        if self.requested_by:
            subject = _("Expense {0}: {1}").format(action.title(), self.expense_title)
            message = self.get_status_message(action, reason)
            
            frappe.sendmail(
                recipients=[self.requested_by],
                subject=subject,
                message=message,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_approver(self):
        """Get appropriate approver based on amount and category."""
        # Simple logic - can be enhanced based on approval matrix
        if flt(self.amount) > 10000:  # High amount expenses
            return frappe.db.get_single_value("School Settings", "finance_manager")
        else:
            return frappe.db.get_single_value("School Settings", "accounts_manager")
    
    def get_approval_message(self):
        """Get approval notification message."""
        return _("""
        Expense Approval Request
        
        Title: {expense_title}
        Category: {expense_category}
        Amount: {amount}
        Date: {expense_date}
        Requested By: {requested_by}
        
        Description:
        {description}
        
        Justification:
        {justification}
        
        Please review and approve/reject this expense.
        """).format(
            expense_title=self.expense_title,
            expense_category=self.expense_category,
            amount=self.amount,
            expense_date=self.expense_date,
            requested_by=self.requested_by,
            description=self.description,
            justification=self.justification or "Not provided"
        )
    
    def get_status_message(self, action, reason=None):
        """Get status notification message."""
        message = _("""
        Expense Status Update
        
        Title: {expense_title}
        Amount: {amount}
        Status: {status}
        
        """).format(
            expense_title=self.expense_title,
            amount=self.amount,
            status=action.title()
        )
        
        if action == "approved":
            message += _("Your expense has been approved and will be processed for payment.")
        elif action == "rejected":
            message += _("Your expense has been rejected.")
            if reason:
                message += f"\n\nReason: {reason}"
        
        return message
    
    def get_expense_summary(self):
        """Get expense summary for reporting."""
        return {
            "expense_title": self.expense_title,
            "category": self.expense_category,
            "amount": self.amount,
            "date": self.expense_date,
            "status": self.status,
            "payment_status": self.payment_status,
            "account": self.account,
            "vendor": self.vendor,
            "requested_by": self.requested_by,
            "approved_by": self.approved_by
        }
    
    @frappe.whitelist()
    def get_related_expenses(self):
        """Get related expenses by category or vendor."""
        filters = []
        
        if self.expense_category:
            filters.append(["expense_category", "=", self.expense_category])
        
        if self.vendor:
            filters.append(["vendor", "=", self.vendor])
        
        if filters:
            return frappe.get_all("Expense Entry",
                filters=filters,
                fields=["name", "expense_title", "amount", "expense_date", "status"],
                order_by="expense_date desc",
                limit=10
            )
        
        return []
