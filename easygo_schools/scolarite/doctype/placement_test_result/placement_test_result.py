# Copyright (c) 2024, EasyGo Education Team and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PlacementTestResult(Document):
	def before_save(self):
		"""Calculate percentage before saving"""
		if self.total_marks and self.marks_obtained:
			self.percentage = (self.marks_obtained / self.total_marks) * 100
			
	def validate(self):
		"""Validate placement test result data"""
		if self.marks_obtained and self.total_marks:
			if self.marks_obtained > self.total_marks:
				frappe.throw("Marks obtained cannot be greater than total marks")