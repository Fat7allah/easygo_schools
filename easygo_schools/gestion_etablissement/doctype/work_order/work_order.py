"""Work Order DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, flt, time_diff_in_hours, add_days


class WorkOrder(Document):
    """Work order management for maintenance and facility operations."""
    
    def validate(self):
        """Validate work order data."""
        self.validate_dates()
        self.validate_assignments()
        self.validate_costs()
        self.calculate_hours()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate work order dates."""
        if self.expected_completion_date and self.date:
            if getdate(self.expected_completion_date) < getdate(self.date):
                frappe.throw(_("Expected completion date cannot be before work order date"))
        
        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                frappe.throw(_("End time must be after start time"))
        
        if self.follow_up_required and self.follow_up_date:
            if getdate(self.follow_up_date) <= getdate():
                frappe.throw(_("Follow-up date must be in the future"))
    
    def validate_assignments(self):
        """Validate work order assignments."""
        if self.assigned_to and not frappe.db.exists("User", self.assigned_to):
            frappe.throw(_("Assigned user does not exist"))
        
        if self.requested_by and not frappe.db.exists("User", self.requested_by):
            frappe.throw(_("Requesting user does not exist"))
        
        # Check if assigned user has maintenance role
        if self.assigned_to:
            user_roles = frappe.get_roles(self.assigned_to)
            if not any(role in ["Maintenance Manager", "Maintenance User"] for role in user_roles):
                frappe.msgprint(_("Warning: Assigned user does not have maintenance role"))
    
    def validate_costs(self):
        """Validate cost information."""
        if self.estimated_cost and flt(self.estimated_cost) < 0:
            frappe.throw(_("Estimated cost cannot be negative"))
        
        if self.actual_cost and flt(self.actual_cost) < 0:
            frappe.throw(_("Actual cost cannot be negative"))
        
        # Warning if actual cost exceeds estimated by more than 20%
        if self.estimated_cost and self.actual_cost:
            variance = (flt(self.actual_cost) - flt(self.estimated_cost)) / flt(self.estimated_cost) * 100
            if variance > 20:
                frappe.msgprint(_("Warning: Actual cost exceeds estimated cost by {0}%").format(round(variance, 2)))
    
    def calculate_hours(self):
        """Calculate total hours worked."""
        if self.start_time and self.end_time:
            self.total_hours = time_diff_in_hours(self.end_time, self.start_time)
    
    def set_defaults(self):
        """Set default values."""
        if not self.requested_by:
            self.requested_by = frappe.session.user
        
        if not self.date:
            self.date = getdate()
        
        # Set expected completion based on priority
        if not self.expected_completion_date and self.priority:
            days_to_add = {
                "Urgent": 1,
                "High": 3,
                "Medium": 7,
                "Low": 14
            }.get(self.priority, 7)
            
            self.expected_completion_date = add_days(self.date, days_to_add)
    
    def before_save(self):
        """Actions before saving work order."""
        # Auto-approve low priority work orders
        if self.priority == "Low" and not self.approval_required:
            self.status = "Approved"
            self.approved_by = frappe.session.user
            self.approval_date = getdate()
    
    def on_update(self):
        """Actions on work order update."""
        if self.has_value_changed("status"):
            self.handle_status_change()
        
        if self.has_value_changed("assigned_to"):
            self.send_assignment_notification()
    
    def handle_status_change(self):
        """Handle work order status changes."""
        if self.status == "In Progress" and not self.start_time:
            self.start_time = now_datetime()
        
        elif self.status == "Completed":
            if not self.end_time:
                self.end_time = now_datetime()
            
            self.calculate_hours()
            self.send_completion_notifications()
            
            # Create follow-up work order if required
            if self.follow_up_required:
                self.create_follow_up_work_order()
        
        elif self.status == "Approved":
            self.send_approval_notification()
        
        elif self.status == "Cancelled":
            self.send_cancellation_notification()
    
    def on_submit(self):
        """Actions on work order submission."""
        self.validate_submission()
        self.send_work_order_notifications()
        self.update_asset_maintenance_log()
    
    def validate_submission(self):
        """Validate work order before submission."""
        if self.approval_required and self.status != "Approved":
            frappe.throw(_("Work order must be approved before submission"))
        
        if self.status == "Completed" and not self.completion_notes:
            frappe.throw(_("Completion notes are required for completed work orders"))
        
        if self.safety_requirements and not self.safety_checklist_completed:
            frappe.throw(_("Safety checklist must be completed"))
    
    def send_work_order_notifications(self):
        """Send work order notifications."""
        # Notify assigned user
        if self.assigned_to:
            self.send_assignment_notification()
        
        # Notify maintenance manager
        self.send_manager_notification()
        
        # Notify requester
        if self.requested_by:
            self.send_requester_notification()
    
    def send_assignment_notification(self):
        """Send notification to assigned user."""
        if not self.assigned_to:
            return
        
        frappe.sendmail(
            recipients=[self.assigned_to],
            subject=_("Work Order Assigned - {0}").format(self.name),
            message=self.get_assignment_notification_message(),
            reference_doctype=self.doctype,
            reference_name=self.name
        )
    
    def get_assignment_notification_message(self):
        """Get assignment notification message."""
        return _("""
        Work Order Assignment
        
        Work Order: {work_order}
        Title: {title}
        Priority: {priority}
        Expected Completion: {completion_date}
        
        Description:
        {description}
        
        Location: {location}
        Equipment: {equipment}
        
        Safety Requirements:
        {safety_requirements}
        
        Tools Required:
        {tools_required}
        
        Please review and start work as per priority level.
        
        Maintenance Management System
        """).format(
            work_order=self.name,
            title=self.title,
            priority=self.priority,
            completion_date=frappe.format(self.expected_completion_date, "Date"),
            description=self.description or "None",
            location=self.location or "Not specified",
            equipment=self.equipment or "Not specified",
            safety_requirements=self.safety_requirements or "None",
            tools_required=self.tools_required or "Standard tools"
        )
    
    def send_manager_notification(self):
        """Send notification to maintenance managers."""
        managers = frappe.get_all("Has Role",
            filters={"role": "Maintenance Manager"},
            fields=["parent"]
        )
        
        if managers:
            recipients = [user.parent for user in managers]
            
            frappe.sendmail(
                recipients=recipients,
                subject=_("New Work Order - {0}").format(self.name),
                message=self.get_manager_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_manager_notification_message(self):
        """Get manager notification message."""
        return _("""
        New Work Order Created
        
        Work Order: {work_order}
        Type: {work_order_type}
        Priority: {priority}
        Status: {status}
        
        Requested By: {requested_by}
        Assigned To: {assigned_to}
        
        Title: {title}
        Location: {location}
        Department: {department}
        
        Estimated Cost: {estimated_cost}
        Expected Completion: {completion_date}
        
        {approval_info}
        
        Description:
        {description}
        
        Maintenance Management System
        """).format(
            work_order=self.name,
            work_order_type=self.work_order_type,
            priority=self.priority,
            status=self.status,
            requested_by=self.requested_by,
            assigned_to=self.assigned_to or "Not assigned",
            title=self.title,
            location=self.location or "Not specified",
            department=self.department or "Not specified",
            estimated_cost=frappe.format(self.estimated_cost, "Currency") if self.estimated_cost else "Not estimated",
            completion_date=frappe.format(self.expected_completion_date, "Date"),
            approval_info="Approval Required" if self.approval_required else "No approval required",
            description=self.description or "None"
        )
    
    def send_requester_notification(self):
        """Send notification to work order requester."""
        frappe.sendmail(
            recipients=[self.requested_by],
            subject=_("Work Order Status Update - {0}").format(self.name),
            message=self.get_requester_notification_message(),
            reference_doctype=self.doctype,
            reference_name=self.name
        )
    
    def get_requester_notification_message(self):
        """Get requester notification message."""
        return _("""
        Work Order Status Update
        
        Your work order has been processed:
        
        Work Order: {work_order}
        Title: {title}
        Status: {status}
        Priority: {priority}
        
        Assigned To: {assigned_to}
        Expected Completion: {completion_date}
        
        {status_message}
        
        You will receive updates as work progresses.
        
        Maintenance Management System
        """).format(
            work_order=self.name,
            title=self.title,
            status=self.status,
            priority=self.priority,
            assigned_to=self.assigned_to or "Not yet assigned",
            completion_date=frappe.format(self.expected_completion_date, "Date"),
            status_message=self.get_status_message()
        )
    
    def get_status_message(self):
        """Get status-specific message."""
        messages = {
            "Open": "Your work order is open and awaiting assignment.",
            "In Progress": "Work has started on your request.",
            "Pending Approval": "Your work order is pending management approval.",
            "Approved": "Your work order has been approved and will be scheduled.",
            "Completed": "Your work order has been completed.",
            "Cancelled": "Your work order has been cancelled.",
            "On Hold": "Your work order is temporarily on hold."
        }
        return messages.get(self.status, "")
    
    def send_completion_notifications(self):
        """Send completion notifications."""
        # Notify requester
        if self.requested_by:
            frappe.sendmail(
                recipients=[self.requested_by],
                subject=_("Work Order Completed - {0}").format(self.name),
                message=self.get_completion_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
        
        # Notify managers
        managers = frappe.get_all("Has Role",
            filters={"role": "Maintenance Manager"},
            fields=["parent"]
        )
        
        if managers:
            recipients = [user.parent for user in managers]
            
            frappe.sendmail(
                recipients=recipients,
                subject=_("Work Order Completed - {0}").format(self.name),
                message=self.get_manager_completion_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_completion_notification_message(self):
        """Get completion notification message."""
        return _("""
        Work Order Completed
        
        Your work order has been completed:
        
        Work Order: {work_order}
        Title: {title}
        Completed By: {assigned_to}
        
        Work Details:
        {work_details}
        
        Completion Notes:
        {completion_notes}
        
        Total Hours: {total_hours}
        Actual Cost: {actual_cost}
        
        {follow_up_info}
        {warranty_info}
        
        Thank you for using our maintenance services.
        
        Maintenance Management System
        """).format(
            work_order=self.name,
            title=self.title,
            assigned_to=self.assigned_to,
            work_details=self.work_details or "Standard maintenance work performed",
            completion_notes=self.completion_notes or "Work completed successfully",
            total_hours=self.total_hours or "Not recorded",
            actual_cost=frappe.format(self.actual_cost, "Currency") if self.actual_cost else "Not recorded",
            follow_up_info=f"Follow-up scheduled for {frappe.format(self.follow_up_date, 'Date')}" if self.follow_up_required else "",
            warranty_info=f"Warranty period: {self.warranty_period}" if self.warranty_applicable else ""
        )
    
    def get_manager_completion_message(self):
        """Get manager completion notification message."""
        return _("""
        Work Order Completion Report
        
        Work Order: {work_order}
        Type: {work_order_type}
        Priority: {priority}
        
        Assigned To: {assigned_to}
        Total Hours: {total_hours}
        
        Cost Analysis:
        - Estimated: {estimated_cost}
        - Actual: {actual_cost}
        - Variance: {cost_variance}
        
        Completion Notes:
        {completion_notes}
        
        {follow_up_info}
        
        Maintenance Management System
        """).format(
            work_order=self.name,
            work_order_type=self.work_order_type,
            priority=self.priority,
            assigned_to=self.assigned_to,
            total_hours=self.total_hours or "Not recorded",
            estimated_cost=frappe.format(self.estimated_cost, "Currency") if self.estimated_cost else "Not estimated",
            actual_cost=frappe.format(self.actual_cost, "Currency") if self.actual_cost else "Not recorded",
            cost_variance=self.get_cost_variance(),
            completion_notes=self.completion_notes or "Work completed successfully",
            follow_up_info=f"Follow-up required on {frappe.format(self.follow_up_date, 'Date')}" if self.follow_up_required else "No follow-up required"
        )
    
    def get_cost_variance(self):
        """Calculate cost variance."""
        if self.estimated_cost and self.actual_cost:
            variance = flt(self.actual_cost) - flt(self.estimated_cost)
            percentage = (variance / flt(self.estimated_cost)) * 100
            return f"{frappe.format(variance, 'Currency')} ({percentage:.1f}%)"
        return "Cannot calculate"
    
    def send_approval_notification(self):
        """Send approval notification."""
        if self.assigned_to:
            frappe.sendmail(
                recipients=[self.assigned_to],
                subject=_("Work Order Approved - {0}").format(self.name),
                message=_("Work order {0} has been approved. You can now proceed with the work.").format(self.name),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def send_cancellation_notification(self):
        """Send cancellation notification."""
        recipients = []
        if self.assigned_to:
            recipients.append(self.assigned_to)
        if self.requested_by:
            recipients.append(self.requested_by)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Work Order Cancelled - {0}").format(self.name),
                message=_("Work order {0} has been cancelled. Reason: {1}").format(
                    self.name, self.rejection_reason or "Not specified"
                ),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def create_follow_up_work_order(self):
        """Create follow-up work order."""
        if not self.follow_up_required or not self.follow_up_date:
            return
        
        follow_up = frappe.copy_doc(self)
        follow_up.title = f"Follow-up: {self.title}"
        follow_up.date = self.follow_up_date
        follow_up.status = "Open"
        follow_up.work_order_type = "Inspection"
        follow_up.priority = "Medium"
        follow_up.description = f"Follow-up inspection for work order {self.name}"
        follow_up.follow_up_required = 0
        follow_up.start_time = None
        follow_up.end_time = None
        follow_up.total_hours = 0
        follow_up.completion_notes = None
        follow_up.work_details = None
        
        follow_up.insert()
        
        frappe.msgprint(_("Follow-up work order {0} created").format(follow_up.name))
        return follow_up
    
    def update_asset_maintenance_log(self):
        """Update asset maintenance log."""
        if self.asset and self.status == "Completed":
            # Create maintenance log entry
            maintenance_log = frappe.get_doc({
                "doctype": "Asset Maintenance Log",
                "asset_name": self.asset,
                "maintenance_type": self.maintenance_type,
                "periodicity": "Manual",
                "maintenance_status": "Completed",
                "completion_date": getdate(),
                "actions_performed": self.completion_notes,
                "maintenance_team_member": self.assigned_to,
                "cost": self.actual_cost
            })
            
            try:
                maintenance_log.insert()
            except Exception as e:
                frappe.log_error(f"Failed to create asset maintenance log: {str(e)}")
    
    @frappe.whitelist()
    def approve_work_order(self):
        """Approve work order."""
        if not self.approval_required:
            frappe.throw(_("This work order does not require approval"))
        
        if self.status == "Approved":
            frappe.throw(_("Work order is already approved"))
        
        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approval_date = getdate()
        self.save()
        
        frappe.msgprint(_("Work order approved successfully"))
        return self
    
    @frappe.whitelist()
    def reject_work_order(self, reason):
        """Reject work order."""
        if not self.approval_required:
            frappe.throw(_("This work order does not require approval"))
        
        self.status = "Cancelled"
        self.rejection_reason = reason
        self.save()
        
        frappe.msgprint(_("Work order rejected"))
        return self
    
    @frappe.whitelist()
    def start_work(self):
        """Start work on order."""
        if self.status not in ["Open", "Approved"]:
            frappe.throw(_("Cannot start work on work order with status {0}").format(self.status))
        
        if self.approval_required and self.status != "Approved":
            frappe.throw(_("Work order must be approved before starting work"))
        
        self.status = "In Progress"
        self.start_time = now_datetime()
        self.save()
        
        frappe.msgprint(_("Work started"))
        return self
    
    @frappe.whitelist()
    def complete_work(self, completion_notes=None, actual_cost=None):
        """Complete work order."""
        if self.status != "In Progress":
            frappe.throw(_("Only work orders in progress can be completed"))
        
        self.status = "Completed"
        self.end_time = now_datetime()
        
        if completion_notes:
            self.completion_notes = completion_notes
        
        if actual_cost:
            self.actual_cost = flt(actual_cost)
        
        self.calculate_hours()
        self.save()
        
        frappe.msgprint(_("Work order completed"))
        return self
    
    @frappe.whitelist()
    def get_work_order_analytics(self):
        """Get work order analytics."""
        # Get department workload
        dept_workload = frappe.db.sql("""
            SELECT department, COUNT(*) as count, AVG(total_hours) as avg_hours
            FROM `tabWork Order`
            WHERE department IS NOT NULL
            AND status = 'Completed'
            AND docstatus = 1
            GROUP BY department
        """, as_dict=True)
        
        # Get maintenance type distribution
        maintenance_types = frappe.db.sql("""
            SELECT maintenance_type, COUNT(*) as count
            FROM `tabWork Order`
            WHERE maintenance_type IS NOT NULL
            AND docstatus = 1
            GROUP BY maintenance_type
            ORDER BY count DESC
        """, as_dict=True)
        
        # Get priority distribution
        priority_dist = frappe.db.sql("""
            SELECT priority, COUNT(*) as count
            FROM `tabWork Order`
            WHERE docstatus = 1
            GROUP BY priority
        """, as_dict=True)
        
        # Get recent completed work orders
        recent_completed = frappe.get_all("Work Order",
            filters={"status": "Completed", "docstatus": 1},
            fields=["name", "title", "assigned_to", "total_hours", "actual_cost"],
            order_by="modified desc",
            limit=10
        )
        
        return {
            "current_work_order": {
                "name": self.name,
                "title": self.title,
                "status": self.status,
                "priority": self.priority,
                "estimated_cost": self.estimated_cost,
                "actual_cost": self.actual_cost
            },
            "department_workload": dept_workload,
            "maintenance_types": maintenance_types,
            "priority_distribution": priority_dist,
            "recent_completed": recent_completed,
            "cost_analysis": {
                "estimated": self.estimated_cost,
                "actual": self.actual_cost,
                "variance": self.get_cost_variance() if self.estimated_cost and self.actual_cost else None
            },
            "time_analysis": {
                "start_time": self.start_time,
                "end_time": self.end_time,
                "total_hours": self.total_hours
            }
        }
    
    def get_work_order_summary(self):
        """Get work order summary for reporting."""
        return {
            "work_order_name": self.name,
            "title": self.title,
            "work_order_type": self.work_order_type,
            "priority": self.priority,
            "status": self.status,
            "date": self.date,
            "expected_completion_date": self.expected_completion_date,
            "location": self.location,
            "department": self.department,
            "requested_by": self.requested_by,
            "assigned_to": self.assigned_to,
            "maintenance_type": self.maintenance_type,
            "estimated_cost": self.estimated_cost,
            "actual_cost": self.actual_cost,
            "total_hours": self.total_hours,
            "approval_required": self.approval_required,
            "approved_by": self.approved_by,
            "follow_up_required": self.follow_up_required,
            "warranty_applicable": self.warranty_applicable
        }
