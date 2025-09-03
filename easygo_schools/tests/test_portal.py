"""Test portal functionality for students, parents, and teachers."""

import frappe
import unittest
from frappe.utils import nowdate


class TestPortalAccess(unittest.TestCase):
    """Test portal access and functionality."""
    
    def setUp(self):
        """Set up test environment."""
        frappe.set_user("Administrator")
        self.cleanup_test_data()
        
        # Create test student
        self.test_student = frappe.get_doc({
            "doctype": "Student",
            "name": "PORTAL-TEST-STUDENT",
            "student_name": "Portal Test Student",
            "gender": "Male",
            "date_of_birth": "2010-01-01",
            "joining_date": nowdate(),
            "email_id": "student.portal@test.com",
            "enabled": 1
        })
        self.test_student.insert()
        
        # Create test user for student
        if not frappe.db.exists("User", "student.portal@test.com"):
            user = frappe.get_doc({
                "doctype": "User",
                "email": "student.portal@test.com",
                "first_name": "Portal",
                "last_name": "Student",
                "user_type": "Website User",
                "roles": [{"role": "Student"}]
            })
            user.insert()
    
    def tearDown(self):
        """Clean up test data."""
        self.cleanup_test_data()
    
    def cleanup_test_data(self):
        """Clean up test data."""
        # Delete test documents
        for doctype in ["Student", "User"]:
            docs = frappe.get_all(doctype, {"name": ["like", "%portal%"]})
            for doc in docs:
                try:
                    frappe.delete_doc(doctype, doc.name, force=True)
                except:
                    pass
    
    def test_student_portal_access(self):
        """Test student portal access and permissions."""
        
        # Switch to student user
        frappe.set_user("student.portal@test.com")
        
        # Test student can access their own record
        student = frappe.get_doc("Student", self.test_student.name)
        self.assertEqual(student.student_name, "Portal Test Student")
        
        # Test student cannot create new students
        with self.assertRaises(frappe.PermissionError):
            new_student = frappe.get_doc({
                "doctype": "Student",
                "student_name": "Unauthorized Student",
                "gender": "Female",
                "date_of_birth": "2010-01-01",
                "joining_date": nowdate(),
                "enabled": 1
            })
            new_student.insert()
        
        # Reset to Administrator
        frappe.set_user("Administrator")
    
    def test_portal_dashboard_access(self):
        """Test portal dashboard access."""
        
        # Create test attendance for dashboard
        attendance = frappe.get_doc({
            "doctype": "Student Attendance",
            "student": self.test_student.name,
            "student_name": self.test_student.student_name,
            "attendance_date": nowdate(),
            "status": "Present",
            "academic_year": "2024-2025"
        })
        attendance.insert()
        attendance.submit()
        
        # Switch to student user
        frappe.set_user("student.portal@test.com")
        
        # Test dashboard data access
        from easygo_education.api.portal import get_student_dashboard
        dashboard_data = get_student_dashboard()
        
        self.assertIsInstance(dashboard_data, dict)
        self.assertIn("attendance_summary", dashboard_data)
        
        # Reset to Administrator
        frappe.set_user("Administrator")
        
        # Clean up
        attendance.cancel()
        frappe.delete_doc("Student Attendance", attendance.name, force=True)


class TestWebForms(unittest.TestCase):
    """Test web form functionality."""
    
    def setUp(self):
        """Set up test environment."""
        frappe.set_user("Administrator")
    
    def test_student_admission_webform(self):
        """Test student admission web form."""
        
        # Test web form exists
        self.assertTrue(
            frappe.db.exists("Web Form", "student-admission"),
            "Student admission web form not found"
        )
        
        # Get web form
        webform = frappe.get_doc("Web Form", "student-admission")
        
        # Test web form configuration
        self.assertEqual(webform.doc_type, "Student")
        self.assertTrue(webform.published)
        self.assertTrue(webform.allow_web_form_write)
    
    def test_meeting_request_webform(self):
        """Test meeting request web form."""
        
        # Test web form exists
        self.assertTrue(
            frappe.db.exists("Web Form", "meeting-request"),
            "Meeting request web form not found"
        )
        
        # Get web form
        webform = frappe.get_doc("Web Form", "meeting-request")
        
        # Test web form configuration
        self.assertEqual(webform.doc_type, "Meeting Request")
        self.assertTrue(webform.published)


class TestAPIEndpoints(unittest.TestCase):
    """Test API endpoints for portal integration."""
    
    def setUp(self):
        """Set up test environment."""
        frappe.set_user("Administrator")
    
    def test_student_api_endpoints(self):
        """Test student-related API endpoints."""
        
        # Test get_student_dashboard endpoint
        from easygo_education.api.portal import get_student_dashboard
        
        # Should work for Administrator
        dashboard = get_student_dashboard()
        self.assertIsInstance(dashboard, dict)
    
    def test_attendance_api_endpoints(self):
        """Test attendance-related API endpoints."""
        
        # Test get_attendance_summary endpoint
        from easygo_education.api.portal import get_attendance_summary
        
        # Should return attendance data
        attendance_data = get_attendance_summary()
        self.assertIsInstance(attendance_data, dict)
    
    def test_fee_api_endpoints(self):
        """Test fee-related API endpoints."""
        
        # Test get_fee_summary endpoint
        from easygo_education.api.portal import get_fee_summary
        
        # Should return fee data
        fee_data = get_fee_summary()
        self.assertIsInstance(fee_data, dict)


if __name__ == "__main__":
    unittest.main()
