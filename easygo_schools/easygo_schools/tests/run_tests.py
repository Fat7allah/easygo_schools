"""Test runner for EasyGo Education app."""

import frappe
import unittest
import sys
import os


def run_all_tests():
    """Run all tests for the EasyGo Education app."""
    
    # Set up test environment
    frappe.init(site="test_site")
    frappe.connect()
    frappe.set_user("Administrator")
    
    print("=" * 60)
    print("EASYGO EDUCATION - COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    
    # Test modules to run
    test_modules = [
        'test_installation',
        'test_student', 
        'test_fee_bill',
        'test_export_import',
        'test_portal',
        'test_reports'
    ]
    
    # E2E tests
    e2e_modules = [
        'e2e.test_student_workflow'
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    # Run unit tests
    print("\n🧪 RUNNING UNIT TESTS")
    print("-" * 40)
    
    for module in test_modules:
        try:
            print(f"\n📋 Running {module}...")
            
            # Import and run test module
            test_module = __import__(f'easygo_education.tests.{module}', fromlist=[''])
            
            # Load test suite
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromModule(test_module)
            
            # Run tests
            runner = unittest.TextTestRunner(verbosity=1, stream=sys.stdout)
            result = runner.run(suite)
            
            # Update counters
            total_tests += result.testsRun
            passed_tests += result.testsRun - len(result.failures) - len(result.errors)
            failed_tests += len(result.failures) + len(result.errors)
            
            if result.wasSuccessful():
                print(f"✅ {module}: PASSED ({result.testsRun} tests)")
            else:
                print(f"❌ {module}: FAILED ({len(result.failures + result.errors)} failures)")
                
        except Exception as e:
            print(f"❌ {module}: ERROR - {str(e)}")
            failed_tests += 1
    
    # Run E2E tests
    print("\n🔄 RUNNING END-TO-END TESTS")
    print("-" * 40)
    
    for module in e2e_modules:
        try:
            print(f"\n📋 Running {module}...")
            
            # Import and run E2E test module
            test_module = __import__(f'easygo_education.tests.{module}', fromlist=[''])
            
            # Load test suite
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromModule(test_module)
            
            # Run tests
            runner = unittest.TextTestRunner(verbosity=1, stream=sys.stdout)
            result = runner.run(suite)
            
            # Update counters
            total_tests += result.testsRun
            passed_tests += result.testsRun - len(result.failures) - len(result.errors)
            failed_tests += len(result.failures) + len(result.errors)
            
            if result.wasSuccessful():
                print(f"✅ {module}: PASSED ({result.testsRun} tests)")
            else:
                print(f"❌ {module}: FAILED ({len(result.failures + result.errors)} failures)")
                
        except Exception as e:
            print(f"❌ {module}: ERROR - {str(e)}")
            failed_tests += 1
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
    
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    print(f"Success Rate: {success_rate:.1f}%")
    
    if failed_tests == 0:
        print("\n🎉 ALL TESTS PASSED! EasyGo Education is ready for production.")
        return True
    else:
        print(f"\n⚠️  {failed_tests} tests failed. Please review and fix issues.")
        return False


def run_specific_test(test_name):
    """Run a specific test module."""
    
    frappe.init(site="test_site")
    frappe.connect()
    frappe.set_user("Administrator")
    
    print(f"Running specific test: {test_name}")
    
    try:
        # Import test module
        if 'e2e' in test_name:
            test_module = __import__(f'easygo_education.tests.{test_name}', fromlist=[''])
        else:
            test_module = __import__(f'easygo_education.tests.{test_name}', fromlist=[''])
        
        # Load and run test suite
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(test_module)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        return result.wasSuccessful()
        
    except Exception as e:
        print(f"Error running test {test_name}: {str(e)}")
        return False


def run_installation_check():
    """Quick installation verification."""
    
    frappe.init(site="test_site")
    frappe.connect()
    frappe.set_user("Administrator")
    
    print("🔍 QUICK INSTALLATION CHECK")
    print("-" * 40)
    
    checks = [
        ("App installed", lambda: "easygo_education" in frappe.get_installed_apps()),
        ("Modules exist", lambda: frappe.db.exists("Module Def", "Scolarité")),
        ("DocTypes exist", lambda: frappe.db.exists("DocType", "Student")),
        ("Roles created", lambda: frappe.db.exists("Role", "Student")),
        ("Reports exist", lambda: frappe.db.exists("Report", "Student Attendance Report")),
        ("Fixtures loaded", lambda: frappe.db.exists("Desktop Icon", "Students"))
    ]
    
    passed = 0
    total = len(checks)
    
    for check_name, check_func in checks:
        try:
            if check_func():
                print(f"✅ {check_name}")
                passed += 1
            else:
                print(f"❌ {check_name}")
        except Exception as e:
            print(f"❌ {check_name}: {str(e)}")
    
    print(f"\nInstallation Check: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "check":
            run_installation_check()
        else:
            run_specific_test(sys.argv[1])
    else:
        run_all_tests()
