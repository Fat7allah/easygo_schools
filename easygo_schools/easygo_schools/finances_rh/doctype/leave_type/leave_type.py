import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint
from frappe import _


class LeaveType(Document):
    def validate(self):
        self.validate_allocation_limits()
        self.validate_salary_fraction()
        self.set_leave_type_code()
        
    def validate_allocation_limits(self):
        """Validate leave allocation limits"""
        if self.max_leaves_allowed and self.max_leaves_allowed < 0:
            frappe.throw(_("Maximum leaves allowed cannot be negative"))
            
        if self.max_continuous_days_allowed and self.max_continuous_days_allowed < 0:
            frappe.throw(_("Maximum continuous days allowed cannot be negative"))
            
        if self.applicable_after and self.applicable_after < 0:
            frappe.throw(_("Applicable after days cannot be negative"))
            
    def validate_salary_fraction(self):
        """Validate salary fraction for leave encashment"""
        if self.is_encash_leave and self.fraction_of_daily_salary_per_leave:
            if self.fraction_of_daily_salary_per_leave < 0 or self.fraction_of_daily_salary_per_leave > 1:
                frappe.throw(_("Fraction of daily salary per leave must be between 0 and 1"))
                
    def set_leave_type_code(self):
        """Set leave type code if not provided"""
        if not self.leave_type_code:
            # Generate code from name (first 3 characters + numbers)
            code_base = ''.join([c.upper() for c in self.leave_type_name if c.isalpha()])[:3]
            
            # Check for existing codes
            existing_codes = frappe.db.sql_list("""
                SELECT leave_type_code FROM `tabLeave Type`
                WHERE leave_type_code LIKE %s AND name != %s
            """, (f"{code_base}%", self.name))
            
            counter = 1
            new_code = code_base
            while new_code in existing_codes:
                new_code = f"{code_base}{counter}"
                counter += 1
                
            self.leave_type_code = new_code
            
    def get_leave_balance(self, employee, from_date=None, to_date=None):
        """Get leave balance for an employee"""
        conditions = ["employee = %s", "leave_type = %s"]
        values = [employee, self.name]
        
        if from_date:
            conditions.append("from_date >= %s")
            values.append(from_date)
            
        if to_date:
            conditions.append("to_date <= %s")
            values.append(to_date)
            
        # Get allocated leaves
        allocated = frappe.db.sql("""
            SELECT SUM(new_leaves_allocated) as allocated
            FROM `tabLeave Allocation`
            WHERE {0} AND docstatus = 1
        """.format(" AND ".join(conditions)), values)
        
        allocated_leaves = allocated[0][0] if allocated and allocated[0][0] else 0
        
        # Get used leaves
        used = frappe.db.sql("""
            SELECT SUM(total_leave_days) as used
            FROM `tabLeave Application`
            WHERE {0} AND status = 'Approved' AND docstatus = 1
        """.format(" AND ".join(conditions)), values)
        
        used_leaves = used[0][0] if used and used[0][0] else 0
        
        return {
            "allocated": flt(allocated_leaves),
            "used": flt(used_leaves),
            "balance": flt(allocated_leaves) - flt(used_leaves)
        }
        
    def can_apply_leave(self, employee, from_date, to_date, total_days):
        """Check if employee can apply for this leave type"""
        errors = []
        
        # Check if leave type is active
        if not self.is_active:
            errors.append(_("Leave type {0} is not active").format(self.leave_type_name))
            
        # Check gender eligibility
        if self.applicable_gender:
            employee_gender = frappe.db.get_value("Employee", employee, "gender")
            if employee_gender != self.applicable_gender:
                errors.append(_("Leave type {0} is not applicable for {1}").format(
                    self.leave_type_name, employee_gender))
                    
        # Check maximum continuous days
        if self.max_continuous_days_allowed and total_days > self.max_continuous_days_allowed:
            errors.append(_("Cannot apply for more than {0} continuous days for {1}").format(
                self.max_continuous_days_allowed, self.leave_type_name))
                
        # Check leave balance
        if not self.allow_negative:
            balance = self.get_leave_balance(employee)
            if balance["balance"] < total_days:
                errors.append(_("Insufficient leave balance. Available: {0}, Requested: {1}").format(
                    balance["balance"], total_days))
                    
        # Check minimum days between applications
        if self.min_days_between_application:
            last_application = frappe.db.sql("""
                SELECT MAX(to_date) as last_date
                FROM `tabLeave Application`
                WHERE employee = %s AND leave_type = %s
                AND status = 'Approved' AND docstatus = 1
            """, (employee, self.name))
            
            if last_application and last_application[0][0]:
                from frappe.utils import date_diff, getdate
                days_since_last = date_diff(getdate(from_date), last_application[0][0])
                if days_since_last < self.min_days_between_application:
                    errors.append(_("Minimum {0} days required between applications for {1}").format(
                        self.min_days_between_application, self.leave_type_name))
                        
        return {"can_apply": len(errors) == 0, "errors": errors}
        
    def calculate_leave_encashment(self, employee, days):
        """Calculate leave encashment amount"""
        if not self.is_encash_leave:
            return 0
            
        if not self.fraction_of_daily_salary_per_leave:
            return 0
            
        # Get employee's daily salary
        daily_salary = self.get_employee_daily_salary(employee)
        if not daily_salary:
            return 0
            
        encashment_per_day = daily_salary * self.fraction_of_daily_salary_per_leave
        return flt(days) * flt(encashment_per_day)
        
    def get_employee_daily_salary(self, employee):
        """Get employee's daily salary"""
        # Get current salary structure assignment
        salary_structure = frappe.db.get_value("Salary Structure Assignment", {
            "employee": employee,
            "docstatus": 1
        }, "base", order_by="from_date desc")
        
        if salary_structure:
            # Assuming 30 days per month
            return flt(salary_structure) / 30
            
        return 0


@frappe.whitelist()
def get_leave_types_for_employee(employee):
    """Get applicable leave types for an employee"""
    employee_doc = frappe.get_doc("Employee", employee)
    
    conditions = ["is_active = 1"]
    
    # Filter by gender if applicable
    if employee_doc.gender:
        conditions.append("(applicable_gender IS NULL OR applicable_gender = '' OR applicable_gender = %s)")
        
    leave_types = frappe.db.sql(f"""
        SELECT name, leave_type_name, max_leaves_allowed, max_continuous_days_allowed,
               is_carry_forward, is_encash_leave, description
        FROM `tabLeave Type`
        WHERE {' AND '.join(conditions)}
        ORDER BY leave_type_name
    """, (employee_doc.gender,) if employee_doc.gender else (), as_dict=True)
    
    # Add balance information
    for leave_type in leave_types:
        lt_doc = frappe.get_doc("Leave Type", leave_type.name)
        balance = lt_doc.get_leave_balance(employee)
        leave_type.update(balance)
        
    return leave_types


@frappe.whitelist()
def get_leave_type_analytics():
    """Get leave type analytics"""
    return {
        "total_leave_types": frappe.db.count("Leave Type"),
        "active_leave_types": frappe.db.count("Leave Type", {"is_active": 1}),
        "encashable_types": frappe.db.count("Leave Type", {"is_encash_leave": 1}),
        "carry_forward_types": frappe.db.count("Leave Type", {"is_carry_forward": 1}),
        "usage_stats": frappe.db.sql("""
            SELECT 
                lt.leave_type_name,
                COUNT(la.name) as applications,
                SUM(la.total_leave_days) as total_days,
                AVG(la.total_leave_days) as avg_days_per_application
            FROM `tabLeave Type` lt
            LEFT JOIN `tabLeave Application` la ON lt.name = la.leave_type
            WHERE lt.is_active = 1 AND la.docstatus = 1
            GROUP BY lt.name, lt.leave_type_name
            ORDER BY applications DESC
        """, as_dict=True)
    }


def create_default_leave_types():
    """Create default leave types for new installation"""
    default_types = [
        {
            "leave_type_name": "Annual Leave",
            "leave_type_code": "AL",
            "max_leaves_allowed": 21,
            "is_carry_forward": 1,
            "is_encash_leave": 1,
            "fraction_of_daily_salary_per_leave": 1.0,
            "description": "Annual vacation leave"
        },
        {
            "leave_type_name": "Sick Leave",
            "leave_type_code": "SL",
            "max_leaves_allowed": 12,
            "max_continuous_days_allowed": 7,
            "description": "Medical leave for illness"
        },
        {
            "leave_type_name": "Maternity Leave",
            "leave_type_code": "ML",
            "max_leaves_allowed": 98,
            "applicable_gender": "Female",
            "description": "Maternity leave for female employees"
        },
        {
            "leave_type_name": "Paternity Leave",
            "leave_type_code": "PL",
            "max_leaves_allowed": 3,
            "applicable_gender": "Male",
            "description": "Paternity leave for male employees"
        },
        {
            "leave_type_name": "Emergency Leave",
            "leave_type_code": "EL",
            "max_leaves_allowed": 5,
            "max_continuous_days_allowed": 2,
            "allow_negative": 1,
            "description": "Emergency leave for urgent situations"
        }
    ]
    
    for leave_type_data in default_types:
        if not frappe.db.exists("Leave Type", leave_type_data["leave_type_name"]):
            leave_type = frappe.new_doc("Leave Type")
            leave_type.update(leave_type_data)
            leave_type.insert()
            frappe.db.commit()
