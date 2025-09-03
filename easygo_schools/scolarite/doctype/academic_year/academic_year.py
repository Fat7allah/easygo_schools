"""Academic Year doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class AcademicYear(Document):
    """Academic Year doctype controller with business rules."""
    
    def validate(self):
        """Validate academic year data."""
        self.validate_dates()
        self.validate_default_year()
    
    def validate_dates(self):
        """Validate start and end dates."""
        if self.year_start_date and self.year_end_date:
            if getdate(self.year_start_date) >= getdate(self.year_end_date):
                frappe.throw(_("Year End Date must be after Year Start Date"))
    
    def validate_default_year(self):
        """Ensure only one default academic year exists."""
        if self.is_default:
            existing_default = frappe.db.get_value(
                "Academic Year",
                {"is_default": 1, "name": ["!=", self.name]},
                "name"
            )
            if existing_default:
                frappe.throw(_("Academic Year {0} is already set as default").format(existing_default))
    
    def on_update(self):
        """Actions when academic year is updated."""
        if self.is_default:
            # Update school settings with current academic year
            frappe.db.set_single_value("School Settings", "current_academic_year", self.name)
