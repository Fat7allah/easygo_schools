"""Add sample assessments and grades."""

import frappe
from frappe.utils import nowdate, add_days
import random


def execute():
    """Create sample assessments and grades."""
    if frappe.db.exists("Student Assessment", {"assessment_name": "Évaluation Trimestre 1"}):
        return
        
    print("Creating sample assessments...")
    
    # Get students and subjects
    students = frappe.get_all("Student", {"enabled": 1}, ["name", "student_name"])
    subjects = ["Mathématiques", "Français", "Sciences", "Histoire-Géographie"]
    
    # Create sample assessments
    for i, student in enumerate(students[:4]):  # Limit to first 4 students
        assessment = frappe.get_doc({
            "doctype": "Student Assessment",
            "student": student.name,
            "student_name": student.student_name,
            "academic_year": "2024-2025",
            "assessment_name": f"Évaluation Trimestre 1 - {student.student_name}",
            "assessment_date": nowdate(),
            "assessment_period": "Trimestre 1",
            "total_score": 0,
            "total_max_score": 0,
            "assessment_details": []
        })
        
        total_score = 0
        total_max_score = 0
        
        # Add subject scores
        for subject in subjects:
            max_score = 20
            # Generate realistic scores (70-95% range)
            score = round(random.uniform(14, 19), 1)
            
            assessment.append("assessment_details", {
                "subject": subject,
                "score": score,
                "max_score": max_score,
                "grade": get_grade(score, max_score),
                "remarks": get_remarks(score, max_score)
            })
            
            total_score += score
            total_max_score += max_score
        
        assessment.total_score = total_score
        assessment.total_max_score = total_max_score
        assessment.percentage = (total_score / total_max_score) * 100 if total_max_score > 0 else 0
        
        assessment.insert(ignore_permissions=True)
        assessment.submit()
    
    print("Sample assessments created successfully")


def get_grade(score, max_score):
    """Get grade based on percentage."""
    percentage = (score / max_score) * 100 if max_score > 0 else 0
    
    if percentage >= 90:
        return "Excellent"
    elif percentage >= 80:
        return "Très Bien"
    elif percentage >= 70:
        return "Bien"
    elif percentage >= 60:
        return "Assez Bien"
    elif percentage >= 50:
        return "Passable"
    else:
        return "Insuffisant"


def get_remarks(score, max_score):
    """Get remarks based on performance."""
    percentage = (score / max_score) * 100 if max_score > 0 else 0
    
    if percentage >= 90:
        return "Excellent travail, continuez ainsi!"
    elif percentage >= 80:
        return "Très bon niveau, félicitations."
    elif percentage >= 70:
        return "Bon travail, peut encore s'améliorer."
    elif percentage >= 60:
        return "Travail satisfaisant, des efforts à poursuivre."
    else:
        return "Doit fournir plus d'efforts."
