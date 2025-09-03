"""Canteen Menu DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, flt, cint


class CanteenMenu(Document):
    """Canteen Menu management."""
    
    def validate(self):
        """Validate canteen menu data."""
        self.validate_menu_date()
        self.calculate_totals()
        self.validate_nutritional_requirements()
        self.set_defaults()
    
    def validate_menu_date(self):
        """Validate menu date."""
        if self.menu_date and self.menu_date < getdate():
            frappe.msgprint(_("Warning: Menu date is in the past"))
        
        # Check for duplicate menu on same date and meal type
        existing = frappe.db.exists("Canteen Menu", {
            "menu_date": self.menu_date,
            "meal_type": self.meal_type,
            "name": ["!=", self.name],
            "is_active": 1
        })
        
        if existing:
            frappe.throw(_("Active menu already exists for {0} on {1}").format(
                self.meal_type, frappe.format(self.menu_date, "Date")
            ))
    
    def calculate_totals(self):
        """Calculate total cost and nutritional values."""
        total_cost = 0
        total_calories = 0
        total_protein = 0
        total_carbs = 0
        total_fat = 0
        
        for item in self.menu_items:
            if item.quantity and item.unit_cost:
                item.total_cost = flt(item.quantity) * flt(item.unit_cost)
                total_cost += item.total_cost
            
            # Calculate nutritional values if available
            if item.calories_per_serving and item.servings:
                item.total_calories = flt(item.calories_per_serving) * flt(item.servings)
                total_calories += item.total_calories
            
            if item.protein_per_serving and item.servings:
                total_protein += flt(item.protein_per_serving) * flt(item.servings)
            
            if item.carbs_per_serving and item.servings:
                total_carbs += flt(item.carbs_per_serving) * flt(item.servings)
            
            if item.fat_per_serving and item.servings:
                total_fat += flt(item.fat_per_serving) * flt(item.servings)
        
        self.total_cost = total_cost
        
        # Update nutritional info
        if total_calories > 0:
            nutritional_summary = f"""
            Total Calories: {total_calories:.0f}
            Protein: {total_protein:.1f}g
            Carbohydrates: {total_carbs:.1f}g
            Fat: {total_fat:.1f}g
            """
            
            if self.nutritional_info:
                self.nutritional_info += nutritional_summary
            else:
                self.nutritional_info = nutritional_summary
    
    def validate_nutritional_requirements(self):
        """Validate nutritional requirements for school meals."""
        if not self.menu_items:
            return
        
        # Basic nutritional guidelines for school meals
        guidelines = {
            "Breakfast": {"min_calories": 300, "max_calories": 500},
            "Lunch": {"min_calories": 500, "max_calories": 800},
            "Dinner": {"min_calories": 400, "max_calories": 700},
            "Snack": {"min_calories": 100, "max_calories": 250}
        }
        
        if self.meal_type in guidelines:
            total_calories = sum(
                flt(item.calories_per_serving) * flt(item.servings) 
                for item in self.menu_items 
                if item.calories_per_serving and item.servings
            )
            
            guideline = guidelines[self.meal_type]
            if total_calories > 0:
                if total_calories < guideline["min_calories"]:
                    frappe.msgprint(_("Warning: Total calories ({0}) below recommended minimum ({1}) for {2}").format(
                        total_calories, guideline["min_calories"], self.meal_type
                    ))
                elif total_calories > guideline["max_calories"]:
                    frappe.msgprint(_("Warning: Total calories ({0}) above recommended maximum ({1}) for {2}").format(
                        total_calories, guideline["max_calories"], self.meal_type
                    ))
    
    def set_defaults(self):
        """Set default values."""
        if not self.prepared_by:
            # Get canteen manager
            canteen_manager = frappe.db.get_value("Employee", 
                {"department": "Canteen", "designation": ["like", "%Manager%"]}, 
                "name"
            )
            if canteen_manager:
                self.prepared_by = canteen_manager
        
        if not self.preparation_date:
            self.preparation_date = getdate()
    
    def on_submit(self):
        """Actions on submit."""
        self.approved_by = frappe.session.user
        self.approval_date = getdate()
        
        # Create meal orders if auto-ordering is enabled
        self.create_automatic_meal_orders()
        
        # Send menu notification
        self.send_menu_notification()
        
        # Update stock requirements
        self.update_stock_requirements()
    
    def create_automatic_meal_orders(self):
        """Create automatic meal orders for regular subscribers."""
        # Get students with active meal subscriptions
        subscriptions = frappe.get_all("Meal Subscription",
            filters={
                "meal_type": self.meal_type,
                "status": "Active",
                "end_date": [">=", self.menu_date],
                "start_date": ["<=", self.menu_date]
            },
            fields=["student", "student_name", "meal_type", "auto_order"]
        )
        
        for subscription in subscriptions:
            if subscription.auto_order:
                # Check if order already exists
                existing_order = frappe.db.exists("Meal Order", {
                    "student": subscription.student,
                    "menu_date": self.menu_date,
                    "meal_type": self.meal_type
                })
                
                if not existing_order:
                    meal_order = frappe.get_doc({
                        "doctype": "Meal Order",
                        "student": subscription.student,
                        "student_name": subscription.student_name,
                        "menu": self.name,
                        "menu_date": self.menu_date,
                        "meal_type": self.meal_type,
                        "quantity": 1,
                        "price_per_meal": self.price_per_meal,
                        "total_amount": self.price_per_meal,
                        "order_type": "Automatic",
                        "status": "Confirmed"
                    })
                    
                    meal_order.insert(ignore_permissions=True)
    
    def send_menu_notification(self):
        """Send menu notification to stakeholders."""
        # Get notification settings
        notify_parents = frappe.db.get_single_value("School Settings", "notify_parents_menu")
        notify_students = frappe.db.get_single_value("School Settings", "notify_students_menu")
        
        if notify_parents or notify_students:
            self.send_menu_email_notification()
            self.send_menu_sms_notification()
    
    def send_menu_email_notification(self):
        """Send email notification about new menu."""
        recipients = []
        
        # Get parent emails
        parent_emails = frappe.db.sql("""
            SELECT DISTINCT g.email_address
            FROM `tabGuardian` g
            INNER JOIN `tabStudent Guardian` sg ON g.name = sg.guardian
            INNER JOIN `tabStudent` s ON sg.parent = s.name
            WHERE g.email_address IS NOT NULL
            AND s.enabled = 1
        """, as_dict=True)
        
        recipients.extend([p.email_address for p in parent_emails if p.email_address])
        
        # Get student emails
        student_emails = frappe.get_all("Student",
            filters={"enabled": 1, "student_email_id": ["!=", ""]},
            fields=["student_email_id"]
        )
        
        recipients.extend([s.student_email_id for s in student_emails if s.student_email_id])
        
        if recipients:
            frappe.sendmail(
                recipients=list(set(recipients)),  # Remove duplicates
                subject=_("New Menu Available - {0} for {1}").format(
                    self.meal_type, frappe.format(self.menu_date, "Date")
                ),
                message=self.get_menu_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def send_menu_sms_notification(self):
        """Send SMS notification about new menu."""
        # Get parent mobile numbers
        parent_mobiles = frappe.db.sql("""
            SELECT DISTINCT g.mobile_number
            FROM `tabGuardian` g
            INNER JOIN `tabStudent Guardian` sg ON g.name = sg.guardian
            INNER JOIN `tabStudent` s ON sg.parent = s.name
            WHERE g.mobile_number IS NOT NULL
            AND s.enabled = 1
        """, as_dict=True)
        
        message = _("New {0} menu for {1}: {2}. Price: {3}. Order via school portal.").format(
            self.meal_type,
            frappe.format(self.menu_date, "Date"),
            self.menu_name,
            frappe.format_value(self.price_per_meal, "Currency")
        )
        
        # Use SMS adapter
        from easygo_education.finances_rh.adapters.sms import send_sms
        
        for parent in parent_mobiles:
            if parent.mobile_number:
                send_sms(parent.mobile_number, message)
    
    def get_menu_notification_message(self):
        """Get menu notification email message."""
        menu_items_list = "\n".join([
            f"- {item.item_name} ({item.quantity} {item.unit})"
            for item in self.menu_items
        ])
        
        return _("""
        New Menu Available
        
        Menu: {menu_name}
        Date: {menu_date}
        Meal Type: {meal_type}
        Price per Meal: {price}
        
        Menu Items:
        {menu_items}
        
        Nutritional Information:
        {nutritional_info}
        
        Allergen Information:
        {allergen_info}
        
        Special Notes:
        {special_notes}
        
        To order meals, please log in to the school portal or contact the canteen directly.
        
        School Canteen Team
        """).format(
            menu_name=self.menu_name,
            menu_date=frappe.format(self.menu_date, "Date"),
            meal_type=self.meal_type,
            price=frappe.format_value(self.price_per_meal, "Currency"),
            menu_items=menu_items_list,
            nutritional_info=self.nutritional_info or "Not available",
            allergen_info=self.allergen_info or "None specified",
            special_notes=self.special_notes or "None"
        )
    
    def update_stock_requirements(self):
        """Update stock requirements based on menu items."""
        for item in self.menu_items:
            if item.stock_item and item.quantity:
                # Check current stock level
                current_stock = frappe.db.get_value("Stock Item", item.stock_item, "current_stock")
                
                if current_stock and flt(current_stock) < flt(item.quantity):
                    # Create stock requirement
                    stock_requirement = frappe.get_doc({
                        "doctype": "Stock Requirement",
                        "item": item.stock_item,
                        "required_quantity": item.quantity,
                        "current_stock": current_stock,
                        "shortage": flt(item.quantity) - flt(current_stock),
                        "required_date": self.menu_date,
                        "purpose": f"Canteen Menu: {self.menu_name}",
                        "priority": "Medium",
                        "requested_by": self.prepared_by
                    })
                    
                    stock_requirement.insert(ignore_permissions=True)
    
    @frappe.whitelist()
    def duplicate_menu(self, new_date, new_meal_type=None):
        """Duplicate menu for another date."""
        new_menu = frappe.copy_doc(self)
        new_menu.menu_date = new_date
        new_menu.meal_type = new_meal_type or self.meal_type
        new_menu.menu_name = f"{self.menu_name} - {frappe.format(new_date, 'Date')}"
        
        # Clear approval fields
        new_menu.approved_by = None
        new_menu.approval_date = None
        new_menu.actual_servings = None
        
        new_menu.insert()
        
        frappe.msgprint(_("Menu duplicated: {0}").format(new_menu.name))
        return new_menu.name
    
    @frappe.whitelist()
    def update_actual_servings(self, actual_servings):
        """Update actual servings after meal service."""
        self.actual_servings = cint(actual_servings)
        self.save()
        
        # Calculate waste percentage
        if self.estimated_servings:
            waste_percentage = ((self.estimated_servings - self.actual_servings) / self.estimated_servings) * 100
            
            if waste_percentage > 20:  # High waste threshold
                self.create_waste_alert(waste_percentage)
        
        frappe.msgprint(_("Actual servings updated"))
        return self
    
    def create_waste_alert(self, waste_percentage):
        """Create waste alert for high food waste."""
        alert = frappe.get_doc({
            "doctype": "Canteen Alert",
            "alert_type": "High Food Waste",
            "menu": self.name,
            "menu_date": self.menu_date,
            "estimated_servings": self.estimated_servings,
            "actual_servings": self.actual_servings,
            "waste_percentage": waste_percentage,
            "alert_date": getdate(),
            "status": "Open"
        })
        
        alert.insert(ignore_permissions=True)
        
        # Notify canteen manager
        if self.prepared_by:
            self.send_waste_alert_notification(waste_percentage)
    
    def send_waste_alert_notification(self, waste_percentage):
        """Send waste alert notification."""
        manager_user = frappe.db.get_value("Employee", self.prepared_by, "user_id")
        
        if manager_user:
            frappe.sendmail(
                recipients=[manager_user],
                subject=_("High Food Waste Alert - {0}").format(self.menu_name),
                message=self.get_waste_alert_message(waste_percentage),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_waste_alert_message(self, waste_percentage):
        """Get waste alert message."""
        return _("""
        High Food Waste Alert
        
        Menu: {menu_name}
        Date: {menu_date}
        Meal Type: {meal_type}
        
        Servings:
        - Estimated: {estimated}
        - Actual: {actual}
        - Waste: {waste}%
        
        Please review ordering patterns and adjust future estimates accordingly.
        
        Canteen Management System
        """).format(
            menu_name=self.menu_name,
            menu_date=frappe.format(self.menu_date, "Date"),
            meal_type=self.meal_type,
            estimated=self.estimated_servings,
            actual=self.actual_servings,
            waste=round(waste_percentage, 1)
        )
    
    @frappe.whitelist()
    def get_menu_analytics(self):
        """Get menu analytics and performance metrics."""
        # Get order statistics
        order_stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_orders,
                SUM(quantity) as total_quantity,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as avg_order_value
            FROM `tabMeal Order`
            WHERE menu = %s
        """, [self.name], as_dict=True)[0]
        
        # Get popular items
        popular_items = frappe.db.sql("""
            SELECT 
                cmi.item_name,
                SUM(mo.quantity) as total_ordered
            FROM `tabCanteen Menu Item` cmi
            INNER JOIN `tabMeal Order` mo ON mo.menu = cmi.parent
            WHERE cmi.parent = %s
            GROUP BY cmi.item_name
            ORDER BY total_ordered DESC
        """, [self.name], as_dict=True)
        
        # Calculate efficiency metrics
        efficiency_metrics = {
            "waste_percentage": 0,
            "utilization_rate": 0,
            "cost_per_serving": 0
        }
        
        if self.estimated_servings and self.actual_servings:
            efficiency_metrics["waste_percentage"] = ((self.estimated_servings - self.actual_servings) / self.estimated_servings) * 100
            efficiency_metrics["utilization_rate"] = (self.actual_servings / self.estimated_servings) * 100
        
        if self.actual_servings and self.total_cost:
            efficiency_metrics["cost_per_serving"] = self.total_cost / self.actual_servings
        
        return {
            "menu_info": {
                "name": self.menu_name,
                "date": self.menu_date,
                "meal_type": self.meal_type,
                "price_per_meal": self.price_per_meal,
                "total_cost": self.total_cost
            },
            "order_statistics": order_stats,
            "popular_items": popular_items,
            "efficiency_metrics": efficiency_metrics,
            "nutritional_summary": self.nutritional_info
        }
    
    @frappe.whitelist()
    def generate_shopping_list(self):
        """Generate shopping list for menu items."""
        shopping_list = []
        
        for item in self.menu_items:
            if item.stock_item:
                current_stock = frappe.db.get_value("Stock Item", item.stock_item, "current_stock") or 0
                required_quantity = flt(item.quantity)
                
                if required_quantity > current_stock:
                    shopping_list.append({
                        "item": item.item_name,
                        "stock_item": item.stock_item,
                        "required_quantity": required_quantity,
                        "current_stock": current_stock,
                        "to_purchase": required_quantity - current_stock,
                        "unit": item.unit,
                        "estimated_cost": (required_quantity - current_stock) * flt(item.unit_cost)
                    })
        
        return shopping_list
    
    def get_menu_summary(self):
        """Get menu summary for reporting."""
        return {
            "menu_name": self.menu_name,
            "menu_date": self.menu_date,
            "meal_type": self.meal_type,
            "price_per_meal": self.price_per_meal,
            "total_cost": self.total_cost,
            "estimated_servings": self.estimated_servings,
            "actual_servings": self.actual_servings,
            "items_count": len(self.menu_items),
            "dietary_restrictions": self.dietary_restrictions,
            "is_active": self.is_active,
            "prepared_by": self.prepared_by,
            "approved_by": self.approved_by
        }
