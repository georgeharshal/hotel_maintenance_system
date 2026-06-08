# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

"""Task 7.2 - Asset Failure Analysis.

Aggregates Maintenance Issues per asset: number of issues, average days between
consecutive failures, the most common reported problem, and how many distinct
properties are affected.
"""

from collections import Counter

import frappe
from frappe.utils import date_diff, flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "Asset", "fieldname": "asset", "fieldtype": "Link", "options": "Room Asset", "width": 140},
		{"label": "Asset Name", "fieldname": "asset_name", "fieldtype": "Data", "width": 160},
		{"label": "Category", "fieldname": "category", "fieldtype": "Data", "width": 120},
		{"label": "Total Issues", "fieldname": "total_issues", "fieldtype": "Int", "width": 100},
		{"label": "Avg Days Between Failures", "fieldname": "avg_days_between_failures", "fieldtype": "Float", "width": 180, "precision": 1},
		{"label": "Common Problem", "fieldname": "common_problem", "fieldtype": "Data", "width": 220},
		{"label": "Properties Affected", "fieldname": "properties_affected", "fieldtype": "Int", "width": 140},
	]


def get_data(filters):
	issue_filters = [["asset", "is", "set"]]
	if filters.get("category"):
		# category lives on the asset; resolve matching assets first.
		assets = frappe.get_all(
			"Room Asset", filters={"category": filters.category}, pluck="name"
		)
		issue_filters.append(["asset", "in", assets or [""]])
	if filters.get("from_date"):
		issue_filters.append(["raised_date", ">=", filters.from_date])
	if filters.get("to_date"):
		issue_filters.append(["raised_date", "<=", filters.to_date])

	issues = frappe.get_all(
		"Maintenance Issue",
		filters=issue_filters,
		fields=["asset", "property", "priority", "description", "raised_date"],
		order_by="asset asc, raised_date asc",
	)

	# Group issues per asset.
	grouped = {}
	for issue in issues:
		grouped.setdefault(issue.asset, []).append(issue)

	# Asset metadata for names/categories.
	asset_meta = {
		a.name: a
		for a in frappe.get_all(
			"Room Asset",
			filters={"name": ["in", list(grouped.keys()) or [""]]},
			fields=["name", "asset_name", "category"],
		)
	}

	rows = []
	for asset, asset_issues in grouped.items():
		meta = asset_meta.get(asset, frappe._dict())
		total = len(asset_issues)

		# Average gap (in days) between consecutive failures.
		dates = [getdate(i.raised_date) for i in asset_issues if i.raised_date]
		dates.sort()
		if len(dates) > 1:
			gaps = [date_diff(dates[i], dates[i - 1]) for i in range(1, len(dates))]
			avg_gap = sum(gaps) / len(gaps)
		else:
			avg_gap = 0

		# Most common problem: mode of priority + description snippet.
		problems = Counter(
			(i.description or "").strip().split("\n")[0][:60] or i.priority
			for i in asset_issues
		)
		common_problem = problems.most_common(1)[0][0] if problems else ""

		properties_affected = len({i.property for i in asset_issues if i.property})

		rows.append(
			{
				"asset": asset,
				"asset_name": meta.get("asset_name"),
				"category": meta.get("category"),
				"total_issues": total,
				"avg_days_between_failures": flt(avg_gap, 1),
				"common_problem": common_problem,
				"properties_affected": properties_affected,
			}
		)

	rows.sort(key=lambda r: -r["total_issues"])
	return rows
