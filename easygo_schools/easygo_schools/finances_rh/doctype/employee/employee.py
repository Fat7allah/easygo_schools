"""Employee doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class Employee(Document):
    """Employee doctype controller with business rules."""
    
    def validate(self):
        """Validate employee data."""
        self.validate_dates()
        self.validate_emails()
        self.set_employee_name()
        self.validate_employee_id()
        self.validate_reporting_structure()
    
    def validate_dates(self):
        """Validate date fields."""
        if self.date_of_birth and getdate(self.date_of_birth) >= getdate(today()):
            frappe.throw(_("Date of Birth cannot be today or in the future"))
        
        if self.date_of_joining and getdate(self.date_of_joining) > getdate(today()):
            frappe.throw(_("Date of Joining cannot be in the future"))
        
        if self.date_of_birth and self.date_of_joining:
            age_at_joining = getdate(self.date_of_joining).year - getdate(self.date_of_birth).year
            if age_at_joining < 16:
                frappe.throw(_("Employee must be at least 16 years old at the time of joining"))
    
    def validate_emails(self):
        """Validate email formats."""
        if self.personal_email and not frappe.utils.validate_email_address(self.personal_email):
            frappe.throw(_("Invalid personal email address"))
        
        if self.company_email and not frappe.utils.validate_email_address(self.company_email):
            frappe.throw(_("Invalid company email address"))
    
    def set_employee_name(self):
        """Set employee name from first and last name."""
        if self.first_name:
            self.employee_name = self.first_name
            if self.last_name:
                self.employee_name += " " + self.last_name
    
    def validate_employee_id(self):
        """Validate employee ID uniqueness."""
        if self.employee_id:
            existing = frappe.db.get_value(
                "Employee",
                {"employee_id": self.employee_id, "name": ["!=", self.name]},
                "name"
            )
            if existing:
                frappe.throw(_("Employee ID {0} already exists").format(self.employee_id))
    
    def validate_reporting_structure(self):
        """Validate reporting structure to prevent circular references."""
        if self.reports_to:
            if self.reports_to == self.name:
                frappe.throw(_("Employee cannot report to themselves"))
            
            # Check for circular reporting
            current_manager = self.reports_to
            visited = set()
            
            while current_manager and current_manager not in visited:
                visited.add(current_manager)
                next_manager = frappe.db.get_value("Employee", current_manager, "reports_to")
                
                if next_manager == self.name:
                    frappe.throw(_("Circular reporting structure detected"))
                
                current_manager = next_manager
    
    def before_save(self):
        """Actions before saving."""
        # Set status based on is_active
        if not self.is_active:
            self.status = "Inactive"
        elif self.status == "Inactive" and self.is_active:
            self.status = "Active"
    
    def after_insert(self):
        """Actions after employee creation."""
        self.create_user_account()
        self.assign_default_roles()
    
    def create_user_account(self):
        """Create user account for employee if email provided."""
        if not self.company_email:
            return
        
        # Check if user already exists
        if frappe.db.exists("User", self.company_email):
            existing_user = frappe.get_doc("User", self.company_email)
            self.user_id = existing_user.name
            self.save(ignore_permissions=True)
            return
        
        try:
            # Create new user
            user = frappe.get_doc({
                "doctype": "User",
                "email": self.company_email,
                "first_name": self.first_name,
                "last_name": self.last_name or "",
                "full_name": self.employee_name,
                "send_welcome_email": 1,
                "user_type": "System User"
            })
            user.insert(ignore_permissions=True)
            
            self.user_id = user.name
            self.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Failed to create user account for employee {self.name}: {str(e)}")
    
    def assign_default_roles(self):
        """Assign default roles based on employee type."""
        if not self.user_id:
            return
        
        role_mapping = {
            "Teacher": ["Teacher"],
            "Administrative": ["Academic User"],
            "Support Staff": ["Academic User"],
            "Management": ["Education Manager"]
        }
        
        roles = role_mapping.get(self.employee_type, ["Academic User"])
        
        try:
            user = frappe.get_doc("User", self.user_id)
            for role in roles:
                if not any(r.role == role for r in user.roles):
                    user.append("roles", {"role": role})
            user.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Failed to assign roles to employee {self.name}: {str(e)}")
    
    def on_update(self):
        """Actions on employee update."""
        # Update user account if email changed
        if self.has_value_changed("company_email"):
            self.update_user_account()
        
        # Update user roles if employee type changed
        if self.has_value_changed("employee_type"):
            self.assign_default_roles()
    
    def update_user_account(self):
        """Update user account details."""
        if not self.user_id:
            return
        
        try:
            user = frappe.get_doc("User", self.user_id)
            user.first_name = self.first_name
            user.last_name = self.last_name or ""
            user.full_name = self.employee_name
            
            if self.company_email and user.email != self.company_email:
                # Check if new email is available
                if not frappe.db.exists("User", self.company_email):
                    user.email = self.company_email
                else:
                    frappe.msgprint(_("Email {0} is already in use by another user").format(
                        self.company_email
                    ), alert=True)
            
            user.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Failed to update user account for employee {self.name}: {str(e)}")
    
    def get_teaching_load(self):
        """Get teaching load for teacher employees."""
        if self.employee_type != "Teacher":
            return {}
        
        # Get course schedules
        schedules = frappe.get_all("Course Schedule",
            filters={"instructor": self.name, "is_active": 1},
            fields=["subject", "school_class", "day_of_week", "duration_minutes"]
        )
        
        total_hours = sum([s.duration_minutes for s in schedules]) / 60
        subjects = list(set([s.subject for s in schedules]))
        classes = list(set([s.school_class for s in schedules]))
        
        return {
            "total_weekly_hours": total_hours,
            "subjects_taught": len(subjects),
            "classes_taught": len(classes),
            "subjects": subjects,
            "classes": classes
        }
