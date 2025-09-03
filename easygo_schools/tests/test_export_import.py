"""Test data export/import and conflict resolution."""

import frappe
import unittest
import json
from frappe.utils import nowdate


class TestExportImport(unittest.TestCase):
    """Test data export/import functionality."""
    
    def setUp(self):
        """Set up test environment."""
        frappe.set_user("Administrator")
        self.cleanup_test_data()
    
    def tearDown(self):
        """Clean up test data."""
        self.cleanup_test_data()
    
    def cleanup_test_data(self):
        """Clean up test data."""
        for doctype in ["Student", "Employee"]:
            docs = frappe.get_all(doctype, {"name": ["like", "EXPORT-TEST-%"]})
            for doc in docs:
                try:
                    frappe.delete_doc(doctype, doc.name, force=True)
                except:
                    pass
    
    def test_student_export_import(self):
        """Test student data export and import."""
        
        # Create test student
        original_student = frappe.get_doc({
            "doctype": "Student",
            "name": "EXPORT-TEST-STUDENT",
            "student_name": "Export Test Student",
            "gender": "Male",
            "date_of_birth": "2010-05-15",
            "joining_date": nowdate(),
            "enabled": 1
        })
        original_student.insert()
        
        # Export student data
        export_data = frappe.get_doc("Student", original_student.name).as_dict()
        
        # Delete original
        frappe.delete_doc("Student", original_student.name, force=True)
        
        # Import student data
        imported_student = frappe.get_doc(export_data)
        imported_student.insert()
        
        # Verify imported data
        self.assertEqual(imported_student.student_name, "Export Test Student")
        self.assertEqual(imported_student.gender, "Male")
        self.assertTrue(imported_student.enabled)
    
    def test_duplicate_import_handling(self):
        """Test handling of duplicate imports."""
        
        # Create original student
        student_data = {
            "doctype": "Student",
            "name": "EXPORT-TEST-DUP",
            "student_name": "Duplicate Test Student",
            "gender": "Female",
            "date_of_birth": "2011-08-20",
            "joining_date": nowdate(),
            "enabled": 1
        }
        
        original_student = frappe.get_doc(student_data)
        original_student.insert()
        
        # Try to import duplicate
        with self.assertRaises(frappe.DuplicateEntryError):
            duplicate_student = frappe.get_doc(student_data)
            duplicate_student.insert()
    
    def test_bulk_export_import(self):
        """Test bulk export and import operations."""
        
        # Create multiple test records
        students = []
        for i in range(3):
            student = frappe.get_doc({
                "doctype": "Student",
                "name": f"EXPORT-TEST-BULK-{i+1}",
                "student_name": f"Bulk Test Student {i+1}",
                "gender": "Male" if i % 2 == 0 else "Female",
                "date_of_birth": "2010-01-01",
                "joining_date": nowdate(),
                "enabled": 1
            })
            student.insert()
            students.append(student)
        
        # Export all students
        export_data = []
        for student in students:
            export_data.append(frappe.get_doc("Student", student.name).as_dict())
        
        # Delete originals
        for student in students:
            frappe.delete_doc("Student", student.name, force=True)
        
        # Import all students
        imported_count = 0
        for data in export_data:
            imported_student = frappe.get_doc(data)
            imported_student.insert()
            imported_count += 1
        
        # Verify all imported
        self.assertEqual(imported_count, 3)
        
        # Verify data integrity
        for i in range(3):
            student_name = f"EXPORT-TEST-BULK-{i+1}"
            self.assertTrue(frappe.db.exists("Student", student_name))


class TestDataIntegrity(unittest.TestCase):
    """Test data integrity and validation."""
    
    def setUp(self):
        """Set up test environment."""
        frappe.set_user("Administrator")
    
    def test_required_field_validation(self):
        """Test required field validation."""
        
        # Test missing student name
        with self.assertRaises(frappe.ValidationError):
            student = frappe.get_doc({
                "doctype": "Student",
                "gender": "Male",
                "date_of_birth": "2010-01-01"
                # Missing student_name
            })
            student.insert()
    
    def test_date_validation(self):
        """Test date field validation."""
        
        # Test invalid date format
        with self.assertRaises((frappe.ValidationError, ValueError)):
            student = frappe.get_doc({
                "doctype": "Student",
                "student_name": "Invalid Date Test",
                "gender": "Male",
                "date_of_birth": "invalid-date",
                "joining_date": nowdate(),
                "enabled": 1
            })
            student.insert()
    
    def test_email_validation(self):
        """Test email field validation."""
        
        # Test invalid email format
        with self.assertRaises(frappe.ValidationError):
            student = frappe.get_doc({
                "doctype": "Student",
                "student_name": "Email Test Student",
                "gender": "Male",
                "date_of_birth": "2010-01-01",
                "joining_date": nowdate(),
                "email_id": "invalid-email",
                "enabled": 1
            })
            student.insert()


if __name__ == "__main__":
    unittest.main()
