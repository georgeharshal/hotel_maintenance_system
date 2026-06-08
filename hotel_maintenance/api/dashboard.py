# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

"""Task 3 - Server-side data providers for the custom dashboard pages."""

import frappe
from frappe.utils import add_to_date, flt, get_datetime, getdate, now_datetime, today

OPEN_ISSUE_STATUSES = ("Open", "In Progress")
DONE_WO_STATUSES = ("Completed", "Verified", "Closed", "Cancelled")
CLOSED_ISSUE_STATUSES = ("Completed", "Verified", "Closed")


@frappe.whitelist()
def get_director_dashboard_data():
	"""KPI cards + property health table for the Director dashboard."""
	current_date = getdate(today())
	start_of_today = f"{current_date} 00:00:00"
	seven_days_ago = add_to_date(now_datetime(), days=-7)
	thirty_days_ago = add_to_date(now_datetime(), days=-30)

	open_issues_today = frappe.db.count(
		"Maintenance Issue",
		{"status": ["in", OPEN_ISSUE_STATUSES], "raised_date": [">=", start_of_today]},
	)

	overdue_work_orders = frappe.db.count(
		"Maintenance Work Order",
		{"status": ["not in", DONE_WO_STATUSES], "due_date": ["<", current_date]},
	)

	negative_reviews_7days = frappe.db.count(
		"Negative Review", {"review_date": [">=", seven_days_ago]}
	)

	avg_resolution = (
		frappe.db.sql(
			"""
			SELECT AVG(resolution_hours)
			FROM `tabMaintenance Issue`
			WHERE resolution_hours > 0 AND raised_date >= %(since)s
			""",
			{"since": thirty_days_ago},
		)[0][0]
		or 0
	)

	return {
		"kpi": {
			"open_issues_today": open_issues_today,
			"overdue_work_orders": overdue_work_orders,
			"negative_reviews_7days": negative_reviews_7days,
			"avg_resolution_time": flt(avg_resolution, 2),
		},
		"property_health": get_property_health(thirty_days_ago),
	}


def get_property_health(since):
	rows = []
	properties = frappe.get_all("Property", fields=["name", "gm"], order_by="name")
	for prop in properties:
		open_issues = frappe.db.count(
			"Maintenance Issue",
			{"property": prop.name, "status": ["in", OPEN_ISSUE_STATUSES]},
		)
		completed_issues = frappe.db.count(
			"Maintenance Issue",
			{
				"property": prop.name,
				"status": ["in", CLOSED_ISSUE_STATUSES],
				"raised_date": [">=", since],
			},
		)
		negative_points = (
			frappe.db.sql(
				"""
				SELECT COALESCE(SUM(points), 0)
				FROM `tabNegative Review`
				WHERE property = %(property)s AND review_date >= %(since)s
				""",
				{"property": prop.name, "since": since},
			)[0][0]
			or 0
		)
		health_score = max(0, 100 - int(negative_points) * 2)

		rows.append(
			{
				"property": prop.name,
				"gm": prop.gm,
				"open_issues": open_issues,
				"completed_issues": completed_issues,
				"negative_points": int(negative_points),
				"health_score": health_score,
			}
		)
	return rows


@frappe.whitelist()
def get_gm_dashboard_data(gm=None):
	"""Open issues, overdue work orders and negative points for a GM."""
	gm = gm or frappe.session.user
	thirty_days_ago = add_to_date(now_datetime(), days=-30)
	current_date = getdate(today())

	# Properties managed by this GM.
	properties = frappe.get_all("Property", filters={"gm": gm}, pluck="name")
	if not properties:
		return {
			"properties": [],
			"open_issues": 0,
			"overdue_work_orders": 0,
			"negative_points": 0,
			"escalation_warnings": [],
			"open_issue_list": [],
			"overdue_work_order_list": [],
		}

	open_issue_list = frappe.get_all(
		"Maintenance Issue",
		filters=[["property", "in", properties], ["status", "in", OPEN_ISSUE_STATUSES]],
		fields=["name", "property", "room", "priority", "status", "raised_date"],
		order_by="raised_date desc",
		limit=50,
	)

	overdue_work_order_list = frappe.get_all(
		"Maintenance Work Order",
		filters=[
			["property", "in", properties],
			["status", "not in", DONE_WO_STATUSES],
			["due_date", "<", current_date],
		],
		fields=["name", "property", "assigned_to", "due_date", "status"],
		order_by="due_date asc",
		limit=50,
	)

	negative_points = (
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(points), 0)
			FROM `tabNegative Review`
			WHERE gm = %(gm)s AND review_date >= %(since)s
			""",
			{"gm": gm, "since": thirty_days_ago},
		)[0][0]
		or 0
	)

	escalation_warnings = frappe.db.sql(
		"""
		SELECT ee.level, ee.threshold_points, ee.escalated_on
		FROM `tabEscalation Entry` ee
		INNER JOIN `tabNegative Review` nr ON ee.parent = nr.name
		WHERE nr.gm = %(gm)s AND ee.escalated_on >= %(since)s
		ORDER BY ee.escalated_on DESC
		""",
		{"gm": gm, "since": thirty_days_ago},
		as_dict=True,
	)

	return {
		"properties": properties,
		"open_issues": len(open_issue_list),
		"overdue_work_orders": len(overdue_work_order_list),
		"negative_points": int(negative_points),
		"escalation_warnings": escalation_warnings,
		"open_issue_list": open_issue_list,
		"overdue_work_order_list": overdue_work_order_list,
	}
