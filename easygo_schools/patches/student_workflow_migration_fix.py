import frappe

def execute():
    """Fix Student workflow migration issues"""

    # Check if there are any existing Student documents
    students = frappe.get_all("Student", fields=["name", "docstatus", "workflow_state"])

    if students:
        print(f"Found {len(students)} existing Student documents")

        for student in students:
            # If document is submitted but has no workflow state, set it to Draft
            if student.docstatus == 1 and not student.workflow_state:
                print(f"Fixing submitted student {student.name}")
                frappe.db.set_value("Student", student.name, "workflow_state", "Draft")
                frappe.db.set_value("Student", student.name, "docstatus", 0)

            # If document has workflow_state but it's not in our defined states
            elif student.workflow_state and student.workflow_state not in ["Draft", "Under Review", "Approved", "Rejected"]:
                print(f"Fixing student {student.name} with invalid workflow state: {student.workflow_state}")
                frappe.db.set_value("Student", student.name, "workflow_state", "Draft")

        frappe.db.commit()
        print("Student workflow migration fix completed")
    else:
        print("No existing Student documents found - workflow should work normally")
