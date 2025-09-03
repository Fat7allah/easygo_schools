"""Installment Plan DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, add_months, add_days, flt, cint


class InstallmentPlan(Document):
    """Installment Plan management."""
    
    def validate(self):
        """Validate installment plan data."""
        self.validate_dates()
        self.validate_amounts()
        self.calculate_installments()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate start date and installment dates."""
        if self.start_date and self.start_date < getdate():
            frappe.throw(_("Start date cannot be in the past"))
    
    def validate_amounts(self):
        """Validate fee amounts and discounts."""
        if self.total_fee_amount <= 0:
            frappe.throw(_("Total fee amount must be greater than zero"))
        
        if self.number_of_installments <= 0:
            frappe.throw(_("Number of installments must be greater than zero"))
        
        if self.discount_percentage and (self.discount_percentage < 0 or self.discount_percentage > 100):
            frappe.throw(_("Discount percentage must be between 0 and 100"))
        
        if self.late_fee_percentage and self.late_fee_percentage < 0:
            frappe.throw(_("Late fee percentage cannot be negative"))
    
    def calculate_installments(self):
        """Calculate installment schedule."""
        if not self.installments or len(self.installments) != self.number_of_installments:
            self.installments = []
            
            # Calculate discount
            discount_amount = 0
            if self.discount_percentage:
                discount_amount = flt(self.total_fee_amount) * flt(self.discount_percentage) / 100
            elif self.discount_amount:
                discount_amount = flt(self.discount_amount)
            
            self.discount_amount = discount_amount
            net_amount = flt(self.total_fee_amount) - discount_amount
            
            # Calculate installment amount
            installment_amount = net_amount / cint(self.number_of_installments)
            
            # Generate installment schedule
            current_date = getdate(self.start_date)
            
            for i in range(cint(self.number_of_installments)):
                due_date = self.get_next_due_date(current_date, i)
                
                self.append("installments", {
                    "installment_number": i + 1,
                    "due_date": due_date,
                    "amount": installment_amount,
                    "status": "Pending",
                    "late_fee": 0,
                    "paid_amount": 0
                })
    
    def get_next_due_date(self, start_date, installment_index):
        """Get next due date based on frequency."""
        if self.installment_frequency == "Monthly":
            return add_months(start_date, installment_index)
        elif self.installment_frequency == "Quarterly":
            return add_months(start_date, installment_index * 3)
        elif self.installment_frequency == "Semi-Annual":
            return add_months(start_date, installment_index * 6)
        else:  # Custom
            return add_months(start_date, installment_index)
    
    def set_defaults(self):
        """Set default values."""
        if not self.academic_year:
            self.academic_year = frappe.db.get_single_value("School Settings", "current_academic_year")
        
        if not self.installment_frequency:
            self.installment_frequency = "Monthly"
        
        if not self.grace_period_days:
            self.grace_period_days = 7
    
    def on_submit(self):
        """Actions on submit."""
        self.status = "Active"
        self.approved_by = frappe.session.user
        self.approval_date = getdate()
        
        # Create fee bills for each installment
        self.create_fee_bills()
        
        # Send notification to guardian
        self.send_installment_plan_notification()
    
    def create_fee_bills(self):
        """Create fee bills for each installment."""
        for installment in self.installments:
            fee_bill = frappe.get_doc({
                "doctype": "Fee Bill",
                "student": self.student,
                "academic_year": self.academic_year,
                "installment_plan": self.name,
                "installment_number": installment.installment_number,
                "due_date": installment.due_date,
                "total_amount": installment.amount,
                "status": "Unpaid",
                "bill_type": "Installment"
            })
            
            fee_bill.insert(ignore_permissions=True)
            installment.fee_bill = fee_bill.name
    
    def send_installment_plan_notification(self):
        """Send installment plan notification to guardian."""
        student = frappe.get_doc("Student", self.student)
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            
            if guardian.email_address:
                frappe.sendmail(
                    recipients=[guardian.email_address],
                    subject=_("Installment Plan Approved - {0}").format(self.student_name),
                    message=self.get_installment_plan_message(),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
            
            if guardian.mobile_number:
                self.send_installment_plan_sms(guardian.mobile_number)
    
    def send_installment_plan_sms(self, mobile_number):
        """Send SMS notification."""
        message = _("Installment plan approved for {0}. {1} installments of {2} each. First due: {3}").format(
            self.student_name,
            self.number_of_installments,
            frappe.format_value(self.installments[0].amount, "Currency"),
            frappe.format(self.installments[0].due_date, "Date")
        )
        
        # Use SMS adapter
        from easygo_education.finances_rh.adapters.sms import send_sms
        send_sms(mobile_number, message)
    
    def get_installment_plan_message(self):
        """Get installment plan email message."""
        installment_schedule = "\n".join([
            f"Installment {inst.installment_number}: {frappe.format_value(inst.amount, 'Currency')} due on {frappe.format(inst.due_date, 'Date')}"
            for inst in self.installments
        ])
        
        return _("""
        Dear Parent/Guardian,
        
        The installment plan for {student_name} has been approved.
        
        Plan Details:
        - Academic Year: {academic_year}
        - Total Fee Amount: {total_amount}
        - Discount Applied: {discount}
        - Number of Installments: {installments}
        - Frequency: {frequency}
        - Late Fee: {late_fee}% after {grace_period} days
        
        Installment Schedule:
        {schedule}
        
        Please ensure timely payments to avoid late fees.
        
        Finance Office
        """).format(
            student_name=self.student_name,
            academic_year=self.academic_year,
            total_amount=frappe.format_value(self.total_fee_amount, "Currency"),
            discount=frappe.format_value(self.discount_amount, "Currency") if self.discount_amount else "None",
            installments=self.number_of_installments,
            frequency=self.installment_frequency,
            late_fee=self.late_fee_percentage or 0,
            grace_period=self.grace_period_days,
            schedule=installment_schedule
        )
    
    @frappe.whitelist()
    def mark_installment_paid(self, installment_number, paid_amount, payment_date=None, payment_reference=None):
        """Mark an installment as paid."""
        installment = None
        for inst in self.installments:
            if inst.installment_number == cint(installment_number):
                installment = inst
                break
        
        if not installment:
            frappe.throw(_("Installment {0} not found").format(installment_number))
        
        if installment.status == "Paid":
            frappe.throw(_("Installment {0} is already paid").format(installment_number))
        
        payment_date = payment_date or getdate()
        paid_amount = flt(paid_amount)
        
        # Calculate late fee if applicable
        late_fee = 0
        if payment_date > add_days(installment.due_date, self.grace_period_days):
            if self.late_fee_percentage:
                late_fee = flt(installment.amount) * flt(self.late_fee_percentage) / 100
        
        installment.paid_amount = paid_amount
        installment.payment_date = payment_date
        installment.payment_reference = payment_reference
        installment.late_fee = late_fee
        installment.status = "Paid" if paid_amount >= (installment.amount + late_fee) else "Partial"
        
        # Update fee bill
        if installment.fee_bill:
            fee_bill = frappe.get_doc("Fee Bill", installment.fee_bill)
            fee_bill.paid_amount = paid_amount
            fee_bill.payment_date = payment_date
            fee_bill.late_fee = late_fee
            fee_bill.status = "Paid" if paid_amount >= (fee_bill.total_amount + late_fee) else "Partial"
            fee_bill.save()
        
        self.save()
        
        # Check if plan is completed
        self.check_plan_completion()
        
        frappe.msgprint(_("Installment {0} marked as {1}").format(installment_number, installment.status))
        return self
    
    def check_plan_completion(self):
        """Check if installment plan is completed."""
        all_paid = all(inst.status == "Paid" for inst in self.installments)
        
        if all_paid and self.status != "Completed":
            self.status = "Completed"
            self.save()
            
            # Send completion notification
            self.send_completion_notification()
    
    def send_completion_notification(self):
        """Send plan completion notification."""
        student = frappe.get_doc("Student", self.student)
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            
            if guardian.email_address:
                frappe.sendmail(
                    recipients=[guardian.email_address],
                    subject=_("Installment Plan Completed - {0}").format(self.student_name),
                    message=self.get_completion_message(),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
    
    def get_completion_message(self):
        """Get completion message."""
        return _("""
        Dear Parent/Guardian,
        
        We are pleased to inform you that the installment plan for {student_name} has been completed successfully.
        
        All {installments} installments have been paid in full.
        
        Thank you for your timely payments throughout the academic year.
        
        Finance Office
        """).format(
            student_name=self.student_name,
            installments=self.number_of_installments
        )
    
    @frappe.whitelist()
    def get_payment_status(self):
        """Get payment status summary."""
        total_paid = sum(flt(inst.paid_amount) for inst in self.installments)
        total_due = sum(flt(inst.amount) for inst in self.installments)
        total_late_fees = sum(flt(inst.late_fee) for inst in self.installments)
        
        pending_installments = [inst for inst in self.installments if inst.status == "Pending"]
        overdue_installments = [inst for inst in self.installments 
                              if inst.status == "Pending" and inst.due_date < getdate()]
        
        return {
            "plan_name": self.name,
            "student": self.student_name,
            "total_fee_amount": self.total_fee_amount,
            "discount_amount": self.discount_amount,
            "net_amount": total_due,
            "total_paid": total_paid,
            "total_late_fees": total_late_fees,
            "balance_due": total_due - total_paid + total_late_fees,
            "pending_installments": len(pending_installments),
            "overdue_installments": len(overdue_installments),
            "completion_percentage": (total_paid / total_due * 100) if total_due else 0,
            "status": self.status,
            "next_due_date": pending_installments[0].due_date if pending_installments else None,
            "next_due_amount": pending_installments[0].amount if pending_installments else 0
        }
    
    @frappe.whitelist()
    def send_payment_reminder(self, installment_number=None):
        """Send payment reminder for overdue installments."""
        installments_to_remind = []
        
        if installment_number:
            installment = next((inst for inst in self.installments 
                              if inst.installment_number == cint(installment_number)), None)
            if installment and installment.status == "Pending":
                installments_to_remind.append(installment)
        else:
            # Send reminder for all overdue installments
            installments_to_remind = [inst for inst in self.installments 
                                    if inst.status == "Pending" and inst.due_date < getdate()]
        
        if not installments_to_remind:
            frappe.msgprint(_("No overdue installments found"))
            return
        
        student = frappe.get_doc("Student", self.student)
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            
            if guardian.email_address:
                frappe.sendmail(
                    recipients=[guardian.email_address],
                    subject=_("Payment Reminder - {0}").format(self.student_name),
                    message=self.get_payment_reminder_message(installments_to_remind),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
            
            if guardian.mobile_number:
                self.send_payment_reminder_sms(guardian.mobile_number, installments_to_remind)
        
        frappe.msgprint(_("Payment reminders sent successfully"))
        return self
    
    def get_payment_reminder_message(self, overdue_installments):
        """Get payment reminder message."""
        overdue_details = "\n".join([
            f"Installment {inst.installment_number}: {frappe.format_value(inst.amount, 'Currency')} (Due: {frappe.format(inst.due_date, 'Date')})"
            for inst in overdue_installments
        ])
        
        total_overdue = sum(flt(inst.amount) for inst in overdue_installments)
        
        return _("""
        Dear Parent/Guardian,
        
        This is a reminder that the following installments for {student_name} are overdue:
        
        {overdue_details}
        
        Total Overdue Amount: {total_overdue}
        
        Please make the payment at your earliest convenience to avoid late fees.
        
        Late Fee: {late_fee}% will be applied after {grace_period} days from due date.
        
        Finance Office
        """).format(
            student_name=self.student_name,
            overdue_details=overdue_details,
            total_overdue=frappe.format_value(total_overdue, "Currency"),
            late_fee=self.late_fee_percentage or 0,
            grace_period=self.grace_period_days
        )
    
    def send_payment_reminder_sms(self, mobile_number, overdue_installments):
        """Send SMS payment reminder."""
        total_overdue = sum(flt(inst.amount) for inst in overdue_installments)
        
        message = _("Payment reminder: {0} has {1} overdue installments totaling {2}. Please pay to avoid late fees.").format(
            self.student_name,
            len(overdue_installments),
            frappe.format_value(total_overdue, "Currency")
        )
        
        # Use SMS adapter
        from easygo_education.finances_rh.adapters.sms import send_sms
        send_sms(mobile_number, message)
    
    @frappe.whitelist()
    def modify_installment_plan(self, new_installments, reason):
        """Modify existing installment plan."""
        if self.status not in ["Active", "Pending Approval"]:
            frappe.throw(_("Cannot modify installment plan in {0} status").format(self.status))
        
        # Create modification log
        modification_log = frappe.get_doc({
            "doctype": "Installment Plan Modification",
            "installment_plan": self.name,
            "modification_date": getdate(),
            "modified_by": frappe.session.user,
            "reason": reason,
            "old_installments": len(self.installments),
            "new_installments": new_installments
        })
        
        modification_log.insert()
        
        # Update plan
        self.number_of_installments = new_installments
        self.calculate_installments()
        self.save()
        
        # Recreate fee bills
        self.recreate_fee_bills()
        
        frappe.msgprint(_("Installment plan modified successfully"))
        return self
    
    def recreate_fee_bills(self):
        """Recreate fee bills after modification."""
        # Cancel existing unpaid fee bills
        existing_bills = frappe.get_all("Fee Bill",
            filters={"installment_plan": self.name, "status": ["!=", "Paid"]},
            fields=["name"]
        )
        
        for bill in existing_bills:
            bill_doc = frappe.get_doc("Fee Bill", bill.name)
            bill_doc.cancel()
        
        # Create new fee bills
        self.create_fee_bills()
    
    def get_installment_plan_summary(self):
        """Get installment plan summary for reporting."""
        payment_status = self.get_payment_status()
        
        return {
            "plan_name": self.name,
            "student": self.student_name,
            "academic_year": self.academic_year,
            "total_fee_amount": self.total_fee_amount,
            "discount_amount": self.discount_amount,
            "number_of_installments": self.number_of_installments,
            "installment_frequency": self.installment_frequency,
            "status": self.status,
            "completion_percentage": payment_status["completion_percentage"],
            "total_paid": payment_status["total_paid"],
            "balance_due": payment_status["balance_due"],
            "overdue_installments": payment_status["overdue_installments"],
            "approved_by": self.approved_by,
            "approval_date": self.approval_date
        }
