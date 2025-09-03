"""Add sample communications and notifications."""

import frappe
from frappe.utils import nowdate, add_days


def execute():
    """Create sample communications and notifications."""
    if frappe.db.exists("School Communication", {"subject": "Bienvenue à l'École EasyGo"}):
        return
        
    print("Creating sample communications...")
    
    # Create sample communications
    communications = [
        {
            "subject": "Bienvenue à l'École EasyGo",
            "message": "Chers parents, nous vous souhaitons la bienvenue dans notre établissement pour cette nouvelle année scolaire 2024-2025.",
            "communication_type": "Announcement",
            "priority": "Medium",
            "target_audience": "Parents"
        },
        {
            "subject": "Réunion Parents-Professeurs",
            "message": "Une réunion parents-professeurs aura lieu le 15 octobre 2024 à 18h00 en salle polyvalente.",
            "communication_type": "Meeting",
            "priority": "High",
            "target_audience": "Parents"
        },
        {
            "subject": "Sortie Pédagogique - Musée",
            "message": "Les élèves de CP et CE1 participeront à une sortie pédagogique au Musée des Sciences le 20 novembre 2024.",
            "communication_type": "Event",
            "priority": "Medium",
            "target_audience": "Parents"
        }
    ]
    
    for comm_data in communications:
        communication = frappe.get_doc({
            "doctype": "School Communication",
            "subject": comm_data["subject"],
            "message": comm_data["message"],
            "communication_type": comm_data["communication_type"],
            "priority": comm_data["priority"],
            "target_audience": comm_data["target_audience"],
            "send_date": nowdate(),
            "status": "Sent"
        })
        communication.insert(ignore_permissions=True)
    
    # Create sample communication logs
    students = frappe.get_all("Student", {"enabled": 1}, ["name", "student_name"])
    
    for student in students[:3]:  # Limit to first 3 students
        log = frappe.get_doc({
            "doctype": "Communication Log",
            "communication_type": "SMS",
            "channel": "SMS",
            "recipient": f"parent_{student.name}@example.com",
            "subject": "Notification de présence",
            "message": f"Votre enfant {student.student_name} est bien arrivé à l'école aujourd'hui.",
            "sent_date": nowdate(),
            "status": "Delivered"
        })
        log.insert(ignore_permissions=True)
        log.submit()
    
    print("Sample communications created successfully")
