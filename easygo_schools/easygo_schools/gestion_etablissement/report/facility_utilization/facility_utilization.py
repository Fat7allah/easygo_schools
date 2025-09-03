"""Facility Utilization Report."""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    """Execute the Facility Utilization Report."""
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data)
    
    return columns, data, None, chart


def get_columns():
    """Get report columns."""
    return [
        {
            "label": _("Room"),
            "fieldname": "room_name",
            "fieldtype": "Link",
            "options": "Room",
            "width": 150
        },
        {
            "label": _("Room Type"),
            "fieldname": "room_type",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Capacity"),
            "fieldname": "capacity",
            "fieldtype": "Int",
            "width": 80
        },
        {
            "label": _("Total Bookings"),
            "fieldname": "total_bookings",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": _("Hours Booked"),
            "fieldname": "hours_booked",
            "fieldtype": "Float",
            "width": 120,
            "precision": 1
        },
        {
            "label": _("Utilization Rate"),
            "fieldname": "utilization_rate",
            "fieldtype": "Percent",
            "width": 120
        },
        {
            "label": _("Peak Usage Hours"),
            "fieldname": "peak_hours",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Maintenance Hours"),
            "fieldname": "maintenance_hours",
            "fieldtype": "Float",
            "width": 120,
            "precision": 1
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        }
    ]


def get_data(filters):
    """Get report data."""
    conditions = get_conditions(filters)
    
    # Get room data with booking statistics
    data = frappe.db.sql(f"""
        SELECT 
            r.room_name,
            r.room_type,
            r.capacity,
            r.status,
            COALESCE(bookings.total_bookings, 0) as total_bookings,
            COALESCE(bookings.hours_booked, 0) as hours_booked,
            COALESCE(maintenance.maintenance_hours, 0) as maintenance_hours
        FROM `tabRoom` r
        LEFT JOIN (
            SELECT 
                room,
                COUNT(*) as total_bookings,
                SUM(TIMESTAMPDIFF(HOUR, start_time, end_time)) as hours_booked
            FROM `tabRoom Booking`
            WHERE status = 'Confirmed' {conditions.get('booking_conditions', '')}
            GROUP BY room
        ) bookings ON bookings.room = r.name
        LEFT JOIN (
            SELECT 
                room,
                SUM(TIMESTAMPDIFF(HOUR, work_started, work_completed)) as maintenance_hours
            FROM `tabMaintenance Request`
            WHERE status = 'Completed' 
            AND work_started IS NOT NULL 
            AND work_completed IS NOT NULL
            {conditions.get('maintenance_conditions', '')}
            GROUP BY room
        ) maintenance ON maintenance.room = r.name
        WHERE r.is_active = 1 {conditions.get('room_conditions', '')}
        ORDER BY r.room_name
    """, as_dict=True)
    
    # Calculate utilization rates and peak hours
    for row in data:
        # Calculate utilization rate based on available hours
        # Assuming 8 hours per day, 5 days per week for calculation
        available_hours_per_week = 40
        weeks_in_period = get_weeks_in_period(filters)
        total_available_hours = available_hours_per_week * weeks_in_period
        
        if total_available_hours > 0:
            row.utilization_rate = (row.hours_booked / total_available_hours) * 100
        else:
            row.utilization_rate = 0
        
        # Get peak usage hours (simplified - would need actual booking data)
        row.peak_hours = get_peak_usage_hours(row.room_name, filters)
    
    return data


def get_conditions(filters):
    """Get query conditions based on filters."""
    conditions = {
        'room_conditions': '',
        'booking_conditions': '',
        'maintenance_conditions': ''
    }
    
    if filters.get('room_type'):
        conditions['room_conditions'] += f" AND r.room_type = '{filters['room_type']}'"
    
    if filters.get('from_date'):
        conditions['booking_conditions'] += f" AND booking_date >= '{filters['from_date']}'"
        conditions['maintenance_conditions'] += f" AND request_date >= '{filters['from_date']}'"
    
    if filters.get('to_date'):
        conditions['booking_conditions'] += f" AND booking_date <= '{filters['to_date']}'"
        conditions['maintenance_conditions'] += f" AND request_date <= '{filters['to_date']}'"
    
    return conditions


def get_weeks_in_period(filters):
    """Calculate number of weeks in the reporting period."""
    if filters.get('from_date') and filters.get('to_date'):
        from frappe.utils import date_diff
        days = date_diff(filters['to_date'], filters['from_date'])
        return max(1, days / 7)
    return 4  # Default to 4 weeks


def get_peak_usage_hours(room_name, filters):
    """Get peak usage hours for a room (simplified implementation)."""
    # This would analyze actual booking patterns
    # For now, return a placeholder
    peak_times = [
        "9:00-10:00 AM",
        "10:00-11:00 AM", 
        "2:00-3:00 PM"
    ]
    
    # In real implementation, would query booking data to find actual peak hours
    return ", ".join(peak_times[:2])


def get_chart_data(data):
    """Get chart data for visualization."""
    if not data:
        return None
    
    # Sort by utilization rate for better visualization
    sorted_data = sorted(data, key=lambda x: x.utilization_rate, reverse=True)[:10]
    
    labels = [row.room_name for row in sorted_data]
    utilization_rates = [flt(row.utilization_rate) for row in sorted_data]
    
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Utilization Rate %"),
                    "values": utilization_rates
                }
            ]
        },
        "type": "bar",
        "height": 300,
        "colors": ["#17a2b8"]
    }
