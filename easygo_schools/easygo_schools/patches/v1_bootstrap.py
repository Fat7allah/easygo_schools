"""Bootstrap patch for EasyGo Education v1.0."""

import frappe
from frappe import _
from frappe.utils import nowdate, add_days, add_months, getdate


def execute():
    """Execute bootstrap patch - creates initial demo data."""
    # Check if patch already executed using a different marker
    if frappe.db.exists("School Settings", "School Settings"):
        # Patch already executed
        return
    
    print("Executing EasyGo Education bootstrap patch...")
    
    try:
        # Create demo data in order (skip Academic Year dependent functions)
        create_school_settings()
        # create_academic_years()  # Disabled - Academic Year moved to Education app in v15
        create_programs_and_subjects()
        # create_fee_structures()  # Disabled - depends on Academic Year
        create_salary_structures()
        create_demo_employees()
        # create_demo_classes()  # Disabled - depends on Academic Year
        # create_demo_students()  # Disabled - depends on Academic Year
        # create_sample_attendance()  # Disabled - depends on students
        # create_sample_fees()  # Disabled - depends on students
        
        frappe.db.commit()
        print("Bootstrap patch executed successfully")
        
    except Exception as e:
        frappe.db.rollback()
        print(f"Bootstrap patch failed: {str(e)}")
        raise


def create_school_settings():
    """Create initial school settings."""
    if not frappe.db.exists("School Settings", "School Settings"):
        settings = frappe.get_doc({
            "doctype": "School Settings",
            "school_name": "École Démonstration EasyGo",
            "school_abbreviation": "EDE",
            "address": "123 Rue de l'Éducation, Casablanca, Maroc",
            "phone": "+212 522 123 456",
            "email": "contact@easygo-demo.ma",
            "website": "www.easygo-demo.ma",
            "academic_year_start_month": "September",
            "default_currency": "MAD",
            "language": "fr",
            "time_zone": "Africa/Casablanca"
        })
        settings.insert(ignore_permissions=True)


def create_academic_years():
    """Create academic years and terms - DISABLED for Frappe v15."""
    # Academic Year DocType moved to Education app in Frappe v15
    # This function is disabled to prevent import errors
    print("Academic Year creation skipped - DocType moved to Education app in v15")
    return


def create_programs_and_subjects():
    """Create educational programs and subjects."""
    # Create programs
    programs = [
        {"name": "Primaire", "description": "Enseignement Primaire"},
        {"name": "Collège", "description": "Enseignement Collégial"},
        {"name": "Lycée", "description": "Enseignement Secondaire"}
    ]
    
    for prog_data in programs:
        if not frappe.db.exists("Program", prog_data["name"]):
            program = frappe.get_doc({
                "doctype": "Program",
                "program_name": prog_data["name"],
                "description": prog_data["description"]
            })
            program.insert(ignore_permissions=True)
    
    # Create subjects
    subjects = [
        "Mathématiques", "Français", "Arabe", "Sciences", "Histoire-Géographie",
        "Anglais", "Éducation Physique", "Arts Plastiques", "Musique", "Informatique",
        "Physique-Chimie", "Sciences de la Vie et de la Terre", "Philosophie"
    ]
    
    for subject_name in subjects:
        if not frappe.db.exists("Subject", subject_name):
            subject = frappe.get_doc({
                "doctype": "Subject",
                "subject_name": subject_name,
                "subject_code": subject_name[:3].upper()
            })
            subject.insert(ignore_permissions=True)


def create_fee_structures():
    """Create fee structures."""
    fee_types = [
        {"name": "Frais de Scolarité", "amount": 5000},
        {"name": "Frais d'Inscription", "amount": 1000},
        {"name": "Frais de Transport", "amount": 800},
        {"name": "Frais de Cantine", "amount": 600},
        {"name": "Frais d'Activités", "amount": 300}
    ]
    
    for fee_data in fee_types:
        if not frappe.db.exists("Fee Type", fee_data["name"]):
            fee_type = frappe.get_doc({
                "doctype": "Fee Type",
                "fee_type_name": fee_data["name"],
                "description": f"Frais pour {fee_data['name']}"
            })
            fee_type.insert(ignore_permissions=True)
            # Fee structure creation disabled - depends on Academic Year
            print("Fee structure creation skipped - depends on Academic Year DocType")


def create_salary_structures():
    """Create salary structures."""
    # Create salary components
    components = [
        {"name": "Salaire de Base", "type": "Earning", "amount": 8000},
        {"name": "Prime de Transport", "type": "Earning", "amount": 500},
        {"name": "Prime de Responsabilité", "type": "Earning", "amount": 1000},
        {"name": "Cotisations Sociales", "type": "Deduction", "amount": 800},
        {"name": "Impôt sur le Revenu", "type": "Deduction", "amount": 1200}
    ]
    
    for comp_data in components:
        if not frappe.db.exists("Salary Component", comp_data["name"]):
            component = frappe.get_doc({
                "doctype": "Salary Component",
                "salary_component": comp_data["name"],
                "type": comp_data["type"],
                "amount_based_on_formula": 0
            })
            component.insert(ignore_permissions=True)
    
    # Create salary structure
    if not frappe.db.exists("Salary Structure", "Structure Enseignant 2024"):
        salary_structure = frappe.get_doc({
            "doctype": "Salary Structure",
            "name": "Structure Enseignant 2024",
            "is_active": "Yes",
            "from_date": "2024-09-01",
            "earnings": [
                {"salary_component": "Salaire de Base", "amount": 8000},
                {"salary_component": "Prime de Transport", "amount": 500}
            ],
            "deductions": [
                {"salary_component": "Cotisations Sociales", "amount": 800},
                {"salary_component": "Impôt sur le Revenu", "amount": 1200}
            ]
        })
        salary_structure.insert(ignore_permissions=True)


def create_demo_employees():
    """Create demo employees."""
    employees = [
        {
            "name": "Ahmed Bennani",
            "designation": "Directeur",
            "department": "Administration",
            "email": "ahmed.bennani@easygo-demo.ma",
            "phone": "+212 661 123 456"
        },
        {
            "name": "Fatima Alaoui",
            "designation": "Enseignante Primaire",
            "department": "Enseignement",
            "email": "fatima.alaoui@easygo-demo.ma",
            "phone": "+212 662 234 567"
        },
        {
            "name": "Mohamed Tazi",
            "designation": "Enseignant Mathématiques",
            "department": "Enseignement",
            "email": "mohamed.tazi@easygo-demo.ma",
            "phone": "+212 663 345 678"
        },
        {
            "name": "Aicha Idrissi",
            "designation": "Secrétaire",
            "department": "Administration",
            "email": "aicha.idrissi@easygo-demo.ma",
            "phone": "+212 664 456 789"
        }
    ]
    
    for emp_data in employees:
        if not frappe.db.exists("Employee", {"employee_name": emp_data["name"]}):
            employee = frappe.get_doc({
                "doctype": "Employee",
                "employee_name": emp_data["name"],
                "designation": emp_data["designation"],
                "department": emp_data["department"],
                "personal_email": emp_data["email"],
                "cell_number": emp_data["phone"],
                "status": "Active",
                "date_of_joining": "2024-09-01"
            })
            employee.insert(ignore_permissions=True)


def create_demo_classes():
    """Create demo classes."""
    classes = [
        {"name": "CP-A", "program": "Primaire", "capacity": 25, "teacher": "Fatima Alaoui"},
        {"name": "CE1-A", "program": "Primaire", "capacity": 25, "teacher": "Fatima Alaoui"},
        {"name": "6ème-A", "program": "Collège", "capacity": 30, "teacher": "Mohamed Tazi"},
        {"name": "5ème-A", "program": "Collège", "capacity": 30, "teacher": "Mohamed Tazi"}
    ]
    
    for class_data in classes:
        if not frappe.db.exists("School Class", class_data["name"]):
            school_class = frappe.get_doc({
                "doctype": "School Class",
                "class_name": class_data["name"],
                "program": class_data["program"],
                "academic_year": "2024-2025",
                "max_strength": class_data["capacity"],
                "class_teacher": class_data["teacher"]
            })
            school_class.insert(ignore_permissions=True)


def create_demo_students():
    """Create demo students."""
    students = [
        {"name": "Youssef Amrani", "class": "CP-A", "gender": "Male", "dob": "2018-03-15"},
        {"name": "Lina Benjelloun", "class": "CP-A", "gender": "Female", "dob": "2018-05-22"},
        {"name": "Omar Fassi", "class": "CE1-A", "gender": "Male", "dob": "2017-08-10"},
        {"name": "Salma Kettani", "class": "CE1-A", "gender": "Female", "dob": "2017-11-03"},
        {"name": "Amine Berrada", "class": "6ème-A", "gender": "Male", "dob": "2012-01-18"},
        {"name": "Nour Lahlou", "class": "6ème-A", "gender": "Female", "dob": "2012-04-25"},
        {"name": "Karim Sebti", "class": "5ème-A", "gender": "Male", "dob": "2011-07-12"},
        {"name": "Meryem Chraibi", "class": "5ème-A", "gender": "Female", "dob": "2011-09-30"}
    ]
    
    for student_data in students:
        if not frappe.db.exists("Student", {"student_name": student_data["name"]}):
            student = frappe.get_doc({
                "doctype": "Student",
                "student_name": student_data["name"],
                "gender": student_data["gender"],
                "date_of_birth": student_data["dob"],
                "enabled": 1,
                "joining_date": "2024-09-01"
            })
            student.insert(ignore_permissions=True)
            
            # Enroll student in class
            enrollment = frappe.get_doc({
                "doctype": "Student Enrollment",
                "student": student.name,
                "academic_year": "2024-2025",
                "program": "Primaire" if "CP" in student_data["class"] or "CE" in student_data["class"] else "Collège",
                "school_class": student_data["class"],
                "enrollment_date": "2024-09-01"
            })
            enrollment.insert(ignore_permissions=True)


def create_sample_attendance():
    """Create sample attendance records."""
    # Get all students
    students = frappe.get_all("Student", {"enabled": 1}, ["name", "student_name"])
    
    # Create attendance for the last 30 days
    import random
    from datetime import datetime, timedelta
    
    start_date = datetime.now() - timedelta(days=30)
    
    for i in range(30):
        current_date = start_date + timedelta(days=i)
        
        # Skip weekends
        if current_date.weekday() >= 5:
            continue
            
        for student in students[:6]:  # Limit to first 6 students
            # 90% attendance rate
            status = "Present" if random.random() < 0.9 else "Absent"
            
            if not frappe.db.exists("Student Attendance", {
                "student": student.name,
                "attendance_date": current_date.date()
            }):
                attendance = frappe.get_doc({
                    "doctype": "Student Attendance",
                    "student": student.name,
                    "student_name": student.student_name,
                    "attendance_date": current_date.date(),
                    "status": status,
                    "academic_year": "2024-2025"
                })
                attendance.insert(ignore_permissions=True)
                attendance.submit()


def create_sample_fees():
    """Create sample fee bills."""
    # Get enrolled students
    enrollments = frappe.get_all("Student Enrollment", 
        {"academic_year": "2024-2025"}, 
        ["student", "student_name", "program"])
    
    for enrollment in enrollments[:4]:  # Limit to first 4 students
        if not frappe.db.exists("Fee Bill", {"student": enrollment.student, "academic_year": "2024-2025"}):
            fee_bill = frappe.get_doc({
                "doctype": "Fee Bill",
                "student": enrollment.student,
                "student_name": enrollment.student_name,
                "academic_year": "2024-2025",
                "program": enrollment.program,
                "posting_date": nowdate(),
                "due_date": add_days(nowdate(), 30),
                "fee_items": [
                    {"fee_type": "Frais de Scolarité", "amount": 5000, "quantity": 1, "total_amount": 5000},
                    {"fee_type": "Frais d'Inscription", "amount": 1000, "quantity": 1, "total_amount": 1000}
                ],
                "total_amount": 6000,
                "status": "Unpaid"
            })
            fee_bill.insert(ignore_permissions=True)
