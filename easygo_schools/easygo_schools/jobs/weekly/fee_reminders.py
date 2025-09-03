"""Weekly job for fee payment reminders."""

import frappe
from frappe import _
from frappe.utils import getdate, add_days


def execute():
    """Send weekly fee payment reminders."""
    today = getdate()
    
    # Get overdue fee bills
    overdue_bills = get_overdue_fee_bills()
    
    for bill in overdue_bills:
        send_overdue_reminder(bill)
    
    # Get bills due in next 7 days
    upcoming_bills = get_upcoming_fee_bills(today)
    
    for bill in upcoming_bills:
        send_upcoming_reminder(bill)


def get_overdue_fee_bills():
    """Get overdue fee bills."""
    return frappe.get_list("Fee Bill",
        filters={
            "status": ["in", ["Unpaid", "Partially Paid"]],
            "due_date": ["<", getdate()]
        },
        fields=["name", "student", "total_amount", "due_date", "outstanding_amount"]
    )


def get_upcoming_fee_bills(today):
    """Get fee bills due in next 7 days."""
    next_week = add_days(today, 7)
    
    return frappe.get_list("Fee Bill",
        filters={
            "status": "Unpaid",
            "due_date": ["between", [today, next_week]]
        },
        fields=["name", "student", "total_amount", "due_date"]
    )


def send_overdue_reminder(bill):
    """Send overdue payment reminder."""
    student = frappe.get_doc("Student", bill['student'])
    
    if not student.parent_email:
        return
    
    subject = _("Overdue Fee Payment - {0}").format(student.student_name)
    message = _("""
    Dear Parent,
    
    This is a reminder that the fee payment for {0} is overdue.
    
    Bill Number: {1}
    Due Date: {2}
    Outstanding Amount: {3} DH
    
    Please make the payment as soon as possible to avoid late fees.
    
    Best regards,
    School Finance Department
    """).format(
        student.student_name,
        bill['name'],
        bill['due_date'],
        bill.get('outstanding_amount', bill['total_amount'])
    )
    
    try:
        frappe.sendmail(
            recipients=[student.parent_email],
            subject=subject,
            message=message
        )
    except Exception as e:
        frappe.log_error(f"Failed to send overdue reminder: {str(e)}")


def send_upcoming_reminder(bill):
    """Send upcoming payment reminder."""
    student = frappe.get_doc("Student", bill['student'])
    
    if not student.parent_email:
        return
    
    subject = _("Fee Payment Due Soon - {0}").format(student.student_name)
    message = _("""
    Dear Parent,
    
    This is a friendly reminder that a fee payment for {0} is due soon.
    
    Bill Number: {1}
    Due Date: {2}
    Amount: {3} DH
    
    Please ensure payment is made before the due date.
    
    Best regards,
    School Finance Department
    """).format(
        student.student_name,
        bill['name'],
        bill['due_date'],
        bill['total_amount']
    )
    
    try:
        frappe.sendmail(
            recipients=[student.parent_email],
            subject=subject,
            message=message
        )
    except Exception as e:
        frappe.log_error(f"Failed to send upcoming reminder: {str(e)}")
