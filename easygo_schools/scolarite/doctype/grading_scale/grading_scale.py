"""Grading Scale doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, flt


class GradingScale(Document):
    """Grading Scale doctype controller."""
    
    def validate(self):
        """Validate grading scale data."""
        self.validate_score_range()
        self.validate_intervals()
        self.validate_default_scale()
        self.set_defaults()
    
    def validate_score_range(self):
        """Validate score range."""
        if self.minimum_score >= self.maximum_score:
            frappe.throw(_("Maximum score must be greater than minimum score"))
        
        if self.passing_grade < self.minimum_score or self.passing_grade > self.maximum_score:
            frappe.throw(_("Passing grade must be between minimum and maximum scores"))
    
    def validate_intervals(self):
        """Validate grade intervals."""
        if not self.intervals:
            frappe.throw(_("At least one grade interval is required"))
        
        # Sort intervals by minimum score
        self.intervals = sorted(self.intervals, key=lambda x: x.min_score)
        
        # Validate intervals don't overlap and cover the full range
        for i, interval in enumerate(self.intervals):
            if interval.min_score >= interval.max_score:
                frappe.throw(_("Row {0}: Maximum score must be greater than minimum score").format(i + 1))
            
            if i > 0:
                prev_interval = self.intervals[i - 1]
                if interval.min_score <= prev_interval.max_score:
                    frappe.throw(_("Row {0}: Intervals cannot overlap").format(i + 1))
        
        # Check if intervals cover the full range
        first_interval = self.intervals[0]
        last_interval = self.intervals[-1]
        
        if first_interval.min_score > self.minimum_score:
            frappe.throw(_("Grade intervals must start from minimum score"))
        
        if last_interval.max_score < self.maximum_score:
            frappe.throw(_("Grade intervals must cover up to maximum score"))
    
    def validate_default_scale(self):
        """Validate only one default scale exists."""
        if self.is_default:
            existing_default = frappe.db.get_value("Grading Scale", 
                {"is_default": 1, "name": ["!=", self.name or ""]}, "name")
            
            if existing_default:
                frappe.throw(_("Another default grading scale already exists: {0}").format(existing_default))
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
        
        if not self.decimal_places:
            self.decimal_places = 2
        
        if not self.rounding_method:
            self.rounding_method = "Round to Nearest"
    
    @frappe.whitelist()
    def calculate_grade(self, score):
        """Calculate grade based on score."""
        score = flt(score)
        
        if score < self.minimum_score or score > self.maximum_score:
            return {
                "letter_grade": "Invalid",
                "grade_point": 0,
                "description": "Score out of range"
            }
        
        # Apply rounding
        if self.rounding_method == "Round Up":
            import math
            score = math.ceil(score * (10 ** self.decimal_places)) / (10 ** self.decimal_places)
        elif self.rounding_method == "Round Down":
            import math
            score = math.floor(score * (10 ** self.decimal_places)) / (10 ** self.decimal_places)
        elif self.rounding_method == "Round to Nearest":
            score = round(score, self.decimal_places)
        
        # Find matching interval
        for interval in self.intervals:
            if interval.min_score <= score <= interval.max_score:
                return {
                    "letter_grade": interval.grade_letter,
                    "grade_point": interval.grade_point if self.grade_points_enabled else None,
                    "description": interval.description,
                    "is_passing": score >= self.passing_grade,
                    "is_honor_roll": self.honor_roll_threshold and score >= self.honor_roll_threshold
                }
        
        return {
            "letter_grade": "N/A",
            "grade_point": 0,
            "description": "No matching grade interval"
        }
    
    @frappe.whitelist()
    def get_grade_distribution(self, academic_year=None, program=None):
        """Get grade distribution statistics."""
        conditions = ["g.grading_scale = %s"]
        values = [self.name]
        
        if academic_year:
            conditions.append("s.academic_year = %s")
            values.append(academic_year)
        
        if program:
            conditions.append("s.program = %s")
            values.append(program)
        
        query = f"""
            SELECT 
                g.letter_grade,
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
            FROM `tabGrade` g
            INNER JOIN `tabStudent` s ON g.student = s.name
            WHERE {' AND '.join(conditions)}
            GROUP BY g.letter_grade
            ORDER BY MIN(g.percentage) DESC
        """
        
        distribution = frappe.db.sql(query, values, as_dict=True)
        
        return distribution
    
    @frappe.whitelist()
    def get_performance_metrics(self, academic_year=None):
        """Get performance metrics for this grading scale."""
        conditions = ["g.grading_scale = %s"]
        values = [self.name]
        
        if academic_year:
            conditions.append("s.academic_year = %s")
            values.append(academic_year)
        
        query = f"""
            SELECT 
                COUNT(*) as total_grades,
                AVG(g.percentage) as average_score,
                MIN(g.percentage) as min_score,
                MAX(g.percentage) as max_score,
                COUNT(CASE WHEN g.percentage >= %s THEN 1 END) as passing_count,
                COUNT(CASE WHEN g.percentage >= %s THEN 1 END) as honor_roll_count
            FROM `tabGrade` g
            INNER JOIN `tabStudent` s ON g.student = s.name
            WHERE {' AND '.join(conditions)}
        """
        
        values.extend([self.passing_grade, self.honor_roll_threshold or self.maximum_score])
        
        metrics = frappe.db.sql(query, values, as_dict=True)
        
        if metrics:
            result = metrics[0]
            if result.total_grades > 0:
                result["passing_rate"] = round((result.passing_count / result.total_grades) * 100, 2)
                result["honor_roll_rate"] = round((result.honor_roll_count / result.total_grades) * 100, 2)
            else:
                result["passing_rate"] = 0
                result["honor_roll_rate"] = 0
            
            return result
        
        return {
            "total_grades": 0,
            "average_score": 0,
            "passing_rate": 0,
            "honor_roll_rate": 0
        }
