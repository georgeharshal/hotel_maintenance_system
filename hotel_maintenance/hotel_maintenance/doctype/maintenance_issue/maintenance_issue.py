# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

# Work Order statuses that count as "done" for the purpose of closing an issue.
WORK_ORDER_DONE_STATUSES = ("Completed", "Verified", "Closed")


class MaintenanceIssue(Document):
	def before_insert(self):
		# Default the reporter and the timestamp the issue was raised.
		if not self.raised_by:
			self.raised_by = frappe.session.user
		if not self.raised_date:
			self.raised_date = now_datetime()

	def validate(self):
		self.validate_building_room_property()
		self.validate_closure_constraint()

	def before_update_after_submit(self):
		# A submittable DocType does NOT run validate() when a submitted
		# document is updated (e.g. changing the status field, which is
		# allow_on_submit). Re-run the closure constraint here so it is
		# enforced throughout the issue lifecycle, not just before submit.
		self.validate_closure_constraint()

	def validate_building_room_property(self):
		"""Keep the location hierarchy (property -> building -> room) consistent."""
		if self.building and self.property:
			building_property = frappe.db.get_value("Building", self.building, "property")
			if building_property and building_property != self.property:
				frappe.throw(
					_("Building {0} does not belong to Property {1}").format(
						frappe.bold(self.building), frappe.bold(self.property)
					)
				)
		if self.room and self.property:
			room_property = frappe.db.get_value("Room", self.room, "property")
			if room_property and room_property != self.property:
				frappe.throw(
					_("Room {0} does not belong to Property {1}").format(
						frappe.bold(self.room), frappe.bold(self.property)
					)
				)

	def validate_closure_constraint(self):
		"""Task 2.4 - Issue Closure Constraint.

		An Issue can only move to "Verified" or "Closed" when:
		  * every linked Work Order is "Completed"/"Verified"/"Closed", and
		  * the Issue has already passed through the "Completed" stage.
		"""
		if self.status not in ("Verified", "Closed"):
			return

		# The issue must have been "Completed" before it can be verified/closed.
		previous_status = self.get_db_value("status") if not self.is_new() else None
		if self.status == "Verified" and previous_status not in ("Completed", "Verified"):
			frappe.throw(
				_("Issue must be marked as 'Completed' before it can be 'Verified'.")
			)
		if self.status == "Closed" and previous_status not in ("Completed", "Verified", "Closed"):
			frappe.throw(
				_("Issue must be 'Completed'/'Verified' before it can be 'Closed'.")
			)

		# No linked work order may still be pending.
		pending = frappe.get_all(
			"Maintenance Work Order",
			filters={
				"issue": self.name,
				"status": ["not in", WORK_ORDER_DONE_STATUSES],
				"docstatus": ["<", 2],
			},
			pluck="name",
		)
		if pending:
			frappe.throw(
				_("Cannot mark Issue as '{0}'. The following Work Orders are not completed yet: {1}").format(
					self.status, ", ".join(frappe.bold(wo) for wo in pending)
				)
			)
