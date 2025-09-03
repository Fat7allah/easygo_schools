"""Monthly scheduled jobs for EasyGo Education."""

import frappe
from frappe import _
from frappe.utils import today, add_months, getdate, get_first_day, get_last_day
import csv
import os


def massar_exports():
    """Generate and export MASSAR data files."""
    try:
        # Get all active students
        students = frappe.db.sql("""
            SELECT 
                s.name,
                s.student_name,
                s.massar_code,
                s.date_of_birth,
                s.gender,
                s.school_class,
                s.guardian_name,
                s.guardian_phone,
                s.address,
                ay.name as academic_year
            FROM `tabStudent` s
            LEFT JOIN `tabAcademic Year` ay ON ay.is_default = 1
            WHERE s.status = 'Active'
            AND s.massar_code IS NOT NULL
            AND s.massar_code != ''
            ORDER BY s.school_class, s.student_name
        """, as_dict=True)
        
        if not students:
            print("No students with MASSAR codes found for export")
            return
        
        # Create export directory if it doesn't exist
        export_dir = frappe.get_site_path("private", "files", "massar_exports")
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
        
        # Generate filename with current date
        filename = f"massar_students_{today().replace('-', '_')}.csv"
        filepath = os.path.join(export_dir, filename)
        
        # Write CSV file
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'MASSAR_CODE', 'STUDENT_NAME', 'DATE_OF_BIRTH', 'GENDER',
                'CLASS', 'GUARDIAN_NAME', 'GUARDIAN_PHONE', 'ADDRESS', 'ACADEMIC_YEAR'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for student in students:
                writer.writerow({
                    'MASSAR_CODE': student.massar_code,
                    'STUDENT_NAME': student.student_name,
                    'DATE_OF_BIRTH': student.date_of_birth.strftime('%Y-%m-%d') if student.date_of_birth else '',
                    'GENDER': student.gender or '',
                    'CLASS': student.school_class or '',
                    'GUARDIAN_NAME': student.guardian_name or '',
                    'GUARDIAN_PHONE': student.guardian_phone or '',
                    'ADDRESS': student.address or '',
                    'ACADEMIC_YEAR': student.academic_year or ''
                })
        
        # Create a File document for tracking
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "file_url": f"/private/files/massar_exports/{filename}",
            "is_private": 1,
            "folder": "Home"
        })
        file_doc.insert(ignore_permissions=True)
        
        # Send notification to administrators
        admin_users = frappe.get_all(
            "Has Role",
            filters={"role": ["in", ["Director", "Principal"]]},
            fields=["parent"]
        )
        
        if admin_users:
            admin_emails = [frappe.db.get_value("User", user.parent, "email") 
                          for user in admin_users]
            admin_emails = [email for email in admin_emails if email]
            
            if admin_emails:
                frappe.sendmail(
                    recipients=admin_emails,
                    subject=_("Monthly MASSAR Export Generated"),
                    message=_("Dear Administrator,<br><br>The monthly MASSAR export has been generated successfully.<br><br>File: {0}<br>Students exported: {1}<br>Date: {2}<br><br>The file is available in the File Manager under private files.<br><br>Best regards,<br>EasyGo Education System").format(
                        filename, len(students), frappe.utils.formatdate(today())
                    )
                )
        
        frappe.db.commit()
        print(f"MASSAR export generated: {filename} with {len(students)} students")
        
    except Exception as e:
        frappe.log_error(f"Monthly MASSAR export failed: {str(e)}")


def payroll_checks():
    """Perform monthly payroll validation checks."""
    try:
        # Get current month's salary slips
        current_month_start = get_first_day(today())
        current_month_end = get_last_day(today())
        
        salary_slips = frappe.get_all(
            "Salary Slip",
            filters={
                "start_date": [">=", current_month_start],
                "end_date": ["<=", current_month_end],
                "docstatus": 1
            },
            fields=["name", "employee", "employee_name", "gross_pay", "net_pay"]
        )
        
        issues = []
        
        # Check for employees without salary slips
        active_employees = frappe.get_all(
            "Employee",
            filters={"status": "Active"},
            fields=["name", "employee_name", "company_email"]
        )
        
        employees_with_slips = [slip.employee for slip in salary_slips]
        missing_slips = [emp for emp in active_employees if emp.name not in employees_with_slips]
        
        if missing_slips:
            issues.append({
                "type": "Missing Salary Slips",
                "count": len(missing_slips),
                "details": [emp.employee_name for emp in missing_slips[:5]]  # Show first 5
            })
        
        # Check for unusual salary amounts (basic validation)
        for slip in salary_slips:
            if slip.net_pay <= 0:
                issues.append({
                    "type": "Zero/Negative Net Pay",
                    "count": 1,
                    "details": [f"{slip.employee_name}: {slip.net_pay} MAD"]
                })
            elif slip.gross_pay > 50000:  # Arbitrary high threshold
                issues.append({
                    "type": "Unusually High Gross Pay",
                    "count": 1,
                    "details": [f"{slip.employee_name}: {slip.gross_pay} MAD"]
                })
        
        # Send report to HR and administrators
        if issues or salary_slips:
            admin_users = frappe.get_all(
                "Has Role",
                filters={"role": ["in", ["HR Manager", "Director"]]},
                fields=["parent"]
            )
            
            if admin_users:
                admin_emails = [frappe.db.get_value("User", user.parent, "email") 
                              for user in admin_users]
                admin_emails = [email for email in admin_emails if email]
                
                if admin_emails:
                    report_content = f"<h3>Monthly Payroll Summary</h3>"
                    report_content += f"<p>Total Salary Slips Processed: {len(salary_slips)}</p>"
                    report_content += f"<p>Total Active Employees: {len(active_employees)}</p>"
                    
                    if issues:
                        report_content += "<h4>Issues Found:</h4><ul>"
                        for issue in issues:
                            report_content += f"<li><strong>{issue['type']}</strong>: {issue['count']} case(s)"
                            if issue['details']:
                                report_content += f" - {', '.join(issue['details'][:3])}"
                                if len(issue['details']) > 3:
                                    report_content += f" and {len(issue['details']) - 3} more"
                            report_content += "</li>"
                        report_content += "</ul>"
                    else:
                        report_content += "<p style='color: green;'>✓ No issues found in payroll data</p>"
                    
                    frappe.sendmail(
                        recipients=admin_emails,
                        subject=_("Monthly Payroll Check Report"),
                        message=report_content
                    )
        
        frappe.db.commit()
        print(f"Payroll checks completed: {len(salary_slips)} slips, {len(issues)} issues found")
        
    except Exception as e:
        frappe.log_error(f"Monthly payroll checks failed: {str(e)}")


def asset_rollup():
    """Generate monthly asset status rollup report."""
    try:
        # Get asset summary by category and status
        asset_summary = frappe.db.sql("""
            SELECT 
                asset_category,
                status,
                COUNT(*) as count,
                SUM(gross_purchase_amount) as total_value
            FROM `tabSchool Asset`
            GROUP BY asset_category, status
            ORDER BY asset_category, status
        """, as_dict=True)
        
        # Get maintenance summary
        maintenance_summary = frappe.db.sql("""
            SELECT 
                status,
                COUNT(*) as count
            FROM `tabMaintenance Request`
            WHERE MONTH(creation) = MONTH(CURDATE())
            AND YEAR(creation) = YEAR(CURDATE())
            GROUP BY status
        """, as_dict=True)
        
        # Send report to administrators
        admin_users = frappe.get_all(
            "Has Role",
            filters={"role": ["in", ["Director", "Maintenance"]]},
            fields=["parent"]
        )
        
        if admin_users:
            admin_emails = [frappe.db.get_value("User", user.parent, "email") 
                          for user in admin_users]
            admin_emails = [email for email in admin_emails if email]
            
            if admin_emails:
                report_content = "<h3>Monthly Asset Report</h3>"
                
                if asset_summary:
                    report_content += "<h4>Asset Summary by Category:</h4>"
                    report_content += "<table border='1' style='border-collapse: collapse; width: 100%;'>"
                    report_content += "<tr><th>Category</th><th>Status</th><th>Count</th><th>Total Value (MAD)</th></tr>"
                    
                    for asset in asset_summary:
                        report_content += f"<tr><td>{asset.asset_category or 'Uncategorized'}</td><td>{asset.status}</td><td>{asset.count}</td><td>{asset.total_value or 0:,.2f}</td></tr>"
                    
                    report_content += "</table><br>"
                
                if maintenance_summary:
                    report_content += "<h4>This Month's Maintenance Requests:</h4>"
                    report_content += "<table border='1' style='border-collapse: collapse; width: 100%;'>"
                    report_content += "<tr><th>Status</th><th>Count</th></tr>"
                    
                    for maintenance in maintenance_summary:
                        report_content += f"<tr><td>{maintenance.status}</td><td>{maintenance.count}</td></tr>"
                    
                    report_content += "</table>"
                
                frappe.sendmail(
                    recipients=admin_emails,
                    subject=_("Monthly Asset Report - {0}").format(frappe.utils.formatdate(today(), "MMMM yyyy")),
                    message=report_content
                )
        
        frappe.db.commit()
        print(f"Asset rollup completed: {len(asset_summary)} asset categories, {len(maintenance_summary)} maintenance statuses")
        
    except Exception as e:
        frappe.log_error(f"Monthly asset rollup failed: {str(e)}")


def run_all_monthly_jobs():
    """Run all monthly jobs."""
    print("Starting monthly jobs...")
    massar_exports()
    payroll_checks()
    asset_rollup()
    print("Monthly jobs completed")
