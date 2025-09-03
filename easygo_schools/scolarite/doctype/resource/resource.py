"""Resource doctype controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, get_file_size, get_files_path
import os


class Resource(Document):
    """Resource doctype controller."""
    
    def validate(self):
        """Validate resource data."""
        self.validate_file_or_link()
        self.extract_file_metadata()
        self.set_defaults()
    
    def validate_file_or_link(self):
        """Validate that either file or external link is provided."""
        if not self.file_url and not self.external_link:
            frappe.throw(_("Either file or external link must be provided"))
    
    def extract_file_metadata(self):
        """Extract file metadata if file is uploaded."""
        if self.file_url:
            try:
                file_path = frappe.get_site_path() + self.file_url
                if os.path.exists(file_path):
                    # Get file size
                    size_bytes = os.path.getsize(file_path)
                    if size_bytes < 1024:
                        self.file_size = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        self.file_size = f"{size_bytes / 1024:.1f} KB"
                    else:
                        self.file_size = f"{size_bytes / (1024 * 1024):.1f} MB"
                    
                    # Get file format
                    self.file_format = os.path.splitext(self.file_url)[1].upper().replace('.', '')
                    
            except Exception as e:
                frappe.log_error(f"Failed to extract file metadata: {str(e)}")
    
    def set_defaults(self):
        """Set default values."""
        if not self.created_by:
            self.created_by = frappe.session.user
        
        if not self.creation_date:
            self.creation_date = now()
        
        if not self.upload_date and self.file_url:
            self.upload_date = now().date()
    
    @frappe.whitelist()
    def track_access(self, access_type="view"):
        """Track resource access."""
        if access_type == "view":
            self.view_count = (self.view_count or 0) + 1
        elif access_type == "download":
            self.download_count = (self.download_count or 0) + 1
        
        self.last_accessed = now()
        self.save(ignore_permissions=True)
        
        return True
    
    @frappe.whitelist()
    def add_rating(self, rating_value, feedback=None):
        """Add rating and feedback for this resource."""
        # This would integrate with a rating system
        # For now, just update the rating
        current_rating = self.rating or 0
        feedback_count = self.feedback_count or 0
        
        # Calculate new average rating
        total_rating = (current_rating * feedback_count) + rating_value
        new_feedback_count = feedback_count + 1
        self.rating = total_rating / new_feedback_count
        self.feedback_count = new_feedback_count
        
        self.save()
        
        return True
    
    @frappe.whitelist()
    def get_usage_analytics(self):
        """Get usage analytics for this resource."""
        analytics = {
            "total_views": self.view_count or 0,
            "total_downloads": self.download_count or 0,
            "average_rating": self.rating or 0,
            "feedback_count": self.feedback_count or 0,
            "popularity_score": ((self.view_count or 0) + (self.download_count or 0) * 2) / max(1, (self.feedback_count or 1)),
            "last_accessed": self.last_accessed
        }
        
        return analytics
    
    @frappe.whitelist()
    def get_related_resources(self):
        """Get related resources based on subject and tags."""
        filters = {"is_active": 1, "name": ["!=", self.name]}
        
        if self.subject:
            filters["subject"] = self.subject
        
        related = frappe.get_list("Resource",
            filters=filters,
            fields=["name", "resource_title", "resource_type", "rating", "view_count"],
            limit=10,
            order_by="rating desc, view_count desc"
        )
        
        return related
