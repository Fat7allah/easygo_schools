"""Stock Item DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, add_days


class StockItem(Document):
    """Stock Item management."""
    
    def validate(self):
        """Validate stock item data."""
        self.validate_stock_levels()
        self.validate_rates()
        self.validate_expiry_date()
        self.set_defaults()
    
    def validate_stock_levels(self):
        """Validate stock level configurations."""
        if self.minimum_stock_level and self.maximum_stock_level:
            if flt(self.minimum_stock_level) >= flt(self.maximum_stock_level):
                frappe.throw(_("Minimum stock level must be less than maximum stock level"))
        
        if self.reorder_level and self.minimum_stock_level:
            if flt(self.reorder_level) < flt(self.minimum_stock_level):
                frappe.throw(_("Reorder level should be greater than or equal to minimum stock level"))
    
    def validate_rates(self):
        """Validate pricing information."""
        if self.standard_rate and self.standard_rate < 0:
            frappe.throw(_("Standard rate cannot be negative"))
    
    def validate_expiry_date(self):
        """Validate expiry date."""
        if self.expiry_date and getdate(self.expiry_date) <= getdate():
            frappe.msgprint(_("Warning: Item has expired or will expire soon"), alert=True)
    
    def set_defaults(self):
        """Set default values."""
        if not self.unit_of_measure:
            self.unit_of_measure = "Nos"
        
        if not self.current_stock:
            self.current_stock = 0
    
    def on_update(self):
        """Actions after update."""
        self.check_reorder_level()
        self.update_average_rate()
    
    def check_reorder_level(self):
        """Check if item needs reordering."""
        if (self.is_stock_item and self.reorder_level and 
            flt(self.current_stock) <= flt(self.reorder_level)):
            
            self.create_reorder_alert()
    
    def create_reorder_alert(self):
        """Create reorder alert."""
        existing_alert = frappe.db.exists("Stock Alert", {
            "item_code": self.item_code,
            "alert_type": "Reorder",
            "status": "Open"
        })
        
        if not existing_alert:
            alert_doc = frappe.get_doc({
                "doctype": "Stock Alert",
                "item_code": self.item_code,
                "item_name": self.item_name,
                "alert_type": "Reorder",
                "current_stock": self.current_stock,
                "reorder_level": self.reorder_level,
                "reorder_quantity": self.reorder_quantity,
                "preferred_supplier": self.preferred_supplier,
                "status": "Open",
                "alert_date": getdate()
            })
            
            alert_doc.insert(ignore_permissions=True)
            
            # Notify stock manager
            self.notify_stock_manager("reorder")
    
    def update_average_rate(self):
        """Update average rate based on stock entries."""
        if not self.is_stock_item:
            return
        
        # Calculate weighted average rate
        stock_entries = frappe.db.sql("""
            SELECT SUM(quantity * rate) as total_value, SUM(quantity) as total_qty
            FROM `tabStock Entry Detail`
            WHERE item_code = %s
            AND parent IN (
                SELECT name FROM `tabStock Entry`
                WHERE docstatus = 1
                AND entry_type = 'Material Receipt'
            )
        """, [self.item_code], as_dict=True)
        
        if stock_entries and stock_entries[0].total_qty:
            self.average_rate = flt(stock_entries[0].total_value) / flt(stock_entries[0].total_qty)
    
    @frappe.whitelist()
    def update_stock(self, quantity, rate=None, entry_type="Manual"):
        """Update stock quantity."""
        if not self.is_stock_item:
            frappe.throw(_("Cannot update stock for non-stock item"))
        
        # Create stock entry
        stock_entry = frappe.get_doc({
            "doctype": "Stock Entry",
            "entry_type": entry_type,
            "posting_date": getdate(),
            "items": [{
                "item_code": self.item_code,
                "quantity": quantity,
                "rate": rate or self.standard_rate or 0
            }]
        })
        
        stock_entry.insert()
        stock_entry.submit()
        
        # Update current stock
        self.current_stock = flt(self.current_stock) + flt(quantity)
        
        if rate:
            self.last_purchase_rate = rate
        
        self.save()
        
        return stock_entry.name
    
    @frappe.whitelist()
    def get_stock_balance(self):
        """Get current stock balance."""
        balance = frappe.db.sql("""
            SELECT SUM(
                CASE 
                    WHEN entry_type IN ('Material Receipt', 'Material Transfer In') THEN quantity
                    ELSE -quantity
                END
            ) as balance
            FROM `tabStock Entry Detail` sed
            JOIN `tabStock Entry` se ON se.name = sed.parent
            WHERE sed.item_code = %s
            AND se.docstatus = 1
        """, [self.item_code], as_list=True)
        
        return flt(balance[0][0]) if balance and balance[0][0] else 0
    
    @frappe.whitelist()
    def get_stock_ledger(self, from_date=None, to_date=None):
        """Get stock ledger entries."""
        conditions = ""
        if from_date:
            conditions += f" AND se.posting_date >= '{from_date}'"
        if to_date:
            conditions += f" AND se.posting_date <= '{to_date}'"
        
        ledger_entries = frappe.db.sql(f"""
            SELECT 
                se.posting_date,
                se.entry_type,
                se.name as voucher_no,
                sed.quantity,
                sed.rate,
                sed.amount,
                se.remarks
            FROM `tabStock Entry Detail` sed
            JOIN `tabStock Entry` se ON se.name = sed.parent
            WHERE sed.item_code = %s
            AND se.docstatus = 1
            {conditions}
            ORDER BY se.posting_date DESC, se.creation DESC
        """, [self.item_code], as_dict=True)
        
        # Calculate running balance
        running_balance = 0
        for entry in reversed(ledger_entries):
            if entry.entry_type in ['Material Receipt', 'Material Transfer In']:
                running_balance += flt(entry.quantity)
            else:
                running_balance -= flt(entry.quantity)
            entry['balance'] = running_balance
        
        return list(reversed(ledger_entries))
    
    def notify_stock_manager(self, alert_type):
        """Notify stock manager about alerts."""
        stock_manager = frappe.db.get_single_value("School Settings", "stock_manager")
        
        if stock_manager:
            if alert_type == "reorder":
                subject = _("Reorder Alert: {0}").format(self.item_name)
                message = self.get_reorder_message()
            elif alert_type == "low_stock":
                subject = _("Low Stock Alert: {0}").format(self.item_name)
                message = self.get_low_stock_message()
            else:
                return
            
            frappe.sendmail(
                recipients=[stock_manager],
                subject=subject,
                message=message,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_reorder_message(self):
        """Get reorder notification message."""
        return _("""
        Stock Reorder Alert
        
        Item: {item_name} ({item_code})
        Current Stock: {current_stock} {uom}
        Reorder Level: {reorder_level} {uom}
        Suggested Reorder Quantity: {reorder_quantity} {uom}
        
        Preferred Supplier: {preferred_supplier}
        Lead Time: {lead_time} days
        
        Please initiate purchase order for this item.
        """).format(
            item_name=self.item_name,
            item_code=self.item_code,
            current_stock=self.current_stock,
            uom=self.unit_of_measure,
            reorder_level=self.reorder_level,
            reorder_quantity=self.reorder_quantity or "Not specified",
            preferred_supplier=self.preferred_supplier or "Not specified",
            lead_time=self.lead_time_days or "Not specified"
        )
    
    def get_low_stock_message(self):
        """Get low stock notification message."""
        return _("""
        Low Stock Alert
        
        Item: {item_name} ({item_code})
        Current Stock: {current_stock} {uom}
        Minimum Stock Level: {minimum_stock} {uom}
        
        Please replenish stock for this item.
        """).format(
            item_name=self.item_name,
            item_code=self.item_code,
            current_stock=self.current_stock,
            uom=self.unit_of_measure,
            minimum_stock=self.minimum_stock_level
        )
    
    @frappe.whitelist()
    def check_expiry_items(self):
        """Check for items nearing expiry."""
        if not self.shelf_life_days:
            return []
        
        # Check items expiring in next 30 days
        expiry_threshold = add_days(getdate(), 30)
        
        if self.expiry_date and getdate(self.expiry_date) <= expiry_threshold:
            return [{
                "item_code": self.item_code,
                "item_name": self.item_name,
                "current_stock": self.current_stock,
                "expiry_date": self.expiry_date,
                "days_to_expiry": (getdate(self.expiry_date) - getdate()).days
            }]
        
        return []
    
    def get_consumption_pattern(self, months=6):
        """Get consumption pattern for the item."""
        consumption_data = frappe.db.sql("""
            SELECT 
                DATE_FORMAT(se.posting_date, '%%Y-%%m') as month,
                SUM(sed.quantity) as consumed_qty
            FROM `tabStock Entry Detail` sed
            JOIN `tabStock Entry` se ON se.name = sed.parent
            WHERE sed.item_code = %s
            AND se.entry_type = 'Material Issue'
            AND se.docstatus = 1
            AND se.posting_date >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)
            GROUP BY DATE_FORMAT(se.posting_date, '%%Y-%%m')
            ORDER BY month DESC
        """, [self.item_code, months], as_dict=True)
        
        return consumption_data
    
    @frappe.whitelist()
    def generate_barcode(self):
        """Generate barcode for the item."""
        if not self.barcode:
            # Simple barcode generation - can be enhanced
            self.barcode = f"EGE{self.item_code}"
            self.save()
        
        return self.barcode
    
    @frappe.whitelist()
    def generate_qr_code(self):
        """Generate QR code for the item."""
        if not self.qr_code:
            # QR code contains item information
            qr_data = {
                "item_code": self.item_code,
                "item_name": self.item_name,
                "current_stock": self.current_stock,
                "location": self.storage_location
            }
            
            import json
            self.qr_code = json.dumps(qr_data)
            self.save()
        
        return self.qr_code
