"""Test report generation and functionality."""

import frappe
import unittest
from frappe.utils import nowdate, add_days


class TestReports(unittest.TestCase):
    """Test report generation and data accuracy."""
    
    def setUp(self):
        """Set up test environment."""
        frappe.set_user("Administrator")
        self.setup_test_data()
    
    def tearDown(self):
        """Clean up test data."""
        self.cleanup_test_data()
    
    def setup_test_data(self):
        """Create test data for reports."""
        # Create test student
        if not frappe.db.exists("Student", "REPORT-TEST-STUDENT"):
            self.test_student = frappe.get_doc({
                "doctype": "Student",
                "name": "REPORT-TEST-STUDENT",
                "student_name": "Report Test Student",
                "gender": "Male",
                "date_of_birth": "2010-01-01",
                "joining_date": nowdate(),
                "enabled": 1
            })
            self.test_student.insert()
        else:
            self.test_student = frappe.get_doc("Student", "REPORT-TEST-STUDENT")
        
        # Create test attendance
        if not frappe.db.exists("Student Attendance", {"student": self.test_student.name}):
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
    
    def cleanup_test_data(self):
        """Clean up test data."""
        # Delete attendance records
        attendances = frappe.get_all("Student Attendance", {"student": "REPORT-TEST-STUDENT"})
        for att in attendances:
            try:
                doc = frappe.get_doc("Student Attendance", att.name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc("Student Attendance", att.name, force=True)
            except:
                pass
        
        # Delete student
        if frappe.db.exists("Student", "REPORT-TEST-STUDENT"):
            frappe.delete_doc("Student", "REPORT-TEST-STUDENT", force=True)
    
    def test_student_attendance_report(self):
        """Test Student Attendance Report generation."""
        from easygo_education.scolarite.report.student_attendance_report.student_attendance_report import execute
        
        # Test report execution
        filters = {
            "from_date": nowdate(),
            "to_date": nowdate(),
            "academic_year": "2024-2025"
        }
        
        columns, data = execute(filters)
        
        # Verify report structure
        self.assertIsInstance(columns, list)
        self.assertIsInstance(data, list)
        self.assertGreater(len(columns), 0)
        
        # Verify column structure
        expected_columns = ["student", "student_name", "total_days", "present_days", "absent_days", "attendance_percentage"]
        for col in expected_columns:
            column_names = [c.get("fieldname") if isinstance(c, dict) else c for c in columns]
            self.assertIn(col, column_names)
    
    def test_payroll_summary_report(self):
        """Test Payroll Summary Report generation."""
        from easygo_education.finances_rh.report.payroll_summary_report.payroll_summary_report import execute
        
        # Test report execution
        filters = {
            "from_date": nowdate(),
            "to_date": nowdate()
        }
        
        columns, data = execute(filters)
        
        # Verify report structure
        self.assertIsInstance(columns, list)
        self.assertIsInstance(data, list)
        self.assertGreater(len(columns), 0)
        
        # Verify essential columns exist
        column_names = [c.get("fieldname") if isinstance(c, dict) else c for c in columns]
        self.assertIn("employee", column_names)
        self.assertIn("employee_name", column_names)
    
    def test_inventory_status_report(self):
        """Test Inventory Status Report generation."""
        from easygo_education.gestion_etablissement.report.inventory_status_report.inventory_status_report import execute
        
        # Test report execution
        filters = {}
        
        columns, data = execute(filters)
        
        # Verify report structure
        self.assertIsInstance(columns, list)
        self.assertIsInstance(data, list)
        self.assertGreater(len(columns), 0)
    
    def test_communication_analytics_report(self):
        """Test Communication Analytics Report generation."""
        from easygo_education.administration_comms.report.communication_analytics.communication_analytics import execute
        
        # Test report execution
        filters = {
            "from_date": nowdate(),
            "to_date": nowdate()
        }
        
        columns, data = execute(filters)
        
        # Verify report structure
        self.assertIsInstance(columns, list)
        self.assertIsInstance(data, list)
        self.assertGreater(len(columns), 0)
    
    def test_discipline_report(self):
        """Test Discipline Report generation."""
        from easygo_education.vie_scolaire.report.discipline_report.discipline_report import execute
        
        # Test report execution
        filters = {
            "from_date": nowdate(),
            "to_date": nowdate()
        }
        
        columns, data = execute(filters)
        
        # Verify report structure
        self.assertIsInstance(columns, list)
        self.assertIsInstance(data, list)
        self.assertGreater(len(columns), 0)
    
    def test_academic_calendar_report(self):
        """Test Academic Calendar Report generation."""
        from easygo_education.referentiels.report.academic_calendar_report.academic_calendar_report import execute
        
        # Test report execution
        filters = {
            "academic_year": "2024-2025"
        }
        
        columns, data = execute(filters)
        
        # Verify report structure
        self.assertIsInstance(columns, list)
        self.assertIsInstance(data, list)
        self.assertGreater(len(columns), 0)


class TestDashboards(unittest.TestCase):
    """Test dashboard functionality."""
    
    def setUp(self):
        """Set up test environment."""
        frappe.set_user("Administrator")
    
    def test_dashboard_charts_exist(self):
        """Test that dashboard charts are properly configured."""
        charts = [
            "Student Enrollment Chart",
            "Fee Collection Chart", 
            "Attendance Overview Chart",
            "Payroll Expenses Chart",
            "Inventory Value Chart"
        ]
        
        for chart_name in charts:
            chart_exists = frappe.db.exists("Dashboard Chart", chart_name)
            self.assertTrue(chart_exists, f"Dashboard Chart '{chart_name}' not found")
            
            if chart_exists:
                chart = frappe.get_doc("Dashboard Chart", chart_name)
                self.assertTrue(chart.chart_name)
                self.assertTrue(chart.chart_type)
    
    def test_number_cards_exist(self):
        """Test that number cards are properly configured."""
        cards = [
            "Total Students",
            "Total Teachers",
            "Monthly Revenue"
        ]
        
        for card_name in cards:
            card_exists = frappe.db.exists("Number Card", card_name)
            self.assertTrue(card_exists, f"Number Card '{card_name}' not found")
            
            if card_exists:
                card = frappe.get_doc("Number Card", card_name)
                self.assertTrue(card.label)
                self.assertTrue(card.document_type)
    
    def test_dashboards_exist(self):
        """Test that dashboards are properly configured."""
        dashboards = [
            "Education Dashboard",
            "Finance Dashboard"
        ]
        
        for dashboard_name in dashboards:
            dashboard_exists = frappe.db.exists("Dashboard", dashboard_name)
            self.assertTrue(dashboard_exists, f"Dashboard '{dashboard_name}' not found")
            
            if dashboard_exists:
                dashboard = frappe.get_doc("Dashboard", dashboard_name)
                self.assertTrue(dashboard.dashboard_name)
                self.assertTrue(len(dashboard.charts) > 0 or len(dashboard.number_cards) > 0)


class TestReportPermissions(unittest.TestCase):
    """Test report permissions and access control."""
    
    def setUp(self):
        """Set up test environment."""
        frappe.set_user("Administrator")
    
    def test_report_permissions(self):
        """Test that reports have proper role-based permissions."""
        reports = [
            "Student Attendance Report",
            "Payroll Summary Report",
            "Communication Analytics",
            "Discipline Report",
            "Academic Calendar Report"
        ]
        
        for report_name in reports:
            if frappe.db.exists("Report", report_name):
                report = frappe.get_doc("Report", report_name)
                
                # Check that report has roles assigned
                self.assertTrue(len(report.roles) > 0, f"Report '{report_name}' has no roles assigned")
                
                # Check for common roles
                role_names = [role.role for role in report.roles]
                expected_roles = ["System Manager", "Education Manager"]
                
                has_expected_role = any(role in role_names for role in expected_roles)
                self.assertTrue(has_expected_role, f"Report '{report_name}' missing expected roles")


if __name__ == "__main__":
    unittest.main()
