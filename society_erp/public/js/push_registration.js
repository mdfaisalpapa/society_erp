(() => {
    "use strict";

    if (!location.pathname.startsWith("/resident")) return;
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;

    // --- Loud Incoming Call Ringer ---
    let ringAudio = null;

    function startLoudPhoneRing() {
        stopLoudPhoneRing();

        try {
            ringAudio = new Audio("/assets/society_erp/sounds/phone-ring.mp3");
            ringAudio.loop = true;
            ringAudio.volume = 1.0;

            const playPromise = ringAudio.play();
            if (playPromise !== undefined) {
                playPromise.catch(err => {
                    console.warn("Audio autoplay blocked by browser policy. User gesture required.", err);
                });
            }
        } catch (e) {
            console.error("Failed to play phone ring audio", e);
        }

        showRingingBanner();
    }

    function stopLoudPhoneRing() {
        if (ringAudio) {
            try {
                ringAudio.pause();
                ringAudio.currentTime = 0;
            } catch (e) {}
            ringAudio = null;
        }
        removeRingingBanner();
    }

    function showRingingBanner() {
        removeRingingBanner();
        const banner = document.createElement("div");
        banner.id = "kvc3-ringing-alert-banner";
        banner.style.cssText = `
            position: fixed;
            top: 24px;
            right: 24px;
            z-index: 999999;
            background: linear-gradient(135deg, #d32f2f, #b71c1c);
            color: #ffffff;
            padding: 16px 22px;
            border-radius: 12px;
            box-shadow: 0 12px 30px rgba(0,0,0,0.45);
            display: flex;
            align-items: center;
            gap: 16px;
            border: 2px solid #ffcdd2;
        `;
        banner.innerHTML = `
            <div style="font-size: 28px; line-height: 1;">📞</div>
            <div>
                <strong style="display:block; font-size:16px; letter-spacing: 0.3px;">KVC3 URGENT ALERT</strong>
                <span style="font-size:13px; opacity: 0.95;">Incoming alert ringing on this device...</span>
            </div>
            <button type="button" class="btn btn-sm btn-light ms-2 px-3 fw-bold" id="kvc3-stop-ringing-btn" style="color: #b71c1c; border-radius: 6px;">
                Silence Ring
            </button>
        `;
        document.body.appendChild(banner);
        document.getElementById("kvc3-stop-ringing-btn")?.addEventListener("click", stopLoudPhoneRing);
    }

    function removeRingingBanner() {
        document.getElementById("kvc3-ringing-alert-banner")?.remove();
    }

    // Listen for push events broadcast by Service Worker
    navigator.serviceWorker.addEventListener("message", event => {
        if (event.data?.type === "KVC3_PLAY_LOUD_ALERT") {
            startLoudPhoneRing();
        } else if (event.data?.type === "KVC3_STOP_LOUD_ALERT") {
            stopLoudPhoneRing();
        }
    });

    const api = (method, args = {}) =>
        frappe.call({
            method: `society_erp.push_notifications.api.${method}`,
            httpMethod: "POST",
            args
        });

    function urlBase64ToUint8Array(base64String) {
        const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
        const base64 = (base64String + padding)
            .replace(/-/g, "+")
            .replace(/_/g, "/");

        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);

        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
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

        await navigator.serviceWorker.ready;

        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(publicKey)
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

        stopLoudPhoneRing();

        frappe.show_alert({
            message: "Notifications disabled on this device.",
            indicator: "green"
        });
        renderStatus(false);
    }

    function renderStatus(enabled) {
        // Only render the controls card if the user is on /resident/settings or /resident/profile
        const targetContainer = document.getElementById("push-settings-container");
        if (!targetContainer) {
            // If not on settings or profile page, remove any stray panel from header
            document.getElementById("resident-push-controls")?.remove();
            return;
        }

        let panel = document.getElementById("resident-push-controls");
        if (!panel) {
            panel = document.createElement("section");
            panel.id = "resident-push-controls";
            panel.className = "card p-3 my-3 shadow-sm border";
            panel.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h6 class="mb-0 fw-bold">Push Notifications</h6>
                    <span id="resident-push-badge" class="badge"></span>
                </div>
                <p class="small text-muted mb-2">Receive alerts and announcements from KVC3 on this device.</p>
                <div class="d-flex flex-wrap gap-2">
                    <button type="button" class="btn btn-sm btn-primary" id="resident-push-enable">
                        Enable Notifications
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-danger" id="resident-push-disable">
                        Disable on this device
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-secondary" id="resident-push-test">
                        Send Test Push
                    </button>
                </div>`;
            targetContainer.appendChild(panel);

            panel.querySelector("#resident-push-enable").addEventListener("click", () =>
                enablePush().catch(error => {
                    console.error("Enable push failed", error);
                    frappe.msgprint("Could not enable notifications. Check browser permissions and VAPID setup.");
                })
            );

            panel.querySelector("#resident-push-disable").addEventListener("click", () =>
                disablePush().catch(error => {
                    console.error("Disable push failed", error);
                    frappe.msgprint("Could not disable notifications.");
                })
            );

            panel.querySelector("#resident-push-test").addEventListener("click", async () => {
                startLoudPhoneRing();
                try {
                    const result = await api("send_test_notification");
                    frappe.msgprint(
                        `Test push processed: ${result.message.sent} sent, ${result.message.failed} failed.`
                    );
                } catch (error) {
                    console.error("Test push failed", error);
                    frappe.msgprint("Test notification failed. Check VAPID configuration and server logs.");
                }
            });
        }

        panel.dataset.enabled = String(enabled);
        const badge = panel.querySelector("#resident-push-badge");
        const enableBtn = panel.querySelector("#resident-push-enable");
        const disableBtn = panel.querySelector("#resident-push-disable");
        const testBtn = panel.querySelector("#resident-push-test");

        if (badge) {
            badge.className = `badge ${enabled ? "bg-success text-white" : "bg-secondary text-white"}`;
            badge.textContent = enabled ? "Active" : "Disabled";
        }
        if (enableBtn) enableBtn.style.display = enabled ? "none" : "inline-block";
        if (disableBtn) disableBtn.style.display = enabled ? "inline-block" : "none";
        if (testBtn) testBtn.style.display = enabled ? "inline-block" : "none";
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
