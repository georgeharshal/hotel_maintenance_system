# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

"""Task 5 - Roles & permissions configuration (migration script).

This runs on ``after_install`` and ``after_migrate`` so the custom roles and
their DocType permissions are created/refreshed idempotently. It is the
"migration script" alternative to a static roles.json mentioned in the brief.

Permission matrix (per the assessment task):

  Hotel GM             -> Issue (CRU + Submit/Cancel), Work Order (CRU),
                          Room (CRU), Asset (RU), Property/Building (R),
                          Negative Review (R)
  Senior General Mgr   -> Issue (RU), Work Order (RU), Negative Review (RU),
                          all Properties/masters/alerts (R)
  Director             -> All DocTypes (R), Negative Review (C + U)
  Maintenance Employee -> Work Order (R + update status, only assigned to self,
                          no create/delete) -- row-level enforced in
                          hotel_maintenance.permissions
  Inspection Team      -> Negative Review (RUC), Issue (R), Rooms/Assets (R)
"""

import frappe
from frappe.permissions import add_permission, update_permission_property

CUSTOM_ROLES = [
	"Hotel GM",
	"Senior General Manager",
	"Director",
	"Maintenance Employee",
	"Inspection Team",
]

# right-name -> 1/0 sets. Helper builds a full rights dict from a short spec.
ALL_RIGHTS = ["read", "write", "create", "delete", "submit", "cancel", "export"]


def _rights(**kwargs):
	base = {r: 0 for r in ALL_RIGHTS}
	base.update(kwargs)
	return base


# role -> { doctype -> rights dict }
PERMISSION_MATRIX = {
	"Hotel GM": {
		"Maintenance Issue": _rights(read=1, write=1, create=1, submit=1, cancel=1),
		"Maintenance Work Order": _rights(read=1, write=1, create=1),
		"Room": _rights(read=1, write=1, create=1),
		"Room Asset": _rights(read=1, write=1),
		"Property": _rights(read=1),
		"Building": _rights(read=1),
		"Negative Review": _rights(read=1),
		"Overdue Alert": _rights(read=1),
	},
	"Senior General Manager": {
		"Maintenance Issue": _rights(read=1, write=1),
		"Maintenance Work Order": _rights(read=1, write=1),
		"Negative Review": _rights(read=1, write=1),
		"Property": _rights(read=1),
		"Building": _rights(read=1),
		"Room": _rights(read=1),
		"Room Asset": _rights(read=1),
		"Overdue Alert": _rights(read=1),
	},
	"Director": {
		"Property": _rights(read=1, export=1),
		"Building": _rights(read=1, export=1),
		"Room": _rights(read=1, export=1),
		"Room Asset": _rights(read=1, export=1),
		"Maintenance Issue": _rights(read=1, export=1),
		"Maintenance Work Order": _rights(read=1, export=1),
		"Negative Review": _rights(read=1, create=1, write=1, export=1),
		"Overdue Alert": _rights(read=1, export=1),
	},
	"Maintenance Employee": {
		# Row-level (assigned-to-self) is enforced in hotel_maintenance.permissions.
		"Maintenance Work Order": _rights(read=1, write=1),
	},
	"Inspection Team": {
		"Negative Review": _rights(read=1, write=1, create=1),
		"Maintenance Issue": _rights(read=1),
		"Room": _rights(read=1),
		"Room Asset": _rights(read=1),
	},
}


def after_install():
	setup_roles_and_permissions()


def after_migrate():
	setup_roles_and_permissions()


def setup_roles_and_permissions():
	"""Create the custom roles and apply the permission matrix idempotently."""
	create_roles()
	apply_permissions()
	frappe.db.commit()


def create_roles():
	for role_name in CUSTOM_ROLES:
		if not frappe.db.exists("Role", role_name):
			role = frappe.new_doc("Role")
			role.role_name = role_name
			role.desk_access = 1
			role.insert(ignore_permissions=True)


def apply_permissions():
	for role, doctype_rights in PERMISSION_MATRIX.items():
		for doctype, rights in doctype_rights.items():
			if not frappe.db.exists("DocType", doctype):
				continue

			# Ensure a permission row exists for this (doctype, role) at level 0.
			if not _perm_exists(doctype, role):
				add_permission(doctype, role, permlevel=0)

			for right, value in rights.items():
				update_permission_property(doctype, role, 0, right, value, validate=False)


def _perm_exists(doctype, role):
	return bool(
		frappe.get_all(
			"Custom DocPerm",
			filters={"parent": doctype, "role": role, "permlevel": 0},
			limit=1,
		)
		or frappe.get_all(
			"DocPerm",
			filters={"parent": doctype, "role": role, "permlevel": 0},
			limit=1,
		)
	)
