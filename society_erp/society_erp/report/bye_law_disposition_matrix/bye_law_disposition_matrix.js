// Copyright (c) 2026, Society ERP and contributors
// For license information, please see license.txt

frappe.query_reports["Bye-Law Disposition Matrix"] = {
	filters: [
		{
			fieldname: "consultation",
			label: __("Consultation"),
			fieldtype: "Link",
			options: "Bye-Law Consultation",
		},
		{
			fieldname: "chapter",
			label: __("Chapter"),
			fieldtype: "Data",
		},
		{
			fieldname: "comment_type",
			label: __("Comment Type"),
			fieldtype: "Select",
			options: "\nSuggestion\nObjection\nClarification\nSupport",
		},
		{
			fieldname: "disposition_status",
			label: __("Disposition Status"),
			fieldtype: "Select",
			options: "\nPending\nAccepted\nPartially Accepted\nRejected\nNoted",
		},
		{
			fieldname: "clause_disposition",
			label: __("Clause Disposition"),
			fieldtype: "Select",
			options: "\nPending\nUncontested\nModified\nContested - Poll Required\nLocked",
		},
		{
			fieldname: "only_visible",
			label: __("Only Visible"),
			fieldtype: "Check",
			default: 1,
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "disposition_status" && data && data.disposition_status) {
			const colors = {
				"Accepted": "green",
				"Partially Accepted": "blue",
				"Rejected": "red",
				"Pending": "orange",
				"Noted": "gray",
			};
			const color = colors[data.disposition_status] || "gray";
			value = `<span class="indicator-pill ${color}">${frappe.utils.escape_html(data.disposition_status)}</span>`;
		}
		return value;
	},
};
