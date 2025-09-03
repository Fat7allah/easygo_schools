import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, getdate, date_diff, flt, cint, add_days
from frappe import _
from datetime import datetime, timedelta


class PayrollCycle(Document):
    def validate(self):
        self.validate_dates()
        self.set_payroll_cycle_name()
        self.calculate_working_days()
        
    def validate_dates(self):
        """Validate payroll cycle dates"""
        if getdate(self.end_date) <= getdate(self.start_date):
            frappe.throw(_("End date must be after start date"))
            
        if getdate(self.payment_date) < getdate(self.end_date):
            frappe.throw(_("Payment date cannot be before end date"))
            
    def set_payroll_cycle_name(self):
        """Set payroll cycle name if not provided"""
        if not self.payroll_cycle_name:
            month_year = self.start_date.strftime("%B %Y")
            self.payroll_cycle_name = f"{self.payroll_frequency} Payroll - {month_year}"
            
    def calculate_working_days(self):
        """Calculate total working days in the cycle"""
        if self.start_date and self.end_date:
            total_days = date_diff(self.end_date, self.start_date) + 1
            
            # Assuming 5-day work week (Monday to Friday)
            working_days = 0
            current_date = getdate(self.start_date)
            end_date = getdate(self.end_date)
            
            while current_date <= end_date:
                # 0 = Monday, 6 = Sunday
                if current_date.weekday() < 5:  # Monday to Friday
                    working_days += 1
                current_date = add_days(current_date, 1)
                
            self.total_working_days = working_days
            
    def on_submit(self):
        self.status = "Processing"
        self.create_salary_slips()
        
    def on_cancel(self):
        self.status = "Cancelled"
        self.cancel_salary_slips()
        
    def get_employees(self):
        """Get employees based on filters"""
        conditions = ["status = 'Active'"]
        values = []
        
        if self.department:
            conditions.append("department = %s")
            values.append(self.department)
            
        if self.employee_grade:
            conditions.append("grade = %s")
            values.append(self.employee_grade)
            
        if self.branch:
            conditions.append("branch = %s")
            values.append(self.branch)
            
        if self.designation:
            conditions.append("designation = %s")
            values.append(self.designation)
            
        employees = frappe.db.sql(f"""
            SELECT name, employee_name, department, designation, date_of_joining
            FROM `tabEmployee`
            WHERE {' AND '.join(conditions)}
            ORDER BY employee_name
        """, values, as_dict=True)
        
        # Filter employees who joined before payroll end date
        eligible_employees = []
        for emp in employees:
            if emp.date_of_joining <= getdate(self.end_date):
                eligible_employees.append(emp)
                
        return eligible_employees
        
    @frappe.whitelist()
    def create_salary_slips(self):
        """Create salary slips for all eligible employees"""
        if self.status != "Processing":
            frappe.throw(_("Payroll cycle must be in Processing status"))
            
        employees = self.get_employees()
        created_count = 0
        
        for employee in employees:
            # Check if salary slip already exists
            existing = frappe.db.exists("Salary Slip", {
                "employee": employee.name,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "payroll_cycle": self.name
            })
            
            if not existing:
                salary_slip = self.create_salary_slip(employee)
                if salary_slip:
                    created_count += 1
                    
        self.salary_slips_created = created_count
        self.total_employees = len(employees)
        self.save()
        
        frappe.msgprint(_("Created {0} salary slips").format(created_count))
        
    def create_salary_slip(self, employee):
        """Create individual salary slip"""
        try:
            # Get salary structure assignment
            salary_assignment = frappe.db.get_value("Salary Structure Assignment", {
                "employee": employee.name,
                "docstatus": 1
            }, ["salary_structure", "base"], order_by="from_date desc")
            
            if not salary_assignment:
                frappe.msgprint(_("No salary structure found for {0}").format(employee.employee_name))
                return None
                
            salary_slip = frappe.new_doc("Salary Slip")
            salary_slip.employee = employee.name
            salary_slip.employee_name = employee.employee_name
            salary_slip.start_date = self.start_date
            salary_slip.end_date = self.end_date
            salary_slip.salary_structure = salary_assignment[0]
            salary_slip.payroll_cycle = self.name
            salary_slip.posting_date = self.payment_date
            
            # Calculate attendance and leave days
            attendance_data = self.get_employee_attendance(employee.name)
            salary_slip.payment_days = attendance_data["working_days"]
            salary_slip.leave_without_pay = attendance_data["lwp_days"]
            
            salary_slip.insert()
            return salary_slip
            
        except Exception as e:
            frappe.log_error(f"Error creating salary slip for {employee.name}: {str(e)}")
            return None
            
    def get_employee_attendance(self, employee):
        """Get employee attendance data for the payroll period"""
        attendance = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_days,
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days,
                SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
                SUM(CASE WHEN status = 'Half Day' THEN 0.5 ELSE 0 END) as half_days,
                SUM(CASE WHEN status = 'On Leave' THEN 1 ELSE 0 END) as leave_days
            FROM `tabHR Attendance`
            WHERE employee = %s 
            AND attendance_date BETWEEN %s AND %s
            AND docstatus = 1
        """, (employee, self.start_date, self.end_date), as_dict=True)
        
        if attendance:
            att_data = attendance[0]
            working_days = att_data.present_days + att_data.half_days
            
            # Calculate leave without pay days
            lwp_days = max(0, self.total_working_days - working_days - att_data.leave_days)
            
            return {
                "working_days": working_days,
                "lwp_days": lwp_days,
                "leave_days": att_data.leave_days
            }
            
        return {
            "working_days": self.total_working_days,
            "lwp_days": 0,
            "leave_days": 0
        }
        
    @frappe.whitelist()
    def submit_salary_slips(self):
        """Submit all salary slips in this cycle"""
        salary_slips = frappe.get_all("Salary Slip", {
            "payroll_cycle": self.name,
            "docstatus": 0
        }, ["name"])
        
        submitted_count = 0
        for slip in salary_slips:
            try:
                slip_doc = frappe.get_doc("Salary Slip", slip.name)
                slip_doc.submit()
                submitted_count += 1
            except Exception as e:
                frappe.log_error(f"Error submitting salary slip {slip.name}: {str(e)}")
                
        self.salary_slips_submitted = submitted_count
        self.calculate_payroll_summary()
        
        if submitted_count == self.salary_slips_created:
            self.status = "Completed"
            
        self.save()
        frappe.msgprint(_("Submitted {0} salary slips").format(submitted_count))
        
    def calculate_payroll_summary(self):
        """Calculate payroll summary totals"""
        summary = frappe.db.sql("""
            SELECT 
                SUM(gross_pay) as gross_pay,
                SUM(total_deduction) as total_deduction,
                SUM(net_pay) as net_pay,
                SUM(employer_contribution) as employer_contribution
            FROM `tabSalary Slip`
            WHERE payroll_cycle = %s AND docstatus = 1
        """, (self.name,), as_dict=True)
        
        if summary:
            data = summary[0]
            self.gross_pay = data.gross_pay or 0
            self.total_deduction = data.total_deduction or 0
            self.net_pay = data.net_pay or 0
            self.employer_contribution = data.employer_contribution or 0
            self.total_amount = self.net_pay
            
    def cancel_salary_slips(self):
        """Cancel all salary slips in this cycle"""
        salary_slips = frappe.get_all("Salary Slip", {
            "payroll_cycle": self.name,
            "docstatus": 1
        }, ["name"])
        
        for slip in salary_slips:
            slip_doc = frappe.get_doc("Salary Slip", slip.name)
            slip_doc.cancel()
            
    @frappe.whitelist()
    def create_payment_entries(self):
        """Create payment entries for salary payments"""
        if self.status != "Completed":
            frappe.throw(_("Payroll cycle must be completed first"))
            
        # Get all submitted salary slips
        salary_slips = frappe.get_all("Salary Slip", {
            "payroll_cycle": self.name,
            "docstatus": 1
        }, ["name", "employee", "employee_name", "net_pay"])
        
        payment_entries = []
        for slip in salary_slips:
            if slip.net_pay > 0:
                payment_entry = frappe.new_doc("Payment Entry")
                payment_entry.payment_type = "Pay"
                payment_entry.party_type = "Employee"
                payment_entry.party = slip.employee
                payment_entry.paid_amount = slip.net_pay
                payment_entry.received_amount = slip.net_pay
                payment_entry.posting_date = self.payment_date
                payment_entry.reference_no = self.name
                payment_entry.reference_date = self.payment_date
                payment_entry.insert()
                payment_entries.append(payment_entry.name)
                
        frappe.msgprint(_("Created {0} payment entries").format(len(payment_entries)))
        return payment_entries


@frappe.whitelist()
def get_payroll_cycle_analytics():
    """Get payroll cycle analytics"""
    return {
        "total_cycles": frappe.db.count("Payroll Cycle", {"docstatus": 1}),
        "completed_cycles": frappe.db.count("Payroll Cycle", {
            "status": "Completed", "docstatus": 1
        }),
        "processing_cycles": frappe.db.count("Payroll Cycle", {
            "status": "Processing", "docstatus": 1
        }),
        "total_payroll_amount": frappe.db.sql("""
            SELECT SUM(total_amount) as amount
            FROM `tabPayroll Cycle`
            WHERE status = 'Completed' AND docstatus = 1
        """)[0][0] or 0,
        "by_frequency": frappe.db.sql("""
            SELECT payroll_frequency, COUNT(*) as count, SUM(total_amount) as amount
            FROM `tabPayroll Cycle`
            WHERE docstatus = 1
            GROUP BY payroll_frequency
        """, as_dict=True),
        "recent_cycles": frappe.db.sql("""
            SELECT payroll_cycle_name, start_date, end_date, status, total_amount
            FROM `tabPayroll Cycle`
            WHERE docstatus = 1
            ORDER BY start_date DESC
            LIMIT 5
        """, as_dict=True)
    }


@frappe.whitelist()
def create_monthly_payroll_cycle(month, year):
    """Create monthly payroll cycle for given month/year"""
    from calendar import monthrange
    
    # Calculate dates
    start_date = datetime(int(year), int(month), 1).date()
    last_day = monthrange(int(year), int(month))[1]
    end_date = datetime(int(year), int(month), last_day).date()
    payment_date = add_days(end_date, 5)  # Pay 5 days after month end
    
    # Check if cycle already exists
    existing = frappe.db.exists("Payroll Cycle", {
        "start_date": start_date,
        "end_date": end_date,
        "payroll_frequency": "Monthly"
    })
    
    if existing:
        frappe.throw(_("Payroll cycle already exists for {0}/{1}").format(month, year))
        
    # Create new cycle
    cycle = frappe.new_doc("Payroll Cycle")
    cycle.payroll_frequency = "Monthly"
    cycle.start_date = start_date
    cycle.end_date = end_date
    cycle.payment_date = payment_date
    cycle.insert()
    
    return cycle.name
