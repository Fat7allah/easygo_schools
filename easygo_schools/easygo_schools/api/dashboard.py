"""Dashboard API methods for custom metrics."""

import frappe
from frappe import _
from frappe.utils import today, getdate, add_days


@frappe.whitelist()
def get_attendance_rate():
    """Get current month attendance rate."""
    try:
        # Get first day of current month
        today_date = getdate(today())
        month_start = today_date.replace(day=1)
        
        # Get attendance data for current month
        attendance_data = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_records,
                SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END) as present_count
            FROM `tabStudent Attendance`
            WHERE attendance_date >= %s AND attendance_date <= %s
        """, (month_start, today_date), as_dict=True)
        
        if attendance_data and attendance_data[0].total_records > 0:
            rate = (attendance_data[0].present_count / attendance_data[0].total_records) * 100
            return f"{rate:.1f}%"
        
        return "0%"
        
    except Exception as e:
        frappe.log_error(f"Error calculating attendance rate: {str(e)}")
        return "N/A"


@frappe.whitelist()
def get_teacher_student_count():
    """Get count of students taught by current teacher."""
    try:
        teacher_user = frappe.session.user
        
        # Get employee record for current user
        employee = frappe.db.get_value("Employee", {"user_id": teacher_user}, "name")
        if not employee:
            return 0
        
        # Get unique students from course schedules
        students = frappe.db.sql("""
            SELECT DISTINCT s.name
            FROM `tabStudent` s
            INNER JOIN `tabCourse Schedule` cs ON s.school_class = cs.school_class
            WHERE cs.instructor = %s AND cs.is_active = 1 AND s.status = 'Active'
        """, (employee,))
        
        return len(students)
        
    except Exception as e:
        frappe.log_error(f"Error getting teacher student count: {str(e)}")
        return 0


@frappe.whitelist()
def get_today_classes_count():
    """Get count of classes scheduled for today."""
    try:
        teacher_user = frappe.session.user
        
        # Get employee record for current user
        employee = frappe.db.get_value("Employee", {"user_id": teacher_user}, "name")
        if not employee:
            return 0
        
        # Get today's day of week
        today_date = getdate(today())
        day_name = today_date.strftime("%A")
        
        # Get classes scheduled for today
        classes = frappe.db.count("Course Schedule", {
            "instructor": employee,
            "day_of_week": day_name,
            "is_active": 1
        })
        
        return classes
        
    except Exception as e:
        frappe.log_error(f"Error getting today's classes count: {str(e)}")
        return 0


@frappe.whitelist()
def get_dashboard_summary():
    """Get comprehensive dashboard summary for Education Manager."""
    try:
        summary = {}
        
        # Student statistics
        summary["total_students"] = frappe.db.count("Student", {"status": "Active"})
        summary["total_classes"] = frappe.db.count("School Class", {"is_active": 1})
        summary["total_teachers"] = frappe.db.count("Employee", {
            "status": "Active",
            "designation": ["like", "%Teacher%"]
        })
        
        # Financial statistics
        fee_data = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_bills,
                SUM(total_amount) as total_amount,
                SUM(paid_amount) as paid_amount,
                SUM(outstanding_amount) as outstanding_amount
            FROM `tabFee Bill`
            WHERE docstatus = 1
        """, as_dict=True)
        
        if fee_data:
            summary["total_fee_bills"] = fee_data[0].total_bills
            summary["total_fee_amount"] = fee_data[0].total_amount or 0
            summary["total_collected"] = fee_data[0].paid_amount or 0
            summary["total_outstanding"] = fee_data[0].outstanding_amount or 0
            
            if summary["total_fee_amount"] > 0:
                summary["collection_rate"] = (summary["total_collected"] / summary["total_fee_amount"]) * 100
            else:
                summary["collection_rate"] = 0
        
        # Attendance statistics
        attendance_rate = get_attendance_rate()
        summary["attendance_rate"] = attendance_rate
        
        # Academic statistics
        summary["total_subjects"] = frappe.db.count("Subject", {"is_active": 1})
        summary["total_assessments"] = frappe.db.count("Assessment", {"status": "Active"})
        summary["pending_grades"] = frappe.db.count("Grade", {"docstatus": 0})
        
        # Communication statistics
        summary["pending_meetings"] = frappe.db.count("Meeting Request", {"status": "Pending"})
        summary["total_communications"] = frappe.db.count("Communication Log", {"status": "Sent"})
        
        return summary
        
    except Exception as e:
        frappe.log_error(f"Error getting dashboard summary: {str(e)}")
        return {}


@frappe.whitelist()
def get_performance_analytics():
    """Get performance analytics for charts."""
    try:
        analytics = {}
        
        # Grade distribution
        grade_dist = frappe.db.sql("""
            SELECT 
                letter_grade,
                COUNT(*) as count
            FROM `tabGrade`
            WHERE docstatus = 1
            GROUP BY letter_grade
            ORDER BY letter_grade
        """, as_dict=True)
        
        analytics["grade_distribution"] = {
            "labels": [g.letter_grade for g in grade_dist],
            "data": [g.count for g in grade_dist]
        }
        
        # Attendance trend (last 30 days)
        attendance_trend = frappe.db.sql("""
            SELECT 
                attendance_date,
                COUNT(*) as total,
                SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END) as present
            FROM `tabStudent Attendance`
            WHERE attendance_date >= %s
            GROUP BY attendance_date
            ORDER BY attendance_date
        """, (add_days(today(), -30),), as_dict=True)
        
        analytics["attendance_trend"] = {
            "dates": [a.attendance_date.strftime("%Y-%m-%d") for a in attendance_trend],
            "rates": [(a.present / a.total * 100) if a.total > 0 else 0 for a in attendance_trend]
        }
        
        # Fee collection by month
        fee_trend = frappe.db.sql("""
            SELECT 
                DATE_FORMAT(creation, '%%Y-%%m') as month,
                SUM(paid_amount) as collected
            FROM `tabFee Bill`
            WHERE docstatus = 1 AND creation >= %s
            GROUP BY DATE_FORMAT(creation, '%%Y-%%m')
            ORDER BY month
        """, (add_days(today(), -365),), as_dict=True)
        
        analytics["fee_collection_trend"] = {
            "months": [f.month for f in fee_trend],
            "amounts": [f.collected or 0 for f in fee_trend]
        }
        
        return analytics
        
    except Exception as e:
        frappe.log_error(f"Error getting performance analytics: {str(e)}")
        return {}
