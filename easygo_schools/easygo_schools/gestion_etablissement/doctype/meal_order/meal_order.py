"""Meal Order DocType."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, get_datetime, now_datetime, flt, cint


class MealOrder(Document):
    """Meal Order management."""
    
    def validate(self):
        """Validate meal order data."""
        self.validate_menu_availability()
        self.validate_order_timing()
        self.calculate_amounts()
        self.set_defaults()
    
    def validate_menu_availability(self):
        """Validate menu availability and active status."""
        if self.menu:
            menu_doc = frappe.get_doc("Canteen Menu", self.menu)
            
            if not menu_doc.is_active:
                frappe.throw(_("Selected menu is not active"))
            
            if menu_doc.menu_date < getdate():
                frappe.msgprint(_("Warning: Ordering for a past date menu"))
    
    def validate_order_timing(self):
        """Validate order timing against cutoff times."""
        if self.menu_date:
            # Get order cutoff time from settings
            cutoff_hours = frappe.db.get_single_value("School Settings", "meal_order_cutoff_hours") or 2
            
            # Calculate cutoff time
            menu_datetime = get_datetime(f"{self.menu_date} 08:00:00")
            cutoff_time = menu_datetime - frappe.utils.datetime.timedelta(hours=cutoff_hours)
            
            if get_datetime(self.order_date) > cutoff_time and self.menu_date > getdate():
                frappe.msgprint(_("Warning: Order placed after cutoff time. May not be fulfilled."))
    
    def calculate_amounts(self):
        """Calculate order amounts."""
        if self.quantity and self.price_per_meal:
            self.total_amount = flt(self.quantity) * flt(self.price_per_meal)
            self.final_amount = self.total_amount - flt(self.discount_amount)
    
    def set_defaults(self):
        """Set default values."""
        if not self.order_date:
            self.order_date = now_datetime()
        
        if not self.pickup_location:
            self.pickup_location = "Main Canteen"
        
        if not self.dietary_requirements:
            # Check student's dietary preferences
            student_dietary = frappe.db.get_value("Student", self.student, "dietary_restrictions")
            if student_dietary:
                self.dietary_requirements = student_dietary
    
    def on_submit(self):
        """Actions on submit."""
        self.status = "Confirmed"
        self.create_payment_entry()
        self.send_order_confirmation()
        self.update_menu_servings()
    
    def create_payment_entry(self):
        """Create payment entry if payment method requires it."""
        if self.payment_method in ["School Account", "Meal Plan"]:
            self.process_account_payment()
        elif self.payment_status == "Unpaid":
            self.create_payment_request()
    
    def process_account_payment(self):
        """Process payment from student account or meal plan."""
        if self.payment_method == "School Account":
            # Check student account balance
            account_balance = frappe.db.get_value("Student Account", 
                {"student": self.student}, "balance") or 0
            
            if flt(account_balance) < flt(self.final_amount):
                frappe.throw(_("Insufficient balance in student account"))
            
            # Create account transaction
            transaction = frappe.get_doc({
                "doctype": "Student Account Transaction",
                "student": self.student,
                "transaction_type": "Debit",
                "amount": self.final_amount,
                "description": f"Meal order: {self.name}",
                "reference_document": self.name,
                "transaction_date": now_datetime()
            })
            transaction.insert(ignore_permissions=True)
            
            self.payment_status = "Paid"
            self.payment_date = now_datetime()
            self.payment_reference = transaction.name
    
    def create_payment_request(self):
        """Create payment request for unpaid orders."""
        payment_request = frappe.get_doc({
            "doctype": "Payment Request",
            "payment_request_type": "Inward",
            "party_type": "Student",
            "party": self.student,
            "reference_doctype": self.doctype,
            "reference_name": self.name,
            "grand_total": self.final_amount,
            "currency": frappe.defaults.get_global_default("currency"),
            "subject": f"Payment for Meal Order {self.name}"
        })
        payment_request.insert(ignore_permissions=True)
    
    def send_order_confirmation(self):
        """Send order confirmation to student and guardians."""
        student = frappe.get_doc("Student", self.student)
        recipients = []
        
        # Get guardian emails
        guardians = frappe.get_all("Student Guardian",
            filters={"parent": self.student},
            fields=["guardian"]
        )
        
        for guardian_link in guardians:
            guardian = frappe.get_doc("Guardian", guardian_link.guardian)
            if guardian.email_address:
                recipients.append(guardian.email_address)
        
        # Add student email if available
        if student.student_email_id:
            recipients.append(student.student_email_id)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Meal Order Confirmation - {0}").format(self.name),
                message=self.get_order_confirmation_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_order_confirmation_message(self):
        """Get order confirmation message."""
        menu_doc = frappe.get_doc("Canteen Menu", self.menu)
        
        return _("""
        Dear Student/Guardian,
        
        Your meal order has been confirmed.
        
        Order Details:
        - Order Number: {order_number}
        - Student: {student_name}
        - Menu: {menu_name}
        - Meal Type: {meal_type}
        - Date: {menu_date}
        - Quantity: {quantity}
        - Total Amount: {total_amount}
        
        Pickup Information:
        - Location: {pickup_location}
        - Time: {delivery_time}
        
        Special Instructions:
        {special_instructions}
        
        Payment Status: {payment_status}
        
        Thank you for your order!
        
        School Canteen Team
        """).format(
            order_number=self.name,
            student_name=self.student_name,
            menu_name=menu_doc.menu_name,
            meal_type=self.meal_type,
            menu_date=frappe.format(self.menu_date, "Date"),
            quantity=self.quantity,
            total_amount=frappe.format_value(self.final_amount, "Currency"),
            pickup_location=self.pickup_location,
            delivery_time=self.delivery_time or "Standard meal time",
            special_instructions=self.special_instructions or "None",
            payment_status=self.payment_status
        )
    
    def update_menu_servings(self):
        """Update menu estimated servings."""
        menu_doc = frappe.get_doc("Canteen Menu", self.menu)
        
        # Add to estimated servings if not already counted
        if not menu_doc.estimated_servings:
            menu_doc.estimated_servings = 0
        
        menu_doc.estimated_servings += self.quantity
        menu_doc.save()
    
    @frappe.whitelist()
    def mark_as_preparing(self):
        """Mark order as preparing."""
        if self.status != "Confirmed":
            frappe.throw(_("Order must be confirmed before preparing"))
        
        self.status = "Preparing"
        self.save()
        
        frappe.msgprint(_("Order marked as preparing"))
        return self
    
    @frappe.whitelist()
    def mark_as_ready(self):
        """Mark order as ready for pickup."""
        if self.status != "Preparing":
            frappe.throw(_("Order must be in preparing status"))
        
        self.status = "Ready"
        self.save()
        
        # Send ready notification
        self.send_ready_notification()
        
        frappe.msgprint(_("Order marked as ready"))
        return self
    
    def send_ready_notification(self):
        """Send notification when order is ready."""
        student = frappe.get_doc("Student", self.student)
        
        # Send SMS if mobile number available
        if hasattr(student, 'mobile_number') and student.mobile_number:
            message = _("Your meal order {0} is ready for pickup at {1}").format(
                self.name, self.pickup_location
            )
            
            # Use SMS adapter
            from easygo_education.finances_rh.adapters.sms import send_sms
            send_sms(student.mobile_number, message)
        
        # Send email notification
        if student.student_email_id:
            frappe.sendmail(
                recipients=[student.student_email_id],
                subject=_("Meal Order Ready - {0}").format(self.name),
                message=self.get_ready_notification_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_ready_notification_message(self):
        """Get ready notification message."""
        return _("""
        Dear {student_name},
        
        Your meal order is ready for pickup!
        
        Order: {order_number}
        Pickup Location: {pickup_location}
        
        Please collect your order as soon as possible.
        
        School Canteen Team
        """).format(
            student_name=self.student_name,
            order_number=self.name,
            pickup_location=self.pickup_location
        )
    
    @frappe.whitelist()
    def mark_as_served(self, served_by=None):
        """Mark order as served."""
        if self.status != "Ready":
            frappe.throw(_("Order must be ready before serving"))
        
        self.status = "Served"
        self.served_by = served_by or frappe.session.user
        self.served_date = now_datetime()
        self.save()
        
        # Send feedback request
        self.send_feedback_request()
        
        frappe.msgprint(_("Order marked as served"))
        return self
    
    def send_feedback_request(self):
        """Send feedback request after serving."""
        student = frappe.get_doc("Student", self.student)
        
        if student.student_email_id:
            frappe.sendmail(
                recipients=[student.student_email_id],
                subject=_("Feedback Request - Meal Order {0}").format(self.name),
                message=self.get_feedback_request_message(),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_feedback_request_message(self):
        """Get feedback request message."""
        return _("""
        Dear {student_name},
        
        Thank you for ordering from our canteen!
        
        We would appreciate your feedback on your recent meal order:
        Order: {order_number}
        Menu: {menu_name}
        Date: {menu_date}
        
        Please rate your experience and provide any comments to help us improve our service.
        
        You can provide feedback through the school portal or by replying to this email.
        
        Thank you!
        
        School Canteen Team
        """).format(
            student_name=self.student_name,
            order_number=self.name,
            menu_name=frappe.get_value("Canteen Menu", self.menu, "menu_name"),
            menu_date=frappe.format(self.menu_date, "Date")
        )
    
    @frappe.whitelist()
    def cancel_order(self, cancellation_reason=None):
        """Cancel the order."""
        if self.status in ["Served", "Cancelled"]:
            frappe.throw(_("Cannot cancel order with status {0}").format(self.status))
        
        self.status = "Cancelled"
        
        # Process refund if payment was made
        if self.payment_status == "Paid":
            self.process_refund()
        
        # Add cancellation note
        if cancellation_reason:
            self.add_comment("Comment", f"Order cancelled: {cancellation_reason}")
        
        self.save()
        
        # Send cancellation notification
        self.send_cancellation_notification(cancellation_reason)
        
        frappe.msgprint(_("Order cancelled successfully"))
        return self
    
    def process_refund(self):
        """Process refund for cancelled order."""
        if self.payment_method == "School Account":
            # Credit back to student account
            transaction = frappe.get_doc({
                "doctype": "Student Account Transaction",
                "student": self.student,
                "transaction_type": "Credit",
                "amount": self.final_amount,
                "description": f"Refund for cancelled meal order: {self.name}",
                "reference_document": self.name,
                "transaction_date": now_datetime()
            })
            transaction.insert(ignore_permissions=True)
            
            self.payment_status = "Refunded"
    
    def send_cancellation_notification(self, reason):
        """Send cancellation notification."""
        student = frappe.get_doc("Student", self.student)
        
        if student.student_email_id:
            frappe.sendmail(
                recipients=[student.student_email_id],
                subject=_("Meal Order Cancelled - {0}").format(self.name),
                message=self.get_cancellation_message(reason),
                reference_doctype=self.doctype,
                reference_name=self.name
            )
    
    def get_cancellation_message(self, reason):
        """Get cancellation message."""
        return _("""
        Dear {student_name},
        
        Your meal order has been cancelled.
        
        Order: {order_number}
        Reason: {reason}
        
        {refund_info}
        
        We apologize for any inconvenience.
        
        School Canteen Team
        """).format(
            student_name=self.student_name,
            order_number=self.name,
            reason=reason or "Not specified",
            refund_info="A refund has been processed to your account." if self.payment_status == "Refunded" else ""
        )
    
    @frappe.whitelist()
    def submit_feedback(self, rating, comments=None):
        """Submit feedback for the order."""
        if self.status != "Served":
            frappe.throw(_("Can only provide feedback for served orders"))
        
        self.feedback_rating = cint(rating)
        self.feedback_comments = comments
        self.save()
        
        # Create feedback record
        feedback = frappe.get_doc({
            "doctype": "Canteen Feedback",
            "meal_order": self.name,
            "student": self.student,
            "menu": self.menu,
            "rating": rating,
            "comments": comments,
            "feedback_date": now_datetime()
        })
        feedback.insert(ignore_permissions=True)
        
        frappe.msgprint(_("Thank you for your feedback!"))
        return self
    
    @frappe.whitelist()
    def get_order_analytics(self):
        """Get order analytics and insights."""
        # Get student's order history
        order_history = frappe.get_all("Meal Order",
            filters={"student": self.student, "status": "Served"},
            fields=["menu_date", "meal_type", "final_amount", "feedback_rating"],
            order_by="menu_date desc",
            limit=10
        )
        
        # Calculate statistics
        total_orders = len(order_history)
        total_spent = sum(flt(order.final_amount) for order in order_history)
        avg_rating = sum(flt(order.feedback_rating) for order in order_history if order.feedback_rating) / max(1, len([o for o in order_history if o.feedback_rating]))
        
        # Get popular meal types
        meal_type_stats = frappe.db.sql("""
            SELECT meal_type, COUNT(*) as count
            FROM `tabMeal Order`
            WHERE student = %s AND status = 'Served'
            GROUP BY meal_type
            ORDER BY count DESC
        """, [self.student], as_dict=True)
        
        return {
            "current_order": {
                "name": self.name,
                "status": self.status,
                "amount": self.final_amount,
                "menu_date": self.menu_date
            },
            "student_statistics": {
                "total_orders": total_orders,
                "total_spent": total_spent,
                "average_rating": avg_rating,
                "favorite_meal_types": meal_type_stats
            },
            "recent_orders": order_history
        }
    
    def get_order_summary(self):
        """Get order summary for reporting."""
        return {
            "order_number": self.name,
            "student": self.student_name,
            "menu_date": self.menu_date,
            "meal_type": self.meal_type,
            "quantity": self.quantity,
            "total_amount": self.final_amount,
            "status": self.status,
            "payment_status": self.payment_status,
            "order_type": self.order_type,
            "pickup_location": self.pickup_location,
            "feedback_rating": self.feedback_rating,
            "served_date": self.served_date
        }
