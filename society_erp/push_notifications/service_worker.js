self.addEventListener("push", event => {
    console.log("[KVC3 Push] Push event received");

    let data = {};

    try {
        data = event.data ? event.data.json() : {};
    } catch (error) {
        console.warn("[KVC3 Push] Payload is not JSON", error);
        data = {
            title: "KVC3 Association",
            body: event.data
                ? event.data.text()
                : "You have a new notification."
        };
    }

    const title = data.title || "KVC3 Association";

    event.waitUntil(
        self.registration.showNotification(title, {
            body: data.body || "You have a new notification.",
            icon: "/assets/society_erp/images/icon-192.png",
            badge: "/assets/society_erp/images/icon-192.png",
            data: { url: data.url || "/resident/" },
            tag: data.tag || "kvc3-notification"
        }).then(() => {
            console.log("[KVC3 Push] Notification displayed");
        }).catch(error => {
            console.error("[KVC3 Push] showNotification failed", error);
            throw error;
        })
    );
});
self.addEventListener("notificationclick", event => {
    event.notification.close();

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
