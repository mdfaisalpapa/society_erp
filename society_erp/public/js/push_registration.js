(() => {
    "use strict";

    if (!location.pathname.startsWith("/resident/")) return;
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;

    const api = (method, args = {}) =>
    frappe.call({
        method: `society_erp.push_notifications.api.${method}`,
        httpMethod: "POST",
        args
    });

    function decodeKey(base64) {
        const padded = base64 + "=".repeat((4 - base64.length % 4) % 4);
        const raw = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
        return Uint8Array.from(raw, char => char.charCodeAt(0));
    }

    async function enablePush() {
        const permission = await Notification.requestPermission();
        if (permission !== "granted") {
            frappe.msgprint("Notifications were not permitted by the browser.");
            return;
        }

        const config = await frappe.call({
            method: "society_erp.push_notifications.api.get_public_config"
        });
        const publicKey = config.message?.public_key;
        if (!publicKey) throw new Error("The public VAPID key is unavailable.");

        const registration = await navigator.serviceWorker.register(
            "/api/method/society_erp.push_notifications.api.service_worker",
            { scope: "/resident/" }
        );

        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: decodeKey(publicKey)
        });

        await api("save_subscription", {
            subscription: JSON.stringify(subscription.toJSON())
        });

        frappe.show_alert({
            message: "Notifications enabled on this device.",
            indicator: "green"
        });
        renderStatus(true);
    }

    async function disablePush() {
        const registration = await navigator.serviceWorker.getRegistration("/resident/");
        const subscription = await registration?.pushManager.getSubscription();

        if (subscription) {
            await api("remove_subscription", {
                endpoint: subscription.endpoint
            });
            await subscription.unsubscribe();
        }

        frappe.show_alert({
            message: "Notifications disabled on this device.",
            indicator: "green"
        });
        renderStatus(false);
    }

    function renderStatus(enabled) {
        let panel = document.getElementById("resident-push-controls");
        if (!panel) {
            panel = document.createElement("section");
            panel.id = "resident-push-controls";
            panel.className = "card p-3 my-3";
            panel.innerHTML = `
                <h5>Notifications</h5>
                <p class="mb-2">Receive updates from the association on this device.</p>
                <div class="d-flex flex-wrap gap-2">
                    <button type="button" class="btn btn-primary" id="resident-push-enable">
                        Enable notifications
                    </button>
                    <button type="button" class="btn btn-secondary" id="resident-push-disable">
                        Disable on this device
                    </button>
                    <button type="button" class="btn btn-outline-secondary" id="resident-push-test">
                        Send test
                    </button>
                </div>`;
            const container = document.querySelector(".container") || document.body;
            container.prepend(panel);

            panel.querySelector("#resident-push-enable").addEventListener("click", () =>
                enablePush().catch(error => {
                    console.error("Enable push failed", error);
                    frappe.msgprint("Could not enable notifications. Check the browser permission and server configuration.");
                })
            );

            panel.querySelector("#resident-push-disable").addEventListener("click", () =>
                disablePush().catch(error => {
                    console.error("Disable push failed", error);
                    frappe.msgprint("Could not disable notifications.");
                })
            );

            panel.querySelector("#resident-push-test").addEventListener("click", async () => {
                try {
                    const result = await api("send_test_notification");
                    frappe.msgprint(
                        `Test notifications sent: ${result.message.sent}; failed: ${result.message.failed}.`
                    );
                } catch (error) {
                    console.error("Test push failed", error);
                    frappe.msgprint("Test notification failed. Check VAPID configuration and server logs.");
                }
            });
        }

        panel.dataset.enabled = String(enabled);
    }

    async function initialize() {
        try {
            const registration = await navigator.serviceWorker.getRegistration("/resident/");
            const subscription = await registration?.pushManager.getSubscription();
            renderStatus(Boolean(subscription));
        } catch (error) {
            console.error("Push initialization failed", error);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initialize, { once: true });
    } else {
        initialize();
    }
})();
