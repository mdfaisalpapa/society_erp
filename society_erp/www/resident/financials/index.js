/**
 * Society Financials & Procurement - Resident Portal
 * Interactive frontend viewer for:
 * 1. Profit & Loss Statement & Balance Sheet
 * 2. Purchase Invoices (Detailed Item & Tax View)
 * 3. Maintenance Bills & Transparency:
 *    - Financial Year filtering on billing run list
 *    - "View Considered Invoices" Modal: Date, Invoice ID, Supplier Name, Grand Total
 *    - Refined "View Complete Society GL" Modal: 2-column Account-wise consolidation (Expense Account & Total Amount)
 *    - Compact Level 1 "Block & UDS Maintenance" Modal with clean, objective Single-Tier vs Two-Tier rates
 *    - Level 2 Drill-Down: Block Cost Center GL Breakdown
 */

frappe.ready(function () {
    initFinancialsPortal();
});

function initFinancialsPortal() {
    // 1. Initialize Bootstrap Tabs & Hash Navigation
    initTabsHandler();

    // 2. Initialize Financial Statements Report Engine
    initFinancialReport();

    // 3. Initialize Purchase Invoice Detail Modal Handler
    initPurchaseInvoiceDetailsHandler();

    // 4. Initialize Maintenance Module (FY filter, Considered Invoices, Consolidated Society GL, Multi-Level Drilldown)
    initMaintenanceModule();
}

/**
 * Initializes and manages Sticky iOS-Style Segmented Control & tab switching
 */
function initTabsHandler() {
    // Segmented control button click handler
    $(".segmented-btn").on("click", function (e) {
        e.preventDefault();
        const targetSelector = $(this).data("target");
        if (!targetSelector) return;

        // Update active state in segmented control
        $(".segmented-btn").removeClass("active");
        $(this).addClass("active");

        // Switch active tab pane
        $(".tab-pane").removeClass("show active");
        $(targetSelector).addClass("show active");

        // Sync with legacy bootstrap nav if present
        $(`#financialsTab a[href="${targetSelector}"]`).tab("show");

        // Update URL hash
        if (history.pushState) {
            history.pushState(null, null, targetSelector);
        } else {
            location.hash = targetSelector;
        }
    });

    // Hash-based initial tab activation
    const currentHash = window.location.hash;
    if (currentHash && $(`#financialsSegmentedControl .segmented-btn[data-target="${currentHash}"]`).length) {
        $(`#financialsSegmentedControl .segmented-btn[data-target="${currentHash}"]`).trigger("click");
    } else if (currentHash && $(`#financialsTab a[href="${currentHash}"]`).length) {
        $(`#financialsSegmentedControl .segmented-btn[data-target="${currentHash}"]`).trigger("click");
    }
}

/* ==========================================================================
   PART 1: Financial Reports Engine (P&L and Balance Sheet)
   ========================================================================== */

let reportDebounceTimer = null;

function initFinancialReport() {
    const $form = $("#financial-report-form");
    const $dateFilterType = $("#date_filter_type");

    populateYearDropdown();

    const currentMonth = new Date().getMonth();
    $("#select_month").val(currentMonth);

    // Toggle dynamic date controls and trigger debounced fetch
    $dateFilterType.on("change", function () {
        handleDateFilterToggle($(this).val());
        triggerAutoApplyReport(100);
    });

    // Auto-apply on dropdown selection change (immediate 100ms debounce)
    $form.on("change", "select", function () {
        triggerAutoApplyReport(100);
    });

    // Auto-apply on date picker input change (400ms debounce to prevent rapid consecutive requests)
    $form.on("input change", "input[type='date']", function () {
        triggerAutoApplyReport(400);
    });

    // Print handler: prints strictly the active Financial Statement report
    $("#btn-print-financial-report").on("click", function (e) {
        e.preventDefault();
        printActiveFinancialReport();
    });

    handleDateFilterToggle($dateFilterType.val());
    loadFinancialReport();
}

/**
 * Debounced trigger for auto-applying financial report filters
 */
function triggerAutoApplyReport(delayMs) {
    updateReportMetaPreview();
    if (reportDebounceTimer) {
        clearTimeout(reportDebounceTimer);
    }
    reportDebounceTimer = setTimeout(function () {
        loadFinancialReport();
    }, delayMs || 300);
}

function handleDateFilterToggle(filterType) {
    $(".date-filter-group").addClass("d-none");

    if (filterType === "financial_year") {
        $("#filter-group-fy").removeClass("d-none");
    } else if (filterType === "month_year") {
        $("#filter-group-month").removeClass("d-none");
    } else if (filterType === "custom_range") {
        $("#filter-group-custom").removeClass("d-none");
    }
}

function populateYearDropdown() {
    const $yearSelect = $("#select_year").empty();
    const currentYear = new Date().getFullYear();

    for (let yr = currentYear; yr >= currentYear - 4; yr--) {
        $yearSelect.append(new Option(yr, yr));
    }
}

function resolveActiveDateRange() {
    const filterType = $("#date_filter_type").val();
    let fromDate = null;
    let toDate = null;

    if (filterType === "financial_year") {
        const $selectedOption = $("#fiscal_year_select option:selected");
        fromDate = $selectedOption.data("start");
        toDate = $selectedOption.data("end");
    } else if (filterType === "month_year") {
        const month = parseInt($("#select_month").val(), 10);
        const year = parseInt($("#select_year").val(), 10);

        const startDate = new Date(year, month, 1);
        const endDate = new Date(year, month + 1, 0);

        fromDate = formatDateYMD(startDate);
        toDate = formatDateYMD(endDate);
    } else if (filterType === "custom_range") {
        fromDate = $("#from_date").val();
        toDate = $("#to_date").val();
    }

    return { fromDate: fromDate, toDate: toDate };
}

function formatDateYMD(dateObj) {
    const y = dateObj.getFullYear();
    const m = String(dateObj.getMonth() + 1).padStart(2, "0");
    const d = String(dateObj.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
}

function updateReportMetaPreview() {
    const reportName = $("#report_name").val();
    const costCenter = $("#cost_center").val() || "All Cost Centers";
    const dates = resolveActiveDateRange();

    $("#report-title-display").text(reportName);
    $("#report-subtitle-display").text(
        `Cost Center: ${costCenter} • Period: ${dates.fromDate || "-"} to ${dates.toDate || "-"}`
    );
}

function loadFinancialReport() {
    const reportName = $("#report_name").val();
    const costCenter = $("#cost_center").val();
    const dates = resolveActiveDateRange();

    setLoadingState(true);
    updateReportMetaPreview();

    frappe.call({
        method: "society_erp.www.resident.financials.index.get_financial_report",
        args: {
            report_name: reportName,
            from_date: dates.fromDate,
            to_date: dates.toDate,
            cost_center: costCenter
        },
        callback: function (r) {
            setLoadingState(false);
            if (r.exc || !r.message) {
                showEmptyState(true);
                return;
            }
            renderFinancialTable(r.message);
        },
        error: function (err) {
            setLoadingState(false);
            showErrorState(err);
        }
    });
}

function renderFinancialTable(reportData) {
    const $thead = $("#report-header-row").empty();
    const $tbody = $("#report-body").empty();
    const $cardsWrapper = $("#report-cards-wrapper").empty();
    const columns = reportData.columns || [];
    const result = reportData.result || [];
    const currency = reportData.currency || "INR";

    $("#report-currency-badge").text(`Currency: ${currency}`);

    if (result.length === 0) {
        showEmptyState(true);
        return;
    }

    showEmptyState(false);
    // Ensure mutually exclusive responsive visibility: desktop table vs mobile cards
    $("#report-table-wrapper").removeClass("d-none").addClass("d-none d-md-block");
    $("#report-cards-wrapper").removeClass("d-none").addClass("d-block d-md-none");

    const activeCols = columns.filter(col => {
        const fieldname = typeof col === "object" ? col.fieldname : col;
        return !fieldname.startsWith("__");
    });

    // 1. Build Desktop Table Headers
    activeCols.forEach((col, idx) => {
        const label = typeof col === "object" ? (col.label || col.fieldname) : col;
        const alignClass = idx === 0 ? "text-left" : "text-right";
        $thead.append(`<th class="${alignClass}">${frappe.utils.escape_html(label)}</th>`);
    });

    // 2. Build Desktop Table Body & Mobile Accordion Cards
    let currentGroupId = null;
    let $currentGroupBody = null;
    let groupCounter = 0;

    result.forEach((row, rowIndex) => {
        const accountRaw = row.account_name || row.account || "";
        const cleanAccountName = accountRaw.replace(/^'+|'+$/g, "").trim();

        if (!cleanAccountName) {
            return; // Skip empty separator objects
        }

        const isGroupRow = row.is_group === 1 || row.is_group === true;
        const isTotalRow = cleanAccountName.toLowerCase().includes("total") ||
                           cleanAccountName.toLowerCase().includes("profit") ||
                           cleanAccountName.toLowerCase().includes("loss");
        const indentLevel = typeof row.indent === "number" ? row.indent : 0;

        // Determine desktop row class
        let rowClass = "";
        if (isTotalRow) {
            rowClass = "row-total";
        } else if (isGroupRow) {
            rowClass = "row-group";
        }

        // --- A. Render Desktop Table Row ---
        let trHtml = `<tr class="${rowClass}">`;
        activeCols.forEach((col, idx) => {
            const fieldname = typeof col === "object" ? col.fieldname : col;
            const val = row[fieldname];

            if (idx === 0) {
                const paddingPx = Math.min(indentLevel * 22, 100);
                const icon = isGroupRow ? "📁 " : "";

                trHtml += `
                    <td class="text-left font-weight-${isGroupRow || isTotalRow ? 'bold' : 'normal'}" style="padding-left: ${paddingPx + 12}px;">
                        ${icon}${frappe.utils.escape_html(cleanAccountName)}
                    </td>
                `;
            } else {
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

        // --- B. Render Mobile Card-Based Ledgers (Vertical Stack & Accordion Groups) ---
        // Get the primary amount for mobile card (use total or first value column)
        const primaryValField = activeCols.length > 1 ? (typeof activeCols[activeCols.length - 1] === "object" ? activeCols[activeCols.length - 1].fieldname : activeCols[activeCols.length - 1]) : "total";
        const mobileVal = row.total !== undefined ? row.total : row[primaryValField];
        const formattedAmount = formatFinancialAmount(mobileVal, currency);
        const isNegativeVal = typeof mobileVal === "number" && mobileVal < 0;
        const textClass = isNegativeVal ? "text-danger" : "text-dark";

        if (isTotalRow) {
            // Standalone Total / Net Profit / Loss Card
            const isProfit = cleanAccountName.toLowerCase().includes("profit");
            const isLoss = cleanAccountName.toLowerCase().includes("loss");
            let cardClass = "ledger-total-card";
            if (isProfit) cardClass = "ledger-net-profit-card";
            else if (isLoss) cardClass = "ledger-net-loss-card";

            $cardsWrapper.append(`
                <div class="${cardClass}">
                    <div class="d-flex align-items-center">
                        <span class="mr-2">${isProfit ? '📈' : isLoss ? '📉' : '📊'}</span>
                        <span class="text-uppercase" style="font-size: 0.85rem; letter-spacing: 0.3px;">${frappe.utils.escape_html(cleanAccountName)}</span>
                    </div>
                    <div class="h6 mb-0 font-weight-bold ${textClass}">
                        ${formattedAmount}
                    </div>
                </div>
            `);
            // Reset current group so subsequent items start fresh
            currentGroupId = null;
            $currentGroupBody = null;
        } else if (isGroupRow && indentLevel === 0) {
            // Top-Level Parent Account Group (Accordion Card Header)
            groupCounter++;
            currentGroupId = `ledger-group-collapse-${groupCounter}`;

            const $groupItem = $(`
                <div class="ledger-group-item">
                    <div class="ledger-group-header" data-toggle="collapse" data-target="#${currentGroupId}" aria-expanded="true" aria-controls="${currentGroupId}">
                        <div class="d-flex align-items-center">
                            <span class="group-toggle-icon">▼</span>
                            <span class="font-weight-bold text-dark" style="font-size: 0.9rem;">
                                📁 ${frappe.utils.escape_html(cleanAccountName)}
                            </span>
                        </div>
                        <div class="font-weight-bold ${textClass}" style="font-size: 0.9rem;">
                            ${formattedAmount}
                        </div>
                    </div>
                    <div id="${currentGroupId}" class="collapse show ledger-group-body">
                    </div>
                </div>
            `);

            $cardsWrapper.append($groupItem);
            $currentGroupBody = $groupItem.find(".ledger-group-body");
        } else if (isGroupRow && indentLevel > 0) {
            // Intermediate Sub-group Title
            const subGroupHtml = `
                <div class="ledger-subgroup-title d-flex justify-content-between align-items-center">
                    <span>📁 ${frappe.utils.escape_html(cleanAccountName)}</span>
                    <span class="${textClass}">${formattedAmount}</span>
                </div>
            `;
            if ($currentGroupBody) {
                $currentGroupBody.append(subGroupHtml);
            } else {
                $cardsWrapper.append(`<div class="p-1 mb-1">${subGroupHtml}</div>`);
            }
        } else {
            // Child Ledger Item Card
            const indentPadding = Math.max(0, (indentLevel - 1)) * 14;
            const hasOpening = row.opening_balance !== undefined && row.opening_balance !== null;
            const openingHtml = hasOpening ? `<div class="text-muted" style="font-size: 0.72rem;">Open: ${formatFinancialAmount(row.opening_balance, currency)}</div>` : '';
            const childCardHtml = `
                <div class="ledger-child-card" style="padding-left: ${indentPadding + 6}px;">
                    <div class="flex-grow-1 pr-2">
                        <div class="text-dark ${indentLevel === 1 ? 'font-weight-600' : ''}" style="font-size: 0.85rem; line-height: 1.3;">
                            ${indentLevel > 1 ? '<span class="text-muted mr-1">&bull;</span>' : ''}${frappe.utils.escape_html(cleanAccountName)}
                        </div>
                        ${row.acc_number ? `<small class="text-muted">#${frappe.utils.escape_html(row.acc_number)}</small>` : ''}
                    </div>
                    <div class="text-right flex-shrink-0 font-weight-bold ${textClass}" style="font-size: 0.88rem;">
                        <div>${formattedAmount}</div>
                        ${openingHtml}
                    </div>
                </div>
            `;

            if ($currentGroupBody) {
                $currentGroupBody.append(childCardHtml);
            } else {
                $cardsWrapper.append(`
                    <div class="card p-2 mb-2 bg-white border shadow-none">
                        ${childCardHtml}
                    </div>
                `);
            }
        }
    });

    // Bind accordion icon rotation listener
    $cardsWrapper.find('.ledger-group-header').off('click.toggleIcon').on('click.toggleIcon', function() {
        $(this).toggleClass('collapsed');
    });
}

function formatFinancialAmount(val, currency) {
    if (val == null || val === "") {
        return "-";
    }

    const num = parseFloat(val);
    if (isNaN(num)) {
        return frappe.utils.escape_html(String(val));
    }

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

function setLoadingState(isLoading) {
    const $spinner = $("#report-spinner");
    const $skeleton = $("#report-skeleton");
    const $tableWrapper = $("#report-table-wrapper");
    const $cardsWrapper = $("#report-cards-wrapper");
    const $emptyState = $("#report-empty-state");

    if (isLoading) {
        $spinner.removeClass("d-none");
        $skeleton.removeClass("d-none");
        $tableWrapper.addClass("d-none");
        $cardsWrapper.addClass("d-none");
        $emptyState.addClass("d-none");
    } else {
        $spinner.addClass("d-none");
        $skeleton.addClass("d-none");
    }
}

function showEmptyState(show) {
    if (show) {
        $("#report-table-wrapper").addClass("d-none");
        $("#report-cards-wrapper").addClass("d-none");
        $("#report-empty-state").removeClass("d-none");
    } else {
        $("#report-empty-state").addClass("d-none");
    }
}

function showErrorState(err) {
    $("#report-table-wrapper").addClass("d-none");
    $("#report-cards-wrapper").addClass("d-none");
    $("#report-empty-state")
        .removeClass("d-none")
        .html(`
            <div class="alert alert-danger mx-4 my-4 text-left">
                <h6 class="font-weight-bold mb-1">Failed to load report</h6>
                <p class="small mb-0">${frappe.utils.escape_html(err.message || "An unexpected error occurred while generating the financial statement.")}</p>
            </div>
        `);
}

/**
 * Triggers clean printing of the active Financial Statement report
 */
function printActiveFinancialReport() {
    // Ensure Financial Statements tab is active
    if (!$("#reports-pane").hasClass("active")) {
        $('#financialsTab a[href="#reports-pane"]').tab("show");
    }
    // Small timeout to allow DOM/tab state to settle before printing
    setTimeout(function () {
        window.print();
    }, 50);
}

/* ==========================================================================
   PART 2: Purchase Invoices Detailed Item & Tax View
   ========================================================================== */

function initPurchaseInvoiceDetailsHandler() {
    $(document).on("click", ".btn-view-purchase-invoice", function (e) {
        e.preventDefault();
        const invoiceName = $(this).data("invoice");
        if (!invoiceName) return;

        openPurchaseInvoiceModal(invoiceName);
    });
}

function openPurchaseInvoiceModal(invoiceName) {
    const $modal = $("#purchaseInvoiceModal");
    const $loader = $("#modal-pinv-loader");
    const $error = $("#modal-pinv-error");
    const $errorText = $("#modal-pinv-error-text");
    const $content = $("#modal-pinv-content");

    $("#pinv-modal-id").text(invoiceName);
    $error.addClass("d-none");
    $content.addClass("d-none");
    $loader.removeClass("d-none");

    $modal.modal("show");

    frappe.call({
        method: "society_erp.www.resident.financials.index.get_purchase_invoice_details",
        args: {
            invoice_name: invoiceName
        },
        callback: function (r) {
            $loader.addClass("d-none");

            if (r.exc || !r.message) {
                $errorText.text(r.exc || "Failed to load details for this purchase invoice.");
                $error.removeClass("d-none");
                return;
            }

            renderPurchaseInvoiceDetails(r.message);
        },
        error: function (err) {
            $loader.addClass("d-none");
            $errorText.text(err.message || "An unexpected server or network error occurred.");
            $error.removeClass("d-none");
        }
    });
}

function renderPurchaseInvoiceDetails(data) {
    const $content = $("#modal-pinv-content");
    const $itemsTbody = $("#pinv-items-tbody").empty();
    const $itemsCards = $("#pinv-items-cards").empty();
    const $taxesTbody = $("#pinv-taxes-tbody").empty();
    const $taxesCards = $("#pinv-taxes-cards").empty();

    $("#pinv-supplier-name").text(data.supplier_name);
    $("#pinv-supplier-code").text(data.supplier !== data.supplier_name ? data.supplier : "");
    $("#pinv-bill-no").text(data.bill_no !== "-" ? data.bill_no : data.name);
    $("#pinv-posting-date").text(`Posting Date: ${data.posting_date}`);
    $("#pinv-grand-total").text(data.formatted_grand_total);

    let badgeClass = "badge-secondary";
    if (data.status === "Paid") badgeClass = "badge-success";
    else if (data.status === "Unpaid" || data.status === "Overdue") badgeClass = "badge-danger";
    else if (data.status === "Partly Paid") badgeClass = "badge-warning";
    $("#pinv-status-badge").html(`<span class="badge ${badgeClass} px-3 py-1 font-weight-normal">${data.status}</span>`);

    if (data.remarks && data.remarks.trim()) {
        $("#pinv-remarks-text").text(data.remarks);
        $("#pinv-remarks-wrapper").removeClass("d-none");
    } else {
        $("#pinv-remarks-wrapper").addClass("d-none");
    }

    const items = data.items || [];
    if (items.length === 0) {
        $itemsTbody.append(`
            <tr>
                <td colspan="6" class="text-center py-3 text-muted">No line items recorded for this invoice.</td>
            </tr>
        `);
        $itemsCards.append(`
            <div class="text-center py-3 text-muted small">No line items recorded for this invoice.</div>
        `);
    } else {
        items.forEach((item, idx) => {
            const desc = item.description && item.description !== item.item_name 
                ? `<div class="small text-muted">${frappe.utils.escape_html(item.description)}</div>` 
                : "";

            // Desktop Table Row
            $itemsTbody.append(`
                <tr>
                    <td class="text-muted small">${idx + 1}</td>
                    <td>
                        <div class="font-weight-bold text-dark">${frappe.utils.escape_html(item.item_name)}</div>
                        ${desc}
                        <div class="small text-muted font-italic">${frappe.utils.escape_html(item.item_code)}</div>
                    </td>
                    <td>
                        <span class="badge badge-light border px-2 py-1 font-weight-normal text-muted">
                            ${frappe.utils.escape_html(item.cost_center)}
                        </span>
                    </td>
                    <td class="text-right">${item.qty} ${item.uom || ''}</td>
                    <td class="text-right text-muted">${item.formatted_rate}</td>
                    <td class="text-right font-weight-bold text-dark">${item.formatted_amount}</td>
                </tr>
            `);

            // Mobile Card
            $itemsCards.append(`
                <div class="app-card mb-2 p-2 bg-white border rounded shadow-sm">
                    <div class="d-flex justify-content-between align-items-start mb-1">
                        <div class="pr-2 text-truncate">
                            <div class="font-weight-bold text-dark text-truncate" style="font-size: 0.88rem;">${frappe.utils.escape_html(item.item_name)}</div>
                            ${desc}
                            <span class="badge badge-light border font-weight-normal text-muted" style="font-size: 0.72rem;">${frappe.utils.escape_html(item.cost_center)}</span>
                        </div>
                        <div class="text-right flex-shrink-0">
                            <div class="font-weight-bold text-dark" style="font-size: 0.9rem;">${item.formatted_amount}</div>
                            <small class="text-muted">${item.qty} ${item.uom || ''} &times; ${item.formatted_rate}</small>
                        </div>
                    </div>
                </div>
            `);
        });
    }
    $("#pinv-items-net-total").text(data.formatted_net_total || "₹ 0.00");

    const taxes = data.taxes || [];
    if (taxes.length === 0) {
        $taxesTbody.append(`
            <tr>
                <td colspan="5" class="text-center py-3 text-muted">No taxes or charges recorded for this invoice.</td>
            </tr>
        `);
        $taxesCards.append(`
            <div class="text-center py-3 text-muted small">No taxes or charges recorded for this invoice.</div>
        `);
    } else {
        taxes.forEach((tax, idx) => {
            // Desktop Table Row
            $taxesTbody.append(`
                <tr>
                    <td class="text-muted small">${idx + 1}</td>
                    <td class="font-weight-500 text-dark">
                        ${frappe.utils.escape_html(tax.account_head)}
                    </td>
                    <td class="text-right text-muted">
                        ${tax.rate > 0 ? tax.rate + '%' : '-'}
                    </td>
                    <td>
                        <span class="small text-muted">${frappe.utils.escape_html(tax.cost_center)}</span>
                    </td>
                    <td class="text-right font-weight-bold text-dark">${tax.formatted_tax_amount}</td>
                </tr>
            `);

            // Mobile Card
            $taxesCards.append(`
                <div class="app-card mb-2 p-2 bg-white border rounded shadow-sm">
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="pr-2 text-truncate">
                            <div class="font-weight-500 text-dark text-truncate" style="font-size: 0.85rem;">${frappe.utils.escape_html(tax.account_head)}</div>
                            <small class="text-muted">${frappe.utils.escape_html(tax.cost_center)} ${tax.rate > 0 ? '(' + tax.rate + '%)' : ''}</small>
                        </div>
                        <div class="text-right flex-shrink-0 font-weight-bold text-dark" style="font-size: 0.9rem;">
                            ${tax.formatted_tax_amount}
                        </div>
                    </div>
                </div>
            `);
        });
    }
    $("#pinv-total-taxes").text(data.formatted_total_taxes || "₹ 0.00");

    $content.removeClass("d-none");
}

/* ==========================================================================
   PART 3: Maintenance Bills & Analytics Module
   - Financial Year filtering on billing runs list
   - "View Considered Invoices" Modal: Date, Invoice ID, Supplier Name, Grand Total
   - Refined "View Complete Society GL" Modal: 2-column Account-wise consolidation
   - Compact Level 1 Modal with clean Single-Tier vs Two-Tier rates
   - Level 2 Drill-Down: Block Cost Center GL Breakdown
   ========================================================================== */

let currentMaintenanceRuns = [];
let activeBillingRunData = null;
let currentActiveRunId = null;
let currentActiveRunMonth = null;
let currentActiveRunDate = null;
let currentAllocationBasis = "sba"; // 'sba' (Super Builtup Area - Default) or 'uds'

function initMaintenanceModule() {
    // 1. Initial load of billing runs
    loadMaintenanceRuns();

    // 2. Financial Year filter change
    $("#maintenance_fy_filter").on("change", function () {
        loadMaintenanceRuns($(this).val());
    });

    // 3. Click on "View Blocks & UDS" Button -> Opens Compact Level 1 Modal
    $(document).on("click", ".btn-drilldown-run", function (e) {
        e.preventDefault();
        const runId = $(this).data("run");
        const billingMonth = $(this).data("month") || runId;
        if (!runId) return;

        openRunBlocksModal(runId, billingMonth);
    });

    // 4. Click on "View Considered Invoices" Button -> Opens Considered Invoices Modal
    $(document).on("click", ".btn-view-run-invoices", function (e) {
        e.preventDefault();
        const runId = $(this).data("run");
        const billingMonth = $(this).data("month") || runId;
        const startDate = $(this).data("start");
        const endDate = $(this).data("end");

        openRunInvoicesModal(runId, billingMonth, startDate, endDate);
    });

    // 5. "View Complete Society GL" button click (inside Blocks & UDS modal header)
    $("#btn-view-complete-gl").on("click", function (e) {
        e.preventDefault();
        const runId = currentActiveRunId;
        const billingMonth = currentActiveRunMonth || runId;
        const postingDate = currentActiveRunDate || "";
        openCompleteSocietyGlModal(runId, billingMonth, postingDate);
    });

    // 5B. "View Gross Common Expenses" button click (available in Reports tab and Blocks modal)
    $(document).on("click", ".btn-view-gross-common", function (e) {
        e.preventDefault();
        const runId = $(this).data("run") || currentActiveRunId;
        const billingMonth = $(this).data("month") || currentActiveRunMonth;
        let startDate = $(this).data("start");
        let endDate = $(this).data("end");

        // If not specified on button, check if triggered from financial report tab
        if (!runId && (!startDate || !endDate)) {
            const activeDates = resolveActiveDateRange();
            startDate = activeDates.fromDate;
            endDate = activeDates.toDate;
        }

        openGrossCommonExpensesModal(runId, billingMonth, startDate, endDate);
    });

    // 5C. Filter changes inside the Gross Common Expenses modal
    $("#gross_common_cost_center_filter, #gross_common_month_filter").on("change", function () {
        refreshGrossCommonExpensesModal();
    });

    // 6. Back button from Complete Society GL modal -> Returns to Blocks & UDS modal
    $("#btn-back-from-society-gl").on("click", function () {
        $("#completeSocietyGlModal").modal("hide");
        if (currentActiveRunId) {
            setTimeout(function () {
                $("#runBlocksModal").modal("show");
            }, 300);
        }
    });

    // 7. Level 2 Drilldown: Click on a Block in Level 1 -> Open GL Breakdown
    $(document).on("click", ".btn-block-gl-drilldown, .block-drilldown-row", function (e) {
        if ($(e.target).closest("a, button").length && !$(e.target).closest(".btn-block-gl-drilldown").length) {
            return;
        }
        e.preventDefault();

        const blockName = $(this).data("block");
        const costCenter = $(this).data("costcenter");
        const runId = $(this).data("run") || currentActiveRunId;
        const billingMonth = $(this).data("month") || currentActiveRunMonth;

        if (!blockName) return;

        openBlockGlModal(blockName, costCenter, runId, billingMonth);
    });

    // 8. Back button in Level 2 Modal -> Returns to Blocks & UDS modal
    $("#btn-back-to-blocks").on("click", function () {
        $("#glBreakdownModal").modal("hide");
        if (currentActiveRunId) {
            setTimeout(function () {
                $("#runBlocksModal").modal("show");
            }, 300);
        }
    });

    // 9. Allocation Basis Toggle (UDS vs Super Builtup Area - SBA)
    $('input[name="allocation_basis"]').on("change", function () {
        currentAllocationBasis = $(this).val(); // 'uds' or 'sba'
        if (activeBillingRunData) {
            populateModalAnalyticsHeader(activeBillingRunData);
            renderRunBlocksTable(activeBillingRunData);
        }
    });
}

/**
 * Loads maintenance billing runs from the backend filtered by Financial Year
 */
function loadMaintenanceRuns(fiscalYear) {
    const fy = fiscalYear !== undefined ? fiscalYear : $("#maintenance_fy_filter").val();

    frappe.call({
        method: "society_erp.www.resident.financials.index.get_maintenance_billing_runs",
        args: {
            fiscal_year: fy
        },
        callback: function (r) {
            if (r.exc || !r.message) {
                return;
            }
            const data = r.message;
            currentMaintenanceRuns = data.runs || [];

            $("#maintenance-runs-tab-badge").text(currentMaintenanceRuns.length);
            $("#maintenance-runs-count").text(currentMaintenanceRuns.length);
            $("#maintenance-table-count").text(currentMaintenanceRuns.length);

            renderMaintenanceRunsTable(currentMaintenanceRuns, data.currency);
        }
    });
}

/**
 * Renders the Maintenance Billing Runs table rows and mobile card stack dynamically
 */
function renderMaintenanceRunsTable(runs, currency) {
    const $tbody = $("#maintenance-runs-tbody").empty();
    const $cards = $("#maintenance-runs-cards").empty();

    if (!runs || runs.length === 0) {
        $tbody.append(`
            <tr>
                <td colspan="6" class="text-center py-5 text-muted">
                    <div class="py-4">
                        <div style="font-size: 2.5rem;" class="mb-2">🛠️</div>
                        <h5 class="text-muted font-weight-bold">No Maintenance Runs Found</h5>
                        <p class="small text-muted mb-0">No submitted monthly maintenance billing runs match the selected Financial Year.</p>
                    </div>
                </td>
            </tr>
        `);

        $cards.append(`
            <div class="text-center py-5 text-muted">
                <div style="font-size: 2rem;">🛠️</div>
                <div class="font-weight-bold mt-1">No Maintenance Runs Found</div>
                <small>No submitted runs match this Financial Year.</small>
            </div>
        `);
        return;
    }

    runs.forEach(function (run) {
        const fyBadge = run.fiscal_year 
            ? `<span class="badge badge-light border text-muted px-2 py-1">${frappe.utils.escape_html(run.fiscal_year)}</span>`
            : "-";

        // Desktop Table Row
        $tbody.append(`
            <tr>
                <td class="font-weight-bold text-primary">
                    📅 ${frappe.utils.escape_html(run.billing_month)}
                    <div class="small text-muted font-weight-normal">${frappe.utils.escape_html(run.name)}</div>
                </td>
                <td class="text-muted small">
                    ${run.formatted_posting_date}
                </td>
                <td>
                    ${fyBadge}
                </td>
                <td class="text-center">
                    <span class="badge badge-secondary px-2 py-1 font-weight-normal">
                        ${run.blocks_count} Blocks
                    </span>
                </td>
                <td class="text-right font-weight-bold text-dark">
                    ${run.formatted_total_amount}
                </td>
                <td class="text-center">
                    <div class="btn-group btn-group-sm" role="group">
                        <button type="button" 
                                class="btn btn-outline-primary btn-drilldown-run shadow-none"
                                data-run="${frappe.utils.escape_html(run.name)}"
                                data-month="${frappe.utils.escape_html(run.billing_month)}"
                                title="View Block calculations and Comparative Rate">
                            🏢 View Blocks &amp; UDS &raquo;
                        </button>
                        <button type="button" 
                                class="btn btn-outline-secondary btn-view-run-invoices shadow-none"
                                data-run="${frappe.utils.escape_html(run.name)}"
                                data-month="${frappe.utils.escape_html(run.billing_month)}"
                                data-start="${frappe.utils.escape_html(run.start_date || '')}"
                                data-end="${frappe.utils.escape_html(run.end_date || '')}"
                                title="View vendor purchase invoices for this month">
                            🧾 View Considered Invoices
                        </button>
                    </div>
                </td>
            </tr>
        `);

        // Mobile Banking-App Style Transaction Card
        $cards.append(`
            <div class="app-card mb-2 p-3 bg-white border rounded shadow-sm">
                <div class="d-flex justify-content-between align-items-start mb-1">
                    <div class="d-flex align-items-center flex-grow-1 pr-2 text-truncate">
                        <span class="app-card-icon mr-2">📅</span>
                        <div class="text-truncate">
                            <div class="font-weight-bold text-dark text-truncate h6 mb-0">${frappe.utils.escape_html(run.billing_month)}</div>
                            <div class="small text-muted text-truncate">${frappe.utils.escape_html(run.name)} &bull; ${run.blocks_count} Blocks</div>
                        </div>
                    </div>
                    <div class="text-right flex-shrink-0">
                        <div class="font-weight-bold text-dark h6 mb-0">${run.formatted_total_amount}</div>
                        <div class="small text-muted">${run.formatted_posting_date}</div>
                    </div>
                </div>
                <div class="d-flex justify-content-between align-items-center mt-2 pt-2 border-top">
                    <button type="button" 
                            class="btn btn-xs btn-outline-primary btn-drilldown-run flex-fill mr-1 py-1"
                            data-run="${frappe.utils.escape_html(run.name)}"
                            data-month="${frappe.utils.escape_html(run.billing_month)}">
                        🏢 Blocks &amp; UDS &raquo;
                    </button>
                    <button type="button" 
                            class="btn btn-xs btn-outline-secondary btn-view-run-invoices flex-fill ml-1 py-1"
                            data-run="${frappe.utils.escape_html(run.name)}"
                            data-month="${frappe.utils.escape_html(run.billing_month)}"
                            data-start="${frappe.utils.escape_html(run.start_date || '')}"
                            data-end="${frappe.utils.escape_html(run.end_date || '')}">
                        🧾 Invoices
                    </button>
                </div>
            </div>
        `);
    });
}

/**
 * Level 1 Drill-Down: Open Blocks & UDS Modal with Compact Clean Objective Header
 */
function openRunBlocksModal(runId, billingMonth) {
    currentActiveRunId = runId;
    currentActiveRunMonth = billingMonth;

    const $modal = $("#runBlocksModal");
    const $loader = $("#modal-blocks-loader");
    const $error = $("#modal-blocks-error");
    const $errorText = $("#modal-blocks-error-text");
    const $tableWrapper = $("#modal-blocks-table-wrapper");
    const $tbody = $("#run-blocks-tbody").empty();
    const $subtitle = $("#blocks-modal-subtitle");
    const $footerInfo = $("#blocks-modal-footer-info");
    const $residentBanner = $("#blocks-modal-resident-banner").addClass("d-none");

    $subtitle.text(`Billing Run: ${runId} • Month: ${billingMonth}`);
    $footerInfo.text(`Run ID: ${runId}`);
    $error.addClass("d-none");
    $tableWrapper.addClass("d-none");
    $loader.removeClass("d-none");

    $modal.modal("show");

    frappe.call({
        method: "society_erp.www.resident.financials.index.get_billing_run_blocks",
        args: {
            run_id: runId
        },
        callback: function (r) {
            $loader.addClass("d-none");

            if (r.exc || !r.message) {
                $errorText.text(r.exc || "Failed to load block calculations for this billing run.");
                $error.removeClass("d-none");
                return;
            }

            activeBillingRunData = r.message;
            currentActiveRunDate = activeBillingRunData.raw_posting_date || "";

            populateModalAnalyticsHeader(activeBillingRunData);
            renderRunBlocksTable(activeBillingRunData);
        },
        error: function (err) {
            $loader.addClass("d-none");
            $errorText.text(err.message || "An unexpected server or network error occurred.");
            $error.removeClass("d-none");
        }
    });
}

/**
 * Populates the compact modal header cleanly with objective Single-Tier vs Two-Tier rates
 * based on selected allocation basis ('uds' or 'sba').
 */
function populateModalAnalyticsHeader(data) {
    const isSba = (currentAllocationBasis === "sba");
    const basisLabel = isSba ? "Super Builtup Area (SBA)" : "UDS";
    const basisUnit = isSba ? "sqft SBA" : "sqft UDS";

    $("#modal-analytics-title").text(`${data.billing_month} — Expense & Rate Structure (${basisLabel})`);
    
    // Metric 1: Total Monthly Expenses: [Dynamic Grand Total]
    $("#metric-society-expense").text(data.formatted_society_expense);

    const singleTierRate = isSba 
        ? (parseFloat(data.comparative_rate_sba) || 0)
        : (parseFloat(data.comparative_rate_uds) || 0);

    const userArea = isSba 
        ? (parseFloat(data.user_sba) || 0)
        : (parseFloat(data.user_uds) || 0);

    const currency = data.currency || "INR";

    // Metric 2: Society-Wide Rate (Flat / Area) (Single Tier)
    $("#metric-comparative-rate").text(`₹ ${singleTierRate.toFixed(4)} / sqft`);

    // Render All 4 Flat Types (A Type, B Type, C Type, D Type) in Single Tier Comparison
    const $singleTierList = $("#metric-single-tier-types-list").empty();
    const flatTypeComparison = data.flat_type_comparison || [];

    if (flatTypeComparison.length > 0) {
        let typesHtml = `<div class="d-flex flex-column" style="gap: 2px;">`;
        flatTypeComparison.forEach(function (ft) {
            const areaVal = isSba ? ft.sba : ft.uds;
            const maintVal = isSba ? ft.formatted_total_maintenance_sba : ft.formatted_total_maintenance_uds;
            const isUserType = userArea > 0 && Math.abs(areaVal - userArea) < 0.5;
            const highlightBadge = isUserType ? ' <span class="badge badge-danger px-1 py-0" style="font-size: 0.65rem;">Your Flat</span>' : '';

            typesHtml += `
                <div class="d-flex justify-content-between align-items-center ${isUserType ? 'font-weight-bold' : ''}" style="font-size: 0.72rem;">
                    <span>${frappe.utils.escape_html(ft.flat_type)}${highlightBadge} (${areaVal} ${isSba ? 'SBA' : 'UDS'}):</span>
                    <span class="font-monospace">${singleTierRate.toFixed(4)} &times; ${areaVal} = <strong>${maintVal}</strong></span>
                </div>
            `;
        });
        typesHtml += `</div>`;
        $singleTierList.html(typesHtml);
    } else {
        if (userArea > 0) {
            const singleTierTotal = (singleTierRate * userArea).toFixed(2);
            const singleTierFormattedTotal = formatFinancialAmount(singleTierTotal, currency);
            $singleTierList.text(`(${singleTierRate.toFixed(4)} × ${userArea} ${basisLabel} = ${singleTierFormattedTotal})`);
        } else {
            $singleTierList.text(`(${singleTierRate.toFixed(4)} × ${basisLabel} = Total)`);
        }
    }

    // Metric 3: Block-Wise Rate (Two-Tier): ₹ [Rate] / sqft (₹ [Rate] x Area = Total)
    const blocks = data.blocks || [];
    let blockRate = isSba ? data.user_block_rate_sba : data.user_block_rate;
    let blockName = data.user_block;

    // If user has no resident block assigned (e.g. staff), pick the first block for display
    if (blockRate == null && blocks.length > 0) {
        blockRate = isSba ? blocks[0].rate_per_sba : blocks[0].rate_per_uds;
        blockName = blocks[0].block;
    }

    if (blockRate != null) {
        const parsedBlockRate = parseFloat(blockRate) || 0;
        const blockLabel = blockName ? `Block ${blockName}: ` : "";
        $("#metric-block-wise-rate").text(`${blockLabel}₹ ${parsedBlockRate.toFixed(4)} / sqft`);

        if (userArea > 0) {
            const twoTierTotal = (parsedBlockRate * userArea).toFixed(2);
            const twoTierFormattedTotal = formatFinancialAmount(twoTierTotal, currency);
            $("#metric-two-tier-formula").text(`(₹ ${parsedBlockRate.toFixed(4)} × ${userArea} ${basisLabel} = ${twoTierFormattedTotal})`);
        } else {
            $("#metric-two-tier-formula").text(`(₹ ${parsedBlockRate.toFixed(4)} × ${basisLabel} = Total)`);
        }
    } else {
        $("#metric-block-wise-rate").text("-");
        $("#metric-two-tier-formula").text(`(Block Rate × ${basisLabel} = Total)`);
    }
}

/**
 * Render Level 1 Blocks Table and Mobile Cards
 * dynamically supports UDS or Super Builtup Area (SBA).
 */
function renderRunBlocksTable(data) {
    const isSba = (currentAllocationBasis === "sba");
    const basisLabel = isSba ? "Builtup Area (SBA)" : "UDS";
    const basisShort = isSba ? "SBA" : "UDS";

    // Update column headers for desktop table
    $("#th-total-block-area").text(`Total Block ${basisShort}`);
    $("#th-rate-per-area").html(`Rate / ${basisShort} &bull; Flat Maint`);

    const $tableWrapper = $("#modal-blocks-table-wrapper");
    const $tbody = $("#run-blocks-tbody").empty();
    const $cards = $("#run-blocks-cards").empty();
    const $residentBanner = $("#blocks-modal-resident-banner");
    const blocks = data.blocks || [];

    const userArea = isSba ? (parseFloat(data.user_sba) || 0) : (parseFloat(data.user_uds) || 0);

    if (data.user_block && userArea > 0) {
        const userBlockRow = blocks.find(b => b.block === data.user_block);
        const userShare = userBlockRow && userBlockRow.formatted_resident_share 
            ? userBlockRow.formatted_resident_share 
            : "-";

        $residentBanner.html(`
            <div class="d-flex justify-content-between align-items-center flex-wrap small">
                <div>
                    <strong>Your Flat:</strong> Block <strong>${frappe.utils.escape_html(data.user_block)}</strong> 
                    &bull; ${basisLabel}: <strong>${userArea} sqft</strong>
                </div>
                <div class="mt-1 mt-md-0 font-weight-bold">
                    Monthly Maintenance: <span class="text-primary">${userShare}</span>
                </div>
            </div>
        `).removeClass("d-none");
    } else {
        $residentBanner.addClass("d-none");
    }

    if (blocks.length === 0) {
        $tbody.append(`
            <tr>
                <td colspan="6" class="text-center py-4 text-muted">
                    No block calculations found for this billing run.
                </td>
            </tr>
        `);
        $cards.append(`
            <div class="text-center py-4 text-muted">
                No block calculations found.
            </div>
        `);
    } else {
        blocks.forEach(function (b) {
            const isUserBlock = b.is_user_block;
            const rowClass = isUserBlock ? "table-warning font-weight-500" : "block-drilldown-row";
            const blockBadge = isUserBlock 
                ? `<span class="badge badge-warning px-2 py-1">Block ${frappe.utils.escape_html(b.block)} (Your Block)</span>` 
                : `<span class="badge badge-light border px-2 py-1 font-weight-bold">Block ${frappe.utils.escape_html(b.block)}</span>`;

            const residentShareHtml = isUserBlock && b.formatted_resident_share
                ? `<div class="small text-muted font-weight-normal">Your Share: <span class="text-primary font-weight-bold">${b.formatted_resident_share}</span></div>`
                : "";

            // Use SBA or UDS metrics based on toggle
            const blockTotalArea = isSba ? (parseFloat(b.total_block_sba) || 0) : (parseFloat(b.total_block_uds) || 0);
            const flatArea = isSba ? (parseFloat(b.flat_sba) || 0) : (parseFloat(b.flat_uds) || 0);
            const rateVal = isSba ? (parseFloat(b.rate_per_sba) || 0) : (parseFloat(b.rate_per_uds) || 0);
            const rateFormatted = isSba ? (b.formatted_rate_per_sba || `${rateVal.toFixed(4)} / sqft`) : (b.formatted_rate_per_uds || `${rateVal.toFixed(4)} / sqft`);
            const flatMaintFormatted = b.formatted_flat_maintenance || "-";
            const flatTypeLabel = b.flat_type ? `(${frappe.utils.escape_html(b.flat_type)})` : "";

            // Desktop Table Row
            $tbody.append(`
                <tr class="${rowClass}" data-block="${frappe.utils.escape_html(b.block)}" data-costcenter="${frappe.utils.escape_html(b.cost_center)}" data-run="${frappe.utils.escape_html(data.run_id)}" data-month="${frappe.utils.escape_html(data.billing_month)}" style="cursor: pointer;">
                    <td>${blockBadge} <span class="small text-muted font-weight-normal">${flatTypeLabel}</span></td>
                    <td class="small text-muted">${frappe.utils.escape_html(b.cost_center)}</td>
                    <td class="text-right text-muted">${blockTotalArea.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                    <td class="text-right font-weight-bold text-dark">
                        ${b.formatted_total_expense}
                        ${residentShareHtml}
                    </td>
                    <td class="text-right">
                        <div class="font-weight-bold text-info">${rateFormatted}</div>
                        ${flatArea > 0 ? `
                            <div class="small text-dark font-weight-bold mt-1" title="${rateVal.toFixed(4)} × ${flatArea} ${basisShort}">
                                ${rateVal.toFixed(4)} &times; ${flatArea} = <span class="text-primary font-weight-bold">${flatMaintFormatted}</span>
                                <div class="text-muted font-weight-normal" style="font-size: 0.72rem;">per flat</div>
                            </div>
                        ` : ''}
                    </td>
                    <td class="text-center">
                        <button type="button" 
                                class="btn btn-xs btn-outline-primary btn-block-gl-drilldown px-2 py-1"
                                data-block="${frappe.utils.escape_html(b.block)}"
                                data-costcenter="${frappe.utils.escape_html(b.cost_center)}"
                                data-run="${frappe.utils.escape_html(data.run_id)}"
                                data-month="${frappe.utils.escape_html(data.billing_month)}">
                            🔍 GL Breakdown &raquo;
                        </button>
                    </td>
                </tr>
            `);

            // Mobile Card View: Left = Block Name & Cost Center, Right = Total Expense & Rate with Flat Maintenance, Bottom = Full-width Button
            $cards.append(`
                <div class="app-card mb-2 p-3 ${isUserBlock ? 'border-warning bg-light' : 'bg-white'} shadow-sm">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div class="pr-2">
                            <div class="font-weight-bold text-dark h6 mb-0">
                                🏢 Block ${frappe.utils.escape_html(b.block)} ${flatTypeLabel}
                                ${isUserBlock ? '<span class="badge badge-warning ml-1">Your Flat</span>' : ''}
                            </div>
                            <div class="small text-muted">${frappe.utils.escape_html(b.cost_center)}</div>
                            <div class="small text-muted">${blockTotalArea.toLocaleString("en-IN", { minimumFractionDigits: 0 })} sqft Block ${basisShort}</div>
                        </div>
                        <div class="text-right flex-shrink-0">
                            <div class="font-weight-bold text-dark h6 mb-0">${b.formatted_total_expense}</div>
                            <div class="small text-info font-weight-bold">${rateFormatted}</div>
                        </div>
                    </div>
                    ${flatArea > 0 ? `
                        <div class="mb-2 p-2 bg-light rounded border text-right small">
                            <span class="text-muted">${rateVal.toFixed(4)} &times; ${flatArea} sqft ${basisShort} =</span>
                            <span class="h6 mb-0 font-weight-bold text-primary ml-1">${flatMaintFormatted}</span>
                            <div class="text-muted" style="font-size: 0.72rem;">Monthly Maintenance per Flat</div>
                        </div>
                    ` : ''}
                    ${residentShareHtml ? `<div class="mb-2 py-1 px-2 bg-white rounded border small">${residentShareHtml}</div>` : ''}
                    <button type="button" 
                            class="btn btn-outline-primary btn-block btn-sm btn-block-gl-drilldown font-weight-bold shadow-none"
                            data-block="${frappe.utils.escape_html(b.block)}"
                            data-costcenter="${frappe.utils.escape_html(b.cost_center)}"
                            data-run="${frappe.utils.escape_html(data.run_id)}"
                            data-month="${frappe.utils.escape_html(data.billing_month)}">
                        🔍 GL Breakdown &raquo;
                    </button>
                </div>
            `);
        });
    }

    const totalComplexArea = isSba 
        ? (parseFloat(data.total_run_sba) || 0)
        : (parseFloat(data.total_run_uds) || 0);

    $("#modal-blocks-total-uds").text(totalComplexArea.toLocaleString("en-IN", { minimumFractionDigits: 2 }));
    $("#modal-blocks-total-expense").text(data.formatted_total_run_expense || data.formatted_total_billed_amount || "₹ 0.00");
    $tableWrapper.removeClass("d-none");
    $tableWrapper.find(".table-responsive").removeClass("d-none").addClass("d-none d-md-block");
    $cards.removeClass("d-none").addClass("d-block d-md-none");
}

/**
 * Considered Invoices Modal: Date, Invoice ID, Supplier Name, Grand Total
 */
function openRunInvoicesModal(runId, billingMonth, startDate, endDate) {
    const $modal = $("#runInvoicesModal");
    const $loader = $("#modal-run-invoices-loader");
    const $error = $("#modal-run-invoices-error");
    const $errorText = $("#modal-run-invoices-error-text");
    const $tableWrapper = $("#modal-run-invoices-table-wrapper");
    const $tbody = $("#run-invoices-tbody").empty();
    const $subtitle = $("#run-invoices-modal-subtitle");
    const $total = $("#run-invoices-total-amount");
    const $footerInfo = $("#run-invoices-modal-footer-info");

    $subtitle.text(`Submitted Purchase Invoices considered in ${billingMonth} calculations (${runId})`);
    $footerInfo.text(`Billing Run: ${runId}`);
    $error.addClass("d-none");
    $tableWrapper.addClass("d-none");
    $loader.removeClass("d-none");
    $total.text("₹ 0.00");

    $modal.modal("show");

    frappe.call({
        method: "society_erp.www.resident.financials.index.get_maintenance_run_invoices",
        args: {
            run_id: runId,
            billing_month_start_date: startDate,
            billing_month_end_date: endDate
        },
        callback: function (r) {
            $loader.addClass("d-none");

            if (r.exc || !r.message) {
                $errorText.text(r.exc || "Failed to load considered invoices.");
                $error.removeClass("d-none");
                return;
            }

            renderRunInvoicesTable(r.message);
        },
        error: function (err) {
            $loader.addClass("d-none");
            $errorText.text(err.message || "An unexpected network or server error occurred.");
            $error.removeClass("d-none");
        }
    });
}

function renderRunInvoicesTable(data) {
    const $tableWrapper = $("#modal-run-invoices-table-wrapper");
    const $tbody = $("#run-invoices-tbody").empty();
    const $cards = $("#run-invoices-cards").empty();
    const $total = $("#run-invoices-total-amount");
    const invoices = data.invoices || [];

    if (invoices.length === 0) {
        $tbody.append(`
            <tr>
                <td colspan="5" class="text-center py-4 text-muted">
                    No submitted purchase invoices found for this billing month range (${data.from_date} to ${data.to_date}).
                </td>
            </tr>
        `);
        $cards.append(`
            <div class="text-center py-4 text-muted">
                No submitted purchase invoices found.
            </div>
        `);
    } else {
        invoices.forEach(function (inv) {
            // Desktop Table Row
            $tbody.append(`
                <tr>
                    <td class="text-muted small">${inv.posting_date}</td>
                    <td class="font-weight-bold text-dark">
                        ${frappe.utils.escape_html(inv.name)}
                        ${inv.bill_no !== '-' ? `<div class="small text-muted font-weight-normal">Ref: ${frappe.utils.escape_html(inv.bill_no)}</div>` : ''}
                    </td>
                    <td>
                        <div class="font-weight-500 text-dark">${frappe.utils.escape_html(inv.supplier_name)}</div>
                    </td>
                    <td class="text-right font-weight-bold text-dark">${inv.formatted_grand_total}</td>
                    <td class="text-center">
                        <button type="button" 
                                class="btn btn-xs btn-outline-info btn-view-purchase-invoice px-2 py-1"
                                data-invoice="${frappe.utils.escape_html(inv.name)}">
                            👁️ View
                        </button>
                    </td>
                </tr>
            `);

            // Mobile Card View
            $cards.append(`
                <div class="app-card mb-2 p-3 bg-white btn-view-purchase-invoice" data-invoice="${frappe.utils.escape_html(inv.name)}" role="button">
                    <div class="d-flex justify-content-between align-items-start mb-1">
                        <div class="d-flex align-items-center flex-grow-1 pr-2 text-truncate">
                            <span class="app-card-icon mr-2">🧾</span>
                            <div class="text-truncate">
                                <div class="font-weight-bold text-dark text-truncate">${frappe.utils.escape_html(inv.supplier_name)}</div>
                                <div class="small text-muted text-truncate">${frappe.utils.escape_html(inv.name)}${inv.bill_no && inv.bill_no !== '-' ? ` &bull; Ref: ${frappe.utils.escape_html(inv.bill_no)}` : ''}</div>
                            </div>
                        </div>
                        <div class="text-right flex-shrink-0">
                            <div class="font-weight-bold text-dark h6 mb-0">${inv.formatted_grand_total}</div>
                            <div class="small text-muted">${inv.posting_date}</div>
                        </div>
                    </div>
                    <div class="d-flex justify-content-between align-items-center mt-2 pt-2 border-top small text-primary font-weight-bold">
                        <span>Invoice Items &amp; Taxes</span>
                        <span>View Details &raquo;</span>
                    </div>
                </div>
            `);
        });
    }

    $total.text(data.formatted_total_invoiced || "₹ 0.00");
    $tableWrapper.removeClass("d-none");
    $tableWrapper.find(".table-responsive").removeClass("d-none").addClass("d-none d-md-block");
    $cards.removeClass("d-none").addClass("d-block d-md-none");
}

/**
 * Refined Complete Society GL View: 2-Column Table (Expense Account & Total Amount)
 */
function openCompleteSocietyGlModal(runId, billingMonth, postingDate) {
    const $modal = $("#completeSocietyGlModal");
    const $loader = $("#modal-society-gl-loader");
    const $error = $("#modal-society-gl-error");
    const $errorText = $("#modal-society-gl-error-text");
    const $tableWrapper = $("#modal-society-gl-table-wrapper");
    const $tbody = $("#complete-society-gl-tbody").empty();
    const $subtitle = $("#society-gl-modal-subtitle");
    const $total = $("#complete-society-gl-total");
    const $footerInfo = $("#society-gl-modal-footer-info");

    $("#runBlocksModal").modal("hide");

    $subtitle.text(`Account-wise consolidated society operating expenses • ${billingMonth}`);
    $footerInfo.text(`Billing Run: ${runId}`);
    $error.addClass("d-none");
    $tableWrapper.addClass("d-none");
    $loader.removeClass("d-none");
    $total.text("₹ 0.00");

    $modal.modal("show");

    frappe.call({
        method: "society_erp.www.resident.financials.index.get_complete_society_gl",
        args: {
            run_id: runId,
            posting_date: postingDate
        },
        callback: function (r) {
            $loader.addClass("d-none");

            if (r.exc || !r.message) {
                $errorText.text(r.exc || "Failed to load complete society ledger entries.");
                $error.removeClass("d-none");
                return;
            }

            renderCompleteSocietyGlTable(r.message);
        },
        error: function (err) {
            $loader.addClass("d-none");
            $errorText.text(err.message || "An unexpected server error occurred.");
            $error.removeClass("d-none");
        }
    });
}

function renderCompleteSocietyGlTable(data) {
    const $tableWrapper = $("#modal-society-gl-table-wrapper");
    const $tbody = $("#complete-society-gl-tbody").empty();
    const $cards = $("#complete-society-gl-cards").empty();
    const $total = $("#complete-society-gl-total");
    const entries = data.entries || [];

    if (entries.length === 0) {
        $tbody.append(`
            <tr>
                <td colspan="2" class="text-center py-4 text-muted">
                    No operating expense ledger entries found for this month across the society.
                </td>
            </tr>
        `);
        $cards.append(`
            <div class="text-center py-4 text-muted">
                No operating expense ledger entries found for this month across the society.
            </div>
        `);
    } else {
        entries.forEach((row) => {
            // Desktop Table Row
            $tbody.append(`
                <tr>
                    <td>
                        <div class="font-weight-bold text-dark">${frappe.utils.escape_html(row.account_name || row.account)}</div>
                        <div class="small text-muted">${frappe.utils.escape_html(row.account)}</div>
                    </td>
                    <td class="text-right font-weight-bold text-dark">${row.formatted_net_expense}</td>
                </tr>
            `);

            // Mobile Ledger Card
            $cards.append(`
                <div class="app-card mb-2 p-3 bg-white border rounded shadow-sm">
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="pr-2 text-truncate">
                            <div class="font-weight-bold text-dark text-truncate" style="font-size: 0.9rem;">
                                ${frappe.utils.escape_html(row.account_name || row.account)}
                            </div>
                            <div class="small text-muted text-truncate font-monospace" style="font-size: 0.75rem;">
                                ${frappe.utils.escape_html(row.account)}
                            </div>
                        </div>
                        <div class="text-right flex-shrink-0 font-weight-bold text-dark h6 mb-0">
                            ${row.formatted_net_expense}
                        </div>
                    </div>
                </div>
            `);
        });
    }

    $total.text(data.formatted_total_society_expense || "₹ 0.00");
    $tableWrapper.removeClass("d-none");
    $tableWrapper.find(".table-responsive").removeClass("d-none").addClass("d-none d-md-block");
    $cards.removeClass("d-none").addClass("d-block d-md-none");
}

/**
 * Level 2 Drill-Down: Open GL Entries Modal for a specific Block in that Billing Run
 */
function openBlockGlModal(blockName, costCenter, runId, billingMonth) {
    const $modal = $("#glBreakdownModal");
    const $loader = $("#modal-gl-loader");
    const $error = $("#modal-gl-error");
    const $errorText = $("#modal-gl-error-text");
    const $tableWrapper = $("#modal-gl-table-wrapper");
    const $tbody = $("#gl-breakdown-tbody").empty();
    const $subtitle = $("#gl-modal-subtitle");
    const $totalAmount = $("#modal-gl-total-amount");

    $("#runBlocksModal").modal("hide");

    $subtitle.text(`Block ${blockName} • ${billingMonth || ''} (${costCenter || runId})`);
    $error.addClass("d-none");
    $tableWrapper.addClass("d-none");
    $loader.removeClass("d-none");
    $totalAmount.text("₹ 0.00");

    $modal.modal("show");

    frappe.call({
        method: "society_erp.www.resident.financials.index.get_block_gl_entries",
        args: {
            block_name: blockName,
            cost_center: costCenter,
            run_id: runId
        },
        callback: function (r) {
            $loader.addClass("d-none");

            if (r.exc || !r.message) {
                $errorText.text(r.exc || "Failed to retrieve ledger entries for this block.");
                $error.removeClass("d-none");
                return;
            }

            renderBlockGlTable(r.message);
        },
        error: function (err) {
            $loader.addClass("d-none");
            $errorText.text(err.message || "An unexpected network or server error occurred.");
            $error.removeClass("d-none");
        }
    });
}

function renderBlockGlTable(data) {
    const $tableWrapper = $("#modal-gl-table-wrapper");
    const $tbody = $("#gl-breakdown-tbody").empty();
    const $cards = $("#gl-breakdown-cards").empty();
    const $totalAmount = $("#modal-gl-total-amount");
    const entries = data.entries || [];

    if (entries.length === 0) {
        $tbody.append(`
            <tr>
                <td colspan="5" class="text-center py-4 text-muted">
                    No General Ledger expense entries found for Block ${frappe.utils.escape_html(data.block)} (${data.from_date} to ${data.to_date}).
                </td>
            </tr>
        `);
        $cards.append(`
            <div class="text-center py-4 text-muted">
                No General Ledger expense entries found for Block ${frappe.utils.escape_html(data.block)} (${data.from_date} to ${data.to_date}).
            </div>
        `);
    } else {
        entries.forEach(function (row) {
            const badgeClass = row.root_type === "Expense" ? "badge-danger" : "badge-success";
            const netAmountClass = row.net_amount < 0 ? "text-success" : "text-dark font-weight-bold";

            // Desktop Table Row
            $tbody.append(`
                <tr>
                    <td>
                        <div class="font-weight-bold text-dark">${frappe.utils.escape_html(row.account_name || row.account)}</div>
                        <div class="small text-muted">${frappe.utils.escape_html(row.account)}</div>
                    </td>
                    <td>
                        <span class="badge ${badgeClass} px-2 py-1 font-weight-normal">
                            ${frappe.utils.escape_html(row.root_type || "Expense")}
                        </span>
                    </td>
                    <td class="text-right text-muted">${row.formatted_debit}</td>
                    <td class="text-right text-muted">${row.formatted_credit}</td>
                    <td class="text-right ${netAmountClass}">${row.formatted_net_amount}</td>
                </tr>
            `);

            // Mobile Ledger Card
            $cards.append(`
                <div class="app-card mb-2 p-3 bg-white border rounded shadow-sm">
                    <div class="d-flex justify-content-between align-items-start mb-1">
                        <div class="pr-2 text-truncate">
                            <div class="font-weight-bold text-dark text-truncate" style="font-size: 0.9rem;">
                                ${frappe.utils.escape_html(row.account_name || row.account)}
                            </div>
                            <div class="small text-muted text-truncate font-monospace" style="font-size: 0.75rem;">
                                ${frappe.utils.escape_html(row.account)}
                            </div>
                        </div>
                        <div class="text-right flex-shrink-0">
                            <div class="font-weight-bold ${netAmountClass} h6 mb-0">${row.formatted_net_amount}</div>
                            <span class="badge ${badgeClass} px-2 py-0 small">${frappe.utils.escape_html(row.root_type || "Expense")}</span>
                        </div>
                    </div>
                    <div class="d-flex justify-content-between align-items-center mt-2 pt-1 border-top small text-muted">
                        <span>Debit: <strong>${row.formatted_debit}</strong></span>
                        <span>Credit: <strong>${row.formatted_credit}</strong></span>
                    </div>
                </div>
            `);
        });
    }

    $totalAmount.text(data.formatted_total_expense || "₹ 0.00");
    $tableWrapper.removeClass("d-none");
    $tableWrapper.find(".table-responsive").removeClass("d-none").addClass("d-none d-md-block");
    $cards.removeClass("d-none").addClass("d-block d-md-none");
}

// Global active state tracking for Gross Common Expenses modal
let currentGrossCommonRunId = null;
let currentGrossCommonFy = null;

/**
 * Resolves the currently active Financial Year from the UI
 */
function resolveActiveFinancialYear() {
    // 1. From Financial Statements tab dropdown
    const fyFromReport = $("#fiscal_year_select").val();
    if (fyFromReport && fyFromReport !== "All Fiscal Years") {
        return fyFromReport;
    }

    // 2. From Maintenance Bills FY filter dropdown
    const fyFromMaint = $("#maintenance_fy_filter").val();
    if (fyFromMaint && fyFromMaint !== "All Fiscal Years") {
        return fyFromMaint;
    }

    // 3. Fallback to badge text
    const badgeText = ($("#gross_common_fy_badge").text() || "").replace("FY:", "").trim();
    return badgeText || null;
}

/**
 * Common Area Expense Breakdown: Pre-Apportionment Gross Expenses
 */
function openGrossCommonExpensesModal(runId, billingMonth, startDate, endDate) {
    const $modal = $("#grossCommonExpensesModal");
    currentGrossCommonRunId = runId || null;

    // Resolve Active Financial Year
    currentGrossCommonFy = resolveActiveFinancialYear();
    if (currentGrossCommonFy) {
        $("#gross_common_fy_badge").text(`FY: ${currentGrossCommonFy}`).attr("title", `Active Financial Year: ${currentGrossCommonFy}`);
    }

    // Attempt to set month dropdown in modal based on billingMonth or startDate
    let targetMonth = null;
    if (startDate) {
        try {
            targetMonth = parseInt(startDate.split("-")[1], 10);
        } catch (e) {}
    } else if (billingMonth) {
        const monthNames = [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december"
        ];
        const lowerMonth = billingMonth.toLowerCase();
        for (let idx = 0; idx < monthNames.length; idx++) {
            if (lowerMonth.includes(monthNames[idx])) {
                targetMonth = idx + 1;
                break;
            }
        }
    }

    if (!targetMonth) {
        // If triggered from financial report month/year filter
        if ($("#date_filter_type").val() === "month_year") {
            const mVal = parseInt($("#select_month").val(), 10);
            targetMonth = mVal + 1; // select_month is 0-indexed
        } else {
            targetMonth = new Date().getMonth() + 1;
        }
    }

    if (targetMonth) {
        $("#gross_common_month_filter").val(String(targetMonth));
    }

    // Reset Cost Center filter to combined (blank)
    $("#gross_common_cost_center_filter").val("");

    $modal.modal("show");

    // Fetch and render data with active filters
    refreshGrossCommonExpensesModal(startDate, endDate);
}

/**
 * Re-fetches and renders the Gross Common Expenses modal according to active filters
 */
function refreshGrossCommonExpensesModal(fallbackStartDate, fallbackEndDate) {
    const $loader = $("#modal-gross-common-loader");
    const $error = $("#modal-gross-common-error");
    const $errorText = $("#modal-gross-common-error-text");
    const $empty = $("#modal-gross-common-empty");
    const $tableWrapper = $("#modal-gross-common-table-wrapper");
    const $tbody = $("#gross-common-tbody").empty();
    const $subtitle = $("#gross-common-modal-subtitle");
    const $grandTotal = $("#gross-common-grand-total");
    const $footerInfo = $("#gross-common-modal-footer-info");

    const selectedCostCenter = $("#gross_common_cost_center_filter").val() || "";
    const selectedMonth = $("#gross_common_month_filter").val() || "";
    const activeFy = currentGrossCommonFy || resolveActiveFinancialYear();

    $error.addClass("d-none");
    $empty.addClass("d-none");
    $tableWrapper.addClass("d-none");
    $loader.removeClass("d-none");
    $grandTotal.text("₹ 0.00");

    frappe.call({
        method: "society_erp.www.resident.financials.index.get_gross_common_expenses",
        args: {
            specific_cost_center: selectedCostCenter,
            month: selectedMonth,
            financial_year: activeFy,
            month_start_date: fallbackStartDate || null,
            month_end_date: fallbackEndDate || null,
            run_id: currentGrossCommonRunId || null
        },
        callback: function (r) {
            $loader.addClass("d-none");

            if (r.exc || !r.message) {
                $errorText.text(r.exc || "Failed to load gross common expenses.");
                $error.removeClass("d-none");
                return;
            }

            const data = r.message;
            const costCenterLabel = selectedCostCenter ? $("#gross_common_cost_center_filter option:selected").text().replace("•", "").trim() : "All Common Cost Centers";
            $subtitle.text(`${costCenterLabel} • ${data.billing_month || data.from_date + " to " + data.to_date}`);
            $footerInfo.text(`Financial Year: ${activeFy || "-"} | Period: ${data.from_date} to ${data.to_date}`);

            renderGrossCommonExpensesTable(data);
        },
        error: function (err) {
            $loader.addClass("d-none");
            $errorText.text(err.message || "An unexpected error occurred while fetching common expenses.");
            $error.removeClass("d-none");
        }
    });
}

function renderGrossCommonExpensesTable(data) {
    const $tableWrapper = $("#modal-gross-common-table-wrapper");
    const $tbody = $("#gross-common-tbody").empty();
    const $cards = $("#gross-common-cards").empty();
    const $grandTotal = $("#gross-common-grand-total");
    const $empty = $("#modal-gross-common-empty");
    const entries = data.entries || [];

    if (entries.length === 0) {
        $empty.removeClass("d-none");
        $tableWrapper.addClass("d-none");
        $grandTotal.text(data.formatted_grand_total_gross || "₹ 0.00");
        return;
    }

    entries.forEach(function (row) {
        const typeBadge = row.root_type === "Income" 
            ? `<span class="badge badge-success px-1 py-0 ml-1 small">Income</span>` 
            : "";

        // Desktop Table Row
        $tbody.append(`
            <tr>
                <td>
                    <div class="font-weight-bold text-dark">
                        ${frappe.utils.escape_html(row.account_name || row.account)}
                        ${typeBadge}
                    </div>
                    <div class="small text-muted font-monospace">${frappe.utils.escape_html(row.account)}</div>
                </td>
                <td class="text-right font-weight-bold text-dark">
                    ${row.formatted_gross_debit}
                </td>
            </tr>
        `);

        // Mobile Ledger Card: Left = Expense Account, Right = Total Booked Amount (bold)
        $cards.append(`
            <div class="app-card mb-2 p-3 bg-white border rounded shadow-sm">
                <div class="d-flex justify-content-between align-items-center">
                    <div class="pr-2 text-truncate">
                        <div class="font-weight-bold text-dark text-truncate" style="font-size: 0.9rem;">
                            ${frappe.utils.escape_html(row.account_name || row.account)}
                            ${typeBadge}
                        </div>
                        <div class="small text-muted text-truncate font-monospace" style="font-size: 0.75rem;">
                            ${frappe.utils.escape_html(row.account)}
                        </div>
                    </div>
                    <div class="text-right flex-shrink-0 font-weight-bold text-dark h6 mb-0">
                        ${row.formatted_gross_debit}
                    </div>
                </div>
            </div>
        `);
    });

    $grandTotal.text(data.formatted_grand_total_gross || "₹ 0.00");
    $tableWrapper.removeClass("d-none");
    $tableWrapper.find(".table-responsive").removeClass("d-none").addClass("d-none d-md-block");
    $cards.removeClass("d-none").addClass("d-block d-md-none");
}

