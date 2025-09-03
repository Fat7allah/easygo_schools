"""School Class doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document


class SchoolClass(Document):
    """School Class doctype controller with business rules."""
    
    def validate(self):
        """Validate class data."""
        self.validate_capacity()
        self.validate_time_schedule()
        self.update_current_students()
        self.validate_academic_year()
    
    def validate_capacity(self):
        """Validate student capacity."""
        if self.max_students and self.current_students > self.max_students:
            frappe.throw(_("Current students ({0}) cannot exceed maximum capacity ({1})").format(
                self.current_students, self.max_students
            ))
    
    def validate_time_schedule(self):
        """Validate start and end times."""
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                frappe.throw(_("Start time must be before end time"))
    
    def update_current_students(self):
        """Update current student count."""
        if not self.is_new():
            self.current_students = frappe.db.count("Student", {
                "school_class": self.name,
                "status": "Active"
            })
    
    def validate_academic_year(self):
        """Validate academic year is active."""
        if self.academic_year:
            academic_year = frappe.get_doc("Academic Year", self.academic_year)
            if not academic_year.is_default and not academic_year.is_active:
                frappe.throw(_("Academic Year {0} is not active").format(self.academic_year))
    
    def after_insert(self):
        """Actions after class creation."""
        self.create_default_subjects()
    
    def create_default_subjects(self):
        """Create default subjects based on level."""
        default_subjects = {
            "Primaire": ["Arabe", "Français", "Mathématiques", "Sciences", "Histoire-Géographie", "Education Islamique"],
            "Collège": ["Arabe", "Français", "Mathématiques", "Sciences Physiques", "Sciences de la Vie et de la Terre", "Histoire-Géographie", "Education Islamique", "Anglais"],
            "Lycée": ["Arabe", "Français", "Mathématiques", "Physique-Chimie", "Sciences de la Vie et de la Terre", "Histoire-Géographie", "Philosophie", "Anglais", "Education Islamique"],
            "Supérieur": []  # No default subjects for higher education
        }
        
        subjects = default_subjects.get(self.level, [])
        for subject in subjects:
            # Check if subject already exists
            if not frappe.db.exists("Subject", subject):
                frappe.get_doc({
                    "doctype": "Subject",
                    "subject_name": subject,
                    "subject_code": subject.upper().replace(" ", "_").replace("-", "_")
                }).insert(ignore_permissions=True)
    
    def on_update(self):
        """Actions on class update."""
        # Update student records if class name changed
        if self.has_value_changed("class_name"):
            frappe.db.sql("""
                UPDATE `tabStudent` 
                SET school_class = %s 
                WHERE school_class = %s
            """, (self.class_name, self.get_doc_before_save().class_name))


def get_class_students(class_name):
    """Get all active students in a class."""
    return frappe.get_all("Student", 
        filters={"school_class": class_name, "status": "Active"},
        fields=["name", "student_name", "student_id", "guardian_email"]
    )


def get_class_schedule(class_name):
    """Get weekly schedule for a class."""
    return frappe.get_all("Course Schedule",
        filters={"school_class": class_name, "is_active": 1},
        fields=["day_of_week", "subject", "instructor", "room", "start_time", "end_time"],
        order_by="day_of_week, start_time"
    )
