"""Parent Portal page controller."""

import frappe
from frappe import _


def get_context(context):
    """Get context for parent portal page."""
    # Check if user is logged in
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in to access the parent portal"), frappe.PermissionError)
    
    # Check if user has Parent role
    if "Parent" not in frappe.get_roles():
        frappe.throw(_("Access denied. Parent role required."), frappe.PermissionError)
    
    # Get children records
    children = frappe.get_all("Student", 
        filters={"guardian_email": frappe.session.user, "status": "Active"},
        fields=["name", "student_name", "school_class"]
    )
    
    if not children:
        frappe.throw(_("No student records found for this parent"), frappe.DoesNotExistError)
    
    context.children = children
    context.page_title = _("Parent Portal")
    
    return context
