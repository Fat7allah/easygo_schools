import frappe
from frappe import _
from frappe.utils import flt, cint, getdate


def execute(filters=None):
    """Execute Communication Analytics Report"""
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data, filters)
    
    return columns, data, None, chart


def get_columns():
    """Get report columns"""
    return [
        {
            "fieldname": "communication_type",
            "label": _("Communication Type"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "channel",
            "label": _("Channel"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "total_sent",
            "label": _("Total Sent"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "delivered",
            "label": _("Delivered"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "failed",
            "label": _("Failed"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "delivery_rate",
            "label": _("Delivery Rate %"),
            "fieldtype": "Percent",
            "width": 120
        },
        {
            "fieldname": "avg_response_time",
            "label": _("Avg Response Time (hrs)"),
            "fieldtype": "Float",
            "width": 150
        }
    ]


def get_data(filters):
    """Get report data"""
    conditions = get_conditions(filters)
    
    data = frappe.db.sql(f"""
        SELECT 
            cl.communication_type,
            cl.channel,
            COUNT(*) as total_sent,
            SUM(CASE WHEN cl.status = 'Delivered' THEN 1 ELSE 0 END) as delivered,
            SUM(CASE WHEN cl.status = 'Failed' THEN 1 ELSE 0 END) as failed,
            (SUM(CASE WHEN cl.status = 'Delivered' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as delivery_rate,
            AVG(CASE 
                WHEN cl.response_received = 1 AND cl.response_time IS NOT NULL 
                THEN TIMESTAMPDIFF(HOUR, cl.sent_time, cl.response_time)
                ELSE NULL 
            END) as avg_response_time
        FROM `tabCommunication Log` cl
        WHERE cl.docstatus = 1 {conditions}
        GROUP BY cl.communication_type, cl.channel
        ORDER BY cl.communication_type, cl.channel
    """, filters, as_dict=True)
    
    return data


def get_conditions(filters):
    """Build SQL conditions from filters"""
    conditions = []
    
    if filters.get("from_date"):
        conditions.append("cl.sent_date >= %(from_date)s")
        
    if filters.get("to_date"):
        conditions.append("cl.sent_date <= %(to_date)s")
        
    if filters.get("communication_type"):
        conditions.append("cl.communication_type = %(communication_type)s")
        
    if filters.get("channel"):
        conditions.append("cl.channel = %(channel)s")
        
    if filters.get("status"):
        conditions.append("cl.status = %(status)s")
        
    return " AND " + " AND ".join(conditions) if conditions else ""


def get_chart_data(data, filters):
    """Generate chart data for communication analytics"""
    if not data:
        return None
        
    # Channel-wise delivery rates
    channels = []
    delivery_rates = []
    
    for row in data:
        channels.append(f"{row.communication_type} - {row.channel}")
        delivery_rates.append(flt(row.delivery_rate, 2))
        
    return {
        "data": {
            "labels": channels,
            "datasets": [
                {
                    "name": _("Delivery Rate %"),
                    "values": delivery_rates
                }
            ]
        },
        "type": "bar"
    }


@frappe.whitelist()
def get_communication_summary(filters=None):
    """Get communication summary for dashboard"""
    conditions = get_conditions(filters)
    
    summary = frappe.db.sql(f"""
        SELECT 
            COUNT(*) as total_communications,
            SUM(CASE WHEN cl.status = 'Delivered' THEN 1 ELSE 0 END) as total_delivered,
            SUM(CASE WHEN cl.status = 'Failed' THEN 1 ELSE 0 END) as total_failed,
            SUM(CASE WHEN cl.status = 'Pending' THEN 1 ELSE 0 END) as total_pending,
            AVG(CASE WHEN cl.status = 'Delivered' THEN 100.0 ELSE 0 END) as avg_delivery_rate,
            COUNT(CASE WHEN cl.response_received = 1 THEN 1 END) as responses_received
        FROM `tabCommunication Log` cl
        WHERE cl.docstatus = 1 {conditions}
    """, filters, as_dict=True)
    
    return summary[0] if summary else {}
