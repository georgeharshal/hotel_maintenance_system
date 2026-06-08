# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

"""Task 7.1 - GM Performance Summary.

For each Property/GM within the selected period: total & closed issues, closure
rate, average resolution hours, negative points, escalation count and a derived
performance ranking.
"""

import frappe
from frappe.utils import flt, get_first_day, get_last_day, today

CLOSED_STATUSES = ("Completed", "Verified", "Closed")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	from_date = filters.get("from_date") or get_first_day(today())
	to_date = filters.get("to_date") or get_last_day(today())

	columns = get_columns()
	data = get_data(from_date, to_date, filters.get("property"))
	return columns, data


def get_columns():
	return [
		{"label": "Property", "fieldname": "property", "fieldtype": "Link", "options": "Property", "width": 160},
		{"label": "GM", "fieldname": "gm", "fieldtype": "Link", "options": "User", "width": 180},
		{"label": "Total Issues", "fieldname": "total_issues", "fieldtype": "Int", "width": 100},
		{"label": "Closed Issues", "fieldname": "closed_issues", "fieldtype": "Int", "width": 110},
		{"label": "Closure Rate %", "fieldname": "closure_rate", "fieldtype": "Percent", "width": 120},
		{"label": "Avg Resolution (hrs)", "fieldname": "avg_resolution_hours", "fieldtype": "Float", "width": 150, "precision": 2},
		{"label": "Negative Points", "fieldname": "negative_points", "fieldtype": "Int", "width": 120},
		{"label": "Escalations", "fieldname": "escalation_count", "fieldtype": "Int", "width": 100},
		{"label": "Rank", "fieldname": "ranking", "fieldtype": "Int", "width": 70},
	]


def get_data(from_date, to_date, property_filter=None):
	prop_filters = {}
	if property_filter:
		prop_filters["name"] = property_filter

	properties = frappe.get_all(
		"Property", filters=prop_filters, fields=["name", "gm"], order_by="name"
	)

	rows = []
	for prop in properties:
		total_issues = frappe.db.count(
			"Maintenance Issue",
			{"property": prop.name, "raised_date": ["between", [from_date, to_date]]},
		)
		closed_issues = frappe.db.count(
			"Maintenance Issue",
			{
				"property": prop.name,
				"status": ["in", CLOSED_STATUSES],
				"raised_date": ["between", [from_date, to_date]],
			},
		)
		closure_rate = (closed_issues / total_issues * 100) if total_issues else 0

		avg_resolution = (
			frappe.db.sql(
				"""
				SELECT AVG(resolution_hours)
				FROM `tabMaintenance Issue`
				WHERE property = %(property)s
				  AND resolution_hours > 0
				  AND raised_date BETWEEN %(from_date)s AND %(to_date)s
				""",
				{"property": prop.name, "from_date": from_date, "to_date": to_date},
			)[0][0]
			or 0
		)

		negative_points = (
			frappe.db.sql(
				"""
				SELECT COALESCE(SUM(points), 0)
				FROM `tabNegative Review`
				WHERE property = %(property)s
				  AND review_date BETWEEN %(from_date)s AND %(to_date)s
				""",
				{"property": prop.name, "from_date": from_date, "to_date": to_date},
			)[0][0]
			or 0
		)

		escalation_count = 0
		if prop.gm:
			escalation_count = (
				frappe.db.sql(
					"""
					SELECT COUNT(ee.name)
					FROM `tabEscalation Entry` ee
					INNER JOIN `tabNegative Review` nr ON ee.parent = nr.name
					WHERE nr.gm = %(gm)s
					  AND ee.escalated_on BETWEEN %(from_date)s AND %(to_date)s
					""",
					{"gm": prop.gm, "from_date": from_date, "to_date": to_date},
				)[0][0]
				or 0
			)

		rows.append(
			{
				"property": prop.name,
				"gm": prop.gm,
				"total_issues": total_issues,
				"closed_issues": closed_issues,
				"closure_rate": flt(closure_rate, 2),
				"avg_resolution_hours": flt(avg_resolution, 2),
				"negative_points": int(negative_points),
				"escalation_count": int(escalation_count),
			}
		)

	# Ranking: higher closure rate is better, fewer negative points breaks ties.
	rows.sort(key=lambda r: (-r["closure_rate"], r["negative_points"]))
	for index, row in enumerate(rows, start=1):
		row["ranking"] = index

	return rows
