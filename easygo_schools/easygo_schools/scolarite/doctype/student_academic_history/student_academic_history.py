"""Student Academic History doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, getdate, flt


class StudentAcademicHistory(Document):
    """Student Academic History doctype controller."""
    
    def validate(self):
        """Validate student academic history data."""
        self.validate_dates()
        self.calculate_metrics()
        self.set_defaults()
    
    def validate_dates(self):
        """Validate enrollment and completion dates."""
        if self.enrollment_date and self.completion_date:
            if getdate(self.enrollment_date) >= getdate(self.completion_date):
                frappe.throw(_("Completion date must be after enrollment date"))
    
    def calculate_metrics(self):
        """Calculate academic metrics."""
        # Calculate attendance percentage
        if self.total_days and self.days_present:
            self.attendance_percentage = (self.days_present / self.total_days) * 100
        
        # Calculate subjects failed
        if self.total_subjects and self.subjects_passed:
            self.subjects_failed = self.total_subjects - self.subjects_passed
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
        
        # Fetch student details
        if self.student and not self.student_name:
            student_doc = frappe.get_doc("Student", self.student)
            self.student_name = student_doc.student_name
            
            if not self.program:
                self.program = student_doc.program
            if not self.school_class:
                self.school_class = student_doc.school_class
    
    def before_insert(self):
        """Actions before inserting new record."""
        self.populate_academic_data()
    
    def populate_academic_data(self):
        """Populate academic data from existing records."""
        if not (self.student and self.academic_year):
            return
        
        try:
            # Get grades for this student and academic year
            grades = frappe.get_list("Grade",
                filters={
                    "student": self.student,
                    "academic_year": self.academic_year
                },
                fields=["subject", "percentage", "letter_grade", "status"]
            )
            
            if grades:
                self.total_subjects = len(grades)
                self.subjects_passed = len([g for g in grades if g.status == "Pass"])
                self.overall_percentage = sum([g.percentage or 0 for g in grades]) / len(grades)
                
                # Determine overall grade based on grading scale
                if self.overall_percentage:
                    grading_scale = frappe.db.get_value("Program", self.program, "grading_scale")
                    if grading_scale:
                        scale_doc = frappe.get_doc("Grading Scale", grading_scale)
                        grade_result = scale_doc.calculate_grade(self.overall_percentage)
                        self.overall_grade = grade_result.get("letter_grade")
            
            # Get attendance data
            attendance_data = frappe.db.sql("""
                SELECT 
                    COUNT(*) as total_days,
                    COUNT(CASE WHEN status = 'Present' THEN 1 END) as days_present,
                    COUNT(CASE WHEN status = 'Absent' THEN 1 END) as days_absent
                FROM `tabStudent Attendance`
                WHERE student = %s AND academic_year = %s
            """, (self.student, self.academic_year))
            
            if attendance_data and attendance_data[0]:
                self.total_days = attendance_data[0][0]
                self.days_present = attendance_data[0][1]
                self.days_absent = attendance_data[0][2]
            
            # Get disciplinary actions count
            self.disciplinary_actions = frappe.db.count("Disciplinary Action", {
                "student": self.student,
                "academic_year": self.academic_year
            })
            
        except Exception as e:
            frappe.log_error(f"Failed to populate academic data: {str(e)}")
    
    @frappe.whitelist()
    def generate_transcript(self):
        """Generate academic transcript."""
        transcript = {
            "student_info": {
                "name": self.student_name,
                "student_id": self.student,
                "academic_year": self.academic_year,
                "program": self.program,
                "class": self.school_class
            },
            "academic_performance": {
                "total_subjects": self.total_subjects,
                "subjects_passed": self.subjects_passed,
                "subjects_failed": self.subjects_failed,
                "overall_percentage": self.overall_percentage,
                "overall_grade": self.overall_grade
            },
            "attendance": {
                "total_days": self.total_days,
                "days_present": self.days_present,
                "days_absent": self.days_absent,
                "attendance_percentage": self.attendance_percentage
            },
            "subjects": [],
            "activities": {
                "extracurricular": self.extracurricular_activities,
                "achievements": self.special_achievements,
                "awards": self.awards_recognition
            }
        }
        
        # Get detailed subject grades
        grades = frappe.get_list("Grade",
            filters={
                "student": self.student,
                "academic_year": self.academic_year
            },
            fields=["subject", "percentage", "letter_grade", "status", "assessment_type"]
        )
        
        for grade in grades:
            subject_info = frappe.db.get_value("Subject", grade.subject, 
                ["subject_name", "subject_code"], as_dict=True)
            
            transcript["subjects"].append({
                "subject_code": subject_info.subject_code if subject_info else "",
                "subject_name": subject_info.subject_name if subject_info else grade.subject,
                "percentage": grade.percentage,
                "letter_grade": grade.letter_grade,
                "status": grade.status
            })
        
        return transcript
    
    @frappe.whitelist()
    def get_performance_trend(self):
        """Get performance trend over terms."""
        if not self.academic_year:
            return []
        
        trend_data = frappe.db.sql("""
            SELECT 
                at.term_name,
                AVG(g.percentage) as avg_percentage,
                COUNT(g.name) as total_grades
            FROM `tabGrade` g
            INNER JOIN `tabAcademic Term` at ON g.academic_term = at.name
            WHERE g.student = %s 
                AND g.academic_year = %s
            GROUP BY g.academic_term, at.term_name
            ORDER BY at.term_start_date
        """, (self.student, self.academic_year), as_dict=True)
        
        return trend_data
    
    @frappe.whitelist()
    def compare_with_class_average(self):
        """Compare student performance with class average."""
        if not (self.school_class and self.academic_year):
            return {}
        
        class_avg_data = frappe.db.sql("""
            SELECT 
                AVG(sah.overall_percentage) as class_avg_percentage,
                AVG(sah.attendance_percentage) as class_avg_attendance,
                COUNT(*) as total_students
            FROM `tabStudent Academic History` sah
            WHERE sah.school_class = %s 
                AND sah.academic_year = %s
                AND sah.name != %s
        """, (self.school_class, self.academic_year, self.name), as_dict=True)
        
        if class_avg_data and class_avg_data[0]:
            comparison = class_avg_data[0]
            comparison.update({
                "student_percentage": self.overall_percentage,
                "student_attendance": self.attendance_percentage,
                "performance_difference": (self.overall_percentage or 0) - (comparison.class_avg_percentage or 0),
                "attendance_difference": (self.attendance_percentage or 0) - (comparison.class_avg_attendance or 0)
            })
            return comparison
        
        return {}
    
    @frappe.whitelist()
    def update_promotion_status(self, promoted_to_class=None, remarks=None):
        """Update promotion status."""
        if promoted_to_class:
            self.promoted_to_class = promoted_to_class
            self.status = "Promoted"
        else:
            self.status = "Repeated"
        
        if remarks:
            self.remarks = (self.remarks or "") + f"\nPromotion Decision: {remarks}"
        
        self.save()
        
        return True
