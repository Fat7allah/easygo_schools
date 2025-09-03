"""Teacher Portal page controller."""

import frappe
from frappe import _


def get_context(context):
    """Get context for teacher portal page."""
    # Check if user is logged in
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in to access the teacher portal"), frappe.PermissionError)
    
    # Check if user has Teacher role
    if "Teacher" not in frappe.get_roles():
        frappe.throw(_("Access denied. Teacher role required."), frappe.PermissionError)
    
    # Get teacher record
    teacher = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, ["name", "employee_name"])
    if not teacher:
        frappe.throw(_("Teacher record not found"), frappe.DoesNotExistError)
    
    context.teacher_id = teacher[0]
    context.teacher_name = teacher[1]
    context.page_title = _("Teacher Portal")
    
    return context
