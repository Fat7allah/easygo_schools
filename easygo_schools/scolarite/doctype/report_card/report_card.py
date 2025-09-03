"""Report Card DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, flt


class ReportCard(Document):
    """Report Card management."""
    
    def validate(self):
        """Validate report card data."""
        self.validate_academic_period()
        self.calculate_totals()
        self.calculate_attendance()
        self.determine_promotion_status()
    
    def validate_academic_period(self):
        """Validate academic year and term."""
        if self.academic_year and self.academic_term:
            # Check if term belongs to the academic year
            term_doc = frappe.get_doc("Academic Term", self.academic_term)
            if term_doc.academic_year != self.academic_year:
                frappe.throw(_("Academic term does not belong to the selected academic year"))
    
    def calculate_totals(self):
        """Calculate total marks, obtained marks, and overall percentage."""
        total_marks = 0
        obtained_marks = 0
        total_grade_points = 0
        subject_count = 0
        
        for subject in self.subjects:
            if subject.total_marks and subject.obtained_marks:
                total_marks += flt(subject.total_marks)
                obtained_marks += flt(subject.obtained_marks)
                
                # Calculate grade points (assuming 4.0 scale)
                percentage = (flt(subject.obtained_marks) / flt(subject.total_marks)) * 100
                grade_point = self.percentage_to_grade_point(percentage)
                subject.grade_point = grade_point
                total_grade_points += grade_point
                subject_count += 1
        
        self.total_marks = total_marks
        self.obtained_marks = obtained_marks
        
        if total_marks > 0:
            self.overall_percentage = (obtained_marks / total_marks) * 100
            self.overall_grade = self.percentage_to_grade(self.overall_percentage)
        
        if subject_count > 0:
            self.grade_point_average = total_grade_points / subject_count
    
    def calculate_attendance(self):
        """Calculate attendance statistics."""
        if not self.student or not self.academic_term:
            return
        
        # Get attendance data for the term
        term_doc = frappe.get_doc("Academic Term", self.academic_term)
        
        attendance_data = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_days,
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days,
                SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days
            FROM `tabStudent Attendance`
            WHERE student = %s
            AND attendance_date BETWEEN %s AND %s
        """, [self.student, term_doc.term_start_date, term_doc.term_end_date], as_dict=True)
        
        if attendance_data and attendance_data[0].total_days:
            data = attendance_data[0]
            self.days_present = data.present_days or 0
            self.days_absent = data.absent_days or 0
            
            if data.total_days > 0:
                self.attendance_percentage = (self.days_present / data.total_days) * 100
    
    def determine_promotion_status(self):
        """Determine promotion status based on grades."""
        if not self.promotion_status and self.overall_percentage:
            if self.overall_percentage >= 75:
                self.promotion_status = "Promoted"
            elif self.overall_percentage >= 50:
                self.promotion_status = "Conditional Promotion"
            else:
                self.promotion_status = "Retained"
    
    def percentage_to_grade(self, percentage):
        """Convert percentage to letter grade."""
        if percentage >= 90:
            return "A+"
        elif percentage >= 85:
            return "A"
        elif percentage >= 80:
            return "A-"
        elif percentage >= 75:
            return "B+"
        elif percentage >= 70:
            return "B"
        elif percentage >= 65:
            return "B-"
        elif percentage >= 60:
            return "C+"
        elif percentage >= 55:
            return "C"
        elif percentage >= 50:
            return "C-"
        else:
            return "F"
    
    def percentage_to_grade_point(self, percentage):
        """Convert percentage to grade point (4.0 scale)."""
        if percentage >= 90:
            return 4.0
        elif percentage >= 85:
            return 3.7
        elif percentage >= 80:
            return 3.3
        elif percentage >= 75:
            return 3.0
        elif percentage >= 70:
            return 2.7
        elif percentage >= 65:
            return 2.3
        elif percentage >= 60:
            return 2.0
        elif percentage >= 55:
            return 1.7
        elif percentage >= 50:
            return 1.0
        else:
            return 0.0
    
    def on_submit(self):
        """Actions on submit."""
        self.calculate_class_rank()
        self.notify_parents()
        self.update_student_academic_record()
    
    def calculate_class_rank(self):
        """Calculate student's rank in class."""
        if not self.school_class or not self.overall_percentage:
            return
        
        # Get all submitted report cards for the same class and term
        class_results = frappe.db.sql("""
            SELECT name, overall_percentage
            FROM `tabReport Card`
            WHERE school_class = %s
            AND academic_term = %s
            AND docstatus = 1
            ORDER BY overall_percentage DESC
        """, [self.school_class, self.academic_term], as_dict=True)
        
        rank = 1
        for i, result in enumerate(class_results):
            if result.name == self.name:
                rank = i + 1
                break
        
        self.class_rank = rank
        self.save()
    
    @frappe.whitelist()
    def generate_from_assessments(self):
        """Generate report card from assessment results."""
        if not self.student or not self.academic_term:
            frappe.throw(_("Student and Academic Term are required"))
        
        # Get student's class subjects
        class_subjects = frappe.get_all("Class Subject Teacher",
            filters={"school_class": self.school_class},
            fields=["subject"]
        )
        
        for class_subject in class_subjects:
            subject = class_subject.subject
            
            # Get assessment results for this subject and term
            assessments = frappe.get_all("Assessment",
                filters={
                    "student": self.student,
                    "subject": subject,
                    "academic_term": self.academic_term,
                    "docstatus": 1
                },
                fields=["total_marks", "obtained_marks", "grade"]
            )
            
            if assessments:
                total_marks = sum(flt(a.total_marks) for a in assessments)
                obtained_marks = sum(flt(a.obtained_marks) for a in assessments)
                
                self.append("subjects", {
                    "subject": subject,
                    "total_marks": total_marks,
                    "obtained_marks": obtained_marks,
                    "percentage": (obtained_marks / total_marks * 100) if total_marks > 0 else 0,
                    "grade": self.percentage_to_grade((obtained_marks / total_marks * 100) if total_marks > 0 else 0)
                })
        
        self.save()
        frappe.msgprint(_("Report card generated from assessments"))
        return self
    
    @frappe.whitelist()
    def add_teacher_comment(self, comment):
        """Add teacher comment to report card."""
        self.teacher_comments = comment
        self.save()
        
        frappe.msgprint(_("Teacher comment added"))
        return self
    
    @frappe.whitelist()
    def add_principal_comment(self, comment):
        """Add principal comment to report card."""
        self.principal_comments = comment
        self.save()
        
        frappe.msgprint(_("Principal comment added"))
        return self
    
    def notify_parents(self):
        """Notify parents about report card availability."""
        # Get student's guardians
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            
            if guardian.email_address:
                frappe.sendmail(
                    recipients=[guardian.email_address],
                    subject=_("Report Card Available: {0}").format(self.student_name),
                    message=self.get_parent_notification_message(),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
    
    def update_student_academic_record(self):
        """Update student's academic record."""
        student_doc = frappe.get_doc("Student", self.student)
        
        # Update current academic performance
        student_doc.current_gpa = self.grade_point_average
        student_doc.current_attendance_percentage = self.attendance_percentage
        
        # Add to academic history
        student_doc.append("academic_history", {
            "academic_year": self.academic_year,
            "academic_term": self.academic_term,
            "school_class": self.school_class,
            "overall_grade": self.overall_grade,
            "overall_percentage": self.overall_percentage,
            "gpa": self.grade_point_average,
            "class_rank": self.class_rank,
            "promotion_status": self.promotion_status
        })
        
        student_doc.save()
    
    def get_parent_notification_message(self):
        """Get parent notification message."""
        return _("""
        Report Card Available
        
        Dear Parent/Guardian,
        
        The report card for {student_name} is now available for {academic_term}, {academic_year}.
        
        Academic Performance:
        - Overall Grade: {overall_grade}
        - Overall Percentage: {overall_percentage}%
        - Class Rank: {class_rank}
        - GPA: {gpa}
        
        Attendance:
        - Attendance Percentage: {attendance_percentage}%
        - Days Present: {days_present}
        - Days Absent: {days_absent}
        
        Conduct: {conduct_grade}
        Effort: {effort_grade}
        
        Promotion Status: {promotion_status}
        
        {teacher_comments}
        
        You can view the complete report card in the parent portal.
        
        Best regards,
        {school_name}
        """).format(
            student_name=self.student_name,
            academic_term=self.academic_term,
            academic_year=self.academic_year,
            overall_grade=self.overall_grade,
            overall_percentage=round(self.overall_percentage, 1) if self.overall_percentage else 0,
            class_rank=self.class_rank or "Not calculated",
            gpa=round(self.grade_point_average, 2) if self.grade_point_average else 0,
            attendance_percentage=round(self.attendance_percentage, 1) if self.attendance_percentage else 0,
            days_present=self.days_present or 0,
            days_absent=self.days_absent or 0,
            conduct_grade=self.conduct_grade or "Not graded",
            effort_grade=self.effort_grade or "Not graded",
            promotion_status=self.promotion_status or "Pending",
            teacher_comments=f"\n\nTeacher Comments:\n{self.teacher_comments}" if self.teacher_comments else "",
            school_name=frappe.db.get_single_value("School Settings", "school_name")
        )
    
    @frappe.whitelist()
    def get_subject_analysis(self):
        """Get detailed subject performance analysis."""
        analysis = {
            "strengths": [],
            "areas_for_improvement": [],
            "subject_performance": []
        }
        
        for subject in self.subjects:
            percentage = flt(subject.percentage)
            
            subject_data = {
                "subject": subject.subject,
                "grade": subject.grade,
                "percentage": percentage,
                "performance_level": self.get_performance_level(percentage)
            }
            
            analysis["subject_performance"].append(subject_data)
            
            if percentage >= 80:
                analysis["strengths"].append(subject.subject)
            elif percentage < 60:
                analysis["areas_for_improvement"].append(subject.subject)
        
        return analysis
    
    def get_performance_level(self, percentage):
        """Get performance level description."""
        if percentage >= 90:
            return "Excellent"
        elif percentage >= 80:
            return "Very Good"
        elif percentage >= 70:
            return "Good"
        elif percentage >= 60:
            return "Satisfactory"
        else:
            return "Needs Improvement"
    
    @frappe.whitelist()
    def compare_with_previous_term(self):
        """Compare performance with previous term."""
        # Get previous term report card
        previous_report = frappe.db.get_value("Report Card",
            filters={
                "student": self.student,
                "academic_year": self.academic_year,
                "docstatus": 1,
                "name": ["!=", self.name]
            },
            fieldname=["overall_percentage", "grade_point_average", "attendance_percentage"],
            order_by="creation desc"
        )
        
        if not previous_report:
            return {"message": "No previous report card found for comparison"}
        
        comparison = {
            "overall_percentage": {
                "current": self.overall_percentage,
                "previous": previous_report[0],
                "change": self.overall_percentage - previous_report[0] if previous_report[0] else 0
            },
            "gpa": {
                "current": self.grade_point_average,
                "previous": previous_report[1],
                "change": self.grade_point_average - previous_report[1] if previous_report[1] else 0
            },
            "attendance": {
                "current": self.attendance_percentage,
                "previous": previous_report[2],
                "change": self.attendance_percentage - previous_report[2] if previous_report[2] else 0
            }
        }
        
        return comparison
    
    def get_report_summary(self):
        """Get report card summary for dashboard."""
        return {
            "student": self.student_name,
            "academic_term": self.academic_term,
            "academic_year": self.academic_year,
            "overall_grade": self.overall_grade,
            "overall_percentage": self.overall_percentage,
            "gpa": self.grade_point_average,
            "class_rank": self.class_rank,
            "attendance_percentage": self.attendance_percentage,
            "promotion_status": self.promotion_status,
            "subjects_count": len(self.subjects),
            "activities_count": len(self.extracurricular_activities),
            "achievements_count": len(self.achievements)
        }
