"""Setup demo data for EasyGo Education."""

import frappe
from frappe import _


def execute():
    """Execute demo data setup."""
    if frappe.db.get_single_value("System Settings", "setup_complete"):
        return
    
    # Create basic academic year
    create_academic_year()
    
    # Create sample subjects
    create_subjects()
    
    # Create sample classes
    create_classes()
    
    # Create sample fee types
    create_fee_types()
    
    # Create sample rooms
    create_rooms()
    
    # Create sample activities
    create_activities()
    
    frappe.db.commit()


def create_academic_year():
    """Create current academic year."""
    if not frappe.db.exists("Academic Year", "2024-2025"):
        academic_year = frappe.get_doc({
            "doctype": "Academic Year",
            "academic_year_name": "2024-2025",
            "year_start_date": "2024-09-01",
            "year_end_date": "2025-06-30"
        })
        academic_year.insert(ignore_permissions=True)


def create_subjects():
    """Create sample subjects."""
    subjects = [
        {"subject_name": "Mathématiques", "subject_code": "MATH"},
        {"subject_name": "Français", "subject_code": "FR"},
        {"subject_name": "العربية", "subject_code": "AR"},
        {"subject_name": "Sciences", "subject_code": "SCI"},
        {"subject_name": "Histoire-Géographie", "subject_code": "HG"},
        {"subject_name": "Anglais", "subject_code": "EN"},
        {"subject_name": "Éducation Physique", "subject_code": "EP"},
        {"subject_name": "Arts Plastiques", "subject_code": "ART"}
    ]
    
    for subject_data in subjects:
        if not frappe.db.exists("Subject", subject_data["subject_name"]):
            subject = frappe.get_doc({
                "doctype": "Subject",
                **subject_data
            })
            subject.insert(ignore_permissions=True)


def create_classes():
    """Create sample classes."""
    classes = [
        {"class_name": "CP", "class_numeric": 1},
        {"class_name": "CE1", "class_numeric": 2},
        {"class_name": "CE2", "class_numeric": 3},
        {"class_name": "CM1", "class_numeric": 4},
        {"class_name": "CM2", "class_numeric": 5},
        {"class_name": "6ème", "class_numeric": 6},
        {"class_name": "5ème", "class_numeric": 7},
        {"class_name": "4ème", "class_numeric": 8},
        {"class_name": "3ème", "class_numeric": 9}
    ]
    
    for class_data in classes:
        if not frappe.db.exists("School Class", class_data["class_name"]):
            school_class = frappe.get_doc({
                "doctype": "School Class",
                **class_data
            })
            school_class.insert(ignore_permissions=True)


def create_fee_types():
    """Create sample fee types."""
    fee_types = [
        {
            "fee_type_name": "Frais de scolarité",
            "category": "Tuition",
            "default_amount": 2000,
            "frequency": "Monthly",
            "is_mandatory": 1
        },
        {
            "fee_type_name": "Transport scolaire",
            "category": "Transport",
            "default_amount": 300,
            "frequency": "Monthly",
            "is_mandatory": 0
        },
        {
            "fee_type_name": "Cantine",
            "category": "Meals",
            "default_amount": 400,
            "frequency": "Monthly",
            "is_mandatory": 0
        },
        {
            "fee_type_name": "Activités parascolaires",
            "category": "Activities",
            "default_amount": 150,
            "frequency": "Semester",
            "is_mandatory": 0
        }
    ]
    
    for fee_data in fee_types:
        if not frappe.db.exists("Fee Type", fee_data["fee_type_name"]):
            fee_type = frappe.get_doc({
                "doctype": "Fee Type",
                **fee_data
            })
            fee_type.insert(ignore_permissions=True)


def create_rooms():
    """Create sample rooms."""
    rooms = [
        {"room_name": "Salle 101", "room_type": "Classroom", "capacity": 30},
        {"room_name": "Salle 102", "room_type": "Classroom", "capacity": 30},
        {"room_name": "Laboratoire Sciences", "room_type": "Laboratory", "capacity": 25},
        {"room_name": "Salle Informatique", "room_type": "Computer Lab", "capacity": 20},
        {"room_name": "Bibliothèque", "room_type": "Library", "capacity": 50},
        {"room_name": "Gymnase", "room_type": "Gymnasium", "capacity": 100},
        {"room_name": "Salle de Musique", "room_type": "Music Room", "capacity": 25},
        {"room_name": "Salle des Professeurs", "room_type": "Staff Room", "capacity": 15}
    ]
    
    for room_data in rooms:
        if not frappe.db.exists("Room", room_data["room_name"]):
            room = frappe.get_doc({
                "doctype": "Room",
                **room_data
            })
            room.insert(ignore_permissions=True)


def create_activities():
    """Create sample extracurricular activities."""
    activities = [
        {
            "activity_name": "Club de Football",
            "activity_type": "Sports",
            "description": "Entraînement et matchs de football",
            "max_participants": 20,
            "age_group": "All Ages"
        },
        {
            "activity_name": "Club de Théâtre",
            "activity_type": "Drama",
            "description": "Ateliers de théâtre et représentations",
            "max_participants": 15,
            "age_group": "Middle School"
        },
        {
            "activity_name": "Club de Sciences",
            "activity_type": "Science Club",
            "description": "Expériences et projets scientifiques",
            "max_participants": 12,
            "age_group": "High School"
        },
        {
            "activity_name": "Chorale",
            "activity_type": "Music",
            "description": "Chant choral et spectacles musicaux",
            "max_participants": 25,
            "age_group": "All Ages"
        }
    ]
    
    for activity_data in activities:
        if not frappe.db.exists("Extracurricular Activity", activity_data["activity_name"]):
            activity = frappe.get_doc({
                "doctype": "Extracurricular Activity",
                **activity_data
            })
            activity.insert(ignore_permissions=True)
