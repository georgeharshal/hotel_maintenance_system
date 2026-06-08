# Hotel Maintenance Management System — Development Guide

This guide documents how the assessment task is implemented inside the
`hotel_maintenance` custom app, mapping every required task to the exact files
and design decisions. The app targets **Frappe v16** and uses native Frappe
conventions throughout (DocType JSON + Python controllers, hooks, Script
Reports, desk Pages).

> Bench: `hotel_maintenance/` · Site: `hotel.local` · App module: `Hotel Maintenance`
> App path: `apps/hotel_maintenance/hotel_maintenance/`

---

## Architecture overview

```
Property ──< Building ──< Room ──< Room Asset
   │            │           │
   └────────────┴───────────┴──< Maintenance Issue (submittable)
                                     │
                                     └──< Maintenance Work Order
                                              │
                  Negative Review >──────────-┘  (manual, SLA, or overdue-driven)
                  │  └─ Escalation Entry (child)
                  │
   Overdue Alert >─┴─ Overdue Alert Recipient (child)   (created by daily job)
```

Lifecycle: an **Issue** is raised → one or more **Work Orders** are created and
worked → completing/verifying work orders drives **resolution-time** and
**SLA** logic → poor outcomes create **Negative Reviews** → accumulated GM
points drive **Escalations** → overdue work orders generate **Overdue Alerts**
via a daily scheduled job.

---

## Task 1 — DocTypes
Location: `hotel_maintenance/doctype/<doctype>/`

Ten DocTypes (8 required + `Overdue Alert` & its child for Task 4):

| DocType | Naming | Key relationships |
|---------|--------|-------------------|
| Property | `field:property_name` | GM → User |
| Building | `field:building_code` | Property |
| Room | `format:{building}-{room_number}` | Property, Building |
| Room Asset | `ASSET-.#####` | Room, Building (fetch), Property (fetch) |
| Maintenance Issue | `ISS-.YYYY.-` | Property/Building/Room/Asset — **submittable** |
| Maintenance Work Order | `WO-.YYYY.-` | Issue (+ fetched location) |
| Negative Review | `NR-.YYYY.-` | Issue, Property, GM (fetch) |
| Escalation Entry | child | (in Negative Review) |
| Overdue Alert | `OA-.YYYY.-` | Work Order |
| Overdue Alert Recipient | child | (in Overdue Alert) |

Every **link field** sets `"search_index": 1` to satisfy the "proper indexes on
link fields" requirement. Fetched fields (e.g. `gm` from `property.gm`,
`property` from `issue.property`) keep denormalised data consistent and make
reports/dashboards efficient.

---

## Task 2 — Business logic
Implemented as native controller methods (not Server Script docs) for
testability and version control.

| Rule | File | Method |
|------|------|--------|
| 2.1 Points (Minor 1 / Major 3 / Critical 5) | `doctype/negative_review/negative_review.py` | `calculate_points` |
| 2.2 Escalation (10/20/30/50, no dup levels, auto datetime + user) | same | `apply_escalation` |
| 2.3 Work Order completion (photo + remarks mandatory, auto datetime) | `doctype/maintenance_work_order/maintenance_work_order.py` | `validate_completion_requirements` |
| 2.4 Issue closure constraint | `doctype/maintenance_issue/maintenance_issue.py` | `validate_closure_constraint` |

**Important nuance (2.4):** because *Maintenance Issue* is submittable, status
changes happen post-submit, where Frappe runs `before_update_after_submit` —
**not** `validate`. The constraint is therefore invoked from *both* hooks.

---

## Task 3 — Dashboards
Desk Pages under `hotel_maintenance/page/`, data from
`api/dashboard.py`.

- `director-maintenance-dashboard` — KPI cards, Property Health table
  (`health = max(0, 100 − points×2)`), and a real-time toast bound to the
  `hotel_new_negative_review` event (published from `NegativeReview.after_insert`).
- `gm-maintenance-dashboard` — per-GM open issues, overdue work orders, negative
  points and escalation warnings.

---

## Task 4 — Scheduled job
`hotel_maintenance/tasks.py :: auto_escalate_overdue_work_orders`, registered in
`hooks.py` under `scheduler_events["cron"]["0 9 * * *"]`.

Tiers: 1–2d → assigned user (Reminder), 3–5d → department head (Escalated),
6+d → GM + auto Negative Review (Critical). Creates an **Overdue Alert** with a
notified-recipients child table; suppresses duplicate alerts per work order per
day.

---

## Task 5 — Permissions
`setup/install.py` (run via `after_install` + `after_migrate` hooks) creates the
five roles and applies a declarative permission matrix idempotently — the
"migration script" option from the brief.

Row-level rule for *Maintenance Employee* (assigned-to-self only) lives in
`permissions.py` and is wired via `permission_query_conditions` +
`has_permission` in `hooks.py`.

---

## Task 6 — Resolution time
`doctype/maintenance_work_order/maintenance_work_order.py ::
calculate_issue_resolution_time`, triggered from `on_update` when a Work Order
becomes *Verified*. Stores `resolution_hours` on the Issue and auto-creates an
SLA-breach Negative Review (Critical >24h, High >48h, Medium >5d, Low >7d).

---

## Task 7 — Reports
Script Reports under `hotel_maintenance/report/` (each with `.json`, `.py`,
`.js` filters). Script/Query reports expose Excel/PDF/CSV export natively:
`GM Performance Summary`, `Asset Failure Analysis`, `Overdue Work Order Summary`.

---

## Task 8 — Refactor
`api/work_order.py :: update_overdue_status`. The original did per-row
`get_doc`, committed inside loops, compared dates as strings, and blindly
flagged every open issue. The refactor uses set-based bulk updates, a single
commit, and correctly sets **and clears** `has_overdue_work_order`.

---

## Verification

An end-to-end smoke test exercised all eight tasks against the live site
(21/21 checks passing): master creation & fetch fields, submittable issue,
completion validation, closure constraint (pending vs. done), resolution-time +
SLA review, points & escalation thresholds, the daily job, the refactor, all
three reports, and both dashboards.

```bash
bench --site hotel.local migrate          # installs schema + roles + perms
bench --site hotel.local list-apps        # hotel_maintenance present
```
