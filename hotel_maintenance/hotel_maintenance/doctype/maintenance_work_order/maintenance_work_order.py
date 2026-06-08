# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime, time_diff_in_hours


class MaintenanceWorkOrder(Document):
	def validate(self):
		self.validate_completion_requirements()

	def validate_completion_requirements(self):
		"""Task 2.3 - When a Work Order is marked 'Completed', the completion
		photo and remarks are mandatory and the completion datetime is auto-set.
		"""
		if self.status == "Completed":
			missing = []
			if not self.completion_remarks:
				missing.append(_("Completion Remarks"))
			if not self.completion_photo:
				missing.append(_("Completion Photo"))
			if missing:
				frappe.throw(
					_("The following are mandatory before marking a Work Order as Completed: {0}").format(
						", ".join(missing)
					)
				)
			if not self.completion_date:
				self.completion_date = now_datetime()

	def on_update(self):
		# Task 6 - calculate resolution time the moment a Work Order is Verified.
		if self.status == "Verified" and self.has_value_changed("status"):
			calculate_issue_resolution_time(self)


# ---------------------------------------------------------------------------
# Task 6: Server-side logic -- calculate_issue_resolution_time
# Runs when a Work Order moves to "Verified".
# ---------------------------------------------------------------------------

# priority -> (threshold in hours, negative review severity)
RESOLUTION_THRESHOLDS = {
	"Critical": (24, "Critical"),
	"High": (48, "Major"),
	"Medium": (120, "Minor"),  # 5 days
	"Low": (168, "Minor"),  # 7 days
}


def calculate_issue_resolution_time(work_order):
	"""Compute the resolution time (completion date - issue raised date) in hours,
	store it on the linked Issue, and auto-create a Negative Review when the
	priority-based SLA threshold is breached.
	"""
	if not work_order.issue:
		return

	issue = frappe.get_doc("Maintenance Issue", work_order.issue)
	completion_dt = work_order.completion_date or now_datetime()

	if not issue.raised_date:
		return

	resolution_hours = time_diff_in_hours(get_datetime(completion_dt), get_datetime(issue.raised_date))
	resolution_hours = round(resolution_hours, 2)

	# Store on the issue (read-only field, hence db_set).
	issue.db_set("resolution_hours", resolution_hours)

	# Evaluate SLA breach based on the issue priority.
	threshold = RESOLUTION_THRESHOLDS.get(issue.priority)
	if not threshold:
		return

	threshold_hours, severity = threshold
	if resolution_hours <= threshold_hours:
		return

	create_sla_breach_negative_review(issue, severity, resolution_hours, threshold_hours)


def create_sla_breach_negative_review(issue, severity, resolution_hours, threshold_hours):
	"""Create a Negative Review for an SLA breach, avoiding duplicates per issue."""
	existing = frappe.db.exists(
		"Negative Review",
		{"issue": issue.name, "remarks": ["like", "%SLA breach%"]},
	)
	if existing:
		return

	review = frappe.new_doc("Negative Review")
	review.issue = issue.name
	review.property = issue.property
	review.severity = severity
	review.review_date = now_datetime()
	review.remarks = _(
		"Auto-generated due to SLA breach: resolution took {0} hours against a "
		"{1}h threshold for {2} priority."
	).format(resolution_hours, threshold_hours, issue.priority)
	review.insert(ignore_permissions=True)
