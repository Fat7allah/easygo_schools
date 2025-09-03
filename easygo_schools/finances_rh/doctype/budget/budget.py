"""Budget DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, flt, cint, date_diff


class Budget(Document):
    """Budget management for school financial planning."""
    
    def validate(self):
        """Validate budget data."""
        self.validate_dates()
        self.validate_budget_amounts()
        self.calculate_totals()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate budget period dates."""
        if self.budget_period_start and self.budget_period_end:
            if self.budget_period_start > self.budget_period_end:
                frappe.throw(_("Budget period start date cannot be after end date"))
        
        # Check for overlapping budgets in same cost center
        if self.cost_center and self.budget_period_start and self.budget_period_end:
            overlapping = frappe.db.sql("""
                SELECT name FROM `tabBudget`
                WHERE cost_center = %s 
                AND name != %s
                AND status NOT IN ('Draft', 'Closed')
                AND (
                    (budget_period_start <= %s AND budget_period_end >= %s) OR
                    (budget_period_start <= %s AND budget_period_end >= %s) OR
                    (budget_period_start >= %s AND budget_period_end <= %s)
                )
            """, [self.cost_center, self.name or "", 
                  self.budget_period_start, self.budget_period_start,
                  self.budget_period_end, self.budget_period_end,
                  self.budget_period_start, self.budget_period_end])
            
            if overlapping:
                frappe.msgprint(_("Warning: Overlapping budget period detected for this cost center"))
    
    def validate_budget_amounts(self):
        """Validate budget amounts."""
        if self.total_budget_amount <= 0:
            frappe.throw(_("Total budget amount must be positive"))
        
        # Validate budget lines total
        if self.budget_lines:
            lines_total = sum(flt(line.budget_amount) for line in self.budget_lines)
            if abs(lines_total - flt(self.total_budget_amount)) > 0.01:
                frappe.throw(_("Budget lines total ({0}) does not match total budget amount ({1})").format(
                    lines_total, self.total_budget_amount))
    
    def calculate_totals(self):
        """Calculate budget totals and remaining amounts."""
        if self.budget_lines:
            total_allocated = sum(flt(line.allocated_amount) for line in self.budget_lines)
            self.allocated_amount = total_allocated
            self.remaining_amount = flt(self.total_budget_amount) - total_allocated
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = getdate()
        
        if not self.last_modified_by:
            self.last_modified_by = frappe.session.user
        
        if not self.budget_type:
            self.budget_type = "Annual"
    
    def on_submit(self):
        """Actions on submit."""
        if self.approval_required and not self.approved_by:
            self.request_approval()
        else:
            self.activate_budget()
    
    def request_approval(self):
        """Request budget approval."""
        self.status = "Pending Approval"
        
        # Get approvers
        approvers = self.get_budget_approvers()
        
        if approvers:
            frappe.sendmail(
                recipients=approvers,
                subject=_("Budget Approval Required - {0}").format(self.budget_name),
                message=self.get_approval_request_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_budget_approvers(self):
        """Get list of budget approvers."""
        approvers = []
        
        # Get cost center manager
        if self.cost_center:
            manager = frappe.db.get_value("School Cost Center", self.cost_center, "manager")
            if manager:
                manager_user = frappe.db.get_value("Employee", manager, "user_id")
                if manager_user:
                    approvers.append(manager_user)
        
        # Get accounts manager
        accounts_manager = frappe.db.get_single_value("School Settings", "accounts_manager")
        if accounts_manager:
            approvers.append(accounts_manager)
        
        # Get education manager for high amounts
        if flt(self.total_budget_amount) > 100000:  # Configurable threshold
            education_manager = frappe.db.get_single_value("School Settings", "education_manager")
            if education_manager:
                approvers.append(education_manager)
        
        return list(set(approvers))  # Remove duplicates
    
    def get_approval_request_message(self):
        """Get approval request message."""
        return _("""
        Budget Approval Request
        
        Budget: {budget_name}
        Cost Center: {cost_center}
        Budget Type: {budget_type}
        Period: {start_date} to {end_date}
        Total Amount: {total_amount}
        
        Description:
        {description}
        
        Budget Breakdown:
        {budget_breakdown}
        
        Please review and approve this budget.
        
        Finance Team
        """).format(
            budget_name=self.budget_name,
            cost_center=self.cost_center,
            budget_type=self.budget_type,
            start_date=frappe.format(self.budget_period_start, "Date"),
            end_date=frappe.format(self.budget_period_end, "Date"),
            total_amount=frappe.format_value(self.total_budget_amount, "Currency"),
            description=self.description or "No description provided",
            budget_breakdown=self.get_budget_breakdown_text()
        )
    
    def get_budget_breakdown_text(self):
        """Get budget breakdown as text."""
        if not self.budget_lines:
            return "No breakdown available"
        
        breakdown = []
        for line in self.budget_lines:
            breakdown.append(f"- {line.account}: {frappe.format_value(line.budget_amount, 'Currency')}")
        
        return "\n".join(breakdown)
    
    def activate_budget(self):
        """Activate the budget."""
        self.status = "Active"
        self.send_activation_notifications()
        self.create_budget_alerts()
    
    def send_activation_notifications(self):
        """Send budget activation notifications."""
        # Notify cost center manager
        if self.cost_center:
            manager = frappe.db.get_value("School Cost Center", self.cost_center, "manager")
            if manager:
                manager_user = frappe.db.get_value("Employee", manager, "user_id")
                if manager_user:
                    frappe.sendmail(
                        recipients=[manager_user],
                        subject=_("Budget Activated - {0}").format(self.budget_name),
                        message=self.get_activation_message(),
                        reference_doctype=self.doctype,
                        reference_name=self.name
                    )
    
    def get_activation_message(self):
        """Get budget activation message."""
        return _("""
        Budget Activated
        
        Budget: {budget_name}
        Cost Center: {cost_center}
        Period: {start_date} to {end_date}
        Total Budget: {total_amount}
        
        The budget is now active and available for allocation.
        
        Please monitor spending against this budget and ensure compliance with allocated amounts.
        
        Finance Team
        """).format(
            budget_name=self.budget_name,
            cost_center=self.cost_center,
            start_date=frappe.format(self.budget_period_start, "Date"),
            end_date=frappe.format(self.budget_period_end, "Date"),
            total_amount=frappe.format_value(self.total_budget_amount, "Currency")
        )
    
    def create_budget_alerts(self):
        """Create budget monitoring alerts."""
        # Create alerts for 80% and 95% utilization
        for threshold in [80, 95]:
            alert = frappe.get_doc({
                "doctype": "Budget Alert",
                "budget": self.name,
                "threshold_percentage": threshold,
                "alert_type": "Utilization",
                "is_active": 1
            })
            alert.insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def approve_budget(self, approval_notes=None):
        """Approve the budget."""
        if self.status != "Pending Approval":
            frappe.throw(_("Only pending budgets can be approved"))
        
        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approval_date = getdate()
        
        if approval_notes:
            self.budget_notes = (self.budget_notes or "") + f"\nApproval Notes: {approval_notes}"
        
        self.save()
        
        # Activate budget
        self.activate_budget()
        
        frappe.msgprint(_("Budget approved and activated"))
        return self
    
    @frappe.whitelist()
    def reject_budget(self, rejection_reason):
        """Reject the budget."""
        if self.status != "Pending Approval":
            frappe.throw(_("Only pending budgets can be rejected"))
        
        self.status = "Draft"
        self.budget_notes = (self.budget_notes or "") + f"\nRejection Reason: {rejection_reason}"
        
        self.save()
        
        # Send rejection notification
        self.send_rejection_notification(rejection_reason)
        
        frappe.msgprint(_("Budget rejected"))
        return self
    
    def send_rejection_notification(self, reason):
        """Send budget rejection notification."""
        if self.created_by:
            frappe.sendmail(
                recipients=[self.created_by],
                subject=_("Budget Rejected - {0}").format(self.budget_name),
                message=self.get_rejection_message(reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_rejection_message(self, reason):
        """Get budget rejection message."""
        return _("""
        Budget Rejected
        
        Budget: {budget_name}
        Rejection Reason: {reason}
        
        Please review the feedback and resubmit the budget with necessary modifications.
        
        Finance Team
        """).format(
            budget_name=self.budget_name,
            reason=reason
        )
    
    @frappe.whitelist()
    def allocate_amount(self, account, amount, allocation_reason=None):
        """Allocate amount from budget."""
        if self.status != "Active":
            frappe.throw(_("Can only allocate from active budgets"))
        
        amount = flt(amount)
        
        if amount <= 0:
            frappe.throw(_("Allocation amount must be positive"))
        
        if amount > self.remaining_amount:
            frappe.throw(_("Allocation amount exceeds remaining budget"))
        
        # Find budget line for account
        budget_line = None
        for line in self.budget_lines:
            if line.account == account:
                budget_line = line
                break
        
        if not budget_line:
            frappe.throw(_("Account {0} not found in budget lines").format(account))
        
        # Check if allocation exceeds line budget
        if flt(budget_line.allocated_amount) + amount > flt(budget_line.budget_amount):
            frappe.throw(_("Allocation exceeds budget line amount"))
        
        # Update allocation
        budget_line.allocated_amount = flt(budget_line.allocated_amount) + amount
        
        # Add allocation note
        if allocation_reason:
            budget_line.notes = (budget_line.notes or "") + f"\nAllocation: {amount} - {allocation_reason}"
        
        # Recalculate totals
        self.calculate_totals()
        self.save()
        
        # Create allocation record
        allocation = frappe.get_doc({
            "doctype": "Budget Allocation",
            "budget": self.name,
            "account": account,
            "allocation_amount": amount,
            "allocation_date": getdate(),
            "allocation_reason": allocation_reason,
            "allocated_by": frappe.session.user
        })
        allocation.insert(ignore_permissions=True)
        
        # Check for alerts
        self.check_budget_alerts()
        
        frappe.msgprint(_("Amount allocated successfully"))
        return self
    
    def check_budget_alerts(self):
        """Check and trigger budget alerts."""
        utilization_percentage = (self.allocated_amount / self.total_budget_amount * 100) if self.total_budget_amount else 0
        
        # Check for threshold alerts
        alerts = frappe.get_all("Budget Alert",
            filters={"budget": self.name, "is_active": 1},
            fields=["threshold_percentage", "alert_type"]
        )
        
        for alert in alerts:
            if utilization_percentage >= alert.threshold_percentage:
                self.send_budget_alert(alert.threshold_percentage, utilization_percentage)
    
    def send_budget_alert(self, threshold, current_utilization):
        """Send budget utilization alert."""
        recipients = self.get_budget_approvers()
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Budget Alert - {0}% Utilization").format(int(current_utilization)),
                message=self.get_budget_alert_message(threshold, current_utilization),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_budget_alert_message(self, threshold, current_utilization):
        """Get budget alert message."""
        return _("""
        Budget Utilization Alert
        
        Budget: {budget_name}
        Cost Center: {cost_center}
        
        Current Utilization: {current_utilization:.1f}%
        Alert Threshold: {threshold}%
        
        Budget Details:
        - Total Budget: {total_budget}
        - Allocated: {allocated_amount}
        - Remaining: {remaining_amount}
        
        Please review budget utilization and take appropriate action.
        
        Finance Team
        """).format(
            budget_name=self.budget_name,
            cost_center=self.cost_center,
            current_utilization=current_utilization,
            threshold=threshold,
            total_budget=frappe.format_value(self.total_budget_amount, "Currency"),
            allocated_amount=frappe.format_value(self.allocated_amount, "Currency"),
            remaining_amount=frappe.format_value(self.remaining_amount, "Currency")
        )
    
    @frappe.whitelist()
    def revise_budget(self, revision_reason, new_total_amount=None):
        """Create budget revision."""
        if self.status not in ["Active", "Approved"]:
            frappe.throw(_("Can only revise active or approved budgets"))
        
        # Create revision record
        revision = frappe.get_doc({
            "doctype": "Budget Revision",
            "original_budget": self.name,
            "revision_reason": revision_reason,
            "original_amount": self.total_budget_amount,
            "revised_amount": new_total_amount or self.total_budget_amount,
            "revision_date": getdate(),
            "revised_by": frappe.session.user
        })
        revision.insert(ignore_permissions=True)
        
        if new_total_amount:
            self.total_budget_amount = flt(new_total_amount)
            self.calculate_totals()
        
        self.status = "Revised"
        self.budget_notes = (self.budget_notes or "") + f"\nRevision: {revision_reason}"
        self.save()
        
        # Send revision notifications
        self.send_revision_notifications(revision_reason)
        
        frappe.msgprint(_("Budget revised successfully"))
        return self
    
    def send_revision_notifications(self, reason):
        """Send budget revision notifications."""
        recipients = self.get_budget_approvers()
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Budget Revised - {0}").format(self.budget_name),
                message=self.get_revision_message(reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_revision_message(self, reason):
        """Get budget revision message."""
        return _("""
        Budget Revision Notice
        
        Budget: {budget_name}
        Revision Reason: {reason}
        
        Updated Budget Amount: {total_amount}
        Allocated Amount: {allocated_amount}
        Remaining Amount: {remaining_amount}
        
        Please review the revised budget and update your planning accordingly.
        
        Finance Team
        """).format(
            budget_name=self.budget_name,
            reason=reason,
            total_amount=frappe.format_value(self.total_budget_amount, "Currency"),
            allocated_amount=frappe.format_value(self.allocated_amount, "Currency"),
            remaining_amount=frappe.format_value(self.remaining_amount, "Currency")
        )
    
    @frappe.whitelist()
    def close_budget(self, closure_reason=None):
        """Close the budget."""
        if self.status == "Closed":
            frappe.throw(_("Budget is already closed"))
        
        self.status = "Closed"
        
        if closure_reason:
            self.budget_notes = (self.budget_notes or "") + f"\nClosure Reason: {closure_reason}"
        
        self.save()
        
        # Send closure notifications
        self.send_closure_notifications(closure_reason)
        
        frappe.msgprint(_("Budget closed"))
        return self
    
    def send_closure_notifications(self, reason):
        """Send budget closure notifications."""
        recipients = self.get_budget_approvers()
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Budget Closed - {0}").format(self.budget_name),
                message=self.get_closure_message(reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_closure_message(self, reason):
        """Get budget closure message."""
        utilization_percentage = (self.allocated_amount / self.total_budget_amount * 100) if self.total_budget_amount else 0
        
        return _("""
        Budget Closure Notice
        
        Budget: {budget_name}
        Closure Date: {closure_date}
        {closure_reason}
        
        Final Budget Summary:
        - Total Budget: {total_budget}
        - Total Allocated: {allocated_amount}
        - Utilization: {utilization:.1f}%
        - Remaining: {remaining_amount}
        
        Finance Team
        """).format(
            budget_name=self.budget_name,
            closure_date=frappe.format(getdate(), "Date"),
            closure_reason=f"Closure Reason: {reason}" if reason else "",
            total_budget=frappe.format_value(self.total_budget_amount, "Currency"),
            allocated_amount=frappe.format_value(self.allocated_amount, "Currency"),
            utilization=utilization_percentage,
            remaining_amount=frappe.format_value(self.remaining_amount, "Currency")
        )
    
    @frappe.whitelist()
    def get_budget_analytics(self):
        """Get budget analytics and insights."""
        # Calculate utilization metrics
        utilization_percentage = (self.allocated_amount / self.total_budget_amount * 100) if self.total_budget_amount else 0
        
        # Get allocation history
        allocations = frappe.get_all("Budget Allocation",
            filters={"budget": self.name},
            fields=["allocation_date", "account", "allocation_amount"],
            order_by="allocation_date desc"
        )
        
        # Calculate monthly allocation trends
        monthly_allocations = {}
        for allocation in allocations:
            month = allocation.allocation_date.strftime("%Y-%m")
            if month not in monthly_allocations:
                monthly_allocations[month] = 0
            monthly_allocations[month] += flt(allocation.allocation_amount)
        
        # Get budget line utilization
        line_utilization = []
        for line in self.budget_lines:
            line_util = (flt(line.allocated_amount) / flt(line.budget_amount) * 100) if line.budget_amount else 0
            line_utilization.append({
                "account": line.account,
                "budget_amount": line.budget_amount,
                "allocated_amount": line.allocated_amount,
                "utilization_percentage": line_util
            })
        
        return {
            "budget_info": {
                "name": self.name,
                "budget_name": self.budget_name,
                "cost_center": self.cost_center,
                "status": self.status,
                "budget_type": self.budget_type
            },
            "financial_summary": {
                "total_budget_amount": self.total_budget_amount,
                "allocated_amount": self.allocated_amount,
                "remaining_amount": self.remaining_amount,
                "utilization_percentage": utilization_percentage
            },
            "timeline": {
                "budget_period_start": self.budget_period_start,
                "budget_period_end": self.budget_period_end,
                "days_remaining": date_diff(self.budget_period_end, getdate()) if self.budget_period_end else 0
            },
            "allocation_trends": monthly_allocations,
            "line_utilization": line_utilization,
            "recent_allocations": allocations[:10]
        }
    
    def get_budget_summary(self):
        """Get budget summary for reporting."""
        utilization_percentage = (self.allocated_amount / self.total_budget_amount * 100) if self.total_budget_amount else 0
        
        return {
            "budget_name": self.budget_name,
            "cost_center": self.cost_center,
            "budget_type": self.budget_type,
            "status": self.status,
            "fiscal_year": self.fiscal_year,
            "budget_period_start": self.budget_period_start,
            "budget_period_end": self.budget_period_end,
            "total_budget_amount": self.total_budget_amount,
            "allocated_amount": self.allocated_amount,
            "remaining_amount": self.remaining_amount,
            "utilization_percentage": utilization_percentage,
            "approved_by": self.approved_by,
            "approval_date": self.approval_date,
            "created_by": self.created_by,
            "creation_date": self.creation_date
        }
