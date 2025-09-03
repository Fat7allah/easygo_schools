"""Attendance Analytics Report."""

import frappe
from frappe import _
from frappe.utils import getdate, date_diff


def execute(filters=None):
    """Execute the Attendance Analytics Report."""
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data, filters)
    
    return columns, data, None, chart


def get_columns():
    """Get report columns."""
    return [
        {
            "label": _("Date"),
            "fieldname": "attendance_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": _("Class"),
            "fieldname": "school_class",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Total Students"),
            "fieldname": "total_students",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": _("Present"),
            "fieldname": "present_count",
            "fieldtype": "Int",
            "width": 80
        },
        {
            "label": _("Absent"),
            "fieldname": "absent_count",
            "fieldtype": "Int",
            "width": 80
        },
        {
            "label": _("Late"),
            "fieldname": "late_count",
            "fieldtype": "Int",
            "width": 80
        },
        {
            "label": _("Excused"),
            "fieldname": "excused_count",
            "fieldtype": "Int",
            "width": 80
        },
        {
            "label": _("Attendance Rate"),
            "fieldname": "attendance_rate",
            "fieldtype": "Percent",
            "width": 120
        },
        {
            "label": _("Punctuality Rate"),
            "fieldname": "punctuality_rate",
            "fieldtype": "Percent",
            "width": 120
        }
    ]


def get_data(filters):
    """Get report data."""
    conditions = get_conditions(filters)
    
    data = frappe.db.sql(f"""
        SELECT 
            sa.attendance_date,
            sa.school_class,
            COUNT(*) as total_students,
            COUNT(CASE WHEN sa.status = 'Present' THEN 1 END) as present_count,
            COUNT(CASE WHEN sa.status = 'Absent' THEN 1 END) as absent_count,
            COUNT(CASE WHEN sa.status = 'Late' THEN 1 END) as late_count,
            COUNT(CASE WHEN sa.status = 'Excused' THEN 1 END) as excused_count
        FROM `tabStudent Attendance` sa
        WHERE sa.docstatus = 1 {conditions}
        GROUP BY sa.attendance_date, sa.school_class
        ORDER BY sa.attendance_date DESC, sa.school_class
    """, as_dict=True)
    
    # Calculate rates
    for row in data:
        if row.total_students > 0:
            # Attendance rate (Present + Late + Excused) / Total
            attended = row.present_count + row.late_count + row.excused_count
            row.attendance_rate = (attended / row.total_students) * 100
            
            # Punctuality rate (Present) / (Present + Late)
            on_time_total = row.present_count + row.late_count
            if on_time_total > 0:
                row.punctuality_rate = (row.present_count / on_time_total) * 100
            else:
                row.punctuality_rate = 0
        else:
            row.attendance_rate = 0
            row.punctuality_rate = 0
    
    return data


def get_conditions(filters):
    """Get query conditions based on filters."""
    conditions = ""
    
    if filters.get('from_date'):
        conditions += f" AND sa.attendance_date >= '{filters['from_date']}'"
    
    if filters.get('to_date'):
        conditions += f" AND sa.attendance_date <= '{filters['to_date']}'"
    
    if filters.get('school_class'):
        conditions += f" AND sa.school_class = '{filters['school_class']}'"
    
    if filters.get('academic_year'):
        conditions += f" AND sa.academic_year = '{filters['academic_year']}'"
    
    return conditions


def get_chart_data(data, filters):
    """Get chart data for visualization."""
    if not data:
        return None
    
    # Aggregate data by date for trend analysis
    date_wise_data = {}
    for row in data:
        date = row.attendance_date
        if date not in date_wise_data:
            date_wise_data[date] = {
                'total': 0,
                'present': 0,
                'absent': 0,
                'late': 0,
                'excused': 0
            }
        
        date_wise_data[date]['total'] += row.total_students
        date_wise_data[date]['present'] += row.present_count
        date_wise_data[date]['absent'] += row.absent_count
        date_wise_data[date]['late'] += row.late_count
        date_wise_data[date]['excused'] += row.excused_count
    
    # Sort dates and prepare chart data
    sorted_dates = sorted(date_wise_data.keys())
    
    labels = [str(date) for date in sorted_dates[-30:]]  # Last 30 days
    attendance_rates = []
    
    for date in sorted_dates[-30:]:
        day_data = date_wise_data[date]
        if day_data['total'] > 0:
            attended = day_data['present'] + day_data['late'] + day_data['excused']
            rate = (attended / day_data['total']) * 100
            attendance_rates.append(round(rate, 2))
        else:
            attendance_rates.append(0)
    
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Attendance Rate %"),
                    "values": attendance_rates
                }
            ]
        },
        "type": "line",
        "height": 300,
        "colors": ["#28a745"]
    }
