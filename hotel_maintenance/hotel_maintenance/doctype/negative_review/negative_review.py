# Copyright (c) 2026, Harshal and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, now_datetime

from hotel_maintenance.utils import get_user_with_role, notify_user

# Task 2.1 - severity -> points
SEVERITY_POINTS = {"Minor": 1, "Major": 3, "Critical": 5}

# Task 2.2 - escalation thresholds: (threshold points, level, role to notify)
# The "Warning" level notifies the GM themselves; higher levels notify the
# responsible senior role.
ESCALATION_LEVELS = [
	(10, "Warning", None),
	(20, "SGM Review", "Senior General Manager"),
	(30, "Director Escalation", "Director"),
	(50, "Management Action", "Director"),
]

ESCALATION_WINDOW_DAYS = 30


class NegativeReview(Document):
	def before_insert(self):
		if not self.review_date:
			self.review_date = now_datetime()

	def validate(self):
		self.calculate_points()
		self.apply_escalation()

	def calculate_points(self):
		"""Task 2.1 - derive points from severity."""
		self.points = SEVERITY_POINTS.get(self.severity, 0)

	def apply_escalation(self):
		"""Task 2.2 - sum a GM's points over the last 30 days and append
		escalation entries for any newly-crossed threshold. Duplicate levels
		(already recorded for this GM in the window) are skipped.
		"""
		if not self.gm:
			return

		window_start = add_to_date(now_datetime(), days=-ESCALATION_WINDOW_DAYS)

		# Points from this GM's other reviews in the window + this review's points.
		other_points = (
			frappe.db.sql(
				"""
				SELECT COALESCE(SUM(points), 0)
				FROM `tabNegative Review`
				WHERE gm = %(gm)s
				  AND name != %(name)s
				  AND review_date >= %(window_start)s
				""",
				{"gm": self.gm, "name": self.name or "", "window_start": window_start},
			)[0][0]
			or 0
		)
		total_points = other_points + (self.points or 0)

		# Levels already escalated for this GM in the window (across all reviews).
		existing_levels = set(
			frappe.db.sql_list(
				"""
				SELECT DISTINCT ee.level
				FROM `tabEscalation Entry` ee
				INNER JOIN `tabNegative Review` nr ON ee.parent = nr.name
				WHERE nr.gm = %(gm)s
				  AND ee.escalated_on >= %(window_start)s
				""",
				{"gm": self.gm, "window_start": window_start},
			)
		)
		# Also account for levels already staged on this document in-memory.
		existing_levels.update(row.level for row in self.escalations)

		for threshold, level, role in ESCALATION_LEVELS:
			if total_points >= threshold and level not in existing_levels:
				notified_to = self.gm if role is None else get_user_with_role(role)
				self.append(
					"escalations",
					{
						"level": level,
						"threshold_points": threshold,
						"escalated_on": now_datetime(),
						"notified_to": notified_to,
					},
				)
				existing_levels.add(level)

	def on_update(self):
		self.send_escalation_notifications()

	def after_insert(self):
		self.publish_realtime_alert()

	def send_escalation_notifications(self):
		"""Notify the responsible users for any escalation recorded on this review."""
		for row in self.escalations:
			if row.notified_to:
				notify_user(
					row.notified_to,
					subject=f"Maintenance escalation: {row.level} for GM {self.gm}",
					document_type="Negative Review",
					document_name=self.name,
				)

	def publish_realtime_alert(self):
		"""Task 3 - real-time toast on the Director dashboard for new reviews."""
		frappe.publish_realtime(
			event="hotel_new_negative_review",
			message={
				"name": self.name,
				"property": self.property,
				"gm": self.gm,
				"severity": self.severity,
				"points": self.points,
			},
			after_commit=True,
		)
