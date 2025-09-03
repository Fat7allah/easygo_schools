"""Unit tests for Student DocType."""

import frappe
import unittest
from frappe.utils import nowdate, add_days


class TestStudent(unittest.TestCase):
    """Test Student DocType functionality."""
    
    def setUp(self):
        """Set up test environment."""
        frappe.set_user("Administrator")
        self.test_student_data = {
            "student_name": "Test Student",
            "gender": "Male",
            "date_of_birth": "2010-01-15",
            "joining_date": nowdate(),
            "enabled": 1
        }
    
    def tearDown(self):
        """Clean up test data."""
        if hasattr(self, 'test_student') and self.test_student:
            frappe.delete_doc("Student", self.test_student.name, force=True)
    
    def test_student_creation(self):
        """Test creating a new student."""
        student = frappe.get_doc({
            "doctype": "Student",
            **self.test_student_data
        })
        student.insert()
        self.test_student = student
        
        self.assertTrue(student.name)
        self.assertEqual(student.student_name, "Test Student")
        self.assertEqual(student.gender, "Male")
    
    def test_student_validation(self):
        """Test student validation rules."""
        # Test missing required fields
        with self.assertRaises(frappe.ValidationError):
            student = frappe.get_doc({
                "doctype": "Student",
                "gender": "Male"  # Missing student_name
            })
            student.insert()
    
    def test_student_age_calculation(self):
        """Test age calculation."""
        student = frappe.get_doc({
            "doctype": "Student",
            **self.test_student_data
        })
        student.insert()
        self.test_student = student
        
        # Student born in 2010 should be around 14 years old
        self.assertGreaterEqual(student.age, 13)
        self.assertLessEqual(student.age, 15)
    
    def test_student_enrollment(self):
        """Test student enrollment in class."""
        # Create test student
        student = frappe.get_doc({
            "doctype": "Student",
            **self.test_student_data
        })
        student.insert()
        self.test_student = student
        
        # Create test enrollment
        enrollment = frappe.get_doc({
            "doctype": "Student Enrollment",
            "student": student.name,
            "academic_year": "2024-2025",
            "program": "Collège",
            "enrollment_date": nowdate()
        })
        enrollment.insert()
        
        # Verify enrollment
        self.assertEqual(enrollment.student, student.name)
        self.assertEqual(enrollment.academic_year, "2024-2025")
        
        # Clean up
        frappe.delete_doc("Student Enrollment", enrollment.name, force=True)
    
    def test_student_attendance_creation(self):
        """Test creating attendance for student."""
        # Create test student
        student = frappe.get_doc({
            "doctype": "Student",
            **self.test_student_data
        })
        student.insert()
        self.test_student = student
        
        # Create attendance record
        attendance = frappe.get_doc({
            "doctype": "Student Attendance",
            "student": student.name,
            "student_name": student.student_name,
            "attendance_date": nowdate(),
            "status": "Present",
            "academic_year": "2024-2025"
        })
        attendance.insert()
        attendance.submit()
        
        # Verify attendance
        self.assertEqual(attendance.student, student.name)
        self.assertEqual(attendance.status, "Present")
        
        # Clean up
        attendance.cancel()
        frappe.delete_doc("Student Attendance", attendance.name, force=True)


if __name__ == "__main__":
    unittest.main()
