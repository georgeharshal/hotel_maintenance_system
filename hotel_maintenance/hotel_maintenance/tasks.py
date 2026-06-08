# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

"""Scheduled background jobs for the Hotel Maintenance app."""

import frappe
from frappe.utils import date_diff, getdate, now_datetime, today

from hotel_maintenance.utils import get_user_with_role, notify_user

# Statuses that mean the work order no longer needs escalation.
DONE_STATUSES = ("Completed", "Verified", "Closed", "Cancelled")

# Role used as a proxy for the "department head" escalation tier.
DEPARTMENT_HEAD_ROLE = "Senior General Manager"


def auto_escalate_overdue_work_orders():
	"""Task 4 - runs daily at 09:00.

	Find overdue Work Orders (due date < today and not in a done status) and
	create an Overdue Alert for each, escalating the notified parties based on
	how many days the order is overdue:

	  * 1-2 days  -> notify the assigned user
	  * 3-5 days  -> notify the department head
	  * 6+ days   -> notify the GM and auto-create a Negative Review
	"""
	current_date = getdate(today())

	work_orders = frappe.get_all(
		"Maintenance Work Order",
		filters=[
			["status", "not in", DONE_STATUSES],
			["due_date", "is", "set"],
			["due_date", "<", current_date],
		],
		fields=["name", "assigned_to", "department", "property", "issue", "due_date", "status"],
	)

	created = 0
	for wo in work_orders:
		if not wo.due_date:
			continue

		overdue_days = date_diff(current_date, getdate(wo.due_date))
		if overdue_days <= 0:
			continue

		# Avoid creating more than one alert per work order per day.
		if _alert_exists_today(wo.name, current_date):
			continue

		severity, recipients = _resolve_escalation(wo, overdue_days)
		_create_overdue_alert(wo, overdue_days, severity, recipients)

		# Keep the work order status in sync.
		if wo.status != "Overdue":
			frappe.db.set_value("Maintenance Work Order", wo.name, "status", "Overdue")

		# 6+ days -> auto-create a Negative Review for the property's GM.
		if overdue_days >= 6:
			_auto_create_negative_review(wo, overdue_days)

		created += 1

	frappe.db.commit()
	return created


def _alert_exists_today(work_order, current_date):
	return bool(
		frappe.db.exists(
			"Overdue Alert",
			{"work_order": work_order, "alert_date": [">=", current_date]},
		)
	)


def _resolve_escalation(wo, overdue_days):
	"""Return (severity, recipients) for the given overdue tier.

	recipients is a list of dicts with keys: role, notified_to.
	Each recipient is also sent a desk notification.
	"""
	recipients = []

	if overdue_days <= 2:
		severity = "Reminder"
		if wo.assigned_to:
			recipients.append({"role": None, "notified_to": wo.assigned_to})
	elif overdue_days <= 5:
		severity = "Escalated"
		dept_head = get_user_with_role(DEPARTMENT_HEAD_ROLE)
		recipients.append({"role": DEPARTMENT_HEAD_ROLE, "notified_to": dept_head})
	else:
		severity = "Critical"
		gm = frappe.db.get_value("Property", wo.property, "gm") if wo.property else None
		recipients.append({"role": "Hotel GM", "notified_to": gm})

	# Send desk notifications.
	for r in recipients:
		if r["notified_to"]:
			notify_user(
				r["notified_to"],
				subject=f"Work Order {wo.name} is overdue by {overdue_days} day(s)",
				document_type="Maintenance Work Order",
				document_name=wo.name,
			)

	return severity, recipients


def _create_overdue_alert(wo, overdue_days, severity, recipients):
	alert = frappe.new_doc("Overdue Alert")
	alert.work_order = wo.name
	alert.overdue_days = overdue_days
	alert.severity = severity
	alert.alert_date = now_datetime()
	for r in recipients:
		alert.append(
			"notified_roles",
			{"role": r["role"], "notified_to": r["notified_to"], "notified_on": now_datetime()},
		)
	alert.insert(ignore_permissions=True)
	return alert


def _auto_create_negative_review(wo, overdue_days):
	"""Create a Negative Review (once) for a severely overdue work order."""
	if not wo.issue:
		return

	property_name = wo.property or frappe.db.get_value("Maintenance Issue", wo.issue, "property")

	# Avoid duplicate auto-reviews for the same overdue work order.
	if frappe.db.exists(
		"Negative Review",
		{"issue": wo.issue, "remarks": ["like", f"%overdue Work Order {wo.name}%"]},
	):
		return

	review = frappe.new_doc("Negative Review")
	review.issue = wo.issue
	review.property = property_name
	review.severity = "Major"
	review.review_date = now_datetime()
	review.remarks = (
		f"Auto-generated: overdue Work Order {wo.name} is {overdue_days} days past its due date."
	)
	review.insert(ignore_permissions=True)
