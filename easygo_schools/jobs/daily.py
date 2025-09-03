"""Daily scheduled jobs for EasyGo Education."""

import frappe
from frappe import _
from frappe.utils import today, add_days, getdate


def check_overdue_fees():
    """Check for overdue fee bills and send notifications."""
    try:
        # Get overdue fee bills
        overdue_bills = frappe.get_all(
            "Fee Bill",
            filters={
                "status": ["!=", "Paid"],
                "due_date": ["<", today()],
                "docstatus": 1
            },
            fields=["name", "student", "student_name", "guardian_email", "total_amount", "due_date"]
        )
        
        if not overdue_bills:
            return
            
        # Send notifications for overdue bills
        for bill in overdue_bills:
            try:
                if bill.guardian_email:
                    # Send email notification
                    frappe.sendmail(
                        recipients=[bill.guardian_email],
                        subject=_("Overdue Fee Payment - {0}").format(bill.student_name),
                        message=_("Dear Parent,<br><br>This is a reminder that the fee payment for {0} (Bill: {1}) was due on {2}. Please make the payment at your earliest convenience.<br><br>Amount Due: {3} MAD<br><br>Thank you.").format(
                            bill.student_name, bill.name, frappe.utils.formatdate(bill.due_date), bill.total_amount
                        )
                    )
                    
                # Log the notification
                frappe.get_doc({
                    "doctype": "Communication Log",
                    "reference_doctype": "Fee Bill",
                    "reference_name": bill.name,
                    "communication_type": "Email",
                    "subject": "Overdue Fee Reminder",
                    "status": "Sent"
                }).insert(ignore_permissions=True)
                
            except Exception as e:
                frappe.log_error(f"Failed to send overdue fee notification for {bill.name}: {str(e)}")
                
        frappe.db.commit()
        print(f"Processed {len(overdue_bills)} overdue fee notifications")
        
    except Exception as e:
        frappe.log_error(f"Daily overdue fees check failed: {str(e)}")


def maintenance_reminders():
    """Send maintenance reminders for scheduled work orders."""
    try:
        # Get maintenance requests due today or overdue
        due_maintenance = frappe.get_all(
            "Maintenance Request",
            filters={
                "status": ["in", ["Open", "In Progress"]],
                "scheduled_date": ["<=", today()]
            },
            fields=["name", "asset", "description", "assigned_to", "scheduled_date"]
        )
        
        if not due_maintenance:
            return
            
        # Group by assigned person
        assignments = {}
        for request in due_maintenance:
            if request.assigned_to:
                if request.assigned_to not in assignments:
                    assignments[request.assigned_to] = []
                assignments[request.assigned_to].append(request)
        
        # Send reminders
        for user, requests in assignments.items():
            try:
                user_email = frappe.db.get_value("User", user, "email")
                if user_email:
                    request_list = "<ul>"
                    for req in requests:
                        request_list += f"<li>{req.name}: {req.description} (Due: {frappe.utils.formatdate(req.scheduled_date)})</li>"
                    request_list += "</ul>"
                    
                    frappe.sendmail(
                        recipients=[user_email],
                        subject=_("Maintenance Reminders - {0} items").format(len(requests)),
                        message=_("Dear Team Member,<br><br>You have {0} maintenance requests that are due or overdue:<br><br>{1}<br><br>Please update the status accordingly.<br><br>Thank you.").format(
                            len(requests), request_list
                        )
                    )
                    
            except Exception as e:
                frappe.log_error(f"Failed to send maintenance reminder to {user}: {str(e)}")
                
        frappe.db.commit()
        print(f"Sent maintenance reminders to {len(assignments)} users")
        
    except Exception as e:
        frappe.log_error(f"Daily maintenance reminders failed: {str(e)}")


def attendance_anomalies():
    """Check for attendance anomalies and alert administrators."""
    try:
        # Get students with consecutive absences (3+ days)
        from frappe.utils import add_days
        
        three_days_ago = add_days(today(), -3)
        
        # This is a simplified check - in a real implementation, 
        # we'd need more sophisticated logic
        anomalies = frappe.db.sql("""
            SELECT student, student_name, COUNT(*) as consecutive_absences
            FROM `tabStudent Attendance`
            WHERE status = 'Absent'
            AND attendance_date >= %s
            AND attendance_date <= %s
            GROUP BY student
            HAVING COUNT(*) >= 3
        """, (three_days_ago, today()), as_dict=True)
        
        if not anomalies:
            return
            
        # Send alert to administrators
        admin_users = frappe.get_all(
            "Has Role",
            filters={"role": "Principal"},
            fields=["parent"]
        )
        
        if admin_users:
            admin_emails = [frappe.db.get_value("User", user.parent, "email") 
                          for user in admin_users]
            admin_emails = [email for email in admin_emails if email]
            
            if admin_emails:
                anomaly_list = "<ul>"
                for anomaly in anomalies:
                    anomaly_list += f"<li>{anomaly.student_name} ({anomaly.student}): {anomaly.consecutive_absences} consecutive absences</li>"
                anomaly_list += "</ul>"
                
                frappe.sendmail(
                    recipients=admin_emails,
                    subject=_("Attendance Anomalies Alert - {0} students").format(len(anomalies)),
                    message=_("Dear Administrator,<br><br>The following students have consecutive absences that may require attention:<br><br>{0}<br><br>Please review and take appropriate action.<br><br>Best regards,<br>EasyGo Education System").format(anomaly_list)
                )
                
        frappe.db.commit()
        print(f"Sent attendance anomaly alerts for {len(anomalies)} students")
        
    except Exception as e:
        frappe.log_error(f"Daily attendance anomalies check failed: {str(e)}")


def run_all_daily_jobs():
    """Run all daily jobs."""
    print("Starting daily jobs...")
    check_overdue_fees()
    maintenance_reminders()
    attendance_anomalies()
    print("Daily jobs completed")
