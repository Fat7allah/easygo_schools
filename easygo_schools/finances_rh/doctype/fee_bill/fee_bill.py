"""Fee Bill doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, add_days, flt


class FeeBill(Document):
    """Fee Bill doctype controller with business rules."""
    
    def validate(self):
        """Validate fee bill data."""
        self.validate_dates()
        self.fetch_student_details()
        self.calculate_totals()
        self.update_status()
    
    def validate_dates(self):
        """Validate posting and due dates."""
        if self.posting_date and self.due_date:
            if getdate(self.due_date) < getdate(self.posting_date):
                frappe.throw(_("Due Date cannot be before Posting Date"))
    
    def fetch_student_details(self):
        """Fetch student details when student is selected."""
        if self.student:
            student = frappe.get_doc("Student", self.student)
            self.student_name = student.student_name
            self.school_class = student.school_class
            self.massar_code = student.massar_code
            self.guardian_name = student.guardian_name
            self.guardian_phone = student.guardian_phone
            self.guardian_email = student.guardian_email
    
    def calculate_totals(self):
        """Calculate total amounts."""
        total = 0
        for item in self.fee_items:
            if item.amount:
                total += flt(item.amount)
        
        self.total_amount = total
        self.outstanding_amount = flt(self.total_amount) - flt(self.paid_amount)
    
    def update_status(self):
        """Update payment status based on amounts."""
        if self.docstatus == 1:  # Submitted
            if flt(self.outstanding_amount) <= 0:
                self.status = "Paid"
                self.payment_status = "Fully Paid"
            elif flt(self.paid_amount) > 0:
                self.status = "Partially Paid"
                self.payment_status = "Partially Paid"
            elif getdate(self.due_date) < getdate():
                self.status = "Overdue"
                self.payment_status = "Overdue"
            else:
                self.status = "Submitted"
                self.payment_status = "Pending"
        else:
            self.status = "Draft"
            self.payment_status = "Draft"
    
    def before_submit(self):
        """Actions before submitting the fee bill."""
        self.freeze_totals()
        self.validate_fee_items()
    
    def freeze_totals(self):
        """Freeze totals before submission."""
        self.calculate_totals()
        if not self.due_date:
            # Set default due date to 30 days from posting date
            payment_terms = frappe.db.get_single_value("Finance Settings", "default_payment_terms") or 30
            self.due_date = add_days(self.posting_date, payment_terms)
    
    def validate_fee_items(self):
        """Validate fee items before submission."""
        if not self.fee_items:
            frappe.throw(_("Fee Items are required"))
        
        for item in self.fee_items:
            if not item.fee_type or not item.amount:
                frappe.throw(_("Fee Type and Amount are required for all items"))
    
    def on_submit(self):
        """Actions after submitting the fee bill."""
        self.create_ledger_entry()
        self.send_bill_notification()
    
    def create_ledger_entry(self):
        """Create school ledger entry for receivables."""
        try:
            ledger_entry = frappe.get_doc({
                "doctype": "School Ledger",
                "posting_date": self.posting_date,
                "account": "Student Fees Receivable",
                "student": self.student,
                "reference_type": "Fee Bill",
                "reference_name": self.name,
                "debit_amount": self.total_amount,
                "credit_amount": 0,
                "description": f"Fee bill {self.name} for {self.student_name}"
            })
            ledger_entry.insert(ignore_permissions=True)
            ledger_entry.submit()
            
        except Exception as e:
            frappe.log_error(f"Failed to create ledger entry for fee bill {self.name}: {str(e)}")
    
    def send_bill_notification(self):
        """Send bill notification to guardian."""
        if not self.guardian_email:
            return
            
        try:
            school_name = frappe.db.get_single_value("School Settings", "school_name") or "School"
            
            frappe.sendmail(
                recipients=[self.guardian_email],
                subject=_("Fee Bill Generated - {0}").format(self.student_name),
                message=_("""
                <p>Dear {0},</p>
                
                <p>A new fee bill has been generated for {1}.</p>
                
                <p><strong>Bill Details:</strong></p>
                <ul>
                    <li>Bill Number: {2}</li>
                    <li>Amount: {3} MAD</li>
                    <li>Due Date: {4}</li>
                </ul>
                
                <p>Please make the payment by the due date to avoid late fees.</p>
                
                <p>You can view and pay this bill through the parent portal.</p>
                
                <p>Best regards,<br>
                {5} Administration</p>
                """).format(
                    self.guardian_name or "Guardian",
                    self.student_name,
                    self.name,
                    self.total_amount,
                    frappe.utils.formatdate(self.due_date),
                    school_name
                )
            )
            
        except Exception as e:
            frappe.log_error(f"Failed to send bill notification for {self.name}: {str(e)}")
    
    def on_cancel(self):
        """Actions when fee bill is cancelled."""
        # Cancel related ledger entries
        ledger_entries = frappe.get_all(
            "School Ledger",
            filters={"reference_type": "Fee Bill", "reference_name": self.name},
            fields=["name"]
        )
        
        for entry in ledger_entries:
            ledger_doc = frappe.get_doc("School Ledger", entry.name)
            if ledger_doc.docstatus == 1:
                ledger_doc.cancel()


def freeze_totals(doc, method):
    """Hook function to freeze totals before submission."""
    # This is called from hooks.py
    pass


def create_ledger_entry(doc, method):
    """Hook function to create ledger entry on submission."""
    # This is called from hooks.py - the actual logic is in on_submit
    pass
