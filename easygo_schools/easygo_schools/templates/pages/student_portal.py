"""Student Portal page controller."""

import frappe
from frappe import _


def get_context(context):
    """Get context for student portal page."""
    # Check if user is logged in
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in to access the student portal"), frappe.PermissionError)
    
    # Check if user has Student role
    if "Student" not in frappe.get_roles():
        frappe.throw(_("Access denied. Student role required."), frappe.PermissionError)
    
    # Get student record
    student = frappe.db.get_value("Student", {"user_id": frappe.session.user}, ["name", "student_name"])
    if not student:
        frappe.throw(_("Student record not found"), frappe.DoesNotExistError)
    
    context.student_id = student[0]
    context.student_name = student[1]
    context.page_title = _("Student Portal")
    
    return context
