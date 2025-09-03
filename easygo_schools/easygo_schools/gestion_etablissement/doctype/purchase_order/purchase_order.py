"""Purchase Order DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, flt, cint, add_days


class PurchaseOrder(Document):
    """Purchase order management for procurement."""
    
    def validate(self):
        """Validate purchase order data."""
        self.validate_items()
        self.validate_supplier()
        self.validate_dates()
        self.calculate_totals()
        self.set_defaults()
    
    def validate_items(self):
        """Validate purchase order items."""
        if not self.items:
            frappe.throw(_("Items are required"))
        
        for item in self.items:
            if not item.item_code:
                frappe.throw(_("Item Code is required in row {0}").format(item.idx))
            
            if flt(item.qty) <= 0:
                frappe.throw(_("Quantity must be greater than 0 in row {0}").format(item.idx))
            
            if flt(item.rate) < 0:
                frappe.throw(_("Rate cannot be negative in row {0}").format(item.idx))
    
    def validate_supplier(self):
        """Validate supplier details."""
        if not self.supplier:
            frappe.throw(_("Supplier is required"))
        
        supplier = frappe.get_doc("Supplier", self.supplier)
        if supplier.disabled:
            frappe.throw(_("Supplier {0} is disabled").format(self.supplier))
    
    def validate_dates(self):
        """Validate order dates."""
        if self.schedule_date and self.transaction_date:
            if getdate(self.schedule_date) < getdate(self.transaction_date):
                frappe.throw(_("Required By date cannot be before transaction date"))
        
        if self.required_by and self.transaction_date:
            if getdate(self.required_by) < getdate(self.transaction_date):
                frappe.throw(_("Expected Delivery Date cannot be before transaction date"))
    
    def calculate_totals(self):
        """Calculate order totals."""
        self.total_qty = 0
        self.base_total = 0
        
        for item in self.items:
            item.amount = flt(item.qty) * flt(item.rate)
            self.total_qty += flt(item.qty)
            self.base_total += flt(item.amount)
        
        # Apply additional discount
        if self.additional_discount_percentage:
            self.discount_amount = (self.base_total * flt(self.additional_discount_percentage)) / 100
        
        if self.discount_amount:
            self.base_discount_amount = flt(self.discount_amount) * flt(self.conversion_rate)
        
        # Calculate grand total
        self.grand_total = self.base_total - flt(self.base_discount_amount) + flt(self.total_taxes_and_charges)
        self.base_grand_total = flt(self.grand_total) * flt(self.conversion_rate)
        
        # Set in words
        self.in_words = frappe.utils.money_in_words(self.grand_total, self.currency)
    
    def set_defaults(self):
        """Set default values."""
        if not self.transaction_date:
            self.transaction_date = getdate()
        
        if not self.currency:
            self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
        
        if not self.conversion_rate:
            self.conversion_rate = 1.0
        
        if not self.schedule_date and self.transaction_date:
            self.schedule_date = add_days(self.transaction_date, 7)  # Default 7 days
    
    def on_submit(self):
        """Actions on submit."""
        self.status = "To Receive and Bill"
        self.send_purchase_order_notifications()
        self.create_supplier_quotation_if_needed()
    
    def send_purchase_order_notifications(self):
        """Send purchase order notifications."""
        # Notify supplier
        self.send_supplier_notification()
        
        # Notify purchase team
        self.send_purchase_team_notification()
        
        # Notify accounts team
        self.send_accounts_notification()
    
    def send_supplier_notification(self):
        """Send notification to supplier."""
        supplier = frappe.get_doc("Supplier", self.supplier)
        
        if supplier.email_id:
            frappe.sendmail(
                recipients=[supplier.email_id],
                subject=_("Purchase Order - {0}").format(self.name),
                message=self.get_supplier_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name,
                attachments=[{
                    "fname": f"{self.name}.pdf",
                    "fcontent": frappe.get_print(self.doctype, self.name, "Purchase Order", as_pdf=True)
                }]
            )
    
    def get_supplier_notification_message(self):
        """Get supplier notification message."""
        return _("""
        Dear {supplier_name},
        
        We are pleased to place the following purchase order with you:
        
        Purchase Order: {po_number}
        Date: {po_date}
        Required By: {required_by}
        
        Order Summary:
        - Total Items: {total_items}
        - Total Quantity: {total_qty}
        - Grand Total: {grand_total}
        
        Delivery Address:
        {delivery_address}
        
        Payment Terms:
        {payment_terms}
        
        Please confirm receipt of this order and provide delivery schedule.
        
        Thank you for your business.
        
        Best regards,
        Procurement Team
        """).format(
            supplier_name=self.supplier_name,
            po_number=self.name,
            po_date=frappe.format(self.transaction_date, "Date"),
            required_by=frappe.format(self.required_by, "Date") if self.required_by else "As per schedule",
            total_items=len(self.items),
            total_qty=self.total_qty,
            grand_total=frappe.format(self.grand_total, "Currency"),
            delivery_address=self.shipping_address_display or "Main office",
            payment_terms=self.get_payment_terms_text()
        )
    
    def get_payment_terms_text(self):
        """Get payment terms as text."""
        if self.payment_terms_template:
            template = frappe.get_doc("Payment Terms Template", self.payment_terms_template)
            return template.description or "As per agreement"
        return "As per agreement"
    
    def send_purchase_team_notification(self):
        """Send notification to purchase team."""
        purchase_users = frappe.get_all("Has Role",
            filters={"role": "Purchase Manager"},
            fields=["parent"]
        )
        
        if purchase_users:
            recipients = [user.parent for user in purchase_users]
            
            frappe.sendmail(
                recipients=recipients,
                subject=_("Purchase Order Submitted - {0}").format(self.name),
                message=self.get_purchase_team_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_purchase_team_notification_message(self):
        """Get purchase team notification message."""
        return _("""
        Purchase Order Submitted
        
        PO Number: {po_number}
        Supplier: {supplier_name}
        Date: {po_date}
        Required By: {required_by}
        
        Order Details:
        - Total Items: {total_items}
        - Total Quantity: {total_qty}
        - Grand Total: {grand_total}
        - Status: {status}
        
        Next Steps:
        - Monitor delivery progress
        - Update receipt status
        - Process invoices when received
        
        Procurement Management System
        """).format(
            po_number=self.name,
            supplier_name=self.supplier_name,
            po_date=frappe.format(self.transaction_date, "Date"),
            required_by=frappe.format(self.required_by, "Date") if self.required_by else "TBA",
            total_items=len(self.items),
            total_qty=self.total_qty,
            grand_total=frappe.format(self.grand_total, "Currency"),
            status=self.status
        )
    
    def send_accounts_notification(self):
        """Send notification to accounts team."""
        accounts_users = frappe.get_all("Has Role",
            filters={"role": "Accounts Manager"},
            fields=["parent"]
        )
        
        if accounts_users:
            recipients = [user.parent for user in accounts_users]
            
            frappe.sendmail(
                recipients=recipients,
                subject=_("Purchase Order for Billing - {0}").format(self.name),
                message=self.get_accounts_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_accounts_notification_message(self):
        """Get accounts notification message."""
        return _("""
        Purchase Order Ready for Billing
        
        PO Number: {po_number}
        Supplier: {supplier_name}
        Amount: {grand_total}
        
        Payment Information:
        - Payment Terms: {payment_terms}
        - Advance Paid: {advance_paid}
        - Outstanding: {outstanding}
        
        Please prepare for invoice processing when goods are received.
        
        Accounts Team
        """).format(
            po_number=self.name,
            supplier_name=self.supplier_name,
            grand_total=frappe.format(self.grand_total, "Currency"),
            payment_terms=self.get_payment_terms_text(),
            advance_paid=frappe.format(self.advance_paid, "Currency") if self.advance_paid else "None",
            outstanding=frappe.format(self.grand_total - flt(self.advance_paid), "Currency")
        )
    
    def create_supplier_quotation_if_needed(self):
        """Create supplier quotation if required."""
        # This would typically be done before PO creation
        # But can be useful for record keeping
        pass
    
    @frappe.whitelist()
    def update_delivery_status(self, received_qty_dict, delivery_note=None):
        """Update delivery status based on received quantities."""
        total_received = 0
        total_ordered = 0
        
        for item in self.items:
            received_qty = flt(received_qty_dict.get(item.item_code, 0))
            item.received_qty = flt(item.received_qty or 0) + received_qty
            
            total_received += item.received_qty
            total_ordered += item.qty
        
        # Calculate percentage received
        self.per_received = (total_received / total_ordered) * 100 if total_ordered > 0 else 0
        
        # Update delivery status
        if self.per_received == 0:
            self.delivery_status = "Pending"
        elif self.per_received < 100:
            self.delivery_status = "Partially Delivered"
        elif self.per_received == 100:
            self.delivery_status = "Fully Delivered"
        else:
            self.delivery_status = "Overdelivered"
        
        # Update overall status
        if self.per_received >= 100 and self.per_billed >= 100:
            self.status = "Completed"
        elif self.per_received >= 100:
            self.status = "To Bill"
        elif self.per_billed >= 100:
            self.status = "To Receive"
        
        self.save()
        
        # Send delivery update notification
        self.send_delivery_update_notification(delivery_note)
        
        return self
    
    def send_delivery_update_notification(self, delivery_note=None):
        """Send delivery update notification."""
        # Notify purchase team
        purchase_users = frappe.get_all("Has Role",
            filters={"role": "Purchase Manager"},
            fields=["parent"]
        )
        
        if purchase_users:
            recipients = [user.parent for user in purchase_users]
            
            frappe.sendmail(
                recipients=recipients,
                subject=_("Delivery Update - PO {0}").format(self.name),
                message=self.get_delivery_update_message(delivery_note),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_delivery_update_message(self, delivery_note=None):
        """Get delivery update message."""
        return _("""
        Purchase Order Delivery Update
        
        PO Number: {po_number}
        Supplier: {supplier_name}
        Delivery Status: {delivery_status}
        
        Progress:
        - Received: {per_received}%
        - Billed: {per_billed}%
        
        {delivery_note_info}
        
        Current Status: {status}
        
        Procurement Team
        """).format(
            po_number=self.name,
            supplier_name=self.supplier_name,
            delivery_status=self.delivery_status,
            per_received=self.per_received,
            per_billed=self.per_billed,
            delivery_note_info=f"Delivery Note: {delivery_note}" if delivery_note else "",
            status=self.status
        )
    
    @frappe.whitelist()
    def update_billing_status(self, billed_amount, invoice_reference=None):
        """Update billing status."""
        self.per_billed = (flt(billed_amount) / self.grand_total) * 100 if self.grand_total > 0 else 0
        
        # Update overall status
        if self.per_received >= 100 and self.per_billed >= 100:
            self.status = "Completed"
        elif self.per_received >= 100:
            self.status = "To Bill"
        elif self.per_billed >= 100:
            self.status = "To Receive"
        
        self.save()
        
        # Send billing update notification
        self.send_billing_update_notification(invoice_reference)
        
        return self
    
    def send_billing_update_notification(self, invoice_reference=None):
        """Send billing update notification."""
        # Notify accounts team
        accounts_users = frappe.get_all("Has Role",
            filters={"role": "Accounts Manager"},
            fields=["parent"]
        )
        
        if accounts_users:
            recipients = [user.parent for user in accounts_users]
            
            frappe.sendmail(
                recipients=recipients,
                subject=_("Billing Update - PO {0}").format(self.name),
                message=self.get_billing_update_message(invoice_reference),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_billing_update_message(self, invoice_reference=None):
        """Get billing update message."""
        return _("""
        Purchase Order Billing Update
        
        PO Number: {po_number}
        Supplier: {supplier_name}
        
        Billing Progress:
        - Billed: {per_billed}%
        - Amount Billed: {billed_amount}
        - Outstanding: {outstanding}
        
        {invoice_info}
        
        Current Status: {status}
        
        Accounts Team
        """).format(
            po_number=self.name,
            supplier_name=self.supplier_name,
            per_billed=self.per_billed,
            billed_amount=frappe.format((self.grand_total * self.per_billed) / 100, "Currency"),
            outstanding=frappe.format(self.grand_total - ((self.grand_total * self.per_billed) / 100), "Currency"),
            invoice_info=f"Invoice Reference: {invoice_reference}" if invoice_reference else "",
            status=self.status
        )
    
    @frappe.whitelist()
    def cancel_purchase_order(self, cancellation_reason):
        """Cancel purchase order."""
        if self.status == "Cancelled":
            frappe.throw(_("Purchase order is already cancelled"))
        
        if self.per_received > 0 or self.per_billed > 0:
            frappe.throw(_("Cannot cancel purchase order with deliveries or bills"))
        
        self.status = "Cancelled"
        self.save()
        
        # Send cancellation notification
        self.send_cancellation_notification(cancellation_reason)
        
        frappe.msgprint(_("Purchase order cancelled"))
        return self
    
    def send_cancellation_notification(self, reason):
        """Send cancellation notification."""
        # Notify supplier
        supplier = frappe.get_doc("Supplier", self.supplier)
        if supplier.email_id:
            frappe.sendmail(
                recipients=[supplier.email_id],
                subject=_("Purchase Order Cancelled - {0}").format(self.name),
                message=self.get_cancellation_message(reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
        
        # Notify internal teams
        purchase_users = frappe.get_all("Has Role",
            filters={"role": "Purchase Manager"},
            fields=["parent"]
        )
        
        if purchase_users:
            recipients = [user.parent for user in purchase_users]
            frappe.sendmail(
                recipients=recipients,
                subject=_("PO Cancelled - {0}").format(self.name),
                message=self.get_internal_cancellation_message(reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_cancellation_message(self, reason):
        """Get cancellation message for supplier."""
        return _("""
        Dear {supplier_name},
        
        We regret to inform you that Purchase Order {po_number} dated {po_date} has been cancelled.
        
        Cancellation Reason:
        {reason}
        
        Order Details:
        - Total Amount: {grand_total}
        - Required By: {required_by}
        
        We apologize for any inconvenience caused and look forward to future business opportunities.
        
        Best regards,
        Procurement Team
        """).format(
            supplier_name=self.supplier_name,
            po_number=self.name,
            po_date=frappe.format(self.transaction_date, "Date"),
            reason=reason,
            grand_total=frappe.format(self.grand_total, "Currency"),
            required_by=frappe.format(self.required_by, "Date") if self.required_by else "As scheduled"
        )
    
    def get_internal_cancellation_message(self, reason):
        """Get internal cancellation message."""
        return _("""
        Purchase Order Cancelled
        
        PO Number: {po_number}
        Supplier: {supplier_name}
        Amount: {grand_total}
        
        Cancellation Reason:
        {reason}
        
        Please update any related processes and documentation.
        
        Procurement Team
        """).format(
            po_number=self.name,
            supplier_name=self.supplier_name,
            grand_total=frappe.format(self.grand_total, "Currency"),
            reason=reason
        )
    
    @frappe.whitelist()
    def get_purchase_analytics(self):
        """Get purchase order analytics."""
        # Get supplier performance
        supplier_orders = frappe.get_all("Purchase Order",
            filters={"supplier": self.supplier, "docstatus": 1},
            fields=["name", "grand_total", "per_received", "per_billed", "status"],
            limit=10
        )
        
        # Calculate averages
        avg_order_value = sum(flt(po.grand_total) for po in supplier_orders) / max(1, len(supplier_orders))
        avg_delivery_performance = sum(flt(po.per_received) for po in supplier_orders) / max(1, len(supplier_orders))
        
        # Get item-wise analysis
        item_analysis = {}
        for item in self.items:
            item_analysis[item.item_code] = {
                "qty": item.qty,
                "rate": item.rate,
                "amount": item.amount,
                "received_qty": getattr(item, 'received_qty', 0)
            }
        
        return {
            "current_order": {
                "name": self.name,
                "supplier": self.supplier_name,
                "total_amount": self.grand_total,
                "status": self.status,
                "delivery_status": self.delivery_status
            },
            "supplier_performance": {
                "total_orders": len(supplier_orders),
                "average_order_value": avg_order_value,
                "average_delivery_performance": avg_delivery_performance
            },
            "order_progress": {
                "per_received": self.per_received,
                "per_billed": self.per_billed,
                "total_items": len(self.items),
                "total_qty": self.total_qty
            },
            "item_analysis": item_analysis,
            "financial_summary": {
                "grand_total": self.grand_total,
                "advance_paid": self.advance_paid or 0,
                "outstanding": self.grand_total - flt(self.advance_paid or 0)
            }
        }
