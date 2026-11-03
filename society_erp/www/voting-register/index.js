(() => {
    "use strict";

    const API = "/api/method/society_erp.society_erp.doctype.voting_poll.voting_api.";

    const el = {
        error: document.getElementById("register-error"),
        loading: document.getElementById("register-loading"),
        list: document.getElementById("register-list"),
        detail: document.getElementById("register-detail"),
        title: document.getElementById("register-title"),
        meta: document.getElementById("register-meta"),
        hash: document.getElementById("register-hash"),
        search: document.getElementById("receipt-search"),
        rows: document.getElementById("register-rows"),
        csv: document.getElementById("register-csv"),
        back: document.getElementById("register-back")
    };

    let currentPoll = null;
    let currentRows = [];

    function showError(message) {
        el.error.textContent = message;
        el.error.classList.remove("d-none");
    }

    async function call(method, args = {}) {
        const response = await fetch(API + method, {
            method: "POST",
            credentials: "same-origin",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(args)
        });

        const payload = await response.json();
        if (!response.ok || payload.exc) {
            throw new Error(
                payload._server_messages
                    ? JSON.parse(payload._server_messages)
                        .map(x => JSON.parse(x).message).join("; ")
                    : "The published register could not be loaded."
            );
        }
        return payload.message;
    }

    function showRegisterList() {
        el.detail.classList.add("d-none");
        el.list.classList.remove("d-none");
    }

    async function loadRegisters() {
        try {
            const registers = await call("get_published_ballot_registers");
            el.loading.classList.add("d-none");
            el.list.replaceChildren();

            if (!registers.length) {
                el.list.textContent = "No ballot registers have been published.";
                return;
            }

            registers.forEach(item => {
                const card = document.createElement("div");
                card.className = "card mb-2";
                const body = document.createElement("div");
                body.className = "card-body";

                const heading = document.createElement("h5");
                heading.textContent = item.poll_title || item.name;

                const meta = document.createElement("p");
                meta.className = "small text-muted";
                meta.textContent =
                    `${item.name} · ${item.ballot_count} ballot(s) · Published ${item.published_on || ""}`;

                const button = document.createElement("button");
                button.type = "button";
                button.className = "btn btn-outline-primary btn-sm";
                button.textContent = "View register";
                button.addEventListener("click", () => openRegister(item.name));

                body.append(heading, meta, button);
                card.append(body);
                el.list.append(card);
            });

            const params = new URLSearchParams(window.location.search);
            const poll = params.get("poll");
            if (poll) {
                await openRegister(poll, params.get("receipt") || "");
            }
        } catch (error) {
            el.loading.classList.add("d-none");
            showError(error.message);
        }
    }

    async function openRegister(poll, receipt = "") {
        el.error.classList.add("d-none");
        el.loading.classList.remove("d-none");

        try {
            // This endpoint verifies the stored SHA-256 before returning rows.
            const data = await call("get_published_ballot_register", {
                poll_name: poll
            });

            currentPoll = poll;
            currentRows = data.ballots || [];

            el.title.textContent = data.poll_title || data.poll;
            el.meta.textContent =
                `${data.poll} · Published ${data.published_on || ""} · ${data.ballot_count} ballot(s)`;
            el.hash.textContent = data.register_hash || "";

            el.search.value = receipt;
            renderRows(receipt);

            el.loading.classList.add("d-none");
            el.list.classList.add("d-none");
            el.detail.classList.remove("d-none");

            const params = new URLSearchParams(window.location.search);
            params.set("poll", poll);
            if (receipt) params.set("receipt", receipt);
            else params.delete("receipt");
            history.replaceState(null, "", `${location.pathname}?${params}`);

            if (receipt) {
                const match = el.rows.querySelector(".matched-ballot");
                if (match) {
                    match.scrollIntoView({behavior: "smooth", block: "center"});
                } else {
                    showError("The receipt code was not found in this published register.");
                }
            }
        } catch (error) {
            el.loading.classList.add("d-none");
            showError(error.message);
        }
    }

    function renderRows(search = "") {
        const term = String(search || "").trim().toLowerCase();
        el.rows.replaceChildren();

        currentRows.forEach(ballot => {
            const tr = document.createElement("tr");
            if (term && String(ballot.receipt_code).toLowerCase() === term) {
                tr.classList.add("matched-ballot");
            }

            [
                ballot.receipt_code,
                ballot.selected_option_label,
                Number(ballot.voting_weight || 0).toFixed(3),
                ballot.ballot_hash
            ].forEach(value => {
                const td = document.createElement("td");
                td.textContent = value == null ? "" : String(value);
                tr.append(td);
            });

            el.rows.append(tr);
        });
    }

    el.search.addEventListener("input", () => renderRows(el.search.value));

    el.back.addEventListener("click", () => {
        currentPoll = null;
        currentRows = [];
        el.error.classList.add("d-none");
        showRegisterList();
        history.replaceState(null, "", location.pathname);
    });

    el.csv.addEventListener("click", () => {
        if (!currentPoll) return;
        window.location.href =
            API + "download_published_ballot_register?poll_name="
            + encodeURIComponent(currentPoll);
    });

    loadRegisters();
})();
