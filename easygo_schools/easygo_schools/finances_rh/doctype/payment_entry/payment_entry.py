"""Payment Entry doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate, flt


class PaymentEntry(Document):
    """Payment Entry doctype controller."""
    
    def validate(self):
        """Validate payment entry data."""
        self.validate_payment_amount()
        self.validate_payment_date()
        self.calculate_base_amount()
        self.set_defaults()
    
    def validate_payment_amount(self):
        """Validate payment amount."""
        if self.paid_amount <= 0:
            frappe.throw(_("Paid amount must be greater than 0"))
        
        # Validate against fee bill if linked
        if self.fee_bill:
            fee_bill_doc = frappe.get_doc("Fee Bill", self.fee_bill)
            
            if self.paid_amount > fee_bill_doc.outstanding_amount:
                frappe.msgprint(_("Warning: Payment amount exceeds outstanding amount"), alert=True)
    
    def validate_payment_date(self):
        """Validate payment date."""
        if self.payment_date and getdate(self.payment_date) > getdate():
            frappe.throw(_("Payment date cannot be in the future"))
    
    def calculate_base_amount(self):
        """Calculate base amount using exchange rate."""
        self.base_amount = flt(self.paid_amount) * flt(self.exchange_rate)
    
    def set_defaults(self):
        """Set default values."""
        if not self.processed_by:
            self.processed_by = frappe.session.user
        
        if not self.currency:
            self.currency = "MAD"
        
        if not self.exchange_rate:
            self.exchange_rate = 1.0
        
        # Fetch student name
        if self.student and not self.student_name:
            self.student_name = frappe.db.get_value("Student", self.student, "student_name")
        
        # Fetch academic year from fee bill
        if self.fee_bill and not self.academic_year:
            self.academic_year = frappe.db.get_value("Fee Bill", self.fee_bill, "academic_year")
    
    def on_submit(self):
        """Actions on payment submission."""
        self.status = "Verified"
        self.update_fee_bill()
        self.send_payment_confirmation()
    
    def on_cancel(self):
        """Actions on payment cancellation."""
        self.status = "Cancelled"
        self.reverse_fee_bill_update()
    
    def update_fee_bill(self):
        """Update the related fee bill."""
        if not self.fee_bill:
            return
        
        try:
            fee_bill_doc = frappe.get_doc("Fee Bill", self.fee_bill)
            
            # Update outstanding amount
            fee_bill_doc.outstanding_amount = max(0, fee_bill_doc.outstanding_amount - self.paid_amount)
            fee_bill_doc.paid_amount = (fee_bill_doc.paid_amount or 0) + self.paid_amount
            
            # Update status
            if fee_bill_doc.outstanding_amount <= 0:
                fee_bill_doc.status = "Paid"
            elif fee_bill_doc.paid_amount > 0:
                fee_bill_doc.status = "Partially Paid"
            
            fee_bill_doc.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Failed to update fee bill: {str(e)}")
    
    def reverse_fee_bill_update(self):
        """Reverse fee bill update when payment is cancelled."""
        if not self.fee_bill:
            return
        
        try:
            fee_bill_doc = frappe.get_doc("Fee Bill", self.fee_bill)
            
            # Reverse outstanding amount
            fee_bill_doc.outstanding_amount += self.paid_amount
            fee_bill_doc.paid_amount = max(0, (fee_bill_doc.paid_amount or 0) - self.paid_amount)
            
            # Update status
            if fee_bill_doc.paid_amount <= 0:
                fee_bill_doc.status = "Unpaid"
            elif fee_bill_doc.outstanding_amount > 0:
                fee_bill_doc.status = "Partially Paid"
            
            fee_bill_doc.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Failed to reverse fee bill update: {str(e)}")
    
    def send_payment_confirmation(self):
        """Send payment confirmation to student/guardian."""
        try:
            # Get student's guardian email
            guardian_email = frappe.db.sql("""
                SELECT g.email_address
                FROM `tabGuardian` g
                INNER JOIN `tabStudent Guardian` sg ON g.name = sg.guardian
                WHERE sg.student = %s AND g.primary_guardian = 1
            """, (self.student,))
            
            recipients = []
            if guardian_email and guardian_email[0][0]:
                recipients.append(guardian_email[0][0])
            
            # Also get student's user email if exists
            student_email = frappe.db.get_value("Student", self.student, "email_address")
            if student_email:
                recipients.append(student_email)
            
            if recipients:
                frappe.sendmail(
                    recipients=recipients,
                    subject=_("Payment Confirmation - {0}").format(self.student_name),
                    message=_("Payment of {0} {1} has been received for {2}.\n\nPayment Details:\nAmount: {3}\nDate: {4}\nMethod: {5}\nReference: {6}").format(
                        self.currency, self.paid_amount, self.student_name,
                        f"{self.currency} {self.paid_amount}",
                        self.payment_date,
                        self.payment_method,
                        self.reference_number or "N/A"
                    ),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
        
        except Exception as e:
            frappe.log_error(f"Failed to send payment confirmation: {str(e)}")
    
    @frappe.whitelist()
    def verify_payment(self, remarks=None):
        """Verify the payment."""
        if self.verification_status == "Verified":
            frappe.throw(_("Payment is already verified"))
        
        self.verification_status = "Verified"
        self.verified_by = frappe.session.user
        self.verification_date = now()
        
        if remarks:
            self.remarks = (self.remarks or "") + f"\nVerification: {remarks}"
        
        self.save()
        
        return True
    
    @frappe.whitelist()
    def reject_payment(self, reason=None):
        """Reject the payment."""
        if self.verification_status == "Rejected":
            frappe.throw(_("Payment is already rejected"))
        
        self.verification_status = "Rejected"
        self.status = "Failed"
        self.verified_by = frappe.session.user
        self.verification_date = now()
        
        if reason:
            self.remarks = (self.remarks or "") + f"\nRejection Reason: {reason}"
        
        self.save()
        
        return True
    
    @frappe.whitelist()
    def generate_receipt(self):
        """Generate payment receipt."""
        receipt_data = {
            "payment_entry": self.name,
            "student": self.student,
            "student_name": self.student_name,
            "payment_date": self.payment_date,
            "paid_amount": self.paid_amount,
            "currency": self.currency,
            "payment_method": self.payment_method,
            "reference_number": self.reference_number,
            "processed_by": self.processed_by,
            "components": []
        }
        
        if self.payment_components:
            for component in self.payment_components:
                receipt_data["components"].append({
                    "component_name": component.component_name,
                    "amount": component.amount,
                    "description": component.description
                })
        
        return receipt_data
    
    @frappe.whitelist()
    def get_payment_history(self):
        """Get payment history for this student."""
        payments = frappe.get_list("Payment Entry",
            filters={
                "student": self.student,
                "status": ["in", ["Verified", "Cleared"]]
            },
            fields=[
                "name", "payment_date", "paid_amount", "currency",
                "payment_method", "reference_number", "status"
            ],
            order_by="payment_date desc"
        )
        
        return payments
