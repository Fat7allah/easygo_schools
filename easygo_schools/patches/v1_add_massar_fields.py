"""
Patch to add MASSAR custom fields for Moroccan education system integration
This patch checks if fields exist before creating them to avoid duplicates
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

def execute():
    """Add MASSAR integration fields to relevant DocTypes"""
    
    # Define custom fields for Student
    student_fields = [
        {
            "fieldname": "massar_code",
            "fieldtype": "Data",
            "label": "Code MASSAR",
            "insert_after": "student_name",
            "unique": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
            "description": "Code unique MASSAR attribué par le ministère"
        },
        {
            "fieldname": "cne",
            "fieldtype": "Data",
            "label": "CNE (Code National de l'Étudiant)",
            "insert_after": "massar_code",
            "unique": 1,
            "in_standard_filter": 1,
            "description": "Code National de l'Étudiant pour le baccalauréat"
        },
        {
            "fieldname": "cin_number",
            "fieldtype": "Data",
            "label": "Numéro CIN",
            "insert_after": "cne",
            "description": "Numéro de la Carte d'Identité Nationale"
        },
        {
            "fieldname": "birth_certificate_number",
            "fieldtype": "Data",
            "label": "N° Acte de Naissance",
            "insert_after": "date_of_birth",
            "description": "Numéro de l'acte de naissance"
        },
        {
            "fieldname": "birth_place_ar",
            "fieldtype": "Data",
            "label": "مكان الولادة",
            "insert_after": "birth_place",
            "description": "Lieu de naissance en arabe"
        }
    ]
    
    # Define custom fields for Employee
    employee_fields = [
        {
            "fieldname": "ppr_number",
            "fieldtype": "Data",
            "label": "N° PPR",
            "insert_after": "employee_number",
            "unique": 1,
            "description": "Numéro PPR (Personnel)"
        },
        {
            "fieldname": "som_number",
            "fieldtype": "Data",
            "label": "N° SOM",
            "insert_after": "ppr_number",
            "unique": 1,
            "description": "Numéro SOM (Matricule)"
        }
    ]
    
    # Define custom fields for School Class
    school_class_fields = [
        {
            "fieldname": "massar_level_code",
            "fieldtype": "Select",
            "label": "Code Niveau MASSAR",
            "insert_after": "class_name",
            "options": "\nPS\nMS\nGS\n1AP\n2AP\n3AP\n4AP\n5AP\n6AP\n1AC\n2AC\n3AC\nTC\n1BAC\n2BAC",
            "description": "Code du niveau scolaire selon MASSAR"
        }
    ]
    
    # Function to safely create custom field
    def create_field_if_not_exists(dt, field_dict):
        """Create custom field only if it doesn't already exist"""
        try:
            # Check if field already exists
            if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": field_dict["fieldname"]}):
                field_dict["dt"] = dt
                create_custom_field(field_dict)
                print(f"✅ Created custom field {field_dict['fieldname']} for {dt}")
            else:
                print(f"ℹ️ Field {field_dict['fieldname']} already exists in {dt}, skipping...")
        except Exception as e:
            print(f"⚠️ Error creating field {field_dict.get('fieldname', 'unknown')}: {str(e)}")
    
    # Create Student fields
    print("\n📚 Adding MASSAR fields to Student DocType...")
    for field in student_fields:
        create_field_if_not_exists("Student", field)
    
    # Create Employee fields
    print("\n👥 Adding ministry fields to Employee DocType...")
    for field in employee_fields:
        create_field_if_not_exists("Employee", field)
    
    # Create School Class fields
    print("\n🏫 Adding MASSAR level codes to School Class DocType...")
    for field in school_class_fields:
        create_field_if_not_exists("School Class", field)
    
    # Clear cache
    frappe.clear_cache()
    print("\n✅ MASSAR fields patch completed successfully!")
