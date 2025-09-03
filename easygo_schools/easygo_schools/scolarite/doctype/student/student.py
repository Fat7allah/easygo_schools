"""Student doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, date_diff, today
import re


class Student(Document):
    """Student doctype controller with business rules."""
    
    def validate(self):
        """Validate student data."""
        self.validate_massar_code()
        self.validate_age_and_level()
        self.validate_email()
        self.calculate_age()
    
    def validate_massar_code(self):
        """Validate MASSAR code format and uniqueness."""
        if self.massar_code:
            # Check format: exactly 11 digits
            if not re.fullmatch(r"\d{11}", self.massar_code):
                frappe.throw(_("MASSAR Code must be exactly 11 digits"))
            
            # Check uniqueness
            existing = frappe.db.get_value(
                "Student", 
                {"massar_code": self.massar_code, "name": ["!=", self.name]}, 
                "name"
            )
            if existing:
                frappe.throw(_("MASSAR Code {0} already exists for student {1}").format(
                    self.massar_code, existing
                ))
    
    def validate_age_and_level(self):
        """Validate age is appropriate for the class level."""
        if not self.date_of_birth or not self.school_class:
            return
            
        age = self.calculate_age()
        
        # Get class level from school class
        if self.school_class:
            class_doc = frappe.get_doc("School Class", self.school_class)
            if hasattr(class_doc, 'level'):
                level = class_doc.level
                
                # Basic age validation (can be customized)
                min_age = 6 + int(level) if level.isdigit() else 6
                max_age = min_age + 3
                
                if age < min_age or age > max_age:
                    frappe.msgprint(
                        _("Warning: Student age ({0}) may not be appropriate for class level").format(age),
                        indicator="orange"
                    )
    
    def validate_email(self):
        """Validate guardian email format."""
        if self.guardian_email:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, self.guardian_email):
                frappe.throw(_("Please enter a valid guardian email address"))
    
    def calculate_age(self):
        """Calculate and set student age."""
        if self.date_of_birth:
            age = date_diff(today(), self.date_of_birth) // 365
            self.age = age
            return age
        return 0
    
    def after_insert(self):
        """Actions after student is created."""
        self.send_welcome_email()
        self.create_user_account()
    
    def send_welcome_email(self):
        """Send welcome email to guardian if email is provided."""
        if not self.guardian_email:
            return
            
        try:
            school_name = frappe.db.get_single_value("School Settings", "school_name") or "School"
            
            frappe.sendmail(
                recipients=[self.guardian_email],
                subject=_("Welcome to {0} - {1}").format(school_name, self.student_name),
                message=_("""
                <p>Dear {0},</p>
                
                <p>Welcome to {1}! We are pleased to confirm the enrollment of {2} in our school.</p>
                
                <p><strong>Student Details:</strong></p>
                <ul>
                    <li>Name: {2}</li>
                    <li>Student ID: {3}</li>
                    <li>Class: {4}</li>
                    <li>MASSAR Code: {5}</li>
                </ul>
                
                <p>You can access the parent portal to view your child's progress, attendance, and communicate with teachers.</p>
                
                <p>If you have any questions, please don't hesitate to contact us.</p>
                
                <p>Best regards,<br>
                {1} Administration</p>
                """).format(
                    self.guardian_name or "Guardian",
                    school_name,
                    self.student_name,
                    self.name,
                    self.school_class or "Not assigned",
                    self.massar_code or "Not assigned"
                )
            )
            
        except Exception as e:
            frappe.log_error(f"Failed to send welcome email for student {self.name}: {str(e)}")
    
    def create_user_account(self):
        """Create user accounts for student and guardian portal access."""
        try:
            # Create student user account
            if not frappe.db.exists("User", f"student.{self.name.lower()}@school.local"):
                student_user = frappe.get_doc({
                    "doctype": "User",
                    "email": f"student.{self.name.lower()}@school.local",
                    "first_name": self.student_name,
                    "user_type": "Website User",
                    "send_welcome_email": 0
                })
                student_user.insert(ignore_permissions=True)
                
                # Assign Student role
                student_user.add_roles("Student")
                
            # Create guardian user account if email provided
            if self.guardian_email and not frappe.db.exists("User", self.guardian_email):
                guardian_user = frappe.get_doc({
                    "doctype": "User",
                    "email": self.guardian_email,
                    "first_name": self.guardian_name or "Guardian",
                    "user_type": "Website User",
                    "send_welcome_email": 0
                })
                guardian_user.insert(ignore_permissions=True)
                
                # Assign Parent role
                guardian_user.add_roles("Parent")
                
        except Exception as e:
            frappe.log_error(f"Failed to create user accounts for student {self.name}: {str(e)}")
    
    def on_update(self):
        """Actions when student is updated."""
        # Update related records if class changes
        if self.has_value_changed("school_class"):
            self.update_related_records()
    
    def update_related_records(self):
        """Update related records when student data changes."""
        # Update attendance records, fee bills, etc.
        # This is a placeholder for future implementation
        pass


def validate_student(doc, method):
    """Hook function for student validation."""
    # This is called from hooks.py
    pass


def send_welcome_email(doc, method):
    """Hook function to send welcome email."""
    # This is called from hooks.py - the actual logic is in after_insert
    pass
