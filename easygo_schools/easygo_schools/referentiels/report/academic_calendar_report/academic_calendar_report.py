import frappe
from frappe import _
from frappe.utils import getdate, add_days, get_datetime


def execute(filters=None):
    """Execute Academic Calendar Report"""
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data


def get_columns():
    """Get report columns"""
    return [
        {
            "fieldname": "academic_year",
            "label": _("Academic Year"),
            "fieldtype": "Link",
            "options": "Academic Year",
            "width": 150
        },
        {
            "fieldname": "year_start_date",
            "label": _("Year Start"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "year_end_date",
            "label": _("Year End"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "term_name",
            "label": _("Term"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "term_start_date",
            "label": _("Term Start"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "term_end_date",
            "label": _("Term End"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "total_days",
            "label": _("Total Days"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "working_days",
            "label": _("Working Days"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "holidays",
            "label": _("Holidays"),
            "fieldtype": "Int",
            "width": 100
        }
    ]


def get_data(filters):
    """Get report data"""
    conditions = get_conditions(filters)
    
    # Get academic years with terms
    data = frappe.db.sql(f"""
        SELECT 
            ay.name as academic_year,
            ay.year_start_date,
            ay.year_end_date,
            at.term_name,
            at.term_start_date,
            at.term_end_date,
            DATEDIFF(at.term_end_date, at.term_start_date) + 1 as total_days
        FROM `tabAcademic Year` ay
        LEFT JOIN `tabAcademic Term` at ON at.academic_year = ay.name
        WHERE ay.enabled = 1 {conditions}
        ORDER BY ay.year_start_date, at.term_start_date
    """, filters, as_dict=True)
    
    # Calculate working days and holidays for each term
    for row in data:
        if row.term_start_date and row.term_end_date:
            working_days, holidays = calculate_working_days(
                row.term_start_date, 
                row.term_end_date
            )
            row.working_days = working_days
            row.holidays = holidays
        else:
            row.working_days = 0
            row.holidays = 0
            
    return data


def get_conditions(filters):
    """Build SQL conditions from filters"""
    conditions = []
    
    if filters.get("academic_year"):
        conditions.append("ay.name = %(academic_year)s")
        
    if filters.get("from_date"):
        conditions.append("ay.year_start_date >= %(from_date)s")
        
    if filters.get("to_date"):
        conditions.append("ay.year_end_date <= %(to_date)s")
        
    return " AND " + " AND ".join(conditions) if conditions else ""


def calculate_working_days(start_date, end_date):
    """Calculate working days and holidays between two dates"""
    from frappe.utils import get_weekdays
    
    total_days = (getdate(end_date) - getdate(start_date)).days + 1
    working_days = 0
    holidays = 0
    
    current_date = getdate(start_date)
    end_date = getdate(end_date)
    
    while current_date <= end_date:
        # Check if it's a weekend (assuming Friday-Saturday weekend)
        weekday = current_date.weekday()
        if weekday in [4, 5]:  # Friday = 4, Saturday = 5
            holidays += 1
        else:
            # Check if it's a holiday
            is_holiday = frappe.db.exists("Holiday", {
                "holiday_date": current_date,
                "weekly_off": 0
            })
            
            if is_holiday:
                holidays += 1
            else:
                working_days += 1
                
        current_date = add_days(current_date, 1)
        
    return working_days, holidays


@frappe.whitelist()
def get_calendar_summary(filters=None):
    """Get academic calendar summary"""
    conditions = get_conditions(filters)
    
    summary = frappe.db.sql(f"""
        SELECT 
            COUNT(DISTINCT ay.name) as total_years,
            COUNT(at.name) as total_terms,
            MIN(ay.year_start_date) as earliest_start,
            MAX(ay.year_end_date) as latest_end
        FROM `tabAcademic Year` ay
        LEFT JOIN `tabAcademic Term` at ON at.academic_year = ay.name
        WHERE ay.enabled = 1 {conditions}
    """, filters, as_dict=True)
    
    return summary[0] if summary else {}
