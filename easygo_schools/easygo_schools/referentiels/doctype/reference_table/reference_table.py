"""Reference Table DocType."""

import frappe
from frappe import _
from frappe.model.document import Document


class ReferenceTable(Document):
    """Reference Table for master data and configuration."""
    
    def validate(self):
        """Validate reference table data."""
        self.validate_table_name()
        self.validate_reference_data()
        self.set_defaults()
    
    def validate_table_name(self):
        """Validate table name format."""
        if self.table_name:
            # Ensure table name follows naming conventions
            if not self.table_name.replace("_", "").replace("-", "").isalnum():
                frappe.throw(_("Table name can only contain letters, numbers, underscores, and hyphens"))
            
            # Check for reserved names
            reserved_names = ["user", "role", "doctype", "system", "admin"]
            if self.table_name.lower() in reserved_names:
                frappe.throw(_("Table name '{0}' is reserved").format(self.table_name))
    
    def validate_reference_data(self):
        """Validate reference data items."""
        if self.reference_data:
            codes = []
            for item in self.reference_data:
                if item.code in codes:
                    frappe.throw(_("Duplicate code '{0}' found in reference data").format(item.code))
                codes.append(item.code)
    
    def set_defaults(self):
        """Set default values."""
        if not self.sort_order:
            self.sort_order = 0
        
        if not self.table_type:
            self.table_type = "Master Data"
    
    def on_update(self):
        """Actions after update."""
        self.update_dependent_doctypes()
    
    def update_dependent_doctypes(self):
        """Update DocTypes that depend on this reference table."""
        if self.has_value_changed("reference_data"):
            # Find DocTypes that use this reference table
            dependent_fields = frappe.db.sql("""
                SELECT DISTINCT parent, fieldname
                FROM `tabDocField`
                WHERE options = %s
                AND fieldtype IN ('Select', 'Link')
            """, [self.table_name], as_dict=True)
            
            for field in dependent_fields:
                # Update select options if it's a Select field
                self.update_select_options(field.parent, field.fieldname)
    
    def update_select_options(self, doctype, fieldname):
        """Update select options for dependent fields."""
        if not self.reference_data:
            return
        
        options = "\n".join([item.value for item in self.reference_data if item.is_active])
        
        # Update the DocField
        frappe.db.set_value("DocField", 
            {"parent": doctype, "fieldname": fieldname}, 
            "options", options
        )
    
    @frappe.whitelist()
    def get_active_items(self):
        """Get active reference data items."""
        return [item for item in self.reference_data if item.is_active]
    
    @frappe.whitelist()
    def get_item_by_code(self, code):
        """Get reference data item by code."""
        for item in self.reference_data:
            if item.code == code:
                return item
        return None
    
    @frappe.whitelist()
    def add_reference_item(self, code, value, description=None, is_active=1):
        """Add new reference data item."""
        # Check if code already exists
        existing_item = self.get_item_by_code(code)
        if existing_item:
            frappe.throw(_("Item with code '{0}' already exists").format(code))
        
        self.append("reference_data", {
            "code": code,
            "value": value,
            "description": description,
            "is_active": is_active
        })
        
        self.save()
        return self.reference_data[-1]
    
    @frappe.whitelist()
    def deactivate_item(self, code):
        """Deactivate reference data item."""
        item = self.get_item_by_code(code)
        if item:
            item.is_active = 0
            self.save()
            return item
        else:
            frappe.throw(_("Item with code '{0}' not found").format(code))
    
    def get_reference_options(self):
        """Get formatted options for Select fields."""
        if not self.reference_data:
            return ""
        
        active_items = [item for item in self.reference_data if item.is_active]
        return "\n".join([item.value for item in active_items])
    
    def export_to_csv(self):
        """Export reference data to CSV format."""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(["Code", "Value", "Description", "Is Active", "Sort Order"])
        
        # Write data
        for item in self.reference_data:
            writer.writerow([
                item.code,
                item.value,
                item.description or "",
                "Yes" if item.is_active else "No",
                item.sort_order or 0
            ])
        
        return output.getvalue()
    
    @frappe.whitelist()
    def import_from_csv(self, csv_data):
        """Import reference data from CSV."""
        import csv
        import io
        
        # Clear existing data
        self.reference_data = []
        
        # Parse CSV
        reader = csv.DictReader(io.StringIO(csv_data))
        
        for row in reader:
            self.append("reference_data", {
                "code": row.get("Code", ""),
                "value": row.get("Value", ""),
                "description": row.get("Description", ""),
                "is_active": 1 if row.get("Is Active", "").lower() in ["yes", "1", "true"] else 0,
                "sort_order": int(row.get("Sort Order", 0)) if row.get("Sort Order", "").isdigit() else 0
            })
        
        self.save()
        frappe.msgprint(_("Reference data imported successfully"))
        return len(self.reference_data)


# Child table for Reference Data Items
class ReferenceDataItem(Document):
    """Reference Data Item child table."""
    pass
