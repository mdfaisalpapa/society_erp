/**
 * Society Financials - Resident Portal
 * Interactive frontend viewer for Profit & Loss Statement and Balance Sheet.
 */

frappe.ready(function () {
    initFinancialReport();
});

function initFinancialReport() {
    const $btnGenerate = $("#btn-generate-report");
    const $form = $("#financial-report-form");

    // 1. Bind Click & Submit Handlers
    $btnGenerate.on("click", function (e) {
        e.preventDefault();
        loadFinancialReport();
    });

    $form.on("change", "select, input", function () {
        // Quick update of title badge when report dropdown changes
        updateReportMetaPreview();
    });

    // 2. Auto-load default report on page arrival
    loadFinancialReport();
}

/**
 * Updates header badges dynamically based on user selections
 */
function updateReportMetaPreview() {
    const reportName = $("#report_name").val();
    const costCenterText = $("#cost_center option:selected").text().trim();
    const fromDate = $("#from_date").val();
    const toDate = $("#to_date").val();

    $("#display-report-title").text(
        reportName === "Profit and Loss Statement"
            ? "Profit & Loss Statement"
            : "Balance Sheet"
    );

    $("#display-cost-center-badge").text(
        $("#cost_center").val() ? costCenterText : "All Cost Centers"
    );

    if (fromDate && toDate) {
        $("#display-date-range").text(`From ${fromDate} To ${toDate}`);
    }
}

/**
 * Invokes the whitelisted Python backend to run the native ERPNext report
 */
function loadFinancialReport() {
    const reportName = $("#report_name").val();
    const fromDate = $("#from_date").val();
    const toDate = $("#to_date").val();
    const costCenter = $("#cost_center").val();
    const company = $("#company").val();

    updateReportMetaPreview();

    // Show Loading Skeleton & Disable Button
    setLoadingState(true);

    frappe.call({
        method: "society_erp.www.resident.financials.index.get_financial_report",
        args: {
            report_name: reportName,
            from_date: fromDate,
            to_date: toDate,
            cost_center: costCenter || null,
            company: company || null,
            periodicity: "Yearly"
        },
        callback: function (r) {
            setLoadingState(false);
            if (r.message) {
                renderReportTable(r.message);
            } else {
                showEmptyState(true);
            }
        },
        error: function (err) {
            setLoadingState(false);
            showErrorState(err);
        }
    });
}

/**
 * Parses ERPNext query_report columns and result rows to render the dynamic HTML table
 */
function renderReportTable(data) {
    const columns = data.columns || [];
    const rows = data.result || [];
    const currency = data.currency || "INR";

    const $tableWrapper = $("#report-table-wrapper");
    const $headerRow = $("#report-table-header tr");
    const $tbody = $("#report-table-body");
    const $emptyState = $("#report-empty-state");

    // Filter out hidden columns
    const visibleCols = columns.filter((col) => !col.hidden);

    if (!visibleCols.length || !rows.length) {
        $tableWrapper.addClass("d-none");
        $emptyState.removeClass("d-none");
        return;
    }

    $emptyState.addClass("d-none");
    $tableWrapper.removeClass("d-none");

    // 1. Build Table Headers
    $headerRow.empty();
    visibleCols.forEach((col, idx) => {
        const isNumeric = col.fieldtype === "Currency" || col.fieldtype === "Float" || idx > 0;
        const alignClass = isNumeric ? "text-right" : "text-left";
        const colLabel = col.label || col.fieldname;
        $headerRow.append(
            `<th scope="col" class="${alignClass} border-top-0">${frappe.utils.escape_html(colLabel)}</th>`
        );
    });

    // 2. Build Table Body Rows
    $tbody.empty();

    rows.forEach((row) => {
        // Handle Empty Spacer Rows
        const isSpacer = !row || (!row.account && !row.account_name && row.total == null);
        if (isSpacer) {
            $tbody.append(
                `<tr class="row-spacer"><td colspan="${visibleCols.length}"></td></tr>`
            );
            return;
        }

        // Determine Row Semantic Classes
        const rawAccount = String(row.account || row.account_name || "").trim();
        const isTotalRow =
            (rawAccount.startsWith("'") && rawAccount.endsWith("'")) ||
            rawAccount.toLowerCase().startsWith("total ") ||
            rawAccount.toLowerCase().includes("profit for the year") ||
            rawAccount.toLowerCase().includes("provisional profit");

        const isGroupRow = !isTotalRow && (row.is_group === 1 || row.is_group === true);
        const indentLevel = Math.max(0, parseInt(row.indent) || 0);

        let rowClass = "";
        if (isTotalRow) {
            rowClass = "row-total";
        } else if (isGroupRow) {
            rowClass = "row-group";
        }

        // Strip surrounding single quotes ERPNext uses for calculated totals
        const cleanAccountLabel = rawAccount.replace(/^['"]|['"]$/g, "");

        let trHtml = `<tr class="${rowClass}">`;

        visibleCols.forEach((col, idx) => {
            const fieldname = col.fieldname;
            const val = row[fieldname];
            const isNumeric = col.fieldtype === "Currency" || col.fieldtype === "Float" || idx > 0;

            if (idx === 0) {
                // Primary Account Column with Indentation
                const indentPadding = isTotalRow ? 14 : 14 + indentLevel * 22;
                const icon = isTotalRow
                    ? "📌"
                    : isGroupRow
                    ? "📁"
                    : "•";

                trHtml += `
                    <td class="text-left font-weight-${isTotalRow || isGroupRow ? "bold" : "normal"}" style="padding-left: ${indentPadding}px;">
                        <span class="mr-2 text-muted" style="font-size: 0.85rem;">${icon}</span>
                        <span>${frappe.utils.escape_html(cleanAccountLabel)}</span>
                    </td>
                `;
            } else {
                // Numeric / Value Columns
                const formattedNumber = formatFinancialAmount(val, currency);
                const isNegative = typeof val === "number" && val < 0;
                const textClass = isNegative ? "text-danger" : "";
                const weightClass = isTotalRow || isGroupRow ? "font-weight-bold" : "";

                trHtml += `
                    <td class="text-right ${textClass} ${weightClass}">
                        ${formattedNumber}
                    </td>
                `;
            }
        });

        trHtml += "</tr>";
        $tbody.append(trHtml);
    });
}

/**
 * Formats numeric values with currency symbols and standard comma grouping
 */
function formatFinancialAmount(val, currency) {
    if (val == null || val === "") {
        return "-";
    }

    const num = parseFloat(val);
    if (isNaN(num)) {
        return frappe.utils.escape_html(String(val));
    }

    // Format with 2 decimal places & standard local commas
    const absFormatted = Math.abs(num).toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });

    const symbol = currency === "INR" ? "₹" : currency ? `${currency} ` : "";

    if (num < 0) {
        return `(${symbol}${absFormatted})`;
    } else if (num === 0) {
        return `${symbol}0.00`;
    } else {
        return `${symbol}${absFormatted}`;
    }
}

/**
 * Toggles skeleton UI while querying the backend
 */
function setLoadingState(isLoading) {
    const $spinner = $("#report-spinner");
    const $skeleton = $("#report-skeleton");
    const $tableWrapper = $("#report-table-wrapper");
    const $emptyState = $("#report-empty-state");
    const $btn = $("#btn-generate-report");

    if (isLoading) {
        $btn.prop("disabled", true);
        $spinner.removeClass("d-none");
        $skeleton.removeClass("d-none");
        $tableWrapper.addClass("d-none");
        $emptyState.addClass("d-none");
    } else {
        $btn.prop("disabled", false);
        $spinner.addClass("d-none");
        $skeleton.addClass("d-none");
    }
}

function showEmptyState(show) {
    if (show) {
        $("#report-table-wrapper").addClass("d-none");
        $("#report-empty-state").removeClass("d-none");
    } else {
        $("#report-empty-state").addClass("d-none");
    }
}

function showErrorState(err) {
    $("#report-table-wrapper").addClass("d-none");
    $("#report-empty-state")
        .removeClass("d-none")
        .html(`
            <div class="alert alert-danger mx-4 my-4 text-left">
                <h6 class="font-weight-bold mb-1">Failed to load report</h6>
                <p class="small mb-0">${frappe.utils.escape_html(err.message || "An unexpected error occurred while generating the financial statement.")}</p>
            </div>
        `);
}
