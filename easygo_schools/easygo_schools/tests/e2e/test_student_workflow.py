"""End-to-end workflow tests for student management."""

import frappe
import unittest
from frappe.utils import nowdate, add_days


class TestStudentWorkflow(unittest.TestCase):
    """Test complete student workflow from admission to graduation."""
    
    def setUp(self):
        """Set up test environment."""
        frappe.set_user("Administrator")
        self.cleanup_test_data()
        
        # Create test academic year
        if not frappe.db.exists("Academic Year", "2024-2025"):
            academic_year = frappe.get_doc({
                "doctype": "Academic Year",
                "academic_year_name": "2024-2025",
                "year_start_date": "2024-09-01",
                "year_end_date": "2025-06-30"
            })
            academic_year.insert()
    
    def tearDown(self):
        """Clean up test data."""
        self.cleanup_test_data()
    
    def cleanup_test_data(self):
        """Clean up all test data."""
        # Delete in reverse dependency order
        for doctype in ["Student Assessment", "Student Attendance", "Fee Bill", 
                       "Student Enrollment", "Student"]:
            docs = frappe.get_all(doctype, {"name": ["like", "TEST-%"]})
            for doc in docs:
                try:
                    frappe.delete_doc(doctype, doc.name, force=True)
                except:
                    pass
    
    def test_complete_student_lifecycle(self):
        """Test complete student lifecycle workflow."""
        
        # Step 1: Create student
        student = frappe.get_doc({
            "doctype": "Student",
            "name": "TEST-STUDENT-E2E",
            "student_name": "Ahmed El Mansouri",
            "gender": "Male",
            "date_of_birth": "2012-03-15",
            "joining_date": nowdate(),
            "enabled": 1,
            "email_id": "ahmed.elmansouri@test.com",
            "mobile_number": "+212600123456"
        })
        student.insert()
        
        # Step 2: Enroll student in class
        enrollment = frappe.get_doc({
            "doctype": "Student Enrollment",
            "student": student.name,
            "student_name": student.student_name,
            "academic_year": "2024-2025",
            "program": "Collège",
            "enrollment_date": nowdate()
        })
        enrollment.insert()
        enrollment.submit()
        
        # Step 3: Create fee bill
        fee_bill = frappe.get_doc({
            "doctype": "Fee Bill",
            "student": student.name,
            "student_name": student.student_name,
            "academic_year": "2024-2025",
            "posting_date": nowdate(),
            "due_date": add_days(nowdate(), 30),
            "fee_items": [
                {
                    "fee_type": "Frais de Scolarité",
                    "amount": 4000,
                    "quantity": 1,
                    "total_amount": 4000
                }
            ]
        })
        fee_bill.insert()
        fee_bill.submit()
        
        # Step 4: Mark attendance
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
        
        # Step 5: Create assessment
        assessment = frappe.get_doc({
            "doctype": "Student Assessment",
            "student": student.name,
            "student_name": student.student_name,
            "academic_year": "2024-2025",
            "assessment_name": "Test Assessment E2E",
            "assessment_date": nowdate(),
            "assessment_period": "Trimestre 1",
            "assessment_details": [
                {
                    "subject": "Mathématiques",
                    "score": 16,
                    "max_score": 20,
                    "grade": "Bien",
                    "remarks": "Bon travail"
                }
            ]
        })
        assessment.insert()
        assessment.submit()
        
        # Verify all documents are created and linked
        self.assertTrue(frappe.db.exists("Student", student.name))
        self.assertTrue(frappe.db.exists("Student Enrollment", enrollment.name))
        self.assertTrue(frappe.db.exists("Fee Bill", fee_bill.name))
        self.assertTrue(frappe.db.exists("Student Attendance", attendance.name))
        self.assertTrue(frappe.db.exists("Student Assessment", assessment.name))
        
        # Verify relationships
        self.assertEqual(enrollment.student, student.name)
        self.assertEqual(fee_bill.student, student.name)
        self.assertEqual(attendance.student, student.name)
        self.assertEqual(assessment.student, student.name)


class TestEmployeeWorkflow(unittest.TestCase):
    """Test complete employee workflow."""
    
    def setUp(self):
        """Set up test environment."""
        frappe.set_user("Administrator")
        self.cleanup_test_data()
    
    def tearDown(self):
        """Clean up test data."""
        self.cleanup_test_data()
    
    def cleanup_test_data(self):
        """Clean up test data."""
        for doctype in ["Salary Slip", "Employee"]:
            docs = frappe.get_all(doctype, {"name": ["like", "TEST-%"]})
            for doc in docs:
                try:
                    frappe.delete_doc(doctype, doc.name, force=True)
                except:
                    pass
    
    def test_employee_payroll_workflow(self):
        """Test employee creation and payroll processing."""
        
        # Step 1: Create employee
        employee = frappe.get_doc({
            "doctype": "Employee",
            "name": "TEST-EMP-E2E",
            "employee_name": "Fatima Zahra Benali",
            "gender": "Female",
            "date_of_birth": "1985-07-20",
            "date_of_joining": nowdate(),
            "designation": "Professeur",
            "department": "Enseignement",
            "status": "Active",
            "personal_email": "fatima.benali@test.com",
            "cell_number": "+212661234567"
        })
        employee.insert()
        
        # Step 2: Create salary slip
        salary_slip = frappe.get_doc({
            "doctype": "Salary Slip",
            "employee": employee.name,
            "employee_name": employee.employee_name,
            "posting_date": nowdate(),
            "start_date": nowdate(),
            "end_date": add_days(nowdate(), 30),
            "earnings": [
                {
                    "salary_component": "Salaire de Base",
                    "amount": 8000
                }
            ],
            "deductions": [
                {
                    "salary_component": "CNSS",
                    "amount": 400
                }
            ]
        })
        salary_slip.insert()
        salary_slip.submit()
        
        # Verify documents
        self.assertTrue(frappe.db.exists("Employee", employee.name))
        self.assertTrue(frappe.db.exists("Salary Slip", salary_slip.name))
        self.assertEqual(salary_slip.employee, employee.name)


if __name__ == "__main__":
    unittest.main()
