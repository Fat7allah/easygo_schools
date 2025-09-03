"""Guardian doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now


class Guardian(Document):
    """Guardian doctype controller with business rules."""
    
    def validate(self):
        """Validate guardian data."""
        self.validate_contact_information()
        self.validate_primary_guardian()
        self.set_defaults()
    
    def validate_contact_information(self):
        """Validate contact information."""
        if not self.mobile_number and not self.phone_number:
            frappe.throw(_("At least one phone number is required"))
        
        # Validate email format if provided
        if self.email_address:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, self.email_address):
                frappe.throw(_("Invalid email format"))
    
    def validate_primary_guardian(self):
        """Validate primary guardian settings."""
        if self.primary_guardian:
            # Check if there are other primary guardians for the same students
            students = self.get_linked_students()
            
            for student in students:
                existing_primary = frappe.db.sql("""
                    SELECT g.name, g.guardian_name
                    FROM `tabGuardian` g
                    INNER JOIN `tabStudent Guardian` sg ON g.name = sg.guardian
                    WHERE sg.student = %s 
                        AND g.primary_guardian = 1 
                        AND g.name != %s
                """, (student, self.name or ''), as_dict=True)
                
                if existing_primary:
                    frappe.msgprint(_("Warning: Student {0} already has a primary guardian: {1}").format(
                        student, existing_primary[0].guardian_name
                    ), alert=True)
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
        
        # Set default notification preferences
        if not self.notification_preferences:
            self.notification_preferences = "Email: Yes\nSMS: Yes\nAttendance Alerts: Yes\nGrade Updates: Yes"
    
    def after_insert(self):
        """Actions after guardian creation."""
        if self.portal_enabled and self.email_address:
            self.create_portal_user()
    
    def on_update(self):
        """Actions on guardian update."""
        if self.has_value_changed("portal_enabled"):
            if self.portal_enabled and self.email_address:
                self.create_portal_user()
            elif not self.portal_enabled and self.user_id:
                self.disable_portal_user()
        
        if self.has_value_changed("email_address") and self.user_id:
            self.update_user_email()
    
    def create_portal_user(self):
        """Create portal user for guardian."""
        try:
            if not self.email_address:
                frappe.throw(_("Email address is required to create portal user"))
            
            # Check if user already exists
            existing_user = frappe.db.get_value("User", {"email": self.email_address}, "name")
            
            if existing_user:
                self.user_id = existing_user
                # Add Parent role if not already assigned
                user_doc = frappe.get_doc("User", existing_user)
                if "Parent" not in [role.role for role in user_doc.roles]:
                    user_doc.append("roles", {"role": "Parent"})
                    user_doc.save(ignore_permissions=True)
            else:
                # Create new user
                user_doc = frappe.get_doc({
                    "doctype": "User",
                    "email": self.email_address,
                    "first_name": self.guardian_name.split()[0] if self.guardian_name else "Guardian",
                    "last_name": " ".join(self.guardian_name.split()[1:]) if len(self.guardian_name.split()) > 1 else "",
                    "user_type": "Website User",
                    "send_welcome_email": 1,
                    "roles": [{"role": "Parent"}]
                })
                
                user_doc.insert(ignore_permissions=True)
                self.user_id = user_doc.name
            
            self.save(ignore_permissions=True)
            
            frappe.msgprint(_("Portal user created successfully for {0}").format(self.guardian_name))
            
        except Exception as e:
            frappe.log_error(f"Failed to create portal user for guardian {self.name}: {str(e)}")
            frappe.throw(_("Failed to create portal user: {0}").format(str(e)))
    
    def disable_portal_user(self):
        """Disable portal user for guardian."""
        try:
            if self.user_id:
                user_doc = frappe.get_doc("User", self.user_id)
                user_doc.enabled = 0
                user_doc.save(ignore_permissions=True)
                
                frappe.msgprint(_("Portal access disabled for {0}").format(self.guardian_name))
                
        except Exception as e:
            frappe.log_error(f"Failed to disable portal user for guardian {self.name}: {str(e)}")
    
    def update_user_email(self):
        """Update user email when guardian email changes."""
        try:
            if self.user_id and self.email_address:
                user_doc = frappe.get_doc("User", self.user_id)
                user_doc.email = self.email_address
                user_doc.save(ignore_permissions=True)
                
        except Exception as e:
            frappe.log_error(f"Failed to update user email for guardian {self.name}: {str(e)}")
    
    def get_linked_students(self):
        """Get list of students linked to this guardian."""
        students = frappe.db.sql("""
            SELECT sg.student
            FROM `tabStudent Guardian` sg
            WHERE sg.guardian = %s
        """, (self.name,), as_list=True)
        
        return [student[0] for student in students]
    
    @frappe.whitelist()
    def get_children_summary(self):
        """Get summary of children for portal display."""
        students = frappe.get_list("Student",
            filters={
                "guardian": self.name,
                "status": "Active"
            },
            fields=[
                "name", "student_name", "school_class", "date_of_birth",
                "admission_date", "status"
            ]
        )
        
        # Get additional data for each student
        for student in students:
            # Get latest attendance
            latest_attendance = frappe.db.get_value("Student Attendance",
                {"student": student.name},
                ["attendance_date", "status"],
                order_by="attendance_date desc"
            )
            
            student["latest_attendance"] = {
                "date": latest_attendance[0] if latest_attendance else None,
                "status": latest_attendance[1] if latest_attendance else None
            }
            
            # Get latest grades
            latest_grades = frappe.get_list("Grade",
                filters={"student": student.name},
                fields=["subject", "percentage", "letter_grade"],
                order_by="creation desc",
                limit=5
            )
            
            student["recent_grades"] = latest_grades
            
            # Get pending fee bills
            pending_fees = frappe.db.get_value("Fee Bill",
                {"student": student.name, "status": ["!=", "Paid"]},
                ["sum(outstanding_amount)"]
            )
            
            student["pending_fees"] = pending_fees[0] if pending_fees else 0
        
        return students
    
    @frappe.whitelist()
    def update_last_login(self):
        """Update last login timestamp."""
        self.last_login = now()
        self.save(ignore_permissions=True)
