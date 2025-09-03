import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, flt, cint
from frappe import _


class PurchaseRequest(Document):
    def validate(self):
        self.validate_dates()
        self.validate_items()
        self.calculate_total()
        self.set_department()
        self.check_budget_availability()
        
    def validate_dates(self):
        """Validate date fields"""
        if self.required_by and self.required_by < self.transaction_date:
            frappe.throw(_("Required by date cannot be before request date"))
            
    def validate_items(self):
        """Validate items table"""
        if not self.items:
            frappe.throw(_("Please add at least one item"))
            
        for item in self.items:
            if not item.item_description:
                frappe.throw(_("Item description is required for row {0}").format(item.idx))
            if not item.qty or item.qty <= 0:
                frappe.throw(_("Quantity must be greater than 0 for row {0}").format(item.idx))
                
    def calculate_total(self):
        """Calculate total estimated cost"""
        total = 0
        for item in self.items:
            item.amount = flt(item.qty) * flt(item.rate)
            total += item.amount
        self.total_estimated_cost = total
        
    def set_department(self):
        """Set department from requested by employee"""
        if self.requested_by and not self.department:
            self.department = frappe.db.get_value("Employee", self.requested_by, "department")
            
    def check_budget_availability(self):
        """Check budget availability"""
        if self.budget_account:
            budget_balance = frappe.db.get_value("School Account", self.budget_account, "budget_remaining")
            self.budget_available = budget_balance or 0
            
            if self.total_estimated_cost > self.budget_available:
                frappe.msgprint(_("Warning: Request amount ({0}) exceeds available budget ({1})").format(
                    frappe.format_value(self.total_estimated_cost, "Currency"),
                    frappe.format_value(self.budget_available, "Currency")
                ), indicator="orange")
                
    def on_submit(self):
        self.status = "Pending Approval"
        self.send_approval_notification()
        
    def on_cancel(self):
        self.status = "Cancelled"
        
    def send_approval_notification(self):
        """Send notification to approver"""
        if self.approver:
            approver_email = frappe.db.get_value("Employee", self.approver, "user_id")
            if approver_email:
                frappe.sendmail(
                    recipients=[approver_email],
                    subject=f"Purchase Request Approval Required: {self.title}",
                    message=f"""
                    <p>A purchase request requires your approval:</p>
                    <p><strong>Request:</strong> {self.title}</p>
                    <p><strong>Requested By:</strong> {self.requested_by}</p>
                    <p><strong>Department:</strong> {self.department}</p>
                    <p><strong>Total Cost:</strong> {frappe.format_value(self.total_estimated_cost, "Currency")}</p>
                    <p><strong>Required By:</strong> {self.required_by}</p>
                    <p><strong>Priority:</strong> {self.priority}</p>
                    <p><strong>Purpose:</strong> {self.purpose}</p>
                    <p>Please review and approve/reject this request.</p>
                    """,
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
                
    @frappe.whitelist()
    def approve_request(self):
        """Approve purchase request"""
        if not frappe.has_permission(self.doctype, "write"):
            frappe.throw(_("Not permitted to approve"))
            
        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approval_date = nowdate()
        self.save()
        
        # Notify requester
        requester_email = frappe.db.get_value("Employee", self.requested_by, "user_id")
        if requester_email:
            frappe.sendmail(
                recipients=[requester_email],
                subject=f"Purchase Request Approved: {self.title}",
                message=f"""
                <p>Your purchase request has been approved:</p>
                <p><strong>Request:</strong> {self.title}</p>
                <p><strong>Approved By:</strong> {self.approved_by}</p>
                <p><strong>Approval Date:</strong> {self.approval_date}</p>
                <p>You can now proceed with creating a purchase order.</p>
                """,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
            
        frappe.msgprint(_("Purchase request approved"))
        
    @frappe.whitelist()
    def reject_request(self, reason=None):
        """Reject purchase request"""
        if not frappe.has_permission(self.doctype, "write"):
            frappe.throw(_("Not permitted to reject"))
            
        self.status = "Rejected"
        self.approved_by = frappe.session.user
        self.approval_date = nowdate()
        if reason:
            self.notes = (self.notes or "") + f"\nRejection Reason: {reason}"
        self.save()
        
        # Notify requester
        requester_email = frappe.db.get_value("Employee", self.requested_by, "user_id")
        if requester_email:
            frappe.sendmail(
                recipients=[requester_email],
                subject=f"Purchase Request Rejected: {self.title}",
                message=f"""
                <p>Your purchase request has been rejected:</p>
                <p><strong>Request:</strong> {self.title}</p>
                <p><strong>Rejected By:</strong> {self.approved_by}</p>
                <p><strong>Rejection Date:</strong> {self.approval_date}</p>
                {f'<p><strong>Reason:</strong> {reason}</p>' if reason else ''}
                <p>Please contact your approver for more details.</p>
                """,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
            
        frappe.msgprint(_("Purchase request rejected"))
        
    @frappe.whitelist()
    def create_purchase_order(self):
        """Create purchase order from request"""
        if self.status != "Approved":
            frappe.throw(_("Only approved requests can be converted to purchase orders"))
            
        po = frappe.new_doc("Purchase Order")
        po.title = self.title
        po.supplier = ""  # To be filled
        po.transaction_date = nowdate()
        po.required_by = self.required_by
        po.purchase_request = self.name
        
        for item in self.items:
            po.append("items", {
                "item_description": item.item_description,
                "qty": item.qty,
                "rate": item.rate,
                "amount": item.amount,
                "specifications": item.specifications
            })
            
        po.save()
        
        # Update status
        self.status = "Ordered"
        self.save()
        
        frappe.msgprint(_("Purchase Order {0} created").format(po.name))
        return po.name


@frappe.whitelist()
def get_pending_approvals(approver=None):
    """Get pending purchase requests for approval"""
    filters = {"status": "Pending Approval", "docstatus": 1}
    if approver:
        filters["approver"] = approver
        
    return frappe.get_all("Purchase Request", 
        filters=filters,
        fields=["name", "title", "requested_by", "department", "total_estimated_cost", 
                "required_by", "priority", "transaction_date"],
        order_by="priority desc, required_by asc"
    )


@frappe.whitelist()
def get_purchase_request_analytics():
    """Get purchase request analytics"""
    return {
        "total_requests": frappe.db.count("Purchase Request", {"docstatus": 1}),
        "pending_approval": frappe.db.count("Purchase Request", {
            "status": "Pending Approval", "docstatus": 1
        }),
        "approved_requests": frappe.db.count("Purchase Request", {
            "status": "Approved", "docstatus": 1
        }),
        "total_value": frappe.db.sql("""
            SELECT SUM(total_estimated_cost) as value
            FROM `tabPurchase Request`
            WHERE docstatus = 1
        """)[0][0] or 0,
        "by_type": frappe.db.sql("""
            SELECT request_type, COUNT(*) as count, SUM(total_estimated_cost) as value
            FROM `tabPurchase Request`
            WHERE docstatus = 1
            GROUP BY request_type
        """, as_dict=True),
        "by_priority": frappe.db.sql("""
            SELECT priority, COUNT(*) as count
            FROM `tabPurchase Request`
            WHERE docstatus = 1
            GROUP BY priority
        """, as_dict=True),
        "by_department": frappe.db.sql("""
            SELECT department, COUNT(*) as count, SUM(total_estimated_cost) as value
            FROM `tabPurchase Request`
            WHERE docstatus = 1 AND department IS NOT NULL
            GROUP BY department
        """, as_dict=True)
    }
