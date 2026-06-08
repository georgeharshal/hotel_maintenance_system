// Copyright (c) 2026, Harshal and contributors
// For license information, please see license.txt

frappe.query_reports["Overdue Work Order Summary"] = {
	filters: [
		{
			fieldname: "property",
			label: __("Property"),
			fieldtype: "Link",
			options: "Property",
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Select",
			options: ["", "Engineering", "Housekeeping", "Electrical", "Plumbing", "HVAC", "IT", "General"].join("\n"),
		},
	],
};
