# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

"""Task 7.3 - Overdue Work Order Summary.

Lists every Work Order that is past its due date and not yet done, with the
property, department, assignee, due date, days overdue, status and how long
since the order was last updated.
"""

import frappe
from frappe.utils import date_diff, getdate, today

DONE_STATUSES = ("Completed", "Verified", "Closed", "Cancelled")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "Work Order", "fieldname": "work_order", "fieldtype": "Link", "options": "Maintenance Work Order", "width": 140},
		{"label": "Property", "fieldname": "property", "fieldtype": "Link", "options": "Property", "width": 150},
		{"label": "Department", "fieldname": "department", "fieldtype": "Data", "width": 120},
		{"label": "Assigned To", "fieldname": "assigned_to", "fieldtype": "Link", "options": "User", "width": 170},
		{"label": "Due Date", "fieldname": "due_date", "fieldtype": "Date", "width": 100},
		{"label": "Overdue Days", "fieldname": "overdue_days", "fieldtype": "Int", "width": 110},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": "Days Since Last Update", "fieldname": "days_since_update", "fieldtype": "Int", "width": 170},
	]


def get_data(filters):
	current_date = getdate(today())

	wo_filters = [
		["status", "not in", DONE_STATUSES],
		["due_date", "is", "set"],
		["due_date", "<", current_date],
	]
	if filters.get("property"):
		wo_filters.append(["property", "=", filters.property])
	if filters.get("department"):
		wo_filters.append(["department", "=", filters.department])

	work_orders = frappe.get_all(
		"Maintenance Work Order",
		filters=wo_filters,
		fields=[
			"name", "property", "department", "assigned_to",
			"due_date", "status", "modified",
		],
		order_by="due_date asc",
	)

	rows = []
	for wo in work_orders:
		rows.append(
			{
				"work_order": wo.name,
				"property": wo.property,
				"department": wo.department,
				"assigned_to": wo.assigned_to,
				"due_date": wo.due_date,
				"overdue_days": date_diff(current_date, getdate(wo.due_date)),
				"status": wo.status,
				"days_since_update": date_diff(current_date, getdate(wo.modified)),
			}
		)

	rows.sort(key=lambda r: -r["overdue_days"])
	return rows
