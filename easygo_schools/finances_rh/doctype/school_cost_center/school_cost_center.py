"""School Cost Center DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, flt


class SchoolCostCenter(Document):
    """School Cost Center management."""
    
    def validate(self):
        """Validate cost center data."""
        self.validate_parent_cost_center()
        self.validate_dates()
        self.set_defaults()
    
    def validate_parent_cost_center(self):
        """Validate parent cost center hierarchy."""
        if self.parent_cost_center:
            if self.parent_cost_center == self.name:
                frappe.throw(_("Cost center cannot be its own parent"))
            
            # Check if parent is a group
            parent_doc = frappe.get_doc("School Cost Center", self.parent_cost_center)
            if not parent_doc.is_group:
                frappe.throw(_("Parent cost center must be a group"))
            
            # Prevent circular reference
            self.check_circular_reference()
    
    def check_circular_reference(self):
        """Check for circular reference in cost center hierarchy."""
        visited = set()
        current = self.parent_cost_center
        
        while current:
            if current in visited:
                frappe.throw(_("Circular reference detected in cost center hierarchy"))
            
            visited.add(current)
            parent_doc = frappe.get_doc("School Cost Center", current)
            current = parent_doc.parent_cost_center
    
    def validate_dates(self):
        """Validate opening and closing dates."""
        if self.opening_date and self.closing_date:
            if self.closing_date <= self.opening_date:
                frappe.throw(_("Closing date must be after opening date"))
        
        if self.closing_date and self.closing_date <= getdate():
            self.is_active = 0
    
    def set_defaults(self):
        """Set default values."""
        if not self.cost_center_code:
            self.cost_center_code = self.generate_cost_center_code()
        
        if not self.opening_date:
            self.opening_date = getdate()
        
        if not self.company:
            self.company = frappe.db.get_single_value("School Settings", "default_company")
    
    def generate_cost_center_code(self):
        """Generate cost center code."""
        # Get department abbreviation
        dept_abbr = {
            "Administration": "ADM",
            "Academics": "ACD",
            "Sports": "SPT",
            "Library": "LIB",
            "Laboratory": "LAB",
            "Transport": "TRP",
            "Canteen": "CNT",
            "Maintenance": "MNT",
            "Security": "SEC",
            "Healthcare": "HLT",
            "IT": "IT"
        }.get(self.department, "GEN")
        
        # Get next sequence number
        existing_codes = frappe.get_all("School Cost Center",
            filters={"cost_center_code": ["like", f"{dept_abbr}%"]},
            fields=["cost_center_code"]
        )
        
        sequence = len(existing_codes) + 1
        return f"{dept_abbr}-{sequence:03d}"
    
    def on_update(self):
        """Actions after update."""
        self.update_child_cost_centers()
        self.validate_budget_allocation()
    
    def update_child_cost_centers(self):
        """Update child cost centers if parent becomes inactive."""
        if not self.is_active:
            child_cost_centers = frappe.get_all("School Cost Center",
                filters={"parent_cost_center": self.name},
                fields=["name"]
            )
            
            for child in child_cost_centers:
                child_doc = frappe.get_doc("School Cost Center", child.name)
                child_doc.is_active = 0
                child_doc.save()
    
    def validate_budget_allocation(self):
        """Validate budget allocation against parent."""
        if self.parent_cost_center and self.budget_allocated:
            # Check if total child allocations exceed parent budget
            parent_doc = frappe.get_doc("School Cost Center", self.parent_cost_center)
            
            if parent_doc.budget_allocated:
                total_child_budget = frappe.db.sql("""
                    SELECT SUM(budget_allocated)
                    FROM `tabSchool Cost Center`
                    WHERE parent_cost_center = %s
                    AND name != %s
                    AND is_active = 1
                """, [self.parent_cost_center, self.name])[0][0] or 0
                
                total_child_budget += flt(self.budget_allocated)
                
                if total_child_budget > flt(parent_doc.budget_allocated):
                    frappe.msgprint(_("Warning: Total child cost center budgets ({0}) exceed parent budget ({1})").format(
                        frappe.format_value(total_child_budget, "Currency"),
                        frappe.format_value(parent_doc.budget_allocated, "Currency")
                    ))
    
    @frappe.whitelist()
    def get_budget_utilization(self, from_date=None, to_date=None):
        """Get budget utilization for this cost center."""
        if not from_date:
            from_date = frappe.utils.get_first_day(getdate())
        if not to_date:
            to_date = frappe.utils.get_last_day(getdate())
        
        # Get total expenses
        total_expenses = frappe.db.sql("""
            SELECT SUM(total_amount)
            FROM `tabExpense Entry`
            WHERE cost_center = %s
            AND expense_date BETWEEN %s AND %s
            AND docstatus = 1
        """, [self.name, from_date, to_date])[0][0] or 0
        
        # Get budget allocation
        budget_allocated = flt(self.budget_allocated)
        
        utilization_percentage = (total_expenses / budget_allocated * 100) if budget_allocated else 0
        remaining_budget = budget_allocated - total_expenses
        
        return {
            "cost_center": self.cost_center_name,
            "budget_allocated": budget_allocated,
            "total_expenses": total_expenses,
            "remaining_budget": remaining_budget,
            "utilization_percentage": utilization_percentage,
            "period": f"{frappe.format(from_date, 'Date')} to {frappe.format(to_date, 'Date')}"
        }
    
    @frappe.whitelist()
    def get_expense_breakdown(self, from_date=None, to_date=None):
        """Get expense breakdown by category."""
        if not from_date:
            from_date = frappe.utils.get_first_day(getdate())
        if not to_date:
            to_date = frappe.utils.get_last_day(getdate())
        
        expense_breakdown = frappe.db.sql("""
            SELECT 
                expense_category,
                COUNT(*) as count,
                SUM(total_amount) as total_amount,
                AVG(total_amount) as avg_amount
            FROM `tabExpense Entry`
            WHERE cost_center = %s
            AND expense_date BETWEEN %s AND %s
            AND docstatus = 1
            GROUP BY expense_category
            ORDER BY total_amount DESC
        """, [self.name, from_date, to_date], as_dict=True)
        
        return expense_breakdown
    
    @frappe.whitelist()
    def get_child_cost_centers(self):
        """Get all child cost centers."""
        child_cost_centers = frappe.get_all("School Cost Center",
            filters={"parent_cost_center": self.name},
            fields=["name", "cost_center_name", "budget_allocated", "is_active", "department"],
            order_by="cost_center_name"
        )
        
        # Add budget utilization for each child
        for child in child_cost_centers:
            child_doc = frappe.get_doc("School Cost Center", child.name)
            utilization = child_doc.get_budget_utilization()
            child.update(utilization)
        
        return child_cost_centers
    
    @frappe.whitelist()
    def transfer_budget(self, to_cost_center, amount, reason=None):
        """Transfer budget to another cost center."""
        if not self.budget_allocated or flt(amount) > flt(self.budget_allocated):
            frappe.throw(_("Insufficient budget to transfer"))
        
        to_doc = frappe.get_doc("School Cost Center", to_cost_center)
        
        # Create budget transfer entry
        transfer_entry = frappe.get_doc({
            "doctype": "Budget Transfer",
            "from_cost_center": self.name,
            "to_cost_center": to_cost_center,
            "transfer_amount": amount,
            "reason": reason,
            "transfer_date": getdate(),
            "approved_by": frappe.session.user
        })
        
        transfer_entry.insert()
        
        # Update budgets
        self.budget_allocated = flt(self.budget_allocated) - flt(amount)
        to_doc.budget_allocated = flt(to_doc.budget_allocated) + flt(amount)
        
        self.save()
        to_doc.save()
        
        frappe.msgprint(_("Budget transfer completed: {0} transferred to {1}").format(
            frappe.format_value(amount, "Currency"),
            to_doc.cost_center_name
        ))
        
        return transfer_entry.name
    
    @frappe.whitelist()
    def create_budget_alert(self, threshold_percentage=80):
        """Create budget alert when utilization exceeds threshold."""
        utilization = self.get_budget_utilization()
        
        if utilization["utilization_percentage"] >= threshold_percentage:
            alert = frappe.get_doc({
                "doctype": "Budget Alert",
                "cost_center": self.name,
                "alert_type": "Budget Threshold Exceeded",
                "threshold_percentage": threshold_percentage,
                "current_utilization": utilization["utilization_percentage"],
                "budget_allocated": utilization["budget_allocated"],
                "amount_spent": utilization["total_expenses"],
                "remaining_budget": utilization["remaining_budget"],
                "alert_date": getdate(),
                "status": "Open"
            })
            
            alert.insert()
            
            # Send notification to manager
            if self.manager:
                self.send_budget_alert_notification(alert.name, utilization)
            
            return alert.name
        
        return None
    
    def send_budget_alert_notification(self, alert_name, utilization):
        """Send budget alert notification."""
        manager_user = frappe.db.get_value("Employee", self.manager, "user_id")
        
        if manager_user:
            frappe.sendmail(
                recipients=[manager_user],
                subject=_("Budget Alert: {0}").format(self.cost_center_name),
                message=self.get_budget_alert_message(utilization),
                reference_doctype="Budget Alert",
                reference_name=alert_name
            )
    
    def get_budget_alert_message(self, utilization):
        """Get budget alert message."""
        return _("""
        Budget Alert for Cost Center: {cost_center}
        
        Budget Details:
        - Allocated Budget: {budget_allocated}
        - Amount Spent: {amount_spent}
        - Remaining Budget: {remaining_budget}
        - Utilization: {utilization}%
        
        The cost center has exceeded the budget threshold. Please review expenses and take necessary action.
        
        Finance Team
        """).format(
            cost_center=self.cost_center_name,
            budget_allocated=frappe.format_value(utilization["budget_allocated"], "Currency"),
            amount_spent=frappe.format_value(utilization["total_expenses"], "Currency"),
            remaining_budget=frappe.format_value(utilization["remaining_budget"], "Currency"),
            utilization=round(utilization["utilization_percentage"], 2)
        )
    
    @frappe.whitelist()
    def get_cost_center_hierarchy(self):
        """Get complete cost center hierarchy."""
        def get_children(parent):
            children = frappe.get_all("School Cost Center",
                filters={"parent_cost_center": parent},
                fields=["name", "cost_center_name", "is_group", "budget_allocated", "is_active"]
            )
            
            for child in children:
                child["children"] = get_children(child.name)
                # Add utilization data
                child_doc = frappe.get_doc("School Cost Center", child.name)
                utilization = child_doc.get_budget_utilization()
                child.update(utilization)
            
            return children
        
        if self.is_group:
            return {
                "name": self.name,
                "cost_center_name": self.cost_center_name,
                "is_group": self.is_group,
                "budget_allocated": self.budget_allocated,
                "children": get_children(self.name)
            }
        else:
            return {
                "name": self.name,
                "cost_center_name": self.cost_center_name,
                "is_group": self.is_group,
                "budget_allocated": self.budget_allocated,
                "children": []
            }
    
    @frappe.whitelist()
    def generate_cost_center_report(self, from_date=None, to_date=None):
        """Generate comprehensive cost center report."""
        utilization = self.get_budget_utilization(from_date, to_date)
        expense_breakdown = self.get_expense_breakdown(from_date, to_date)
        
        # Get top expenses
        top_expenses = frappe.get_all("Expense Entry",
            filters={
                "cost_center": self.name,
                "expense_date": ["between", [from_date or frappe.utils.get_first_day(getdate()), 
                                           to_date or frappe.utils.get_last_day(getdate())]],
                "docstatus": 1
            },
            fields=["name", "expense_description", "total_amount", "expense_date", "expense_category"],
            order_by="total_amount desc",
            limit=10
        )
        
        report = {
            "cost_center_info": {
                "name": self.cost_center_name,
                "code": self.cost_center_code,
                "department": self.department,
                "manager": self.manager,
                "is_active": self.is_active
            },
            "budget_utilization": utilization,
            "expense_breakdown": expense_breakdown,
            "top_expenses": top_expenses,
            "child_cost_centers": self.get_child_cost_centers() if self.is_group else []
        }
        
        return report
    
    def get_cost_center_summary(self):
        """Get cost center summary for reporting."""
        utilization = self.get_budget_utilization()
        
        return {
            "cost_center_name": self.cost_center_name,
            "cost_center_code": self.cost_center_code,
            "department": self.department,
            "manager": self.manager,
            "budget_allocated": self.budget_allocated,
            "budget_utilized": utilization["total_expenses"],
            "budget_remaining": utilization["remaining_budget"],
            "utilization_percentage": utilization["utilization_percentage"],
            "is_group": self.is_group,
            "is_active": self.is_active,
            "parent_cost_center": self.parent_cost_center
        }
