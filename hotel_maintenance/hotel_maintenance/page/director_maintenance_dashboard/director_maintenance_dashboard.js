// Copyright (c) 2026, Harshal and contributors
// For license information, please see license.txt

frappe.pages["director-maintenance-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Director Maintenance Dashboard"),
		single_column: true,
	});

	const dashboard = new DirectorMaintenanceDashboard(page);
	dashboard.refresh();

	page.set_primary_action(__("Refresh"), () => dashboard.refresh(), "refresh");

	// Task 3.1 - real-time toast notification on every new Negative Review.
	frappe.realtime.on("hotel_new_negative_review", (data) => {
		frappe.show_alert(
			{
				message: __("New Negative Review {0} for {1} (severity: {2}, {3} pts)", [
					data.name,
					data.property || "-",
					data.severity,
					data.points,
				]),
				indicator: "red",
			},
			10
		);
		dashboard.refresh();
	});
};

class DirectorMaintenanceDashboard {
	constructor(page) {
		this.page = page;
		this.body = $('<div class="director-dashboard p-3"></div>').appendTo(page.main);
	}

	refresh() {
		frappe.call({
			method: "hotel_maintenance.api.dashboard.get_director_dashboard_data",
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
		this.render_kpi_cards(data.kpi);
		this.render_property_health(data.property_health);
	}

	render_kpi_cards(kpi) {
		const cards = [
			{ label: __("Open Issues Today"), value: kpi.open_issues_today, color: "blue" },
			{ label: __("Overdue Work Orders"), value: kpi.overdue_work_orders, color: "orange" },
			{ label: __("Negative Reviews (7d)"), value: kpi.negative_reviews_7days, color: "red" },
			{ label: __("Avg Resolution (hrs)"), value: kpi.avg_resolution_time, color: "green" },
		];

		const row = $('<div class="row"></div>').appendTo(this.body);
		cards.forEach((c) => {
			$(`
				<div class="col-sm-3 mb-3">
					<div class="card h-100" style="border-left: 4px solid var(--${c.color}-500, #5e64ff);">
						<div class="card-body">
							<div class="text-muted small">${frappe.utils.escape_html(c.label)}</div>
							<div style="font-size: 28px; font-weight: 700;">${c.value}</div>
						</div>
					</div>
				</div>
			`).appendTo(row);
		});
	}

	render_property_health(rows) {
		const section = $('<div class="mt-4"></div>').appendTo(this.body);
		$(`<h5>${__("Property Health")}</h5>`).appendTo(section);

		if (!rows || !rows.length) {
			$(`<div class="text-muted">${__("No properties found.")}</div>`).appendTo(section);
			return;
		}

		const table = $(`
			<table class="table table-bordered">
				<thead>
					<tr>
						<th>${__("Property")}</th>
						<th>${__("GM")}</th>
						<th class="text-right">${__("Open Issues")}</th>
						<th class="text-right">${__("Completed (30d)")}</th>
						<th class="text-right">${__("Negative Points (30d)")}</th>
						<th class="text-right">${__("Health Score")}</th>
					</tr>
				</thead>
				<tbody></tbody>
			</table>
		`).appendTo(section);

		const tbody = table.find("tbody");
		rows.forEach((r) => {
			const color = r.health_score >= 80 ? "green" : r.health_score >= 50 ? "orange" : "red";
			$(`
				<tr>
					<td>${frappe.utils.escape_html(r.property)}</td>
					<td>${frappe.utils.escape_html(r.gm || "-")}</td>
					<td class="text-right">${r.open_issues}</td>
					<td class="text-right">${r.completed_issues}</td>
					<td class="text-right">${r.negative_points}</td>
					<td class="text-right"><span class="indicator-pill ${color}">${r.health_score}</span></td>
				</tr>
			`).appendTo(tbody);
		});
	}
}
