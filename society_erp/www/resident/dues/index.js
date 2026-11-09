/**
 * My Dues - Resident Portal
 * Frontend client logic and payment gateway integration hooks.
 */

frappe.ready(function () {
    // 1. Initialize Event Listeners for Online Payment Actions
    setupPaymentHandlers();
});

/**
 * Attaches click event handlers to payment buttons for future payment gateway integration.
 */
function setupPaymentHandlers() {
    // Total Outstanding Payment Handler
    $(document).on("click", ".btn-pay-dues", function (e) {
        e.preventDefault();
        const totalAmount = parseFloat($(this).data("amount") || 0);

        if (totalAmount <= 0) {
            frappe.msgprint({
                title: __("No Dues"),
                indicator: "green",
                message: __("You do not have any pending dues to pay.")
            });
            return;
        }

        // Placeholder for Payment Gateway (e.g., Razorpay, Frappe Payments, Stripe, Paytm)
        frappe.confirm(
            __(
                "Proceed to initiate online payment for your total outstanding balance of <b>{0}</b>?",
                [format_currency(totalAmount)]
            ),
            function () {
                initiatePaymentGateway({
                    amount: totalAmount,
                    invoice: null,
                    description: "Total Society Maintenance Dues Clearance"
                });
            }
        );
    });

    // Single Invoice Payment Handler
    $(document).on("click", ".btn-pay-invoice", function (e) {
        e.preventDefault();
        const invoiceName = $(this).data("invoice");
        const amount = parseFloat($(this).data("amount") || 0);

        frappe.confirm(
            __(
                "Proceed to pay <b>{0}</b> for Invoice <b>{1}</b>?",
                [format_currency(amount), invoiceName]
            ),
            function () {
                initiatePaymentGateway({
                    amount: amount,
                    invoice: invoiceName,
                    description: __("Payment for Invoice {0}", [invoiceName])
                });
            }
        );
    });
}

/**
 * Modular helper to trigger the Payment Gateway integration.
 * Hook this function up to your society payment gateway endpoint or Frappe Payments.
 *
 * @param {Object} paymentData - { amount, invoice, description }
 */
function initiatePaymentGateway(paymentData) {
    frappe.show_alert({
        message: __("Preparing secure payment checkout..."),
        indicator: "blue"
    });

    /*
     * Example future server call to create an order or checkout session:
     *
     * frappe.call({
     *     method: "society_erp.api.payments.create_checkout_session",
     *     args: {
     *         invoice_name: paymentData.invoice,
     *         amount: paymentData.amount
     *     },
     *     freeze: true,
     *     freeze_message: __("Connecting to Payment Gateway..."),
     *     callback: function(r) {
     *         if (r.message && r.message.checkout_url) {
     *             window.location.href = r.message.checkout_url;
     *         } else if (r.message && r.message.razorpay_order_id) {
     *             // Open Razorpay modal
     *             // openRazorpayModal(r.message);
     *         }
     *     }
     * });
     */

    frappe.msgprint({
        title: __("Payment Gateway"),
        indicator: "blue",
        message: __(
            "Payment initiation triggered for <b>{0}</b>.<br><br>" +
            "Connect this handler to your backend payment gateway method (e.g. Razorpay, Paytm, or Frappe Payments).",
            [paymentData.invoice ? paymentData.invoice : "Total Outstanding"]
        )
    });
}
