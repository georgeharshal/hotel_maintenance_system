# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

"""Task 8 - Refactored bulk overdue-status update.

The original implementation (see the task brief) was inefficient and partly
incorrect:

  * It loaded every candidate Work Order with ``frappe.get_doc`` inside a loop
    (one SELECT + full document load per row).
  * It called ``frappe.db.commit()`` on every single iteration.
  * It compared dates as strings via ``frappe.utils.nowdate() > doc.due_date``.
  * It then flagged *every* open Issue as having an overdue work order,
    regardless of whether that was actually true, and again committed per row.

The version below performs the same work with set-based SQL: two bulk UPDATEs
for the work orders and the issue flag, a single commit, and a correct flag
that is both set and cleared based on reality.
"""

import frappe
from frappe.utils import today

DONE_STATUSES = ("Completed", "Verified", "Closed", "Cancelled")


@frappe.whitelist()
def update_overdue_status():
	"""Mark past-due Work Orders as 'Overdue' and sync the parent Issue flag.

	Returns a small summary dict so callers/tests can assert on the effect.
	"""
	current_date = today()

	# 1) Bulk-mark overdue Work Orders in a single UPDATE.
	overdue_work_orders = frappe.get_all(
		"Maintenance Work Order",
		filters=[
			["status", "not in", DONE_STATUSES],
			["status", "!=", "Overdue"],
			["due_date", "is", "set"],
			["due_date", "<", current_date],
		],
		pluck="name",
	)

	if overdue_work_orders:
		frappe.db.set_value(
			"Maintenance Work Order",
			{"name": ["in", overdue_work_orders]},
			"status",
			"Overdue",
			update_modified=True,
		)

	# 2) Recompute the has_overdue_work_order flag on Issues correctly.
	#    An issue is flagged only if it actually has a not-done, past-due order.
	issues_with_overdue = set(
		frappe.get_all(
			"Maintenance Work Order",
			filters=[
				["status", "not in", DONE_STATUSES],
				["due_date", "is", "set"],
				["due_date", "<", current_date],
				["issue", "is", "set"],
			],
			pluck="issue",
		)
	)

	# Set the flag where it should be 1 but currently is 0.
	to_set = frappe.get_all(
		"Maintenance Issue",
		filters=[["has_overdue_work_order", "=", 0], ["name", "in", list(issues_with_overdue) or [""]]],
		pluck="name",
	)
	if to_set:
		frappe.db.set_value(
			"Maintenance Issue", {"name": ["in", to_set]}, "has_overdue_work_order", 1
		)

	# Clear the flag where it is 1 but no longer has any overdue order.
	currently_flagged = set(
		frappe.get_all(
			"Maintenance Issue", filters={"has_overdue_work_order": 1}, pluck="name"
		)
	)
	to_clear = list(currently_flagged - issues_with_overdue)
	if to_clear:
		frappe.db.set_value(
			"Maintenance Issue", {"name": ["in", to_clear]}, "has_overdue_work_order", 0
		)

	# 3) Single commit at the end.
	frappe.db.commit()

	return {
		"work_orders_marked_overdue": len(overdue_work_orders),
		"issues_flagged": len(to_set),
		"issues_cleared": len(to_clear),
	}
