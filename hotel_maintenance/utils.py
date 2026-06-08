# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

"""Shared helper utilities for the Hotel Maintenance app."""

import frappe


def get_user_with_role(role):
	"""Return the first enabled user that holds the given role, or None.

	Used to resolve who an escalation / overdue alert should notify when only
	a role (e.g. "Director", "Senior General Manager") is known.
	"""
	if not role:
		return None

	users = frappe.get_all(
		"Has Role",
		filters={"role": role, "parenttype": "User"},
		pluck="parent",
	)
	for user in users:
		if user in ("Administrator", "Guest"):
			continue
		if frappe.db.get_value("User", user, "enabled"):
			return user
	return None


def get_users_with_role(role):
	"""Return all enabled, real users that hold the given role."""
	users = frappe.get_all(
		"Has Role",
		filters={"role": role, "parenttype": "User"},
		pluck="parent",
	)
	return [
		u
		for u in users
		if u not in ("Administrator", "Guest") and frappe.db.get_value("User", u, "enabled")
	]


def notify_user(user, subject, document_type=None, document_name=None):
	"""Create a desk Notification Log entry for a user (best-effort)."""
	if not user:
		return
	try:
		notification = frappe.new_doc("Notification Log")
		notification.subject = subject
		notification.for_user = user
		notification.type = "Alert"
		if document_type and document_name:
			notification.document_type = document_type
			notification.document_name = document_name
		notification.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Hotel Maintenance: notify_user failed")
