"""Test installation and setup of EasyGo Education app."""

import frappe
import unittest
from frappe.test_runner import make_test_records


class TestInstallation(unittest.TestCase):
    """Test app installation and basic setup."""
    
    def setUp(self):
        """Set up test environment."""
        frappe.set_user("Administrator")
    
    def test_app_installed(self):
        """Test that the app is properly installed."""
        installed_apps = frappe.get_installed_apps()
        self.assertIn("easygo_education", installed_apps)
    
    def test_modules_exist(self):
        """Test that all modules are properly created."""
        expected_modules = [
            "Scolarité",
            "Finances RH", 
            "Administration Comms",
            "Gestion Etablissement",
            "Vie Scolaire",
            "Referentiels"
        ]
        
        for module in expected_modules:
            self.assertTrue(
                frappe.db.exists("Module Def", module),
                f"Module {module} not found"
            )
    
    def test_doctypes_exist(self):
        """Test that core DocTypes are created."""
        core_doctypes = [
            "Student",
            "Employee", 
            "School Class",
            "Fee Bill",
            "Salary Slip",
            "Student Attendance",
            "Academic Year",
            "School Settings"
        ]
        
        for doctype in core_doctypes:
            self.assertTrue(
                frappe.db.exists("DocType", doctype),
                f"DocType {doctype} not found"
            )
    
    def test_roles_created(self):
        """Test that custom roles are created."""
        custom_roles = [
            "Student",
            "Parent", 
            "Teacher",
            "Education Manager",
            "HR Manager",
            "Accounts Manager"
        ]
        
        for role in custom_roles:
            self.assertTrue(
                frappe.db.exists("Role", role),
                f"Role {role} not found"
            )
    
    def test_fixtures_loaded(self):
        """Test that fixtures are properly loaded."""
        # Test desktop icons
        self.assertTrue(
            frappe.db.exists("Desktop Icon", "Students"),
            "Desktop icons not loaded"
        )
        
        # Test letterheads
        self.assertTrue(
            frappe.db.exists("Letter Head", "EasyGo Education Default"),
            "Letterheads not loaded"
        )
    
    def test_reports_exist(self):
        """Test that reports are created."""
        reports = [
            "Student Attendance Report",
            "Payroll Summary Report",
            "Fee Collection Report"
        ]
        
        for report in reports:
            self.assertTrue(
                frappe.db.exists("Report", report),
                f"Report {report} not found"
            )
    
    def test_dashboard_charts_exist(self):
        """Test that dashboard charts are created."""
        charts = [
            "Student Enrollment Chart",
            "Fee Collection Chart",
            "Attendance Chart"
        ]
        
        for chart in charts:
            self.assertTrue(
                frappe.db.exists("Dashboard Chart", chart),
                f"Dashboard Chart {chart} not found"
            )
    
    def test_hooks_configuration(self):
        """Test that hooks are properly configured."""
        from easygo_education import hooks
        
        # Test that hooks module exists and has required attributes
        self.assertTrue(hasattr(hooks, 'app_name'))
        self.assertEqual(hooks.app_name, 'easygo_education')
        
        # Test scheduler events
        self.assertTrue(hasattr(hooks, 'scheduler_events'))
        
        # Test document events
        self.assertTrue(hasattr(hooks, 'doc_events'))
    
    def test_permissions_setup(self):
        """Test that permissions are properly set up."""
        # Test Student permissions for Student role
        student_perms = frappe.get_all("Custom DocPerm", {
            "parent": "Student",
            "role": "Student"
        })
        self.assertTrue(len(student_perms) > 0, "Student permissions not set")
        
        # Test Teacher permissions
        teacher_perms = frappe.get_all("Custom DocPerm", {
            "parent": "Student Attendance", 
            "role": "Teacher"
        })
        self.assertTrue(len(teacher_perms) > 0, "Teacher permissions not set")


def run_installation_tests():
    """Run all installation tests."""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestInstallation)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    unittest.main()
