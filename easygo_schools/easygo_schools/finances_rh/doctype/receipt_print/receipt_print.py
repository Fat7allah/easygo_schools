"""Receipt Print DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, flt, cint, add_days, format_datetime


class ReceiptPrint(Document):
    """Receipt print management for fee payment receipts."""
    
    def validate(self):
        """Validate receipt print data."""
        self.validate_student_info()
        self.validate_amounts()
        self.validate_payment_info()
        self.calculate_balance()
        self.set_defaults()
    
    def validate_student_info(self):
        """Validate student information."""
        if not self.student:
            frappe.throw(_("Student is required"))
        
        # Validate student exists and is active
        student_status = frappe.db.get_value("Student", self.student, "enabled")
        if not student_status:
            frappe.throw(_("Student {0} is not active").format(self.student))
    
    def validate_amounts(self):
        """Validate amount fields."""
        if flt(self.total_amount) <= 0:
            frappe.throw(_("Total amount must be greater than 0"))
        
        if flt(self.paid_amount) < 0:
            frappe.throw(_("Paid amount cannot be negative"))
        
        if flt(self.paid_amount) > flt(self.total_amount):
            frappe.throw(_("Paid amount cannot exceed total amount"))
        
        if self.discount_applied and flt(self.discount_amount) < 0:
            frappe.throw(_("Discount amount cannot be negative"))
        
        if self.late_fee and flt(self.penalty_amount) < 0:
            frappe.throw(_("Penalty amount cannot be negative"))
    
    def validate_payment_info(self):
        """Validate payment information."""
        if self.paid_amount and flt(self.paid_amount) > 0:
            if not self.payment_method:
                frappe.throw(_("Payment method is required for paid receipts"))
            
            if not self.payment_date:
                self.payment_date = getdate()
            
            # Validate payment reference for non-cash payments
            if self.payment_method != "Cash" and not self.payment_reference:
                frappe.msgprint(_("Payment reference is recommended for {0} payments").format(self.payment_method))
    
    def calculate_balance(self):
        """Calculate balance amount."""
        total = flt(self.total_amount)
        
        # Add penalty if applicable
        if self.late_fee and self.penalty_amount:
            total += flt(self.penalty_amount)
        
        # Subtract discount if applicable
        if self.discount_applied and self.discount_amount:
            total -= flt(self.discount_amount)
        
        # Calculate balance
        self.balance_amount = total - flt(self.paid_amount)
    
    def set_defaults(self):
        """Set default values."""
        if not self.generated_by:
            self.generated_by = frappe.session.user
        
        if not self.date:
            self.date = getdate()
        
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        
        # Set fee components from fee structure if not set
        if not self.fee_components and self.fee_structure:
            self.set_fee_components_from_structure()
    
    def generate_receipt_number(self):
        """Generate unique receipt number."""
        # Get the last receipt number for this year
        current_year = str(getdate().year)
        last_receipt = frappe.db.sql("""
            SELECT receipt_number
            FROM `tabReceipt Print`
            WHERE receipt_number LIKE %s
            ORDER BY receipt_number DESC
            LIMIT 1
        """, f"RCP-{current_year}-%")
        
        if last_receipt and last_receipt[0][0]:
            last_number = int(last_receipt[0][0].split('-')[-1])
            new_number = last_number + 1
        else:
            new_number = 1
        
        return f"RCP-{current_year}-{new_number:05d}"
    
    def set_fee_components_from_structure(self):
        """Set fee components from fee structure."""
        if not self.fee_structure:
            return
        
        fee_structure = frappe.get_doc("Fee Structure", self.fee_structure)
        
        # Clear existing components
        self.fee_components = []
        
        # Add components from fee structure
        for component in fee_structure.components:
            self.append("fee_components", {
                "fee_component": component.fees_category,
                "amount": component.amount,
                "description": component.description
            })
    
    def before_save(self):
        """Actions before saving receipt."""
        self.calculate_balance()
        
        # Set receipt template if not set
        if not self.receipt_template:
            self.receipt_template = self.get_default_receipt_template()
    
    def get_default_receipt_template(self):
        """Get default receipt template."""
        # Try to get template based on receipt type
        template_name = f"Receipt Print - {self.receipt_type}"
        
        if frappe.db.exists("Print Format", template_name):
            return template_name
        
        # Fallback to standard template
        if frappe.db.exists("Print Format", "Receipt Print"):
            return "Receipt Print"
        
        return None
    
    def on_submit(self):
        """Actions on receipt submission."""
        self.validate_submission()
        self.update_fee_records()
        self.send_receipt_notifications()
        self.create_accounting_entries()
    
    def validate_submission(self):
        """Validate receipt before submission."""
        if not self.approved_by:
            frappe.throw(_("Receipt must be approved before submission"))
        
        if self.status != "Generated":
            frappe.throw(_("Only generated receipts can be submitted"))
        
        if flt(self.paid_amount) <= 0:
            frappe.throw(_("Paid amount must be greater than 0 for submission"))
    
    def update_fee_records(self):
        """Update related fee records."""
        # Update student fee records
        if self.student and self.academic_year:
            self.update_student_fee_balance()
        
        # Update fee structure records
        if self.fee_structure:
            self.update_fee_structure_collections()
    
    def update_student_fee_balance(self):
        """Update student fee balance."""
        # Find or create student fee record
        fee_record = frappe.db.get_value("Fees",
            filters={
                "student": self.student,
                "academic_year": self.academic_year,
                "fee_structure": self.fee_structure
            }
        )
        
        if fee_record:
            fee_doc = frappe.get_doc("Fees", fee_record)
            fee_doc.paid_amount = (fee_doc.paid_amount or 0) + flt(self.paid_amount)
            fee_doc.outstanding_amount = fee_doc.total_amount - fee_doc.paid_amount
            fee_doc.save(ignore_permissions=True)
    
    def update_fee_structure_collections(self):
        """Update fee structure collection statistics."""
        # This would update collection statistics for the fee structure
        pass
    
    def send_receipt_notifications(self):
        """Send receipt notifications."""
        # Send to student/guardian
        self.send_student_notification()
        
        # Send to accounts team
        self.send_accounts_notification()
        
        # Send SMS notification if enabled
        if self.contact_number:
            self.send_sms_notification()
    
    def send_student_notification(self):
        """Send receipt notification to student/guardian."""
        recipients = []
        
        if self.email:
            recipients.append(self.email)
        
        # Get student email if different
        student_email = frappe.db.get_value("Student", self.student, "student_email_id")
        if student_email and student_email not in recipients:
            recipients.append(student_email)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Fee Payment Receipt - {0}").format(self.name),
                message=self.get_student_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name,
                attachments=[self.get_receipt_pdf()]
            )
    
    def get_student_notification_message(self):
        """Get student notification message."""
        return _("""
        Fee Payment Receipt
        
        Dear {parent_guardian},
        
        This is to confirm the fee payment for {student_name} ({student}).
        
        Receipt Details:
        - Receipt Number: {receipt_number}
        - Date: {date}
        - Amount Paid: {paid_amount}
        - Payment Method: {payment_method}
        - Academic Year: {academic_year}
        
        {balance_info}
        
        Thank you for your payment.
        
        {custom_message}
        
        Best regards,
        Accounts Department
        """).format(
            parent_guardian=self.parent_guardian or "Parent/Guardian",
            student_name=self.student_name,
            student=self.student,
            receipt_number=self.receipt_number,
            date=frappe.format(self.date, "Date"),
            paid_amount=frappe.format(self.paid_amount, "Currency"),
            payment_method=self.payment_method,
            academic_year=self.academic_year or "Current",
            balance_info=f"Outstanding Balance: {frappe.format(self.balance_amount, 'Currency')}" if self.balance_amount > 0 else "No outstanding balance",
            custom_message=self.custom_message or ""
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
                subject=_("Fee Payment Received - {0}").format(self.name),
                message=self.get_accounts_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_accounts_notification_message(self):
        """Get accounts notification message."""
        return _("""
        Fee Payment Received
        
        Receipt: {receipt_number}
        Student: {student_name} ({student})
        Class: {class_section}
        
        Payment Details:
        - Amount: {paid_amount}
        - Method: {payment_method}
        - Reference: {payment_reference}
        - Date: {payment_date}
        
        Fee Structure: {fee_structure}
        Academic Year: {academic_year}
        
        Balance: {balance_amount}
        
        Generated by: {generated_by}
        Approved by: {approved_by}
        
        Accounts Management System
        """).format(
            receipt_number=self.receipt_number,
            student_name=self.student_name,
            student=self.student,
            class_section=self.class_section or "Not specified",
            paid_amount=frappe.format(self.paid_amount, "Currency"),
            payment_method=self.payment_method,
            payment_reference=self.payment_reference or "N/A",
            payment_date=frappe.format(self.payment_date, "Date"),
            fee_structure=self.fee_structure or "Not specified",
            academic_year=self.academic_year or "Current",
            balance_amount=frappe.format(self.balance_amount, "Currency"),
            generated_by=self.generated_by,
            approved_by=self.approved_by
        )
    
    def send_sms_notification(self):
        """Send SMS notification."""
        if not self.contact_number:
            return
        
        message = _("""Fee payment received for {student_name}. Amount: {amount}. Receipt: {receipt}. Balance: {balance}. Thank you!""").format(
            student_name=self.student_name,
            amount=frappe.format(self.paid_amount, "Currency"),
            receipt=self.receipt_number,
            balance=frappe.format(self.balance_amount, "Currency") if self.balance_amount > 0 else "Nil"
        )
        
        try:
            # This would integrate with SMS gateway
            frappe.log_error(f"SMS sent to {self.contact_number}: {message}")
        except Exception as e:
            frappe.log_error(f"Failed to send SMS: {str(e)}")
    
    def create_accounting_entries(self):
        """Create accounting entries."""
        # This would create journal entries for the payment
        # For now, we'll just log the transaction
        self.log_payment_transaction()
    
    def log_payment_transaction(self):
        """Log payment transaction."""
        transaction_log = {
            "receipt": self.name,
            "student": self.student,
            "amount": self.paid_amount,
            "payment_method": self.payment_method,
            "date": self.payment_date,
            "reference": self.payment_reference
        }
        
        frappe.log_error(f"Payment transaction logged: {transaction_log}")
    
    def get_receipt_pdf(self):
        """Get receipt PDF attachment."""
        # Generate PDF using print format
        if self.print_format:
            pdf = frappe.get_print(
                self.doctype,
                self.name,
                print_format=self.print_format,
                letterhead=self.letterhead
            )
            
            return {
                "fname": f"Receipt_{self.receipt_number}.pdf",
                "fcontent": pdf
            }
        
        return None
    
    @frappe.whitelist()
    def approve_receipt(self):
        """Approve receipt for submission."""
        if self.status == "Generated":
            frappe.throw(_("Receipt is already generated"))
        
        self.status = "Generated"
        self.approved_by = frappe.session.user
        self.save()
        
        frappe.msgprint(_("Receipt approved successfully"))
        return self
    
    @frappe.whitelist()
    def print_receipt(self):
        """Mark receipt as printed."""
        self.status = "Printed"
        self.print_date = now_datetime()
        self.save()
        
        frappe.msgprint(_("Receipt marked as printed"))
        return self
    
    @frappe.whitelist()
    def send_receipt(self):
        """Send receipt to student/guardian."""
        if self.status not in ["Generated", "Printed"]:
            frappe.throw(_("Receipt must be generated before sending"))
        
        self.send_student_notification()
        
        self.status = "Sent"
        self.save()
        
        frappe.msgprint(_("Receipt sent successfully"))
        return self
    
    @frappe.whitelist()
    def cancel_receipt(self, reason=None):
        """Cancel receipt."""
        if self.docstatus == 1:
            frappe.throw(_("Cannot cancel submitted receipt"))
        
        self.status = "Cancelled"
        if reason:
            self.remarks = f"Cancelled: {reason}"
        
        self.save()
        
        frappe.msgprint(_("Receipt cancelled"))
        return self
    
    @frappe.whitelist()
    def create_refund_receipt(self, refund_amount, refund_reason):
        """Create refund receipt."""
        if flt(refund_amount) <= 0:
            frappe.throw(_("Refund amount must be greater than 0"))
        
        if flt(refund_amount) > flt(self.paid_amount):
            frappe.throw(_("Refund amount cannot exceed paid amount"))
        
        refund_receipt = frappe.copy_doc(self)
        refund_receipt.receipt_type = "Refund"
        refund_receipt.total_amount = -flt(refund_amount)
        refund_receipt.paid_amount = -flt(refund_amount)
        refund_receipt.original_receipt = self.name
        refund_receipt.remarks = f"Refund for {self.name}: {refund_reason}"
        refund_receipt.status = "Draft"
        refund_receipt.receipt_number = None  # Will be auto-generated
        
        refund_receipt.insert()
        
        frappe.msgprint(_("Refund receipt {0} created").format(refund_receipt.name))
        return refund_receipt
    
    @frappe.whitelist()
    def get_payment_analytics(self):
        """Get payment analytics."""
        # Get student payment history
        student_payments = frappe.get_all("Receipt Print",
            filters={"student": self.student, "docstatus": 1},
            fields=["name", "date", "paid_amount", "payment_method"],
            order_by="date desc",
            limit=10
        )
        
        # Get class payment statistics
        class_payments = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_receipts,
                SUM(paid_amount) as total_collected,
                AVG(paid_amount) as avg_payment
            FROM `tabReceipt Print`
            WHERE class_section = %s
            AND docstatus = 1
        """, self.class_section, as_dict=True)
        
        # Get payment method distribution
        payment_methods = frappe.db.sql("""
            SELECT payment_method, COUNT(*) as count, SUM(paid_amount) as amount
            FROM `tabReceipt Print`
            WHERE docstatus = 1
            GROUP BY payment_method
            ORDER BY amount DESC
        """, as_dict=True)
        
        return {
            "current_receipt": {
                "name": self.name,
                "receipt_number": self.receipt_number,
                "amount": self.paid_amount,
                "balance": self.balance_amount,
                "status": self.status
            },
            "student_payments": student_payments,
            "class_statistics": class_payments[0] if class_payments else {},
            "payment_methods": payment_methods,
            "fee_breakdown": [
                {
                    "component": item.fee_component,
                    "amount": item.amount,
                    "description": item.description
                }
                for item in self.fee_components
            ]
        }
    
    def get_receipt_summary(self):
        """Get receipt summary for reporting."""
        return {
            "receipt_name": self.name,
            "receipt_number": self.receipt_number,
            "receipt_type": self.receipt_type,
            "date": self.date,
            "student": self.student,
            "student_name": self.student_name,
            "class_section": self.class_section,
            "total_amount": self.total_amount,
            "paid_amount": self.paid_amount,
            "balance_amount": self.balance_amount,
            "payment_method": self.payment_method,
            "payment_date": self.payment_date,
            "academic_year": self.academic_year,
            "fee_structure": self.fee_structure,
            "status": self.status,
            "generated_by": self.generated_by,
            "approved_by": self.approved_by
        }
