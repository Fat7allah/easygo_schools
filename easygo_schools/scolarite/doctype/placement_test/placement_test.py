"""Placement Test DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, flt, cint


class PlacementTest(Document):
    """Placement Test management."""
    
    def validate(self):
        """Validate placement test data."""
        self.validate_marks()
        self.calculate_percentage_and_grade()
        self.set_defaults()
    
    def validate_marks(self):
        """Validate marks and test results."""
        if self.obtained_marks > self.total_marks:
            frappe.throw(_("Obtained marks cannot be greater than total marks"))
        
        if self.obtained_marks < 0 or self.total_marks <= 0:
            frappe.throw(_("Marks must be positive values"))
        
        # Validate subject-wise results
        if self.test_results:
            total_subject_marks = sum(flt(result.marks_obtained) for result in self.test_results)
            if abs(total_subject_marks - flt(self.obtained_marks)) > 0.01:
                frappe.msgprint(_("Warning: Sum of subject-wise marks ({0}) does not match total obtained marks ({1})").format(
                    total_subject_marks, self.obtained_marks
                ))
    
    def calculate_percentage_and_grade(self):
        """Calculate percentage and grade."""
        if self.total_marks and self.obtained_marks is not None:
            self.percentage = (flt(self.obtained_marks) / flt(self.total_marks)) * 100
            self.grade = self.get_grade_from_percentage(self.percentage)
    
    def get_grade_from_percentage(self, percentage):
        """Get grade based on percentage."""
        if percentage >= 90:
            return "A+"
        elif percentage >= 80:
            return "A"
        elif percentage >= 70:
            return "B+"
        elif percentage >= 60:
            return "B"
        elif percentage >= 50:
            return "C+"
        elif percentage >= 40:
            return "C"
        elif percentage >= 30:
            return "D"
        else:
            return "F"
    
    def set_defaults(self):
        """Set default values."""
        if not self.academic_year:
            self.academic_year = frappe.db.get_single_value("School Settings", "current_academic_year")
        
        if not self.conducted_by:
            self.conducted_by = frappe.session.user
        
        if not self.placement_status:
            self.placement_status = "Pending"
    
    def on_submit(self):
        """Actions on submit."""
        self.generate_placement_recommendation()
        self.notify_stakeholders()
        self.update_student_record()
    
    def generate_placement_recommendation(self):
        """Generate placement recommendation based on test results."""
        if not self.recommended_program or not self.recommended_level:
            # Auto-generate recommendations based on performance
            if self.percentage >= 85:
                self.recommended_level = "Advanced"
            elif self.percentage >= 70:
                self.recommended_level = "Intermediate"
            elif self.percentage >= 50:
                self.recommended_level = "Beginner"
            else:
                self.recommended_level = "Remedial"
            
            # Get program recommendation based on student's applied program
            student = frappe.get_doc("Student", self.student)
            if hasattr(student, 'program') and student.program:
                self.recommended_program = student.program
    
    def notify_stakeholders(self):
        """Notify relevant stakeholders about test results."""
        # Notify student and guardians
        self.send_result_notification()
        
        # Notify academic team for placement decisions
        self.send_placement_notification()
    
    def send_result_notification(self):
        """Send test result notification to student and guardians."""
        student = frappe.get_doc("Student", self.student)
        
        # Get guardians
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        recipients = []
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            if guardian.email_address:
                recipients.append(guardian.email_address)
        
        # Add student email if available
        if student.student_email_id:
            recipients.append(student.student_email_id)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Placement Test Results - {0}").format(self.student_name),
                message=self.get_result_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def send_placement_notification(self):
        """Send placement notification to academic team."""
        academic_team_emails = frappe.db.get_single_value("School Settings", "academic_team_emails")
        
        if academic_team_emails:
            email_list = [email.strip() for email in academic_team_emails.split(",")]
            
            frappe.sendmail(
                recipients=email_list,
                subject=_("Placement Test Completed - {0}").format(self.student_name),
                message=self.get_placement_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_result_notification_message(self):
        """Get result notification message."""
        subject_results = ""
        if self.test_results:
            subject_results = "\n".join([
                f"- {result.subject}: {result.marks_obtained}/{result.total_marks} ({result.percentage}%)"
                for result in self.test_results
            ])
        
        return _("""
        Dear Student/Guardian,
        
        The placement test results for {student_name} are now available.
        
        Test Details:
        - Test Type: {test_type}
        - Test Date: {test_date}
        - Subjects Tested: {subjects}
        
        Overall Results:
        - Total Marks: {total_marks}
        - Obtained Marks: {obtained_marks}
        - Percentage: {percentage}%
        - Grade: {grade}
        
        Subject-wise Results:
        {subject_results}
        
        Placement Recommendation:
        - Recommended Program: {program}
        - Recommended Level: {level}
        
        The academic team will review these results for final placement decisions.
        
        Academic Office
        """).format(
            student_name=self.student_name,
            test_type=self.test_type,
            test_date=frappe.format(self.test_date, "Date"),
            subjects=self.subjects_tested,
            total_marks=self.total_marks,
            obtained_marks=self.obtained_marks,
            percentage=round(self.percentage, 2),
            grade=self.grade,
            subject_results=subject_results or "Not available",
            program=self.recommended_program or "To be determined",
            level=self.recommended_level or "To be determined"
        )
    
    def get_placement_notification_message(self):
        """Get placement notification message for academic team."""
        return _("""
        Placement Test Completed
        
        Student: {student_name}
        Test Type: {test_type}
        Test Date: {test_date}
        
        Results:
        - Score: {obtained_marks}/{total_marks} ({percentage}%)
        - Grade: {grade}
        
        Recommendations:
        - Program: {program}
        - Level: {level}
        
        Examiner Notes:
        {notes}
        
        Please review for placement approval.
        
        Test ID: {test_id}
        """).format(
            student_name=self.student_name,
            test_type=self.test_type,
            test_date=frappe.format(self.test_date, "Date"),
            obtained_marks=self.obtained_marks,
            total_marks=self.total_marks,
            percentage=round(self.percentage, 2),
            grade=self.grade,
            program=self.recommended_program or "Not specified",
            level=self.recommended_level or "Not specified",
            notes=self.examiner_notes or "None",
            test_id=self.name
        )
    
    def update_student_record(self):
        """Update student record with placement information."""
        if self.placement_status == "Approved" and self.recommended_program:
            student = frappe.get_doc("Student", self.student)
            
            # Update student program if different
            if student.program != self.recommended_program:
                student.program = self.recommended_program
                student.add_comment("Comment", f"Program updated based on placement test {self.name}")
            
            # Add placement test to student's academic history
            student.append("academic_history", {
                "academic_year": self.academic_year,
                "event_type": "Placement Test",
                "event_date": self.test_date,
                "description": f"Placement Test - {self.test_type}",
                "result": f"Score: {self.percentage}%, Grade: {self.grade}",
                "reference_document": self.name
            })
            
            student.save()
    
    @frappe.whitelist()
    def approve_placement(self, approved_program=None, approved_level=None, approval_notes=None):
        """Approve placement recommendation."""
        if self.placement_status == "Approved":
            frappe.throw(_("Placement is already approved"))
        
        self.placement_status = "Approved"
        self.placement_date = getdate()
        self.approved_by = frappe.session.user
        
        if approved_program:
            self.recommended_program = approved_program
        
        if approved_level:
            self.recommended_level = approved_level
        
        if approval_notes:
            current_notes = self.recommendations or ""
            self.recommendations = f"{current_notes}\n\nApproval Notes ({getdate()}):\n{approval_notes}"
        
        self.save()
        
        # Update student record
        self.update_student_record()
        
        # Send approval notification
        self.send_approval_notification()
        
        frappe.msgprint(_("Placement approved successfully"))
        return self
    
    @frappe.whitelist()
    def reject_placement(self, rejection_reason):
        """Reject placement recommendation."""
        if self.placement_status == "Approved":
            frappe.throw(_("Cannot reject approved placement"))
        
        self.placement_status = "Rejected"
        self.approved_by = frappe.session.user
        
        current_notes = self.recommendations or ""
        self.recommendations = f"{current_notes}\n\nRejection Reason ({getdate()}):\n{rejection_reason}"
        
        self.save()
        
        # Send rejection notification
        self.send_rejection_notification(rejection_reason)
        
        frappe.msgprint(_("Placement rejected"))
        return self
    
    def send_approval_notification(self):
        """Send placement approval notification."""
        student = frappe.get_doc("Student", self.student)
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        recipients = []
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            if guardian.email_address:
                recipients.append(guardian.email_address)
        
        if student.student_email_id:
            recipients.append(student.student_email_id)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Placement Approved - {0}").format(self.student_name),
                message=self.get_approval_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_approval_message(self):
        """Get placement approval message."""
        return _("""
        Dear Student/Guardian,
        
        We are pleased to inform you that the placement for {student_name} has been approved.
        
        Placement Details:
        - Program: {program}
        - Level: {level}
        - Effective Date: {placement_date}
        
        Based on the placement test results, {student_name} has been placed in the appropriate program and level.
        
        Please contact the academic office for next steps and enrollment procedures.
        
        Academic Office
        """).format(
            student_name=self.student_name,
            program=self.recommended_program,
            level=self.recommended_level,
            placement_date=frappe.format(self.placement_date, "Date")
        )
    
    def send_rejection_notification(self, rejection_reason):
        """Send placement rejection notification."""
        student = frappe.get_doc("Student", self.student)
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        recipients = []
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            if guardian.email_address:
                recipients.append(guardian.email_address)
        
        if student.student_email_id:
            recipients.append(student.student_email_id)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Placement Under Review - {0}").format(self.student_name),
                message=self.get_rejection_message(rejection_reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_rejection_message(self, rejection_reason):
        """Get placement rejection message."""
        return _("""
        Dear Student/Guardian,
        
        Thank you for taking the placement test. After careful review, we need to reassess the placement for {student_name}.
        
        Reason for Review:
        {reason}
        
        We recommend:
        1. Additional assessment or retesting
        2. Meeting with academic counselor
        3. Review of alternative placement options
        
        Please contact the academic office to schedule a meeting and discuss next steps.
        
        Academic Office
        """).format(
            student_name=self.student_name,
            reason=rejection_reason
        )
    
    @frappe.whitelist()
    def schedule_retest(self, retest_date, retest_reason=None):
        """Schedule a retest for the student."""
        retest = frappe.get_doc({
            "doctype": "Placement Test",
            "student": self.student,
            "test_date": retest_date,
            "test_type": self.test_type,
            "academic_year": self.academic_year,
            "subjects_tested": self.subjects_tested,
            "total_marks": self.total_marks,
            "conducted_by": frappe.session.user,
            "examiner_notes": f"Retest scheduled. Original test: {self.name}. Reason: {retest_reason or 'Performance review'}"
        })
        
        retest.insert()
        
        # Add reference to original test
        self.append("retest_history", {
            "retest_date": retest_date,
            "retest_document": retest.name,
            "reason": retest_reason,
            "scheduled_by": frappe.session.user
        })
        
        self.save()
        
        frappe.msgprint(_("Retest scheduled: {0}").format(retest.name))
        return retest.name
    
    @frappe.whitelist()
    def get_test_analytics(self):
        """Get test analytics and statistics."""
        # Get school-wide placement test statistics
        total_tests = frappe.db.count("Placement Test", {"test_type": self.test_type})
        
        # Get average performance
        avg_performance = frappe.db.sql("""
            SELECT 
                AVG(percentage) as avg_percentage,
                AVG(obtained_marks) as avg_marks,
                COUNT(*) as total_count
            FROM `tabPlacement Test`
            WHERE test_type = %s
            AND docstatus = 1
        """, [self.test_type], as_dict=True)[0]
        
        # Get grade distribution
        grade_distribution = frappe.db.sql("""
            SELECT grade, COUNT(*) as count
            FROM `tabPlacement Test`
            WHERE test_type = %s
            AND docstatus = 1
            GROUP BY grade
            ORDER BY count DESC
        """, [self.test_type], as_dict=True)
        
        # Get placement outcomes
        placement_outcomes = frappe.db.sql("""
            SELECT 
                placement_status,
                recommended_level,
                COUNT(*) as count
            FROM `tabPlacement Test`
            WHERE test_type = %s
            AND docstatus = 1
            GROUP BY placement_status, recommended_level
        """, [self.test_type], as_dict=True)
        
        return {
            "current_test": {
                "name": self.name,
                "student": self.student_name,
                "percentage": self.percentage,
                "grade": self.grade,
                "placement_status": self.placement_status
            },
            "school_statistics": {
                "total_tests": total_tests,
                "average_performance": avg_performance,
                "grade_distribution": grade_distribution,
                "placement_outcomes": placement_outcomes
            },
            "performance_comparison": {
                "above_average": self.percentage > (avg_performance.get("avg_percentage") or 0),
                "percentile_rank": self.calculate_percentile_rank()
            }
        }
    
    def calculate_percentile_rank(self):
        """Calculate percentile rank for this test."""
        lower_scores = frappe.db.count("Placement Test", {
            "test_type": self.test_type,
            "percentage": ["<", self.percentage],
            "docstatus": 1
        })
        
        total_tests = frappe.db.count("Placement Test", {
            "test_type": self.test_type,
            "docstatus": 1
        })
        
        if total_tests == 0:
            return 0
        
        return (lower_scores / total_tests) * 100
    
    def get_placement_test_summary(self):
        """Get placement test summary for reporting."""
        return {
            "test_name": self.name,
            "student": self.student_name,
            "test_type": self.test_type,
            "test_date": self.test_date,
            "total_marks": self.total_marks,
            "obtained_marks": self.obtained_marks,
            "percentage": self.percentage,
            "grade": self.grade,
            "recommended_program": self.recommended_program,
            "recommended_level": self.recommended_level,
            "placement_status": self.placement_status,
            "conducted_by": self.conducted_by,
            "approved_by": self.approved_by,
            "placement_date": self.placement_date
        }
