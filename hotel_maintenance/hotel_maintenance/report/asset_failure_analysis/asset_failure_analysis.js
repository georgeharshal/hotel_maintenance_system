// Copyright (c) 2026, Harshal and contributors
// For license information, please see license.txt

frappe.query_reports["Asset Failure Analysis"] = {
	filters: [
		{
			fieldname: "category",
			label: __("Category"),
			fieldtype: "Select",
			options: ["", "HVAC", "Plumbing", "Electrical", "Furniture", "Electronics", "Appliance", "Safety Equipment", "Other"].join("\n"),
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
	],
};
