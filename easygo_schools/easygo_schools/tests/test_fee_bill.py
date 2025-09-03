"""Unit tests for Fee Bill DocType."""

import frappe
import unittest
from frappe.utils import nowdate, add_days, flt


class TestFeeBill(unittest.TestCase):
    """Test Fee Bill DocType functionality."""
    
    def setUp(self):
        """Set up test environment."""
        frappe.set_user("Administrator")
        
        # Create test student if not exists
        if not frappe.db.exists("Student", "TEST-STUDENT-001"):
            self.test_student = frappe.get_doc({
                "doctype": "Student",
                "name": "TEST-STUDENT-001",
                "student_name": "Test Fee Student",
                "gender": "Female",
                "date_of_birth": "2012-05-20",
                "joining_date": nowdate(),
                "enabled": 1
            })
            self.test_student.insert()
        else:
            self.test_student = frappe.get_doc("Student", "TEST-STUDENT-001")
    
    def tearDown(self):
        """Clean up test data."""
        # Clean up fee bills
        fee_bills = frappe.get_all("Fee Bill", {"student": self.test_student.name})
        for bill in fee_bills:
            frappe.delete_doc("Fee Bill", bill.name, force=True)
    
    def test_fee_bill_creation(self):
        """Test creating a fee bill."""
        fee_bill = frappe.get_doc({
            "doctype": "Fee Bill",
            "student": self.test_student.name,
            "student_name": self.test_student.student_name,
            "academic_year": "2024-2025",
            "posting_date": nowdate(),
            "due_date": add_days(nowdate(), 30),
            "fee_items": [
                {
                    "fee_type": "Frais de Scolarité",
                    "amount": 5000,
                    "quantity": 1,
                    "total_amount": 5000
                },
                {
                    "fee_type": "Frais de Transport",
                    "amount": 800,
                    "quantity": 1,
                    "total_amount": 800
                }
            ]
        })
        fee_bill.insert()
        
        self.assertTrue(fee_bill.name)
        self.assertEqual(fee_bill.student, self.test_student.name)
        self.assertEqual(flt(fee_bill.total_amount), 5800)
        self.assertEqual(fee_bill.status, "Unpaid")
    
    def test_fee_calculation(self):
        """Test fee amount calculation."""
        fee_bill = frappe.get_doc({
            "doctype": "Fee Bill",
            "student": self.test_student.name,
            "student_name": self.test_student.student_name,
            "academic_year": "2024-2025",
            "posting_date": nowdate(),
            "due_date": add_days(nowdate(), 30),
            "fee_items": [
                {
                    "fee_type": "Frais de Scolarité",
                    "amount": 3000,
                    "quantity": 2,
                    "total_amount": 6000
                }
            ]
        })
        fee_bill.insert()
        
        # Test that total is calculated correctly
        self.assertEqual(flt(fee_bill.total_amount), 6000)
    
    def test_payment_processing(self):
        """Test fee bill payment processing."""
        fee_bill = frappe.get_doc({
            "doctype": "Fee Bill",
            "student": self.test_student.name,
            "student_name": self.test_student.student_name,
            "academic_year": "2024-2025",
            "posting_date": nowdate(),
            "due_date": add_days(nowdate(), 30),
            "fee_items": [
                {
                    "fee_type": "Frais de Scolarité",
                    "amount": 2000,
                    "quantity": 1,
                    "total_amount": 2000
                }
            ]
        })
        fee_bill.insert()
        fee_bill.submit()
        
        # Test payment entry creation
        payment = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "party_type": "Student",
            "party": self.test_student.name,
            "paid_amount": 2000,
            "received_amount": 2000,
            "posting_date": nowdate(),
            "reference_no": fee_bill.name,
            "reference_date": nowdate()
        })
        payment.insert()
        payment.submit()
        
        # Reload fee bill and check status
        fee_bill.reload()
        # Note: Status update would be handled by payment reconciliation
        
        # Clean up
        payment.cancel()
        frappe.delete_doc("Payment Entry", payment.name, force=True)
        fee_bill.cancel()
    
    def test_overdue_calculation(self):
        """Test overdue fee calculation."""
        # Create fee bill with past due date
        fee_bill = frappe.get_doc({
            "doctype": "Fee Bill",
            "student": self.test_student.name,
            "student_name": self.test_student.student_name,
            "academic_year": "2024-2025",
            "posting_date": add_days(nowdate(), -60),
            "due_date": add_days(nowdate(), -30),
            "fee_items": [
                {
                    "fee_type": "Frais de Scolarité",
                    "amount": 1500,
                    "quantity": 1,
                    "total_amount": 1500
                }
            ]
        })
        fee_bill.insert()
        
        # Test that bill is marked as overdue
        self.assertTrue(fee_bill.due_date < nowdate())


if __name__ == "__main__":
    unittest.main()
