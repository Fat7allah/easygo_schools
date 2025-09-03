"""Support Trigger Rule DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, flt, cint, add_days
import json


class SupportTriggerRule(Document):
    """Support Trigger Rule management for automatic student support detection."""
    
    def validate(self):
        """Validate support trigger rule data."""
        self.validate_thresholds()
        self.validate_conditions()
        self.set_defaults()
    
    def validate_thresholds(self):
        """Validate threshold values."""
        if self.academic_threshold and (self.academic_threshold < 0 or self.academic_threshold > 100):
            frappe.throw(_("Academic threshold must be between 0 and 100"))
        
        if self.attendance_threshold and (self.attendance_threshold < 0 or self.attendance_threshold > 100):
            frappe.throw(_("Attendance threshold must be between 0 and 100"))
        
        if self.behavioral_threshold and self.behavioral_threshold < 0:
            frappe.throw(_("Behavioral threshold must be positive"))
    
    def validate_conditions(self):
        """Validate custom conditions if provided."""
        if self.conditions and self.trigger_type == "Custom Condition":
            try:
                # Basic syntax validation
                compile(self.conditions, '<string>', 'exec')
            except SyntaxError as e:
                frappe.throw(_("Invalid Python syntax in conditions: {0}").format(str(e)))
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.follow_up_days:
            self.follow_up_days = 7
        
        if not self.escalation_level:
            self.escalation_level = "Level 1"
    
    def on_submit(self):
        """Actions on submit."""
        self.schedule_rule_execution()
    
    def schedule_rule_execution(self):
        """Schedule automatic rule execution."""
        if self.is_active:
            # Create scheduled job for rule evaluation
            frappe.enqueue(
                'easygo_education.vie_scolaire.doctype.support_trigger_rule.support_trigger_rule.evaluate_all_rules',
                queue='long',
                timeout=300,
                is_async=True
            )
    
    @frappe.whitelist()
    def test_rule(self, student=None):
        """Test the rule against a specific student or sample data."""
        if student:
            result = self.evaluate_student(student)
            return {
                "student": student,
                "triggered": result["triggered"],
                "reason": result["reason"],
                "data": result["data"]
            }
        else:
            # Test with sample students
            sample_students = frappe.get_all("Student", 
                fields=["name", "student_name"], 
                limit=5
            )
            
            results = []
            for student_info in sample_students:
                result = self.evaluate_student(student_info.name)
                results.append({
                    "student": student_info.name,
                    "student_name": student_info.student_name,
                    "triggered": result["triggered"],
                    "reason": result["reason"]
                })
            
            return results
    
    def evaluate_student(self, student):
        """Evaluate if a student triggers this rule."""
        try:
            # Get student data
            student_data = self.get_student_data(student)
            
            # Check if rule applies to this student
            if not self.student_matches_scope(student, student_data):
                return {"triggered": False, "reason": "Student not in scope", "data": student_data}
            
            # Evaluate based on trigger type
            if self.trigger_type == "Grade Below Threshold":
                return self.evaluate_academic_threshold(student, student_data)
            elif self.trigger_type == "Attendance Below Threshold":
                return self.evaluate_attendance_threshold(student, student_data)
            elif self.trigger_type == "Missed Assignments":
                return self.evaluate_missed_assignments(student, student_data)
            elif self.trigger_type == "Behavioral Incidents":
                return self.evaluate_behavioral_incidents(student, student_data)
            elif self.trigger_type == "Combined Criteria":
                return self.evaluate_combined_criteria(student, student_data)
            elif self.trigger_type == "Custom Condition":
                return self.evaluate_custom_condition(student, student_data)
            
            return {"triggered": False, "reason": "Unknown trigger type", "data": student_data}
            
        except Exception as e:
            frappe.log_error(f"Error evaluating student {student} for rule {self.name}: {str(e)}")
            return {"triggered": False, "reason": f"Evaluation error: {str(e)}", "data": {}}
    
    def get_student_data(self, student):
        """Get comprehensive student data for evaluation."""
        student_doc = frappe.get_doc("Student", student)
        
        # Get academic performance
        academic_data = self.get_academic_performance(student)
        
        # Get attendance data
        attendance_data = self.get_attendance_data(student)
        
        # Get behavioral data
        behavioral_data = self.get_behavioral_data(student)
        
        # Get assignment data
        assignment_data = self.get_assignment_data(student)
        
        return {
            "student_info": {
                "name": student_doc.name,
                "student_name": student_doc.student_name,
                "student_group": student_doc.student_group,
                "program": student_doc.program
            },
            "academic": academic_data,
            "attendance": attendance_data,
            "behavioral": behavioral_data,
            "assignments": assignment_data
        }
    
    def get_academic_performance(self, student):
        """Get student academic performance data."""
        # Get recent assessment results
        assessments = frappe.get_all("Assessment Result",
            filters={
                "student": student,
                "docstatus": 1
            },
            fields=["assessment", "grade", "total_score", "maximum_score", "result_date"],
            order_by="result_date desc",
            limit=10
        )
        
        if not assessments:
            return {"average_score": 0, "grade_count": 0, "recent_assessments": []}
        
        # Calculate average score
        total_percentage = 0
        valid_scores = 0
        
        for assessment in assessments:
            if assessment.total_score and assessment.maximum_score:
                percentage = (assessment.total_score / assessment.maximum_score) * 100
                total_percentage += percentage
                valid_scores += 1
        
        average_score = total_percentage / valid_scores if valid_scores > 0 else 0
        
        return {
            "average_score": average_score,
            "grade_count": len(assessments),
            "recent_assessments": assessments
        }
    
    def get_attendance_data(self, student):
        """Get student attendance data."""
        # Calculate attendance percentage for the specified time period
        date_range = self.get_date_range()
        
        total_days = frappe.db.count("Student Attendance", {
            "student": student,
            "attendance_date": ["between", date_range],
            "docstatus": 1
        })
        
        present_days = frappe.db.count("Student Attendance", {
            "student": student,
            "attendance_date": ["between", date_range],
            "status": "Present",
            "docstatus": 1
        })
        
        attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 100
        
        return {
            "attendance_percentage": attendance_percentage,
            "total_days": total_days,
            "present_days": present_days,
            "absent_days": total_days - present_days
        }
    
    def get_behavioral_data(self, student):
        """Get student behavioral incident data."""
        date_range = self.get_date_range()
        
        incidents = frappe.get_all("Student Disciplinary Action",
            filters={
                "student": student,
                "incident_date": ["between", date_range],
                "docstatus": 1
            },
            fields=["incident_type", "severity", "incident_date"],
            order_by="incident_date desc"
        )
        
        return {
            "incident_count": len(incidents),
            "incidents": incidents,
            "severe_incidents": len([i for i in incidents if i.severity == "High"])
        }
    
    def get_assignment_data(self, student):
        """Get student assignment submission data."""
        date_range = self.get_date_range()
        
        # Get assignments due in the period
        assignments = frappe.get_all("Student Assignment",
            filters={
                "student": student,
                "due_date": ["between", date_range]
            },
            fields=["assignment", "status", "submission_date", "due_date"]
        )
        
        total_assignments = len(assignments)
        submitted_assignments = len([a for a in assignments if a.status == "Submitted"])
        missed_assignments = len([a for a in assignments if a.status in ["Not Submitted", "Late"]])
        
        return {
            "total_assignments": total_assignments,
            "submitted_assignments": submitted_assignments,
            "missed_assignments": missed_assignments,
            "submission_rate": (submitted_assignments / total_assignments * 100) if total_assignments > 0 else 100
        }
    
    def get_date_range(self):
        """Get date range based on time period setting."""
        today = getdate()
        
        if self.time_period == "Current Week":
            start_date = today - frappe.utils.datetime.timedelta(days=today.weekday())
            end_date = start_date + frappe.utils.datetime.timedelta(days=6)
        elif self.time_period == "Current Month":
            start_date = today.replace(day=1)
            end_date = frappe.utils.get_last_day(today)
        elif self.time_period == "Last 30 Days":
            start_date = today - frappe.utils.datetime.timedelta(days=30)
            end_date = today
        elif self.time_period == "Current Term":
            # Get current academic term
            term = frappe.db.get_value("Academic Term", 
                {"is_active": 1}, 
                ["term_start_date", "term_end_date"])
            if term:
                start_date, end_date = term
            else:
                start_date = today - frappe.utils.datetime.timedelta(days=90)
                end_date = today
        else:  # Current Year
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
        
        return [start_date, end_date]
    
    def student_matches_scope(self, student, student_data):
        """Check if student matches the rule scope."""
        if self.grade_level:
            if student_data["student_info"]["student_group"] != self.grade_level:
                return False
        
        return True
    
    def evaluate_academic_threshold(self, student, student_data):
        """Evaluate academic threshold trigger."""
        average_score = student_data["academic"]["average_score"]
        
        if average_score < self.academic_threshold:
            return {
                "triggered": True,
                "reason": f"Academic performance ({average_score:.1f}%) below threshold ({self.academic_threshold}%)",
                "data": student_data
            }
        
        return {"triggered": False, "reason": "Academic performance above threshold", "data": student_data}
    
    def evaluate_attendance_threshold(self, student, student_data):
        """Evaluate attendance threshold trigger."""
        attendance_percentage = student_data["attendance"]["attendance_percentage"]
        
        if attendance_percentage < self.attendance_threshold:
            return {
                "triggered": True,
                "reason": f"Attendance ({attendance_percentage:.1f}%) below threshold ({self.attendance_threshold}%)",
                "data": student_data
            }
        
        return {"triggered": False, "reason": "Attendance above threshold", "data": student_data}
    
    def evaluate_missed_assignments(self, student, student_data):
        """Evaluate missed assignments trigger."""
        missed_count = student_data["assignments"]["missed_assignments"]
        threshold = self.behavioral_threshold or 3  # Default threshold
        
        if missed_count >= threshold:
            return {
                "triggered": True,
                "reason": f"Missed assignments ({missed_count}) exceeds threshold ({threshold})",
                "data": student_data
            }
        
        return {"triggered": False, "reason": "Missed assignments below threshold", "data": student_data}
    
    def evaluate_behavioral_incidents(self, student, student_data):
        """Evaluate behavioral incidents trigger."""
        incident_count = student_data["behavioral"]["incident_count"]
        
        if incident_count >= self.behavioral_threshold:
            return {
                "triggered": True,
                "reason": f"Behavioral incidents ({incident_count}) exceeds threshold ({self.behavioral_threshold})",
                "data": student_data
            }
        
        return {"triggered": False, "reason": "Behavioral incidents below threshold", "data": student_data}
    
    def evaluate_combined_criteria(self, student, student_data):
        """Evaluate combined criteria trigger."""
        triggers = []
        
        # Check academic threshold
        if self.academic_threshold and student_data["academic"]["average_score"] < self.academic_threshold:
            triggers.append("academic")
        
        # Check attendance threshold
        if self.attendance_threshold and student_data["attendance"]["attendance_percentage"] < self.attendance_threshold:
            triggers.append("attendance")
        
        # Check behavioral threshold
        if self.behavioral_threshold and student_data["behavioral"]["incident_count"] >= self.behavioral_threshold:
            triggers.append("behavioral")
        
        # Trigger if any criteria met (can be customized to require multiple)
        if triggers:
            return {
                "triggered": True,
                "reason": f"Multiple criteria triggered: {', '.join(triggers)}",
                "data": student_data
            }
        
        return {"triggered": False, "reason": "No criteria triggered", "data": student_data}
    
    def evaluate_custom_condition(self, student, student_data):
        """Evaluate custom condition trigger."""
        if not self.conditions:
            return {"triggered": False, "reason": "No custom conditions defined", "data": student_data}
        
        try:
            # Create execution context
            context = {
                "student_data": student_data,
                "student": student,
                "frappe": frappe,
                "getdate": getdate,
                "flt": flt,
                "cint": cint
            }
            
            # Execute custom condition
            exec(self.conditions, context)
            
            # Check if 'triggered' variable was set
            if context.get("triggered"):
                reason = context.get("reason", "Custom condition triggered")
                return {"triggered": True, "reason": reason, "data": student_data}
            
            return {"triggered": False, "reason": "Custom condition not met", "data": student_data}
            
        except Exception as e:
            return {"triggered": False, "reason": f"Custom condition error: {str(e)}", "data": student_data}
    
    def execute_action(self, student, trigger_data):
        """Execute the configured action for triggered student."""
        try:
            if self.action_type == "Create Remedial Plan":
                return self.create_remedial_plan(student, trigger_data)
            elif self.action_type == "Send Notification":
                return self.send_notification(student, trigger_data)
            elif self.action_type == "Schedule Meeting":
                return self.schedule_meeting(student, trigger_data)
            elif self.action_type == "Assign Counselor":
                return self.assign_counselor(student, trigger_data)
            elif self.action_type == "Create Intervention":
                return self.create_intervention(student, trigger_data)
            elif self.action_type == "Custom Action":
                return self.execute_custom_action(student, trigger_data)
            
            return {"success": False, "message": "Unknown action type"}
            
        except Exception as e:
            frappe.log_error(f"Error executing action for student {student}: {str(e)}")
            return {"success": False, "message": str(e)}
    
    def create_remedial_plan(self, student, trigger_data):
        """Create a remedial plan for the student."""
        if not self.auto_create_plan:
            return {"success": False, "message": "Auto create plan disabled"}
        
        remedial_plan = frappe.get_doc({
            "doctype": "Remedial Plan",
            "student": student,
            "trigger_rule": self.name,
            "plan_type": self.category,
            "priority": self.priority,
            "description": f"Auto-generated plan based on rule: {self.rule_name}",
            "trigger_reason": trigger_data["reason"],
            "assigned_counselor": self.assigned_counselor,
            "start_date": getdate(),
            "target_completion_date": add_days(getdate(), self.follow_up_days),
            "status": "Draft"
        })
        
        remedial_plan.insert(ignore_permissions=True)
        
        return {"success": True, "message": f"Remedial plan created: {remedial_plan.name}"}
    
    def send_notification(self, student, trigger_data):
        """Send notification about triggered rule."""
        student_doc = frappe.get_doc("Student", student)
        
        # Get notification recipients
        recipients = []
        
        if self.assigned_counselor:
            counselor = frappe.get_doc("Employee", self.assigned_counselor)
            if counselor.user_id:
                recipients.append(counselor.user_id)
        
        # Add class teacher
        if student_doc.student_group:
            class_teacher = frappe.db.get_value("Student Group", student_doc.student_group, "instructor")
            if class_teacher:
                teacher_user = frappe.db.get_value("Employee", class_teacher, "user_id")
                if teacher_user:
                    recipients.append(teacher_user)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=f"Student Support Alert - {student_doc.student_name}",
                message=self.get_notification_message(student_doc, trigger_data),
                reference_doctype="Support Trigger Rule",
                reference_name=self.name
            )
        
        return {"success": True, "message": "Notification sent"}
    
    def get_notification_message(self, student_doc, trigger_data):
        """Get notification message content."""
        return f"""
        Student Support Alert
        
        Student: {student_doc.student_name} ({student_doc.name})
        Rule: {self.rule_name}
        Priority: {self.priority}
        
        Trigger Reason:
        {trigger_data['reason']}
        
        Recommended Action: {self.action_type}
        
        Please review the student's situation and take appropriate action.
        
        Academic Support Team
        """
    
    def schedule_meeting(self, student, trigger_data):
        """Schedule a meeting for the student."""
        meeting = frappe.get_doc({
            "doctype": "Meeting Request",
            "student": student,
            "meeting_type": "Support Meeting",
            "priority": self.priority,
            "requested_by": self.assigned_counselor or frappe.session.user,
            "subject": f"Support meeting for {trigger_data['reason']}",
            "description": f"Meeting triggered by rule: {self.rule_name}",
            "status": "Requested"
        })
        
        meeting.insert(ignore_permissions=True)
        
        return {"success": True, "message": f"Meeting scheduled: {meeting.name}"}
    
    def assign_counselor(self, student, trigger_data):
        """Assign counselor to student."""
        if not self.assigned_counselor:
            return {"success": False, "message": "No counselor configured"}
        
        # Create counselor assignment
        assignment = frappe.get_doc({
            "doctype": "Student Counselor Assignment",
            "student": student,
            "counselor": self.assigned_counselor,
            "assignment_reason": trigger_data["reason"],
            "assignment_date": getdate(),
            "status": "Active",
            "priority": self.priority
        })
        
        assignment.insert(ignore_permissions=True)
        
        return {"success": True, "message": f"Counselor assigned: {assignment.name}"}
    
    def create_intervention(self, student, trigger_data):
        """Create intervention session for student."""
        intervention = frappe.get_doc({
            "doctype": "Intervention Session",
            "student": student,
            "intervention_type": self.category,
            "trigger_rule": self.name,
            "session_reason": trigger_data["reason"],
            "assigned_counselor": self.assigned_counselor,
            "priority": self.priority,
            "status": "Scheduled"
        })
        
        intervention.insert(ignore_permissions=True)
        
        return {"success": True, "message": f"Intervention created: {intervention.name}"}
    
    def execute_custom_action(self, student, trigger_data):
        """Execute custom action (to be implemented based on specific needs)."""
        return {"success": False, "message": "Custom action not implemented"}
    
    @frappe.whitelist()
    def run_rule_evaluation(self):
        """Manually run rule evaluation for all students."""
        if not self.is_active:
            frappe.throw(_("Rule is not active"))
        
        results = {"triggered": 0, "evaluated": 0, "actions_executed": 0}
        
        # Get students in scope
        filters = {}
        if self.grade_level:
            filters["student_group"] = self.grade_level
        
        students = frappe.get_all("Student", filters=filters, pluck="name")
        
        for student in students:
            results["evaluated"] += 1
            
            evaluation = self.evaluate_student(student)
            
            if evaluation["triggered"]:
                results["triggered"] += 1
                
                # Execute action
                action_result = self.execute_action(student, evaluation)
                
                if action_result["success"]:
                    results["actions_executed"] += 1
                
                # Update statistics
                self.trigger_count = (self.trigger_count or 0) + 1
                self.last_triggered = now_datetime()
        
        self.save()
        
        return results
    
    @frappe.whitelist()
    def get_rule_analytics(self):
        """Get rule analytics and performance metrics."""
        # Get trigger history
        trigger_history = frappe.get_all("Remedial Plan",
            filters={"trigger_rule": self.name},
            fields=["creation", "status", "student"],
            order_by="creation desc",
            limit=50
        )
        
        # Calculate success rate
        completed_plans = len([p for p in trigger_history if p.status == "Completed"])
        total_plans = len(trigger_history)
        success_rate = (completed_plans / total_plans * 100) if total_plans > 0 else 0
        
        # Get recent triggers by category
        category_stats = {}
        for plan in trigger_history:
            month = plan.creation.strftime("%Y-%m")
            if month not in category_stats:
                category_stats[month] = 0
            category_stats[month] += 1
        
        return {
            "rule_info": {
                "name": self.name,
                "rule_name": self.rule_name,
                "category": self.category,
                "priority": self.priority,
                "is_active": self.is_active
            },
            "statistics": {
                "trigger_count": self.trigger_count or 0,
                "success_rate": success_rate,
                "last_triggered": self.last_triggered,
                "total_plans_created": total_plans
            },
            "recent_triggers": trigger_history[:10],
            "monthly_trends": category_stats
        }


@frappe.whitelist()
def evaluate_all_rules():
    """Evaluate all active support trigger rules."""
    active_rules = frappe.get_all("Support Trigger Rule",
        filters={"is_active": 1, "docstatus": 1},
        pluck="name"
    )
    
    total_results = {"rules_evaluated": 0, "students_triggered": 0, "actions_executed": 0}
    
    for rule_name in active_rules:
        rule = frappe.get_doc("Support Trigger Rule", rule_name)
        
        try:
            results = rule.run_rule_evaluation()
            total_results["rules_evaluated"] += 1
            total_results["students_triggered"] += results["triggered"]
            total_results["actions_executed"] += results["actions_executed"]
            
        except Exception as e:
            frappe.log_error(f"Error evaluating rule {rule_name}: {str(e)}")
    
    return total_results


@frappe.whitelist()
def get_student_support_dashboard(student):
    """Get comprehensive support dashboard for a student."""
    # Get all triggered rules for this student
    triggered_rules = []
    
    active_rules = frappe.get_all("Support Trigger Rule",
        filters={"is_active": 1, "docstatus": 1},
        pluck="name"
    )
    
    for rule_name in active_rules:
        rule = frappe.get_doc("Support Trigger Rule", rule_name)
        evaluation = rule.evaluate_student(student)
        
        if evaluation["triggered"]:
            triggered_rules.append({
                "rule": rule_name,
                "rule_name": rule.rule_name,
                "category": rule.category,
                "priority": rule.priority,
                "reason": evaluation["reason"]
            })
    
    # Get active remedial plans
    remedial_plans = frappe.get_all("Remedial Plan",
        filters={"student": student, "status": ["!=", "Completed"]},
        fields=["name", "plan_type", "priority", "status", "start_date", "target_completion_date"]
    )
    
    # Get recent interventions
    interventions = frappe.get_all("Intervention Session",
        filters={"student": student},
        fields=["name", "intervention_type", "session_date", "status"],
        order_by="session_date desc",
        limit=5
    )
    
    return {
        "student": student,
        "triggered_rules": triggered_rules,
        "active_plans": remedial_plans,
        "recent_interventions": interventions,
        "support_level": "High" if len(triggered_rules) > 2 else "Medium" if len(triggered_rules) > 0 else "Low"
    }
