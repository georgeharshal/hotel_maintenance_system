# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

"""Row-level permission rules.

Maintenance Employees may only see and update Work Orders that are assigned to
them (no create/delete). This is enforced via a permission query condition (for
list views / reports) and a has_permission check (for single-document access).
System Managers and any user holding a supervisory role are unaffected.
"""

import frappe

SUPERVISOR_ROLES = {
	"System Manager",
	"Administrator",
	"Director",
	"Senior General Manager",
	"Hotel GM",
}


def _is_restricted_employee(user):
	roles = set(frappe.get_roles(user))
	if roles & SUPERVISOR_ROLES:
		return False
	return "Maintenance Employee" in roles


def work_order_query_conditions(user=None):
	"""Limit Maintenance Employees to work orders assigned to themselves."""
	user = user or frappe.session.user
	if not _is_restricted_employee(user):
		return ""
	return f"`tabMaintenance Work Order`.`assigned_to` = {frappe.db.escape(user)}"


def work_order_has_permission(doc, user=None, permission_type=None):
	"""Allow access to a single work order only if assigned to the employee."""
	user = user or frappe.session.user
	if not _is_restricted_employee(user):
		return True
	return doc.assigned_to == user
