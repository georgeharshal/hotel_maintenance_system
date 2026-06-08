# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

"""Role-based desk: workspaces (sidebar + icon), number cards, charts and a
module profile that hides unrelated modules from limited roles.

Each role lands on its own workspace showing only the data it is concerned
with. Number cards and charts are aggregated through the permission system, so
combined with the row-level rules in hotel_maintenance.permissions a Hotel GM's
cards reflect only their property and a Maintenance Employee's cards only their
assigned work.

Run automatically on after_migrate; also runnable directly:

    bench --site <site> execute hotel_maintenance.setup.workspaces.setup_role_workspaces
"""

import json

import frappe

MODULE = "Hotel Maintenance"

OPEN_ISSUE = ["Open", "In Progress"]
WO_DONE = ["Completed", "Verified", "Closed"]
WO_NOT_DONE = ["Completed", "Verified", "Closed", "Cancelled"]


# ---------------------------------------------------------------------------
# Number cards
# ---------------------------------------------------------------------------

NUMBER_CARDS = [
	{"label": "HM Open Issues", "document_type": "Maintenance Issue", "function": "Count",
		"filters": [["Maintenance Issue", "status", "in", OPEN_ISSUE]], "color": "#5e64ff"},
	{"label": "HM Overdue Work Orders", "document_type": "Maintenance Work Order", "function": "Count",
		"filters": [["Maintenance Work Order", "status", "=", "Overdue"]], "color": "#ff5858"},
	{"label": "HM Negative Reviews", "document_type": "Negative Review", "function": "Count",
		"filters": [], "color": "#ffa00a"},
	{"label": "HM Completed Work Orders", "document_type": "Maintenance Work Order", "function": "Count",
		"filters": [["Maintenance Work Order", "status", "in", WO_DONE]], "color": "#28a745"},
	{"label": "HM Open Work Orders", "document_type": "Maintenance Work Order", "function": "Count",
		"filters": [["Maintenance Work Order", "status", "not in", WO_NOT_DONE]], "color": "#5e64ff"},
]


def _ensure_number_card(spec):
	existing = frappe.db.get_value("Number Card", {"label": spec["label"]}, "name")
	doc = frappe.get_doc("Number Card", existing) if existing else frappe.new_doc("Number Card")
	doc.update(
		{
			"label": spec["label"],
			"type": "Document Type",
			"document_type": spec["document_type"],
			"function": spec["function"],
			"filters_json": json.dumps(spec["filters"]),
			"is_public": 1,
			"show_percentage_stats": 0,
			"color": spec.get("color"),
			"module": MODULE,
		}
	)
	doc.save(ignore_permissions=True)
	return doc.name


# ---------------------------------------------------------------------------
# Dashboard charts
# ---------------------------------------------------------------------------

CHARTS = [
	{"chart_name": "HM Issues by Status", "document_type": "Maintenance Issue",
		"group_by": "status", "group_by_type": "Count", "type": "Donut", "color": "#5e64ff"},
	{"chart_name": "HM Issues by Priority", "document_type": "Maintenance Issue",
		"group_by": "priority", "group_by_type": "Count", "type": "Donut", "color": "#ffa00a"},
	{"chart_name": "HM Work Orders by Status", "document_type": "Maintenance Work Order",
		"group_by": "status", "group_by_type": "Count", "type": "Bar", "color": "#00b8d9"},
	{"chart_name": "HM Negative Points by Property", "document_type": "Negative Review",
		"group_by": "property", "group_by_type": "Sum", "aggregate_field": "points",
		"type": "Bar", "color": "#ff5858"},
]


def _ensure_chart(spec):
	name = spec["chart_name"]
	doc = frappe.get_doc("Dashboard Chart", name) if frappe.db.exists("Dashboard Chart", name) else frappe.new_doc("Dashboard Chart")
	doc.update(
		{
			"chart_name": name,
			"chart_type": "Group By",
			"document_type": spec["document_type"],
			"group_by_based_on": spec["group_by"],
			"group_by_type": spec["group_by_type"],
			"aggregate_function_based_on": spec.get("aggregate_field"),
			"type": spec["type"],
			"is_public": 1,
			"filters_json": "[]",
			"number_of_groups": 0,
			"color": spec.get("color"),
			"module": MODULE,
		}
	)
	doc.save(ignore_permissions=True)
	return doc.name


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------

# Each workspace spec: label, icon, roles, and an ordered list of blocks.
# Block kinds:
#   ("number_card", label, col)
#   ("chart", chart_name, col)
#   ("shortcut", label, link_to, link_type, color, col)
#   ("card", card_label, [(link_label, link_to, link_type), ...], col)
#   ("header", text)

ALL_DOCTYPES = [
	("Property", "Property"),
	("Building", "Building"),
	("Room", "Room"),
	("Room Asset", "Room Asset"),
	("Maintenance Issue", "Maintenance Issue"),
	("Maintenance Work Order", "Maintenance Work Order"),
	("Negative Review", "Negative Review"),
	("Overdue Alert", "Overdue Alert"),
]

WORKSPACES = [
	{
		"label": "Maintenance Director",
		"icon": "dashboard",
		"roles": ["Director"],
		"blocks": [
			("header", "Director — Maintenance Overview"),
			("number_card", "HM Open Issues", 3),
			("number_card", "HM Overdue Work Orders", 3),
			("number_card", "HM Negative Reviews", 3),
			("number_card", "HM Completed Work Orders", 3),
			("chart", "HM Issues by Status", 6),
			("chart", "HM Negative Points by Property", 6),
			("chart", "HM Work Orders by Status", 12),
			("shortcut", "Director Dashboard", "director-maintenance-dashboard", "Page", "Grey", 3),
			("shortcut", "GM Performance Summary", "GM Performance Summary", "Report", "Blue", 3),
			("shortcut", "Asset Failure Analysis", "Asset Failure Analysis", "Report", "Orange", 3),
			("shortcut", "Overdue Work Order Summary", "Overdue Work Order Summary", "Report", "Red", 3),
			("card", "Records", ALL_DOCTYPES, 12),
		],
	},
	{
		"label": "Senior Manager Maintenance",
		"icon": "review",
		"roles": ["Senior General Manager"],
		"blocks": [
			("header", "Senior General Manager"),
			("number_card", "HM Open Issues", 4),
			("number_card", "HM Overdue Work Orders", 4),
			("number_card", "HM Negative Reviews", 4),
			("chart", "HM Issues by Status", 6),
			("chart", "HM Work Orders by Status", 6),
			("shortcut", "GM Performance Summary", "GM Performance Summary", "Report", "Blue", 4),
			("shortcut", "Overdue Work Order Summary", "Overdue Work Order Summary", "Report", "Red", 4),
			("card", "Records", [
				("Maintenance Issue", "Maintenance Issue"),
				("Maintenance Work Order", "Maintenance Work Order"),
				("Negative Review", "Negative Review"),
				("Property", "Property"),
				("Building", "Building"),
				("Overdue Alert", "Overdue Alert"),
			], 12),
		],
	},
	{
		"label": "Hotel GM Workspace",
		"icon": "organization",
		"roles": ["Hotel GM"],
		"blocks": [
			("header", "Hotel GM — My Property"),
			("number_card", "HM Open Issues", 4),
			("number_card", "HM Overdue Work Orders", 4),
			("number_card", "HM Negative Reviews", 4),
			("shortcut", "GM Dashboard", "gm-maintenance-dashboard", "Page", "Blue", 4),
			("card", "My Property", [
				("Maintenance Issue", "Maintenance Issue"),
				("Maintenance Work Order", "Maintenance Work Order"),
				("Room", "Room"),
				("Room Asset", "Room Asset"),
				("Property", "Property"),
			], 12),
		],
	},
	{
		"label": "Maintenance Tasks",
		"icon": "tool",
		"roles": ["Maintenance Employee"],
		"blocks": [
			("header", "My Maintenance Work"),
			("number_card", "HM Open Work Orders", 6),
			("number_card", "HM Completed Work Orders", 6),
			("shortcut", "My Work Orders", "Maintenance Work Order", "DocType", "Blue", 4),
			("card", "Work", [
				("Maintenance Work Order", "Maintenance Work Order"),
			], 12),
		],
	},
	{
		"label": "Inspection",
		"icon": "review",
		"roles": ["Inspection Team"],
		"blocks": [
			("header", "Inspection Team"),
			("number_card", "HM Open Issues", 6),
			("number_card", "HM Negative Reviews", 6),
			("shortcut", "Negative Reviews", "Negative Review", "DocType", "Orange", 4),
			("card", "Inspection", [
				("Negative Review", "Negative Review"),
				("Maintenance Issue", "Maintenance Issue"),
				("Room", "Room"),
				("Room Asset", "Room Asset"),
			], 12),
		],
	},
]


def _build_workspace(spec, seq):
	label = spec["label"]
	if frappe.db.exists("Workspace", label):
		frappe.delete_doc("Workspace", label, force=1, ignore_permissions=True)

	ws = frappe.new_doc("Workspace")
	ws.label = label
	ws.title = label
	ws.module = MODULE
	ws.public = 1
	ws.icon = spec["icon"]
	ws.type = "Workspace"
	ws.sequence_id = seq
	for role in spec["roles"]:
		ws.append("roles", {"role": role})

	content = []
	counter = {"n": 0}

	def _id():
		counter["n"] += 1
		return f"hmblk{counter['n']}"

	for block in spec["blocks"]:
		kind = block[0]
		if kind == "header":
			content.append({"id": _id(), "type": "header",
				"data": {"text": f"<span class='h4'>{block[1]}</span>", "col": 12}})
		elif kind == "number_card":
			_, card_label, col = block
			ws.append("number_cards", {"label": card_label, "number_card_name": card_label})
			content.append({"id": _id(), "type": "number_card",
				"data": {"number_card_name": card_label, "col": col}})
		elif kind == "chart":
			_, chart_name, col = block
			ws.append("charts", {"label": chart_name, "chart_name": chart_name})
			content.append({"id": _id(), "type": "chart",
				"data": {"chart_name": chart_name, "col": col}})
		elif kind == "shortcut":
			_, slabel, link_to, link_type, color, col = block
			ws.append("shortcuts", {
				"type": link_type, "label": slabel, "link_to": link_to, "color": color})
			content.append({"id": _id(), "type": "shortcut",
				"data": {"shortcut_name": slabel, "col": col}})
		elif kind == "card":
			_, card_label, links, col = block
			ws.append("links", {
				"type": "Card Break", "label": card_label, "link_count": len(links),
				"hidden": 0, "onboard": 0, "is_query_report": 0})
			for link_label, link_to in links:
				ws.append("links", {
					"type": "Link", "label": link_label, "link_to": link_to,
					"link_type": "DocType", "hidden": 0, "onboard": 0,
					"is_query_report": 0, "link_count": 0})
			content.append({"id": _id(), "type": "card",
				"data": {"card_name": card_label, "col": col}})

	ws.content = json.dumps(content)
	ws.insert(ignore_permissions=True)
	return ws.name


# ---------------------------------------------------------------------------
# Module profile (hide unrelated modules from limited roles)
# ---------------------------------------------------------------------------

LIMITED_MODULE_PROFILE = "Hotel Maintenance Limited"


def _ensure_module_profile():
	"""A module profile that blocks every module except Hotel Maintenance, so
	limited users (GM / Employee / Inspection) see a clean, focused desk."""
	all_modules = frappe.get_all("Module Def", pluck="name")
	blocked = [m for m in all_modules if m != MODULE]

	if frappe.db.exists("Module Profile", LIMITED_MODULE_PROFILE):
		doc = frappe.get_doc("Module Profile", LIMITED_MODULE_PROFILE)
		doc.set("block_modules", [])
	else:
		doc = frappe.new_doc("Module Profile")
		doc.module_profile_name = LIMITED_MODULE_PROFILE

	for m in blocked:
		doc.append("block_modules", {"module": m})
	doc.save(ignore_permissions=True)
	return doc.name


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def setup_role_workspaces():
	for spec in NUMBER_CARDS:
		_ensure_number_card(spec)
	for spec in CHARTS:
		_ensure_chart(spec)
	for seq, spec in enumerate(WORKSPACES, start=20):
		_build_workspace(spec, seq)
	_ensure_module_profile()
	frappe.db.commit()
	frappe.clear_cache()
