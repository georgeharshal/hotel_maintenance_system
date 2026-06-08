# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

"""Demo / seed data for the Hotel Maintenance app.

Run it to populate a site with realistic sample data that exercises every
feature (issues, work orders, completions, negative reviews + escalation,
overdue alerts, dashboards and reports):

    bench --site hotel.local execute hotel_maintenance.demo.seed.create_demo_data

Re-running is safe: it clears any previously seeded demo data first. To remove
the demo data without re-creating it:

    bench --site hotel.local execute hotel_maintenance.demo.seed.clear_demo_data
"""

import frappe
from frappe.utils import add_to_date, now_datetime, nowdate, add_days

DEMO_PASSWORD = "Hotel@12345"

DEMO_USERS = [
	{"email": "director@hotel.test", "first_name": "Dana", "last_name": "Director", "role": "Director"},
	{"email": "sgm@hotel.test", "first_name": "Sam", "last_name": "Senior", "role": "Senior General Manager"},
	{"email": "gm.grand@hotel.test", "first_name": "Grace", "last_name": "Manager", "role": "Hotel GM"},
	{"email": "gm.bay@hotel.test", "first_name": "Ben", "last_name": "Bayview", "role": "Hotel GM"},
	{"email": "tech1@hotel.test", "first_name": "Tariq", "last_name": "Tech", "role": "Maintenance Employee"},
	{"email": "tech2@hotel.test", "first_name": "Tina", "last_name": "Technician", "role": "Maintenance Employee"},
	{"email": "inspector@hotel.test", "first_name": "Ivy", "last_name": "Inspector", "role": "Inspection Team"},
]

# The two demo properties (used as the cleanup anchor).
DEMO_PROPERTIES = ["Grand Plaza Hotel", "Bayview Resort"]


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def create_demo_data():
	frappe.set_user("Administrator")
	clear_demo_data(verbose=False)

	users = _create_users()
	props = _create_properties()
	buildings = _create_buildings(props)
	rooms = _create_rooms(buildings)
	assets = _create_assets(rooms)
	issues = _create_issues(props, buildings, rooms, assets)
	_create_work_orders(issues)
	_create_negative_reviews(props)
	_run_overdue_job()

	frappe.db.commit()
	_print_summary()


def clear_demo_data(verbose=True):
	frappe.set_user("Administrator")

	# Resolve property names that exist, plus anything tagged DEMO.
	props = [p for p in DEMO_PROPERTIES if frappe.db.exists("Property", p)]

	# Delete in dependency order.
	for nr in frappe.get_all("Negative Review", filters={"property": ["in", props or [""]]}, pluck="name"):
		_force_delete("Negative Review", nr)
	for nr in frappe.get_all("Negative Review", filters={"remarks": ["like", "%DEMO%"]}, pluck="name"):
		_force_delete("Negative Review", nr)
	for oa in frappe.get_all("Overdue Alert", filters={"property": ["in", props or [""]]}, pluck="name"):
		_force_delete("Overdue Alert", oa)

	for dt in ["Maintenance Work Order", "Maintenance Issue", "Room Asset", "Room", "Building"]:
		for n in frappe.get_all(dt, filters={"property": ["in", props or [""]]}, pluck="name"):
			_force_delete(dt, n)

	for p in props:
		_force_delete("Property", p)

	for u in DEMO_USERS:
		if frappe.db.exists("User", u["email"]):
			_force_delete("User", u["email"])

	frappe.db.commit()
	if verbose:
		print("Demo data cleared.")


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _create_users():
	created = {}
	for u in DEMO_USERS:
		if frappe.db.exists("User", u["email"]):
			doc = frappe.get_doc("User", u["email"])
		else:
			doc = frappe.new_doc("User")
			doc.email = u["email"]
			doc.first_name = u["first_name"]
			doc.last_name = u["last_name"]
			doc.send_welcome_email = 0
			doc.new_password = DEMO_PASSWORD
			doc.append("roles", {"role": u["role"]})
			doc.insert(ignore_permissions=True)
		created[u["email"]] = doc.name
	return created


def _create_properties():
	data = [
		{"property_name": "Grand Plaza Hotel", "gm": "gm.grand@hotel.test", "location": "Downtown"},
		{"property_name": "Bayview Resort", "gm": "gm.bay@hotel.test", "location": "Coastline"},
	]
	out = {}
	for d in data:
		doc = frappe.new_doc("Property")
		doc.update(d)
		doc.status = "Active"
		doc.insert(ignore_permissions=True)
		out[d["property_name"]] = doc.name
	return out


def _create_buildings(props):
	data = [
		{"building_code": "GP-A", "building_name": "Main Wing", "property": "Grand Plaza Hotel", "floors": 10},
		{"building_code": "GP-B", "building_name": "Annex", "property": "Grand Plaza Hotel", "floors": 4},
		{"building_code": "BV-A", "building_name": "Ocean Tower", "property": "Bayview Resort", "floors": 8},
		{"building_code": "BV-B", "building_name": "Garden Block", "property": "Bayview Resort", "floors": 3},
	]
	out = {}
	for d in data:
		doc = frappe.new_doc("Building")
		doc.update(d)
		doc.status = "Active"
		doc.insert(ignore_permissions=True)
		out[d["building_code"]] = doc.name
	return out


def _create_rooms(buildings):
	out = []
	plan = {
		"GP-A": [("101", 1, "Deluxe"), ("102", 1, "Standard"), ("201", 2, "Suite")],
		"GP-B": [("A1", 1, "Standard"), ("A2", 1, "Executive")],
		"BV-A": [("1001", 10, "Presidential"), ("502", 5, "Suite")],
		"BV-B": [("G1", 1, "Standard"), ("G2", 1, "Deluxe")],
	}
	bld_prop = {b: frappe.db.get_value("Building", n, "property") for b, n in buildings.items()}
	for code, rooms in plan.items():
		for number, floor, rtype in rooms:
			doc = frappe.new_doc("Room")
			doc.room_number = number
			doc.building = buildings[code]
			doc.property = bld_prop[code]
			doc.floor = floor
			doc.room_type = rtype
			doc.status = "Available"
			doc.insert(ignore_permissions=True)
			out.append(doc.name)
	return out


def _create_assets(rooms):
	categories = ["HVAC", "Plumbing", "Electrical", "Electronics", "Appliance"]
	names = ["Split AC", "Water Heater", "Lighting Panel", "Smart TV", "Mini Fridge"]
	out = []
	for i, room in enumerate(rooms):
		# 1-2 assets per room
		for j in range(1 + (i % 2)):
			idx = (i + j) % len(categories)
			doc = frappe.new_doc("Room Asset")
			doc.asset_name = f"{names[idx]} - {room}"
			doc.category = categories[idx]
			doc.room = room
			doc.serial_no = f"SN-{1000 + i * 10 + j}"
			doc.install_date = add_days(nowdate(), -200 - i * 5)
			doc.status = "Working"
			doc.insert(ignore_permissions=True)
			out.append(doc.name)
	return out


def _create_issues(props, buildings, rooms, assets):
	"""Create a spread of issues: open today, in-progress, and resolvable ones."""
	now = now_datetime()
	specs = [
		# (property, priority, status, days_ago, description, resolvable)
		("Grand Plaza Hotel", "Critical", "Open", 0, "AC not cooling in lobby suite", False),
		("Grand Plaza Hotel", "High", "In Progress", 1, "Elevator making noise", False),
		("Grand Plaza Hotel", "Medium", "Open", 0, "Leaking faucet in room", False),
		("Grand Plaza Hotel", "Critical", "Open", 4, "Power outage on floor 2", True),
		("Bayview Resort", "High", "In Progress", 2, "TV not turning on", False),
		("Bayview Resort", "Low", "Open", 3, "Squeaky door hinge", False),
		("Bayview Resort", "Medium", "Open", 0, "Mini fridge warm", False),
		("Bayview Resort", "Critical", "Open", 5, "Burst pipe in Ocean Tower", True),
	]
	room_list = rooms
	out = []
	for i, (prop, priority, status, days_ago, desc, resolvable) in enumerate(specs):
		room = room_list[i % len(room_list)]
		building = frappe.db.get_value("Room", room, "building")
		room_prop = frappe.db.get_value("Room", room, "property")
		# keep room consistent with property where possible
		if room_prop != props[prop]:
			# pick a room belonging to this property
			match = frappe.get_all("Room", filters={"property": props[prop]}, pluck="name")
			if match:
				room = match[i % len(match)]
				building = frappe.db.get_value("Room", room, "building")

		asset = frappe.db.get_value("Room Asset", {"room": room}, "name")

		doc = frappe.new_doc("Maintenance Issue")
		doc.property = props[prop]
		doc.building = building
		doc.room = room
		doc.asset = asset
		doc.priority = priority
		doc.status = "Open"
		doc.description = desc + " (DEMO)"
		doc.raised_date = add_to_date(now, days=-days_ago)
		doc.insert(ignore_permissions=True)
		doc.submit()
		out.append({"name": doc.name, "status": status, "resolvable": resolvable, "priority": priority})

	# A few historical repeat failures on a single asset so the Asset Failure
	# Analysis report shows a meaningful "avg days between failures".
	recurring_asset = frappe.db.get_value("Room Asset", {"category": "HVAC"}, "name")
	if recurring_asset:
		asset_doc = frappe.get_doc("Room Asset", recurring_asset)
		for gap, days_ago in [(0, 45), (1, 30), (2, 12)]:
			doc = frappe.new_doc("Maintenance Issue")
			doc.property = asset_doc.property
			doc.building = asset_doc.building
			doc.room = asset_doc.room
			doc.asset = recurring_asset
			doc.priority = "High"
			doc.status = "Open"
			doc.description = "Recurring AC compressor trip (DEMO)"
			doc.raised_date = add_to_date(now, days=-days_ago)
			doc.insert(ignore_permissions=True)
			doc.submit()
			out.append({"name": doc.name, "status": "Open", "resolvable": False, "priority": "High"})
	return out


def _create_work_orders(issues):
	techs = ["tech1@hotel.test", "tech2@hotel.test"]
	departments = ["HVAC", "Electrical", "Plumbing", "IT", "Engineering"]
	for i, info in enumerate(issues):
		issue_name = info["name"]
		tech = techs[i % 2]
		dept = departments[i % len(departments)]

		wo = frappe.new_doc("Maintenance Work Order")
		wo.issue = issue_name
		wo.department = dept
		wo.assigned_to = tech
		wo.work_description = "Investigate and repair the reported fault."

		if info["resolvable"]:
			# Completed + verified -> resolution hours + possible SLA review.
			wo.due_date = add_days(nowdate(), -1)
			wo.insert(ignore_permissions=True)
			wo.completion_remarks = "Replaced faulty component and tested."
			wo.completion_photo = "/files/demo_completion.png"
			wo.status = "Completed"
			wo.save(ignore_permissions=True)
			wo.status = "Verified"
			wo.save(ignore_permissions=True)
			# advance the issue through its lifecycle
			issue = frappe.get_doc("Maintenance Issue", issue_name)
			issue.status = "Completed"
			issue.save(ignore_permissions=True)
			issue.reload()
			issue.status = "Verified"
			issue.save(ignore_permissions=True)
		elif i % 3 == 0:
			# overdue, still open -> drives Overdue Alerts + reports
			wo.due_date = add_days(nowdate(), -(3 + i))
			wo.status = "In Progress"
			wo.insert(ignore_permissions=True)
		else:
			# upcoming / in-progress
			wo.due_date = add_days(nowdate(), 2 + i)
			wo.status = "Assigned" if i % 2 else "In Progress"
			wo.insert(ignore_permissions=True)


def _create_negative_reviews(props):
	"""Manual negative reviews that push one GM over escalation thresholds."""
	grand = props["Grand Plaza Hotel"]
	# 3x Critical (15 pts) + 1x Major (3) = 18 -> crosses Warning(10), near SGM(20)
	severities = ["Critical", "Critical", "Critical", "Major"]
	for i, sev in enumerate(severities):
		nr = frappe.new_doc("Negative Review")
		nr.property = grand
		nr.severity = sev
		nr.review_date = add_to_date(now_datetime(), days=-i)
		nr.remarks = f"Guest complaint #{i + 1} (DEMO)"
		nr.insert(ignore_permissions=True)


def _run_overdue_job():
	from hotel_maintenance.hotel_maintenance.tasks import auto_escalate_overdue_work_orders
	auto_escalate_overdue_work_orders()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _force_delete(doctype, name):
	try:
		# cancel submitted docs before deleting
		doc = frappe.get_doc(doctype, name)
		if getattr(doc, "docstatus", 0) == 1:
			doc.cancel()
		frappe.delete_doc(doctype, name, force=1, ignore_permissions=True)
	except Exception:
		try:
			frappe.delete_doc(doctype, name, force=1, ignore_permissions=True)
		except Exception:
			pass


def _print_summary():
	print("\n==== DEMO DATA CREATED ====")
	for dt in [
		"Property", "Building", "Room", "Room Asset", "Maintenance Issue",
		"Maintenance Work Order", "Negative Review", "Overdue Alert",
	]:
		print(f"  {dt}: {frappe.db.count(dt)}")
	print(f"\n  Demo users (password '{DEMO_PASSWORD}'):")
	for u in DEMO_USERS:
		print(f"    {u['email']}  [{u['role']}]")
	print("\n  Dashboards:")
	print("    /app/director-maintenance-dashboard")
	print("    /app/gm-maintenance-dashboard")
