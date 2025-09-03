import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, nowtime, flt, cint
from frappe import _


class StockLedger(Document):
    def validate(self):
        self.validate_item()
        self.validate_warehouse()
        self.validate_qty()
        self.set_item_details()
        
    def validate_item(self):
        """Validate item exists and is active"""
        if not frappe.db.exists("Stock Item", self.item_code):
            frappe.throw(_("Item {0} does not exist").format(self.item_code))
            
        item = frappe.get_doc("Stock Item", self.item_code)
        if not item.is_active:
            frappe.throw(_("Item {0} is inactive").format(self.item_code))
            
    def validate_warehouse(self):
        """Validate warehouse exists"""
        if not self.warehouse:
            frappe.throw(_("Warehouse is required"))
            
    def validate_qty(self):
        """Validate quantity"""
        if not self.actual_qty:
            frappe.throw(_("Quantity change cannot be zero"))
            
    def set_item_details(self):
        """Set item name from item master"""
        if self.item_code and not self.item_name:
            self.item_name = frappe.db.get_value("Stock Item", self.item_code, "item_name")
            
    def before_submit(self):
        self.calculate_stock_value()
        self.update_stock_balance()
        
    def calculate_stock_value(self):
        """Calculate stock value and differences"""
        if not self.valuation_rate:
            # Get last valuation rate
            last_sle = frappe.db.sql("""
                SELECT valuation_rate, stock_value
                FROM `tabStock Ledger`
                WHERE item_code = %s AND warehouse = %s
                AND posting_date <= %s AND posting_time <= %s
                AND docstatus = 1 AND name != %s
                ORDER BY posting_date DESC, posting_time DESC, creation DESC
                LIMIT 1
            """, (self.item_code, self.warehouse, self.posting_date, self.posting_time, self.name), as_dict=True)
            
            if last_sle:
                self.valuation_rate = last_sle[0].valuation_rate or 0
            else:
                # Get standard rate from item
                self.valuation_rate = frappe.db.get_value("Stock Item", self.item_code, "standard_rate") or 0
                
        # Calculate stock value difference
        self.stock_value_difference = flt(self.actual_qty) * flt(self.valuation_rate)
        
        # Get previous stock value
        prev_stock_value = self.get_previous_stock_value()
        self.stock_value = flt(prev_stock_value) + flt(self.stock_value_difference)
        
    def get_previous_stock_value(self):
        """Get previous stock value"""
        prev_sle = frappe.db.sql("""
            SELECT stock_value
            FROM `tabStock Ledger`
            WHERE item_code = %s AND warehouse = %s
            AND posting_date <= %s AND posting_time <= %s
            AND docstatus = 1 AND name != %s
            ORDER BY posting_date DESC, posting_time DESC, creation DESC
            LIMIT 1
        """, (self.item_code, self.warehouse, self.posting_date, self.posting_time, self.name))
        
        return prev_sle[0][0] if prev_sle else 0
        
    def update_stock_balance(self):
        """Update quantity after transaction"""
        prev_qty = self.get_previous_qty()
        self.qty_after_transaction = flt(prev_qty) + flt(self.actual_qty)
        
    def get_previous_qty(self):
        """Get previous quantity balance"""
        prev_sle = frappe.db.sql("""
            SELECT qty_after_transaction
            FROM `tabStock Ledger`
            WHERE item_code = %s AND warehouse = %s
            AND posting_date <= %s AND posting_time <= %s
            AND docstatus = 1 AND name != %s
            ORDER BY posting_date DESC, posting_time DESC, creation DESC
            LIMIT 1
        """, (self.item_code, self.warehouse, self.posting_date, self.posting_time, self.name))
        
        return prev_sle[0][0] if prev_sle else 0
        
    def on_submit(self):
        self.update_item_stock_balance()
        self.create_stock_analytics()
        
    def on_cancel(self):
        self.revert_stock_balance()
        
    def update_item_stock_balance(self):
        """Update stock balance in Stock Item"""
        current_stock = frappe.db.sql("""
            SELECT SUM(actual_qty) as total_qty,
                   SUM(stock_value_difference) as total_value
            FROM `tabStock Ledger`
            WHERE item_code = %s AND warehouse = %s AND docstatus = 1
        """, (self.item_code, self.warehouse), as_dict=True)
        
        if current_stock:
            total_qty = current_stock[0].total_qty or 0
            total_value = current_stock[0].total_value or 0
            
            # Update item stock balance
            frappe.db.sql("""
                UPDATE `tabStock Item`
                SET current_stock = %s, stock_value = %s
                WHERE name = %s
            """, (total_qty, total_value, self.item_code))
            
    def revert_stock_balance(self):
        """Revert stock balance on cancellation"""
        self.update_item_stock_balance()
        
    def create_stock_analytics(self):
        """Create stock movement analytics"""
        frappe.get_doc({
            "doctype": "Stock Analytics",
            "item_code": self.item_code,
            "warehouse": self.warehouse,
            "transaction_type": self.voucher_type,
            "qty_change": self.actual_qty,
            "value_change": self.stock_value_difference,
            "posting_date": self.posting_date,
            "reference_type": self.doctype,
            "reference_name": self.name
        }).insert(ignore_permissions=True)


@frappe.whitelist()
def get_stock_balance(item_code, warehouse=None, posting_date=None):
    """Get current stock balance for item"""
    conditions = ["item_code = %s", "docstatus = 1"]
    values = [item_code]
    
    if warehouse:
        conditions.append("warehouse = %s")
        values.append(warehouse)
        
    if posting_date:
        conditions.append("posting_date <= %s")
        values.append(posting_date)
        
    result = frappe.db.sql("""
        SELECT SUM(actual_qty) as balance,
               SUM(stock_value_difference) as value
        FROM `tabStock Ledger`
        WHERE {0}
    """.format(" AND ".join(conditions)), values, as_dict=True)
    
    if result:
        return {
            "balance": result[0].balance or 0,
            "value": result[0].value or 0
        }
    return {"balance": 0, "value": 0}


@frappe.whitelist()
def get_stock_ledger_entries(item_code, warehouse=None, from_date=None, to_date=None):
    """Get stock ledger entries with filters"""
    conditions = ["item_code = %s", "docstatus = 1"]
    values = [item_code]
    
    if warehouse:
        conditions.append("warehouse = %s")
        values.append(warehouse)
        
    if from_date:
        conditions.append("posting_date >= %s")
        values.append(from_date)
        
    if to_date:
        conditions.append("posting_date <= %s")
        values.append(to_date)
        
    return frappe.db.sql("""
        SELECT name, posting_date, posting_time, voucher_type, voucher_no,
               actual_qty, qty_after_transaction, valuation_rate, stock_value_difference
        FROM `tabStock Ledger`
        WHERE {0}
        ORDER BY posting_date DESC, posting_time DESC, creation DESC
    """.format(" AND ".join(conditions)), values, as_dict=True)


@frappe.whitelist()
def get_stock_analytics():
    """Get stock movement analytics"""
    return {
        "total_transactions": frappe.db.count("Stock Ledger", {"docstatus": 1}),
        "items_in_stock": frappe.db.sql("""
            SELECT COUNT(DISTINCT item_code) as count
            FROM `tabStock Ledger`
            WHERE docstatus = 1
        """)[0][0],
        "total_stock_value": frappe.db.sql("""
            SELECT SUM(stock_value_difference) as value
            FROM `tabStock Ledger`
            WHERE docstatus = 1
        """)[0][0] or 0,
        "by_voucher_type": frappe.db.sql("""
            SELECT voucher_type, COUNT(*) as count, SUM(ABS(actual_qty)) as total_qty
            FROM `tabStock Ledger`
            WHERE docstatus = 1
            GROUP BY voucher_type
        """, as_dict=True),
        "recent_movements": frappe.db.sql("""
            SELECT item_code, warehouse, actual_qty, posting_date, voucher_type
            FROM `tabStock Ledger`
            WHERE docstatus = 1
            ORDER BY posting_date DESC, posting_time DESC
            LIMIT 10
        """, as_dict=True)
    }
