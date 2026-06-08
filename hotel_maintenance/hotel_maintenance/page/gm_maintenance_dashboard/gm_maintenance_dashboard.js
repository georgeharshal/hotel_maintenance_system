// Copyright (c) 2026, Harshal and contributors
// For license information, please see license.txt

frappe.pages["gm-maintenance-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("GM Maintenance Dashboard"),
		single_column: true,
	});

	const dashboard = new GMMaintenanceDashboard(page);

	// Allow a Director / SGM to inspect a specific GM's view.
	const gm_field = page.add_field({
		fieldname: "gm",
		label: __("General Manager"),
		fieldtype: "Link",
		options: "User",
		change() {
			dashboard.gm = gm_field.get_value();
			dashboard.refresh();
		},
	});

	dashboard.refresh();
	page.set_primary_action(__("Refresh"), () => dashboard.refresh(), "refresh");
};

class GMMaintenanceDashboard {
	constructor(page) {
		this.page = page;
		this.gm = null;
		this.body = $('<div class="gm-dashboard p-3"></div>').appendTo(page.main);
	}

	refresh() {
		frappe.call({
			method: "hotel_maintenance.api.dashboard.get_gm_dashboard_data",
			args: { gm: this.gm || undefined },
			freeze: true,
			callback: (r) => {
				if (r.message) {
					this.render(r.message);
				}
			},
		});
	}

	render(data) {
		this.body.empty();

		const cards = [
			{ label: __("Open Issues"), value: data.open_issues, color: "blue" },
			{ label: __("Overdue Work Orders"), value: data.overdue_work_orders, color: "orange" },
			{ label: __("Negative Points (30d)"), value: data.negative_points, color: "red" },
		];
		const row = $('<div class="row"></div>').appendTo(this.body);
		cards.forEach((c) => {
			$(`
				<div class="col-sm-4 mb-3">
					<div class="card h-100" style="border-left: 4px solid var(--${c.color}-500, #5e64ff);">
						<div class="card-body">
							<div class="text-muted small">${frappe.utils.escape_html(c.label)}</div>
							<div style="font-size: 28px; font-weight: 700;">${c.value}</div>
						</div>
					</div>
				</div>
			`).appendTo(row);
		});

		this.render_escalations(data.escalation_warnings);
		this.render_open_issues(data.open_issue_list);
		this.render_overdue(data.overdue_work_order_list);
	}

	render_escalations(warnings) {
		const section = $('<div class="mt-3"></div>').appendTo(this.body);
		$(`<h5>${__("Escalation Warnings")}</h5>`).appendTo(section);
		if (!warnings || !warnings.length) {
			$(`<div class="text-muted">${__("No active escalations.")}</div>`).appendTo(section);
			return;
		}
		warnings.forEach((w) => {
			$(`<span class="indicator-pill red mr-2">${frappe.utils.escape_html(w.level)} (${w.threshold_points} pts)</span>`).appendTo(section);
		});
	}

	render_open_issues(issues) {
		const section = $('<div class="mt-4"></div>').appendTo(this.body);
		$(`<h5>${__("Open Issues")}</h5>`).appendTo(section);
		if (!issues || !issues.length) {
			$(`<div class="text-muted">${__("No open issues.")}</div>`).appendTo(section);
			return;
		}
		const table = $(`
			<table class="table table-bordered">
				<thead><tr>
					<th>${__("Issue")}</th><th>${__("Property")}</th><th>${__("Room")}</th>
					<th>${__("Priority")}</th><th>${__("Status")}</th>
				</tr></thead>
				<tbody></tbody>
			</table>
		`).appendTo(section);
		const tbody = table.find("tbody");
		issues.forEach((i) => {
			$(`<tr>
				<td><a href="/app/maintenance-issue/${encodeURIComponent(i.name)}">${frappe.utils.escape_html(i.name)}</a></td>
				<td>${frappe.utils.escape_html(i.property || "-")}</td>
				<td>${frappe.utils.escape_html(i.room || "-")}</td>
				<td>${frappe.utils.escape_html(i.priority || "-")}</td>
				<td>${frappe.utils.escape_html(i.status || "-")}</td>
			</tr>`).appendTo(tbody);
		});
	}

	render_overdue(orders) {
		const section = $('<div class="mt-4"></div>').appendTo(this.body);
		$(`<h5>${__("Overdue Work Orders")}</h5>`).appendTo(section);
		if (!orders || !orders.length) {
			$(`<div class="text-muted">${__("No overdue work orders.")}</div>`).appendTo(section);
			return;
		}
		const table = $(`
			<table class="table table-bordered">
				<thead><tr>
					<th>${__("Work Order")}</th><th>${__("Property")}</th>
					<th>${__("Assigned To")}</th><th>${__("Due Date")}</th><th>${__("Status")}</th>
				</tr></thead>
				<tbody></tbody>
			</table>
		`).appendTo(section);
		const tbody = table.find("tbody");
		orders.forEach((o) => {
			$(`<tr>
				<td><a href="/app/maintenance-work-order/${encodeURIComponent(o.name)}">${frappe.utils.escape_html(o.name)}</a></td>
				<td>${frappe.utils.escape_html(o.property || "-")}</td>
				<td>${frappe.utils.escape_html(o.assigned_to || "-")}</td>
				<td>${frappe.datetime.str_to_user(o.due_date) || "-"}</td>
				<td>${frappe.utils.escape_html(o.status || "-")}</td>
			</tr>`).appendTo(tbody);
		});
	}
}
