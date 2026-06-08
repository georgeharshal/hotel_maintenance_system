# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

"""Row-level permission rules ("only concerned data").

- Hotel GM: sees only records belonging to the properties they manage
  (Property.gm == user) across Property/Building/Room/Room Asset/Maintenance
  Issue/Maintenance Work Order/Negative Review.
- Maintenance Employee: sees only Work Orders assigned to themselves
  (no create/delete is handled by the role permissions).
- Director / Senior General Manager / System Manager: unrestricted (they
  oversee everything). Inspection Team reads across properties by design.

These are wired in hooks.py via permission_query_conditions (list views,
reports, number cards, charts) and has_permission (single-document access).
"""

import frappe

# Roles that are never row-restricted.
SUPERVISOR_ROLES = {
	"System Manager",
	"Administrator",
	"Director",
	"Senior General Manager",
}


def _roles(user):
	return set(frappe.get_roles(user))


def _is_supervisor(user):
	return bool(_roles(user) & SUPERVISOR_ROLES)


def _is_gm(user):
	return "Hotel GM" in _roles(user) and not _is_supervisor(user)


def _is_plain_employee(user):
	roles = _roles(user)
	if roles & SUPERVISOR_ROLES or "Hotel GM" in roles:
		return False
	return "Maintenance Employee" in roles


def _gm_properties(user):
	return frappe.get_all("Property", filters={"gm": user}, pluck="name")


def _in_clause(table, field, values):
	"""Build a safe `table`.`field` IN (...) clause; matches nothing if empty."""
	if not values:
		return f"`{table}`.`{field}` = '__no_access__'"
	joined = ", ".join(frappe.db.escape(v) for v in values)
	return f"`{table}`.`{field}` in ({joined})"


# ---------------------------------------------------------------------------
# permission_query_conditions
# ---------------------------------------------------------------------------

def _gm_scope(user, table, field="property"):
	if not _is_gm(user):
		return ""
	return _in_clause(table, field, _gm_properties(user))


def maintenance_issue_query_conditions(user=None):
	user = user or frappe.session.user
	return _gm_scope(user, "tabMaintenance Issue")


def negative_review_query_conditions(user=None):
	user = user or frappe.session.user
	return _gm_scope(user, "tabNegative Review")


def room_query_conditions(user=None):
	user = user or frappe.session.user
	return _gm_scope(user, "tabRoom")


def room_asset_query_conditions(user=None):
	user = user or frappe.session.user
	return _gm_scope(user, "tabRoom Asset")


def building_query_conditions(user=None):
	user = user or frappe.session.user
	return _gm_scope(user, "tabBuilding")


def property_query_conditions(user=None):
	user = user or frappe.session.user
	if not _is_gm(user):
		return ""
	return _in_clause("tabProperty", "name", _gm_properties(user))


def work_order_query_conditions(user=None):
	"""GM -> their properties; Maintenance Employee -> assigned to self."""
	user = user or frappe.session.user
	if _is_gm(user):
		return _in_clause("tabMaintenance Work Order", "property", _gm_properties(user))
	if _is_plain_employee(user):
		return f"`tabMaintenance Work Order`.`assigned_to` = {frappe.db.escape(user)}"
	return ""


# ---------------------------------------------------------------------------
# has_permission (single-document access)
# ---------------------------------------------------------------------------

def _gm_doc_allowed(doc, user, property_value):
	if not _is_gm(user):
		return True
	return property_value in _gm_properties(user)


def maintenance_issue_has_permission(doc, user=None, permission_type=None):
	user = user or frappe.session.user
	return _gm_doc_allowed(doc, user, doc.property)


def negative_review_has_permission(doc, user=None, permission_type=None):
	user = user or frappe.session.user
	return _gm_doc_allowed(doc, user, doc.property)


def room_has_permission(doc, user=None, permission_type=None):
	user = user or frappe.session.user
	return _gm_doc_allowed(doc, user, doc.property)


def room_asset_has_permission(doc, user=None, permission_type=None):
	user = user or frappe.session.user
	return _gm_doc_allowed(doc, user, doc.property)


def building_has_permission(doc, user=None, permission_type=None):
	user = user or frappe.session.user
	return _gm_doc_allowed(doc, user, doc.property)


def property_has_permission(doc, user=None, permission_type=None):
	user = user or frappe.session.user
	if not _is_gm(user):
		return True
	return doc.name in _gm_properties(user)


def work_order_has_permission(doc, user=None, permission_type=None):
	user = user or frappe.session.user
	if _is_gm(user):
		return doc.property in _gm_properties(user)
	if _is_plain_employee(user):
		return doc.assigned_to == user
	return True
