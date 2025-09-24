# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, flt, fmt_money, get_last_day, getdate

from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	get_accounting_dimensions,
)
from erpnext.accounts.utils import get_fiscal_year


class BudgetError(frappe.ValidationError):
	pass


class DuplicateBudgetError(frappe.ValidationError):
	pass


class Budget(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.accounts.doctype.budget_account.budget_account import BudgetAccount

		accounts: DF.Table[BudgetAccount]
		action_if_accumulated_monthly_budget_exceeded: DF.Literal["", "Stop", "Warn", "Ignore"]
		action_if_accumulated_monthly_budget_exceeded_on_mr: DF.Literal["", "Stop", "Warn", "Ignore"]
		action_if_accumulated_monthly_budget_exceeded_on_po: DF.Literal["", "Stop", "Warn", "Ignore"]
		action_if_accumulated_monthly_exceeded_on_cumulative_expense: DF.Literal["", "Stop", "Warn", "Ignore"]
		action_if_annual_budget_exceeded: DF.Literal["", "Stop", "Warn", "Ignore"]
		action_if_annual_budget_exceeded_on_mr: DF.Literal["", "Stop", "Warn", "Ignore"]
		action_if_annual_budget_exceeded_on_po: DF.Literal["", "Stop", "Warn", "Ignore"]
		action_if_annual_exceeded_on_cumulative_expense: DF.Literal["", "Stop", "Warn", "Ignore"]
		amended_from: DF.Link | None
		applicable_on_booking_actual_expenses: DF.Check
		applicable_on_cumulative_expense: DF.Check
		applicable_on_material_request: DF.Check
		applicable_on_purchase_order: DF.Check
		budget_against: DF.Literal["", "Cost Center", "Project"]
		company: DF.Link
		cost_center: DF.Link | None
		fiscal_year: DF.Link
		monthly_distribution: DF.Link | None
		naming_series: DF.Literal["BUDGET-.YYYY.-"]
		project: DF.Link | None
	# end: auto-generated types

	def validate(self):
		if not self.get(frappe.scrub(self.budget_against)):
			frappe.throw(_("{0} is mandatory").format(self.budget_against))
		self.validate_duplicate()
		self.validate_accounts()
		self.set_null_value()
		self.validate_applicable_for()

	def validate_duplicate(self):
		budget_against_field = frappe.scrub(self.budget_against)
		budget_against = self.get(budget_against_field)

		accounts = [d.account for d in self.accounts] or []
		existing_budget = frappe.db.sql(
			"""
			select
				b.name, ba.account from `tabBudget` b, `tabBudget Account` ba
			where
				ba.parent = b.name and b.docstatus < 2 and b.company = {} and {}={} and
				b.fiscal_year={} and b.name != {} and ba.account in ({}) """.format(
				"%s", budget_against_field, "%s", "%s", "%s", ",".join(["%s"] * len(accounts))
			),
			(self.company, budget_against, self.fiscal_year, self.name, *tuple(accounts)),
			as_dict=1,
		)

		for d in existing_budget:
			frappe.throw(
				_(
					"Another Budget record 	{0}	 already exists against {1} 	{2}	 and account 	{3}	 for fiscal year {4}"
				).format(d.name, self.budget_against, budget_against, d.account, self.fiscal_year),
				DuplicateBudgetError,
			)

	def validate_accounts(self):
		account_list = []
		for d in self.get("accounts"):
			if d.account:
				account_details = frappe.get_cached_value(
					"Account", d.account, ["is_group", "company", "report_type"], as_dict=1
				)

				if account_details.is_group:
					frappe.throw(_("Budget cannot be assigned against Group Account {0}").format(d.account))
				elif account_details.company != self.company:
					frappe.throw(
						_("Account {0} does not belongs to company {1}").format(d.account, self.company)
					)
				elif account_details.report_type != "Profit and Loss":
					frappe.throw(
						_(
							"Budget cannot be assigned against {0}, as it	s not an Income or Expense account"
						).format(d.account)
					)

				if d.account in account_list:
					frappe.throw(_("Account {0} has been entered multiple times").format(d.account))
				else:
					account_list.append(d.account)

	def set_null_value(self):
		if self.budget_against == "Cost Center":
			self.project = None
		else:
			self.cost_center = None

	def validate_applicable_for(self):
		if self.applicable_on_material_request and not (
			self.applicable_on_purchase_order and self.applicable_on_booking_actual_expenses
		):
			frappe.throw(
				_("Please enable Applicable on Purchase Order and Applicable on Booking Actual Expenses")
			)

		elif self.applicable_on_purchase_order and not (self.applicable_on_booking_actual_expenses):
			frappe.throw(_("Please enable Applicable on Booking Actual Expenses"))

		elif not (
			self.applicable_on_material_request
			or self.applicable_on_purchase_order
			or self.applicable_on_booking_actual_expenses
		):
			self.applicable_on_booking_actual_expenses = 1

