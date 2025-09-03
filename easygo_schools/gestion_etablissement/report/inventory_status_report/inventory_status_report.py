import frappe
from frappe import _
from frappe.utils import flt, cint


def execute(filters=None):
    """Execute Inventory Status Report"""
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data, filters)
    
    return columns, data, None, chart


def get_columns():
    """Get report columns"""
    return [
        {
            "fieldname": "item_code",
            "label": _("Item Code"),
            "fieldtype": "Link",
            "options": "Item",
            "width": 120
        },
        {
            "fieldname": "item_name",
            "label": _("Item Name"),
            "fieldtype": "Data",
            "width": 180
        },
        {
            "fieldname": "item_group",
            "label": _("Item Group"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "warehouse",
            "label": _("Warehouse"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "current_qty",
            "label": _("Current Qty"),
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "valuation_rate",
            "label": _("Valuation Rate"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "stock_value",
            "label": _("Stock Value"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "reorder_level",
            "label": _("Reorder Level"),
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 100
        }
    ]


def get_data(filters):
    """Get report data"""
    conditions = get_conditions(filters)
    
    data = frappe.db.sql(f"""
        SELECT 
            sl.item_code,
            sl.item_name,
            sl.item_group,
            sl.warehouse,
            SUM(sl.actual_qty) as current_qty,
            AVG(sl.valuation_rate) as valuation_rate,
            SUM(sl.stock_value) as stock_value,
            COALESCE(i.reorder_level, 0) as reorder_level
        FROM `tabStock Ledger` sl
        LEFT JOIN `tabItem` i ON sl.item_code = i.name
        WHERE sl.docstatus = 1 {conditions}
        GROUP BY sl.item_code, sl.warehouse
        HAVING current_qty != 0
        ORDER BY sl.item_name, sl.warehouse
    """, filters, as_dict=True)
    
    # Add status based on stock levels
    for row in data:
        current_qty = flt(row.current_qty)
        reorder_level = flt(row.reorder_level)
        
        if current_qty <= 0:
            row.status = "Out of Stock"
        elif reorder_level > 0 and current_qty <= reorder_level:
            row.status = "Low Stock"
        elif current_qty > reorder_level * 2:
            row.status = "Overstock"
        else:
            row.status = "Normal"
            
    return data


def get_conditions(filters):
    """Build SQL conditions from filters"""
    conditions = []
    
    if filters.get("item_code"):
        conditions.append("sl.item_code = %(item_code)s")
        
    if filters.get("item_group"):
        conditions.append("sl.item_group = %(item_group)s")
        
    if filters.get("warehouse"):
        conditions.append("sl.warehouse = %(warehouse)s")
        
    if filters.get("from_date"):
        conditions.append("sl.posting_date >= %(from_date)s")
        
    if filters.get("to_date"):
        conditions.append("sl.posting_date <= %(to_date)s")
        
    return " AND " + " AND ".join(conditions) if conditions else ""


def get_chart_data(data, filters):
    """Generate chart data for inventory report"""
    if not data:
        return None
        
    # Stock status distribution
    status_counts = {}
    status_values = {}
    
    for row in data:
        status = row.get("status", "Unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        status_values[status] = status_values.get(status, 0) + flt(row.get("stock_value", 0))
        
    return {
        "data": {
            "labels": list(status_counts.keys()),
            "datasets": [
                {
                    "name": _("Stock Value"),
                    "values": list(status_values.values())
                }
            ]
        },
        "type": "pie",
        "colors": ["#28a745", "#ffc107", "#dc3545", "#17a2b8"]
    }


@frappe.whitelist()
def get_inventory_summary(filters=None):
    """Get inventory summary for dashboard"""
    conditions = get_conditions(filters)
    
    summary = frappe.db.sql(f"""
        SELECT 
            COUNT(DISTINCT sl.item_code) as total_items,
            COUNT(DISTINCT sl.warehouse) as total_warehouses,
            SUM(sl.actual_qty) as total_qty,
            SUM(sl.stock_value) as total_value,
            AVG(sl.valuation_rate) as avg_rate
        FROM `tabStock Ledger` sl
        WHERE sl.docstatus = 1 {conditions}
    """, filters, as_dict=True)
    
    # Get low stock items count
    low_stock_count = frappe.db.sql(f"""
        SELECT COUNT(DISTINCT sl.item_code) as count
        FROM `tabStock Ledger` sl
        LEFT JOIN `tabItem` i ON sl.item_code = i.name
        WHERE sl.docstatus = 1 {conditions}
        GROUP BY sl.item_code
        HAVING SUM(sl.actual_qty) <= COALESCE(i.reorder_level, 0)
    """, filters)
    
    result = summary[0] if summary else {}
    result["low_stock_items"] = len(low_stock_count) if low_stock_count else 0
    
    return result
