self.addEventListener("install", event => {
    // Activate immediately upon update
    self.skipWaiting();
});

self.addEventListener("activate", event => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener("push", event => {
    console.log("[KVC3 Push] Push event received");

    let data = {};

    try {
        data = event.data ? event.data.json() : {};
    } catch (error) {
        console.warn("[KVC3 Push] Payload is not JSON", error);
        data = {
            title: "KVC3 Urgent Notice",
            body: event.data ? event.data.text() : "Important notice from KVC3 Association."
        };
    }

    const title = data.title || "KVC3 Urgent Notice";

    // Call-like vibration pattern: [vibrate, pause, vibrate, pause...]
    const ringVibration = [600, 250, 600, 250, 600, 250, 600, 250, 1000];

    const notificationOptions = {
        body: data.body || "Incoming announcement from KVC3.",
        icon: "/assets/society_erp/images/icon-192.png",
        badge: "/assets/society_erp/images/icon-192.png",
        data: { url: data.url || "/resident/" },
        tag: data.tag || "kvc3-urgent-call",
        // Stays on screen permanently until user explicitly acts on it
        requireInteraction: true,
        // Trigger sound & vibration again even if a previous notification is present
        renotify: true,
        vibrate: ringVibration,
        silent: false
    };

    // Forward push message to all open tabs so they can play a continuous audio ringtone
    const broadcastToClients = self.clients.matchAll({
        type: "window",
        includeUncontrolled: true
    }).then(clients => {
        clients.forEach(client => {
            client.postMessage({
                type: "KVC3_PLAY_LOUD_ALERT",
                title: title,
                body: data.body
            });
        });
    });

    event.waitUntil(
        Promise.all([
            self.registration.showNotification(title, notificationOptions),
            broadcastToClients
        ]).then(() => {
            console.log("[KVC3 Push] Persistent notification & audio broadcast completed");
        }).catch(error => {
            console.error("[KVC3 Push] showNotification failed", error);
            throw error;
        })
    );
});

self.addEventListener("notificationclick", event => {
    event.notification.close();

    // Tell any open tabs to stop ringing
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(clients => {
        clients.forEach(client => {
            client.postMessage({ type: "KVC3_STOP_LOUD_ALERT" });
        });
    });

    const target = new URL(
        event.notification.data?.url || "/resident/",
        self.location.origin
    );

    if (target.origin !== self.location.origin) return;

    event.waitUntil((async () => {
        const windows = await self.clients.matchAll({
            type: "window",
            includeUncontrolled: true
        });

        for (const client of windows) {
            if (new URL(client.url).origin === self.location.origin) {
                await client.navigate(target.href);
                return client.focus();
            }
        }

        return self.clients.openWindow(target.href);
    })());
});
