# Hotel Maintenance Management System

A Frappe v16 application that manages the full hotel maintenance lifecycle —
properties, buildings, rooms and assets; maintenance issues and work orders;
GM negative-review scoring with automatic escalation; overdue-work-order
escalation; role-based access; custom dashboards and analytical reports.

---

## Table of Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Default Roles & Passwords](#default-roles--passwords)
4. [DocTypes](#doctypes)
5. [Business Logic](#business-logic)
6. [Dashboards](#dashboards)
7. [Scheduled Job](#scheduled-job)
8. [Reports](#reports)
9. [API / Whitelisted Methods](#api--whitelisted-methods)
10. [Project Structure](#project-structure)

---

## Installation

Prerequisites: a working Frappe bench (v15/v16), MariaDB and Redis.

```bash
# 1. From your bench directory, fetch the app
bench get-app hotel_maintenance https://github.com/<your-org>/hotel_maintenance_system.git

# 2. Install it onto a site
bench --site <your-site> install-app hotel_maintenance

# 3. Apply schema + run setup hooks (roles & permissions)
bench --site <your-site> migrate

# 4. (Production) build assets
bench build --app hotel_maintenance
```

The app installs without errors via `bench get-app` and `bench install-app`.
The custom **roles**, **role profiles** and **DocType permissions** are shipped
as **fixtures** (`hotel_maintenance/fixtures/`, filtered to only this app's
records) and imported automatically on install/migrate. The `after_install` /
`after_migrate` hooks additionally create the roles/role profiles and the
role-based workspaces idempotently. The permission matrix lives, fully readable,
in `setup/install.py` (`apply_permissions()`), which can be run manually to
re-seed permissions on a site without fixtures. To re-export the fixtures after
a change:

```bash
bench --site <your-site> export-fixtures --app hotel_maintenance
```

To enable the scheduled job in development:

```bash
bench --site <your-site> enable-scheduler
```

---

## Configuration

| Item                | Value / Location |
|---------------------|------------------|
| App name            | `hotel_maintenance` |
| Module              | `Hotel Maintenance` |
| Scheduled job       | `auto_escalate_overdue_work_orders` — daily at **09:00** (cron `0 9 * * *`) |
| Naming series       | Issues `ISS-.YYYY.-`, Work Orders `WO-.YYYY.-`, Negative Reviews `NR-.YYYY.-`, Overdue Alerts `OA-.YYYY.-` |
| Real-time event     | `hotel_new_negative_review` (drives the Director toast) |

### First-time data setup

1. Create one or more **Property** records and set the **GM (User)** for each.
2. Add **Building**, **Room** and **Room Asset** records under each property.
3. Assign the relevant role (see below) to each user via *User → Roles*.

---

## Default Roles & Passwords

This app does **not** create login users or set passwords (that would be a
security risk in a shared repo). It creates the following **roles** and their
permissions automatically on install/migrate:

| Role | Key Permissions |
|------|-----------------|
| **Hotel GM** | Issue (Create/Read/Update + Submit/Cancel), Work Order (CRU), Room (CRU), Room Asset (RU), Property/Building (R), Negative Review (R), GM Dashboard (R) |
| **Senior General Manager** | Issue (RU), Work Order (RU), Negative Review (RU), all masters/dashboards (R) |
| **Director** | All DocTypes (R), Negative Review (Create + Update), Director Dashboard (RW), Reports (R + Export) |
| **Maintenance Employee** | Work Order (R + update status) — **only work orders assigned to self**, no create/delete (enforced row-level) |
| **Inspection Team** | Negative Review (RUC), Issue (R), Rooms/Assets (R) |

The default administrator account is the standard Frappe `Administrator`, whose
password is whatever was set when the site was created
(`bench new-site` → *administrator password*). To create role users:

```bash
bench --site <your-site> add-user gm@example.com --first-name "Hotel GM" --add-role "Hotel GM"
```

### Demo / Backup Login Credentials

The accompanying site backup is pre-seeded (via
`hotel_maintenance.demo.seed.create_demo_data`) with the following demo users.
**All demo users share the password `Hotel@12345`.** Use these to explore the
role-specific workspaces, dashboards and data isolation.

| Username (login email) | Password | Role | Notes |
|------------------------|----------|------|-------|
| `director@hotel.test` | `Hotel@12345` | Director | Full overview, all properties + reports |
| `sgm@hotel.test` | `Hotel@12345` | Senior General Manager | Oversees all properties |
| `gm.grand@hotel.test` | `Hotel@12345` | Hotel GM | Manages **Grand Plaza Hotel** (sees only its data) |
| `gm.bay@hotel.test` | `Hotel@12345` | Hotel GM | Manages **Bayview Resort** (sees only its data) |
| `tech1@hotel.test` | `Hotel@12345` | Maintenance Employee | Sees only work orders assigned to self |
| `tech2@hotel.test` | `Hotel@12345` | Maintenance Employee | Sees only work orders assigned to self |
| `inspector@hotel.test` | `Hotel@12345` | Inspection Team | Logs negative reviews; restricted module access |
| `Administrator` | *(set at `bench new-site`)* | System Manager | Full system access |

> ⚠️ These are **demo credentials for the reference backup only**. Change or
> remove them before any production use. The demo data (and these users) can be
> regenerated with `bench --site <site> execute
> hotel_maintenance.demo.seed.create_demo_data` or removed with
> `...seed.clear_demo_data`.

---

## Role-based Desk & Data Isolation

Each role gets its **own workspace** (sidebar entry + icon), its **own number
cards/charts**, and only the **data it is concerned with**.

**Workspaces** (created idempotently by `setup/workspaces.py` on install/migrate;
each restricted via its `roles`):

| Workspace | Role | Highlights |
|-----------|------|------------|
| Maintenance Director | Director | 4 KPI number cards, 3 charts, Director Dashboard + all reports, all records |
| Senior Manager Maintenance | Senior General Manager | KPI cards, status charts, reports |
| Hotel GM Workspace | Hotel GM | scoped KPI cards, GM Dashboard, own-property records |
| Maintenance Tasks | Maintenance Employee | open/completed work-order cards, assigned work orders |
| Inspection | Inspection Team | issue/review cards, Negative Reviews |

**Row-level data access** (`hotel_maintenance/permissions.py`,
`permission_query_conditions` + `has_permission`):

- **Hotel GM** sees only records of the properties they manage
  (`Property.gm == user`) across Property/Building/Room/Asset/Issue/Work
  Order/Negative Review — so their number cards and lists are auto-scoped.
- **Maintenance Employee** sees only Work Orders assigned to themselves.
- **Director / Senior General Manager / System Manager** are unrestricted.

**Module isolation** — a `Module Profile` ("Hotel Maintenance Limited") blocks
every module except *Hotel Maintenance*; it is assigned to limited roles (GM,
Maintenance Employee, Inspection Team) so their desk is focused and they no
longer see Build/Users/Website/Integrations. Supervisory roles keep full
access. (Assigned to the demo users automatically by the seed script.)

---

## DocTypes

| DocType | Notes |
|---------|-------|
| **Property** | name, GM (User), location, status |
| **Building** | code, name, Property, floors, status |
| **Room** | number, Property, Building, floor, type, status (auto-named `{building}-{number}`) |
| **Room Asset** | name, category, Room, Building (fetched), Property (fetched), serial number, install date, status |
| **Maintenance Issue** | naming series, Property/Building/Room/Asset, priority, status, raised by/date, description, photo, resolution hours (RO), has-overdue flag. **Submittable.** |
| **Maintenance Work Order** | naming series, Issue, department, assigned to, location (fetched), due/completion date, status, work description, completion remarks/photo |
| **Negative Review** | naming series, Issue, Property, GM (fetched), severity, points (RO), review date, remarks, escalation child table |
| **Escalation Entry** | *(child of Negative Review)* level, threshold points, escalated on, notified to |
| **Overdue Alert** | naming series, Work Order, Property/assignee (fetched), overdue days, severity, notified-roles child table |
| **Overdue Alert Recipient** | *(child of Overdue Alert)* role, notified user, notified on |

All link fields carry a database index (`search_index`) per the requirements.

---

## Business Logic

- **Points calculation** (`Negative Review`): Minor = 1, Major = 3, Critical = 5.
- **Escalation trigger** (`Negative Review`): on save, sums the GM's points over
  the last 30 days and appends escalation entries at thresholds
  **10 → Warning, 20 → SGM Review, 30 → Director Escalation, 50 → Management
  Action**. Duplicate levels (already recorded for the GM in the window) are
  skipped; datetime and notified user are auto-populated.
- **Work Order completion** (`Maintenance Work Order`): marking *Completed*
  requires the completion photo **and** remarks, and auto-stamps the completion
  datetime.
- **Issue closure constraint** (`Maintenance Issue`): an Issue can move to
  *Verified*/*Closed* only after it has been *Completed* and every linked Work
  Order is *Completed*/*Verified*/*Closed*. Enforced in both `validate` and
  `before_update_after_submit` (because the DocType is submittable).
- **Resolution time** (`calculate_issue_resolution_time`): when a Work Order is
  *Verified*, the resolution hours (completion − raised) are stored on the
  Issue, and an SLA-breach Negative Review is auto-created when the
  priority-based threshold is exceeded (Critical > 24h → Critical, High > 48h →
  Major, Medium > 5d / Low > 7d → Minor).

---

## Dashboards

- **Director Dashboard** — route `director-maintenance-dashboard`. KPI cards
  (open issues today, overdue work orders, negative reviews in 7 days, average
  resolution time), a Property Health table (health score = `max(0, 100 −
  points×2)`), and a **real-time toast** on every new Negative Review.
- **GM Dashboard** — route `gm-maintenance-dashboard`. Open issues, overdue
  work orders and total negative points + escalation warnings for the logged-in
  GM (Directors/SGMs can inspect a specific GM via the filter).

---

## Scheduled Job

`auto_escalate_overdue_work_orders` (daily 09:00) finds overdue work orders
(due date < today, not Completed/Verified/Closed/Cancelled) and creates an
**Overdue Alert** per order, escalating by age:

| Overdue | Severity | Action |
|---------|----------|--------|
| 1–2 days | Reminder | notify assigned user |
| 3–5 days | Escalated | notify department head |
| 6+ days  | Critical | notify GM **and** auto-create a Negative Review |

Duplicate alerts for the same work order on the same day are suppressed.

---

## Reports

All three are Script Reports with filters and full **Excel / PDF / CSV** export:

1. **GM Performance Summary** — per GM/Property: total & closed issues, closure
   rate, avg resolution hours, negative points, escalation count, ranking.
2. **Asset Failure Analysis** — per asset: issue count, avg days between
   failures, most common problem, properties affected.
3. **Overdue Work Order Summary** — Property, department, assignee, WO number,
   due date, overdue days, status, days since last update.

---

## API / Whitelisted Methods

| Method | Purpose |
|--------|---------|
| `hotel_maintenance.api.work_order.update_overdue_status` | Bulk-mark overdue work orders and sync the issue flag (Task 8 refactor). |
| `hotel_maintenance.api.dashboard.get_director_dashboard_data` | Director KPIs + property health. |
| `hotel_maintenance.api.dashboard.get_gm_dashboard_data` | GM dashboard data. |

---

## Project Structure

```
hotel_maintenance/
├── hooks.py                       # events, scheduler, permissions wiring
├── permissions.py                 # row-level access (Maintenance Employee)
├── utils.py                       # shared helpers (role/user resolution, notify)
├── api/
│   ├── dashboard.py               # dashboard data providers
│   └── work_order.py              # refactored update_overdue_status (Task 8)
├── setup/
│   └── install.py                 # roles & permission matrix (Task 5)
└── hotel_maintenance/
    ├── tasks.py                   # scheduled job (Task 4)
    ├── doctype/                   # 10 DocTypes (JSON + controllers)
    ├── page/                      # director & GM dashboards (Task 3)
    └── report/                    # 3 script reports (Task 7)
```

## Contributing

This app uses `pre-commit` for code formatting and linting (ruff, eslint,
prettier, pyupgrade):

```bash
cd apps/hotel_maintenance
pre-commit install
```

## License

MIT
