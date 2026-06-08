# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Room(Document):
	def validate(self):
		self.validate_building_property()

	def validate_building_property(self):
		"""Ensure the selected building actually belongs to the selected property."""
		if self.building and self.property:
			building_property = frappe.db.get_value("Building", self.building, "property")
			if building_property and building_property != self.property:
				frappe.throw(
					_("Building {0} does not belong to Property {1}").format(
						frappe.bold(self.building), frappe.bold(self.property)
					)
				)
