"""Stock Entry DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, flt, cint, add_days


class StockEntry(Document):
    """Stock entry management for inventory transactions."""
    
    def validate(self):
        """Validate stock entry data."""
        self.validate_purpose()
        self.validate_items()
        self.validate_warehouses()
        self.calculate_totals()
        self.set_defaults()
    
    def validate_purpose(self):
        """Validate stock entry purpose."""
        if not self.purpose:
            frappe.throw(_("Purpose is required"))
        
        # Validate purpose-specific requirements
        if self.purpose in ["Material Transfer", "Material Transfer for Manufacture"]:
            if not self.from_warehouse and not any(item.s_warehouse for item in self.items):
                frappe.throw(_("Source warehouse is required for {0}").format(self.purpose))
            
            if not self.to_warehouse and not any(item.t_warehouse for item in self.items):
                frappe.throw(_("Target warehouse is required for {0}").format(self.purpose))
        
        elif self.purpose == "Material Issue":
            if not self.from_warehouse and not any(item.s_warehouse for item in self.items):
                frappe.throw(_("Source warehouse is required for Material Issue"))
        
        elif self.purpose == "Material Receipt":
            if not self.to_warehouse and not any(item.t_warehouse for item in self.items):
                frappe.throw(_("Target warehouse is required for Material Receipt"))
    
    def validate_items(self):
        """Validate stock entry items."""
        if not self.items:
            frappe.throw(_("Items are required"))
        
        for item in self.items:
            if not item.item_code:
                frappe.throw(_("Item Code is required in row {0}").format(item.idx))
            
            if flt(item.qty) <= 0:
                frappe.throw(_("Quantity must be greater than 0 in row {0}").format(item.idx))
            
            # Validate warehouse requirements based on purpose
            if self.purpose in ["Material Transfer", "Material Transfer for Manufacture"]:
                if not item.s_warehouse:
                    item.s_warehouse = self.from_warehouse
                if not item.t_warehouse:
                    item.t_warehouse = self.to_warehouse
                
                if not item.s_warehouse or not item.t_warehouse:
                    frappe.throw(_("Source and Target warehouse required for row {0}").format(item.idx))
                
                if item.s_warehouse == item.t_warehouse:
                    frappe.throw(_("Source and Target warehouse cannot be same in row {0}").format(item.idx))
            
            elif self.purpose == "Material Issue":
                if not item.s_warehouse:
                    item.s_warehouse = self.from_warehouse
                if not item.s_warehouse:
                    frappe.throw(_("Source warehouse required for row {0}").format(item.idx))
            
            elif self.purpose == "Material Receipt":
                if not item.t_warehouse:
                    item.t_warehouse = self.to_warehouse
                if not item.t_warehouse:
                    frappe.throw(_("Target warehouse required for row {0}").format(item.idx))
    
    def validate_warehouses(self):
        """Validate warehouse details."""
        warehouses = set()
        
        # Collect all warehouses
        if self.from_warehouse:
            warehouses.add(self.from_warehouse)
        if self.to_warehouse:
            warehouses.add(self.to_warehouse)
        
        for item in self.items:
            if item.s_warehouse:
                warehouses.add(item.s_warehouse)
            if item.t_warehouse:
                warehouses.add(item.t_warehouse)
        
        # Validate warehouse existence and status
        for warehouse in warehouses:
            if not frappe.db.exists("Warehouse", warehouse):
                frappe.throw(_("Warehouse {0} does not exist").format(warehouse))
            
            warehouse_doc = frappe.get_doc("Warehouse", warehouse)
            if warehouse_doc.disabled:
                frappe.throw(_("Warehouse {0} is disabled").format(warehouse))
    
    def calculate_totals(self):
        """Calculate stock entry totals."""
        self.total_outgoing_value = 0
        self.total_incoming_value = 0
        self.total_amount = 0
        
        for item in self.items:
            # Calculate item amount
            item.amount = flt(item.qty) * flt(item.basic_rate)
            
            # Add to totals based on purpose
            if item.s_warehouse:  # Outgoing
                self.total_outgoing_value += flt(item.amount)
            
            if item.t_warehouse:  # Incoming
                self.total_incoming_value += flt(item.amount)
            
            self.total_amount += flt(item.amount)
        
        # Calculate value difference
        self.value_difference = self.total_incoming_value - self.total_outgoing_value
        
        # Add additional costs
        self.total_additional_costs = 0
        if self.additional_costs:
            for cost in self.additional_costs:
                self.total_additional_costs += flt(cost.amount)
        
        self.total_amount += self.total_additional_costs
    
    def set_defaults(self):
        """Set default values."""
        if not self.posting_date:
            self.posting_date = getdate()
        
        if not self.posting_time:
            self.posting_time = now_datetime().time()
        
        # Set item defaults
        for item in self.items:
            if not item.basic_rate:
                # Get item valuation rate
                item.basic_rate = self.get_item_valuation_rate(item.item_code, item.s_warehouse)
            
            if not item.uom:
                item.uom = frappe.db.get_value("Item", item.item_code, "stock_uom")
    
    def get_item_valuation_rate(self, item_code, warehouse):
        """Get item valuation rate."""
        # Get latest valuation rate from stock ledger
        valuation_rate = frappe.db.sql("""
            SELECT valuation_rate
            FROM `tabStock Ledger Entry`
            WHERE item_code = %s
            AND warehouse = %s
            AND is_cancelled = 0
            ORDER BY posting_date DESC, posting_time DESC, creation DESC
            LIMIT 1
        """, (item_code, warehouse))
        
        if valuation_rate:
            return flt(valuation_rate[0][0])
        
        # Fallback to item's last purchase rate
        last_purchase_rate = frappe.db.get_value("Item", item_code, "last_purchase_rate")
        return flt(last_purchase_rate) if last_purchase_rate else 0
    
    def on_submit(self):
        """Actions on submit."""
        self.update_stock_ledger()
        self.send_stock_entry_notifications()
        self.update_related_documents()
    
    def update_stock_ledger(self):
        """Update stock ledger entries."""
        # This would typically create Stock Ledger Entry records
        # For now, we'll just validate the stock availability
        self.validate_stock_availability()
    
    def validate_stock_availability(self):
        """Validate stock availability for outgoing items."""
        for item in self.items:
            if item.s_warehouse:  # Outgoing item
                available_qty = self.get_available_stock(item.item_code, item.s_warehouse)
                
                if available_qty < flt(item.qty):
                    frappe.throw(_("Insufficient stock for item {0} in warehouse {1}. Available: {2}, Required: {3}").format(
                        item.item_code, item.s_warehouse, available_qty, item.qty
                    ))
    
    def get_available_stock(self, item_code, warehouse):
        """Get available stock quantity."""
        # Get current stock from stock ledger
        stock_qty = frappe.db.sql("""
            SELECT SUM(actual_qty)
            FROM `tabStock Ledger Entry`
            WHERE item_code = %s
            AND warehouse = %s
            AND is_cancelled = 0
        """, (item_code, warehouse))[0][0] or 0
        
        return flt(stock_qty)
    
    def send_stock_entry_notifications(self):
        """Send stock entry notifications."""
        # Notify stock managers
        self.send_stock_manager_notification()
        
        # Notify warehouse managers
        self.send_warehouse_notification()
        
        # Send purpose-specific notifications
        if self.purpose in ["Material Transfer", "Material Transfer for Manufacture"]:
            self.send_transfer_notification()
    
    def send_stock_manager_notification(self):
        """Send notification to stock managers."""
        stock_managers = frappe.get_all("Has Role",
            filters={"role": "Stock Manager"},
            fields=["parent"]
        )
        
        if stock_managers:
            recipients = [user.parent for user in stock_managers]
            
            frappe.sendmail(
                recipients=recipients,
                subject=_("Stock Entry Submitted - {0}").format(self.name),
                message=self.get_stock_manager_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_stock_manager_notification_message(self):
        """Get stock manager notification message."""
        return _("""
        Stock Entry Submitted
        
        Entry Number: {entry_number}
        Purpose: {purpose}
        Date: {posting_date}
        
        Transaction Summary:
        - Total Items: {total_items}
        - Total Outgoing Value: {outgoing_value}
        - Total Incoming Value: {incoming_value}
        - Value Difference: {value_difference}
        
        Warehouses Involved:
        - Source: {source_warehouse}
        - Target: {target_warehouse}
        
        {supplier_info}
        
        Remarks: {remarks}
        
        Stock Management System
        """).format(
            entry_number=self.name,
            purpose=self.purpose,
            posting_date=frappe.format(self.posting_date, "Date"),
            total_items=len(self.items),
            outgoing_value=frappe.format(self.total_outgoing_value, "Currency"),
            incoming_value=frappe.format(self.total_incoming_value, "Currency"),
            value_difference=frappe.format(self.value_difference, "Currency"),
            source_warehouse=self.from_warehouse or "Multiple",
            target_warehouse=self.to_warehouse or "Multiple",
            supplier_info=f"Supplier: {self.supplier_name}" if self.supplier else "",
            remarks=self.remarks or "None"
        )
    
    def send_warehouse_notification(self):
        """Send notification to warehouse managers."""
        warehouses = set()
        
        if self.from_warehouse:
            warehouses.add(self.from_warehouse)
        if self.to_warehouse:
            warehouses.add(self.to_warehouse)
        
        for item in self.items:
            if item.s_warehouse:
                warehouses.add(item.s_warehouse)
            if item.t_warehouse:
                warehouses.add(item.t_warehouse)
        
        # Get warehouse managers
        for warehouse in warehouses:
            warehouse_managers = frappe.db.get_value("Warehouse", warehouse, "warehouse_manager")
            
            if warehouse_managers:
                frappe.sendmail(
                    recipients=[warehouse_managers],
                    subject=_("Stock Movement - Warehouse {0}").format(warehouse),
                    message=self.get_warehouse_notification_message(warehouse),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
    
    def get_warehouse_notification_message(self, warehouse):
        """Get warehouse notification message."""
        # Get items affecting this warehouse
        warehouse_items = []
        for item in self.items:
            if item.s_warehouse == warehouse or item.t_warehouse == warehouse:
                direction = "OUT" if item.s_warehouse == warehouse else "IN"
                warehouse_items.append(f"- {item.item_code}: {item.qty} {item.uom} ({direction})")
        
        return _("""
        Stock Movement Notification
        
        Warehouse: {warehouse}
        Entry: {entry_number}
        Purpose: {purpose}
        Date: {posting_date}
        
        Items Affected:
        {items_list}
        
        Please verify the physical stock movement.
        
        Stock Management System
        """).format(
            warehouse=warehouse,
            entry_number=self.name,
            purpose=self.purpose,
            posting_date=frappe.format(self.posting_date, "Date"),
            items_list="\n".join(warehouse_items)
        )
    
    def send_transfer_notification(self):
        """Send transfer notification for material transfers."""
        if self.from_warehouse and self.to_warehouse:
            # Get both warehouse managers
            from_manager = frappe.db.get_value("Warehouse", self.from_warehouse, "warehouse_manager")
            to_manager = frappe.db.get_value("Warehouse", self.to_warehouse, "warehouse_manager")
            
            recipients = []
            if from_manager:
                recipients.append(from_manager)
            if to_manager and to_manager != from_manager:
                recipients.append(to_manager)
            
            if recipients:
                frappe.sendmail(
                    recipients=recipients,
                    subject=_("Material Transfer - {0}").format(self.name),
                    message=self.get_transfer_notification_message(),
                    reference_doctype=self.doctype,
                    reference_name=self.name
                )
    
    def get_transfer_notification_message(self):
        """Get transfer notification message."""
        items_list = []
        for item in self.items:
            items_list.append(f"- {item.item_code}: {item.qty} {item.uom}")
        
        return _("""
        Material Transfer Notification
        
        Transfer: {entry_number}
        Date: {posting_date}
        
        From Warehouse: {from_warehouse}
        To Warehouse: {to_warehouse}
        
        Items Transferred:
        {items_list}
        
        Total Value: {total_value}
        
        Please coordinate the physical transfer of materials.
        
        Stock Management System
        """).format(
            entry_number=self.name,
            posting_date=frappe.format(self.posting_date, "Date"),
            from_warehouse=self.from_warehouse,
            to_warehouse=self.to_warehouse,
            items_list="\n".join(items_list),
            total_value=frappe.format(self.total_amount, "Currency")
        )
    
    def update_related_documents(self):
        """Update related documents."""
        # Update work order if linked
        if self.work_order:
            self.update_work_order_status()
        
        # Update purchase order if this is a receipt
        if self.purpose == "Material Receipt" and self.supplier:
            self.update_purchase_order_status()
    
    def update_work_order_status(self):
        """Update work order status."""
        # This would typically update work order material consumption
        pass
    
    def update_purchase_order_status(self):
        """Update purchase order receipt status."""
        # Find related purchase orders and update receipt status
        pass
    
    @frappe.whitelist()
    def get_items_from_purchase_order(self, purchase_order):
        """Get items from purchase order for receipt."""
        if not purchase_order:
            return
        
        po_doc = frappe.get_doc("Purchase Order", purchase_order)
        
        # Clear existing items
        self.items = []
        
        # Add items from purchase order
        for po_item in po_doc.items:
            pending_qty = flt(po_item.qty) - flt(po_item.received_qty or 0)
            
            if pending_qty > 0:
                self.append("items", {
                    "item_code": po_item.item_code,
                    "item_name": po_item.item_name,
                    "description": po_item.description,
                    "qty": pending_qty,
                    "uom": po_item.uom,
                    "basic_rate": po_item.rate,
                    "t_warehouse": self.to_warehouse,
                    "purchase_order": purchase_order,
                    "purchase_order_item": po_item.name
                })
        
        return self
    
    @frappe.whitelist()
    def create_return_entry(self, return_items):
        """Create return stock entry."""
        return_entry = frappe.copy_doc(self)
        return_entry.is_return = 1
        return_entry.return_against = self.name
        return_entry.purpose = "Material Issue" if self.purpose == "Material Receipt" else "Material Receipt"
        
        # Reverse warehouses
        return_entry.from_warehouse = self.to_warehouse
        return_entry.to_warehouse = self.from_warehouse
        
        # Clear and add return items
        return_entry.items = []
        
        for item_code, return_qty in return_items.items():
            original_item = next((item for item in self.items if item.item_code == item_code), None)
            
            if original_item and flt(return_qty) > 0:
                return_entry.append("items", {
                    "item_code": original_item.item_code,
                    "item_name": original_item.item_name,
                    "description": original_item.description,
                    "qty": flt(return_qty),
                    "uom": original_item.uom,
                    "basic_rate": original_item.basic_rate,
                    "s_warehouse": original_item.t_warehouse,
                    "t_warehouse": original_item.s_warehouse
                })
        
        return_entry.insert()
        return return_entry
    
    @frappe.whitelist()
    def get_stock_analytics(self):
        """Get stock entry analytics."""
        # Get warehouse stock levels
        warehouse_stock = {}
        warehouses = set()
        
        if self.from_warehouse:
            warehouses.add(self.from_warehouse)
        if self.to_warehouse:
            warehouses.add(self.to_warehouse)
        
        for warehouse in warehouses:
            stock_data = frappe.db.sql("""
                SELECT item_code, SUM(actual_qty) as qty, AVG(valuation_rate) as rate
                FROM `tabStock Ledger Entry`
                WHERE warehouse = %s
                AND is_cancelled = 0
                GROUP BY item_code
                HAVING qty > 0
            """, warehouse, as_dict=True)
            
            warehouse_stock[warehouse] = {
                "total_items": len(stock_data),
                "total_value": sum(flt(item.qty) * flt(item.rate) for item in stock_data)
            }
        
        # Get recent stock entries
        recent_entries = frappe.get_all("Stock Entry",
            filters={"docstatus": 1},
            fields=["name", "purpose", "posting_date", "total_amount"],
            order_by="posting_date desc",
            limit=10
        )
        
        return {
            "current_entry": {
                "name": self.name,
                "purpose": self.purpose,
                "total_amount": self.total_amount,
                "total_items": len(self.items)
            },
            "warehouse_stock": warehouse_stock,
            "entry_summary": {
                "outgoing_value": self.total_outgoing_value,
                "incoming_value": self.total_incoming_value,
                "value_difference": self.value_difference,
                "additional_costs": self.total_additional_costs
            },
            "recent_entries": recent_entries,
            "item_movements": [
                {
                    "item_code": item.item_code,
                    "qty": item.qty,
                    "from_warehouse": item.s_warehouse,
                    "to_warehouse": item.t_warehouse,
                    "value": item.amount
                }
                for item in self.items
            ]
        }
    
    def get_stock_entry_summary(self):
        """Get stock entry summary for reporting."""
        return {
            "entry_name": self.name,
            "purpose": self.purpose,
            "posting_date": self.posting_date,
            "from_warehouse": self.from_warehouse,
            "to_warehouse": self.to_warehouse,
            "total_items": len(self.items),
            "total_outgoing_value": self.total_outgoing_value,
            "total_incoming_value": self.total_incoming_value,
            "value_difference": self.value_difference,
            "total_amount": self.total_amount,
            "supplier": self.supplier_name,
            "work_order": self.work_order,
            "is_return": self.is_return,
            "return_against": self.return_against
        }
