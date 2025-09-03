"""Weekly scheduled jobs for EasyGo Education."""

import frappe
from frappe import _
from frappe.utils import today, add_days, getdate


def attendance_summaries():
    """Generate weekly attendance summaries for teachers and parents."""
    try:
        from frappe.utils import get_first_day_of_week, get_last_day_of_week
        
        # Get current week dates
        week_start = get_first_day_of_week(today())
        week_end = get_last_day_of_week(today())
        
        # Get all active classes
        classes = frappe.get_all("School Class", filters={"is_active": 1}, fields=["name", "class_teacher"])
        
        for class_doc in classes:
            try:
                # Get attendance summary for this class
                attendance_data = frappe.db.sql("""
                    SELECT 
                        student,
                        student_name,
                        COUNT(*) as total_days,
                        SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days,
                        SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
                        SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late_days
                    FROM `tabStudent Attendance`
                    WHERE school_class = %s
                    AND attendance_date BETWEEN %s AND %s
                    GROUP BY student, student_name
                """, (class_doc.name, week_start, week_end), as_dict=True)
                
                if not attendance_data:
                    continue
                
                # Send summary to class teacher
                if class_doc.class_teacher:
                    teacher_email = frappe.db.get_value("Employee", class_doc.class_teacher, "company_email")
                    if teacher_email:
                        summary_table = "<table border='1' style='border-collapse: collapse; width: 100%;'>"
                        summary_table += "<tr><th>Student</th><th>Present</th><th>Absent</th><th>Late</th><th>Attendance %</th></tr>"
                        
                        for student in attendance_data:
                            attendance_pct = (student.present_days / student.total_days * 100) if student.total_days > 0 else 0
                            summary_table += f"<tr><td>{student.student_name}</td><td>{student.present_days}</td><td>{student.absent_days}</td><td>{student.late_days}</td><td>{attendance_pct:.1f}%</td></tr>"
                        
                        summary_table += "</table>"
                        
                        frappe.sendmail(
                            recipients=[teacher_email],
                            subject=_("Weekly Attendance Summary - {0}").format(class_doc.name),
                            message=_("Dear Teacher,<br><br>Here is the weekly attendance summary for class {0} ({1} to {2}):<br><br>{3}<br><br>Best regards,<br>EasyGo Education System").format(
                                class_doc.name, frappe.utils.formatdate(week_start), frappe.utils.formatdate(week_end), summary_table
                            )
                        )
                
                # Send individual summaries to parents
                for student in attendance_data:
                    guardian_email = frappe.db.get_value("Student", student.student, "guardian_email")
                    if guardian_email and student.absent_days > 0:  # Only send if there are absences
                        attendance_pct = (student.present_days / student.total_days * 100) if student.total_days > 0 else 0
                        
                        frappe.sendmail(
                            recipients=[guardian_email],
                            subject=_("Weekly Attendance Report - {0}").format(student.student_name),
                            message=_("Dear Parent,<br><br>Weekly attendance report for {0} ({1} to {2}):<br><br>Present: {3} days<br>Absent: {4} days<br>Late: {5} days<br>Attendance Rate: {6:.1f}%<br><br>Please contact the school if you have any questions.<br><br>Best regards,<br>EasyGo Education System").format(
                                student.student_name, frappe.utils.formatdate(week_start), frappe.utils.formatdate(week_end),
                                student.present_days, student.absent_days, student.late_days, attendance_pct
                            )
                        )
                        
            except Exception as e:
                frappe.log_error(f"Failed to generate attendance summary for class {class_doc.name}: {str(e)}")
        
        frappe.db.commit()
        print(f"Generated weekly attendance summaries for {len(classes)} classes")
        
    except Exception as e:
        frappe.log_error(f"Weekly attendance summaries failed: {str(e)}")


def teacher_load_analysis():
    """Analyze teacher workload and send alerts for overloaded teachers."""
    try:
        # Get all active teachers
        teachers = frappe.get_all(
            "Employee",
            filters={"status": "Active", "department": "Teaching"},
            fields=["name", "employee_name", "company_email"]
        )
        
        overloaded_teachers = []
        
        for teacher in teachers:
            try:
                # Count scheduled classes for this week
                weekly_hours = frappe.db.sql("""
                    SELECT COUNT(*) * duration_minutes / 60.0 as total_hours
                    FROM `tabCourse Schedule`
                    WHERE instructor = %s
                    AND is_active = 1
                """, teacher.name)[0][0] or 0
                
                # Count assigned classes
                assigned_classes = frappe.db.count("School Class", {"class_teacher": teacher.name})
                
                # Simple overload check (more than 25 hours per week or more than 3 classes)
                if weekly_hours > 25 or assigned_classes > 3:
                    overloaded_teachers.append({
                        "name": teacher.employee_name,
                        "email": teacher.company_email,
                        "weekly_hours": weekly_hours,
                        "assigned_classes": assigned_classes
                    })
                    
            except Exception as e:
                frappe.log_error(f"Failed to analyze load for teacher {teacher.name}: {str(e)}")
        
        # Send alert to administrators if there are overloaded teachers
        if overloaded_teachers:
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
                    teacher_list = "<ul>"
                    for teacher in overloaded_teachers:
                        teacher_list += f"<li>{teacher['name']}: {teacher['weekly_hours']:.1f} hours/week, {teacher['assigned_classes']} classes</li>"
                    teacher_list += "</ul>"
                    
                    frappe.sendmail(
                        recipients=admin_emails,
                        subject=_("Teacher Workload Alert - {0} overloaded teachers").format(len(overloaded_teachers)),
                        message=_("Dear Administrator,<br><br>The following teachers may be overloaded:<br><br>{0}<br><br>Please review their schedules and consider redistributing workload.<br><br>Best regards,<br>EasyGo Education System").format(teacher_list)
                    )
        
        frappe.db.commit()
        print(f"Analyzed teacher load for {len(teachers)} teachers, found {len(overloaded_teachers)} overloaded")
        
    except Exception as e:
        frappe.log_error(f"Weekly teacher load analysis failed: {str(e)}")


def budget_burn_rate():
    """Analyze budget burn rate and send alerts."""
    try:
        # Get current fiscal year
        current_year = frappe.db.get_single_value("Finance Settings", "fiscal_year_start_date")
        if not current_year:
            return
            
        # Get all active budgets
        budgets = frappe.get_all(
            "Budget",
            filters={"fiscal_year": current_year, "is_active": 1},
            fields=["name", "total_budget", "department"]
        )
        
        budget_alerts = []
        
        for budget in budgets:
            try:
                # Calculate actual expenses
                actual_expenses = frappe.db.sql("""
                    SELECT COALESCE(SUM(amount), 0) as total_spent
                    FROM `tabExpense Entry`
                    WHERE budget = %s
                    AND docstatus = 1
                """, budget.name)[0][0] or 0
                
                # Calculate burn rate
                if budget.total_budget > 0:
                    burn_rate = (actual_expenses / budget.total_budget) * 100
                    
                    # Alert if burn rate is over 80%
                    if burn_rate > 80:
                        budget_alerts.append({
                            "name": budget.name,
                            "department": budget.department,
                            "budget": budget.total_budget,
                            "spent": actual_expenses,
                            "burn_rate": burn_rate
                        })
                        
            except Exception as e:
                frappe.log_error(f"Failed to analyze budget {budget.name}: {str(e)}")
        
        # Send alerts if needed
        if budget_alerts:
            admin_users = frappe.get_all(
                "Has Role",
                filters={"role": ["in", ["Director", "Accountant"]]},
                fields=["parent"]
            )
            
            if admin_users:
                admin_emails = [frappe.db.get_value("User", user.parent, "email") 
                              for user in admin_users]
                admin_emails = [email for email in admin_emails if email]
                
                if admin_emails:
                    budget_list = "<ul>"
                    for budget in budget_alerts:
                        budget_list += f"<li>{budget['name']} ({budget['department']}): {budget['burn_rate']:.1f}% spent ({budget['spent']:.2f} / {budget['budget']:.2f} MAD)</li>"
                    budget_list += "</ul>"
                    
                    frappe.sendmail(
                        recipients=admin_emails,
                        subject=_("Budget Alert - {0} budgets over 80%").format(len(budget_alerts)),
                        message=_("Dear Administrator,<br><br>The following budgets have high burn rates:<br><br>{0}<br><br>Please review and take appropriate action.<br><br>Best regards,<br>EasyGo Education System").format(budget_list)
                    )
        
        frappe.db.commit()
        print(f"Analyzed {len(budgets)} budgets, found {len(budget_alerts)} with high burn rates")
        
    except Exception as e:
        frappe.log_error(f"Weekly budget burn rate analysis failed: {str(e)}")


def run_all_weekly_jobs():
    """Run all weekly jobs."""
    print("Starting weekly jobs...")
    attendance_summaries()
    teacher_load_analysis()
    budget_burn_rate()
    print("Weekly jobs completed")
