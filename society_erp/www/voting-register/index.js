(() => {
    "use strict";

    const API = "/api/method/society_erp.society_erp.doctype.voting_poll.voting_api.";

    const el = {
        error: document.getElementById("register-error"),
        verification: document.getElementById("register-verification"),
        loading: document.getElementById("register-loading"),
        list: document.getElementById("register-list"),
        detail: document.getElementById("register-detail"),
        title: document.getElementById("register-title"),
        meta: document.getElementById("register-meta"),
        hash: document.getElementById("register-hash"),
        search: document.getElementById("receipt-search"),
        rows: document.getElementById("register-rows"),
        csv: document.getElementById("register-csv"),
        pdf: document.getElementById("register-pdf"),
        back: document.getElementById("register-back")
    };

    let currentPoll = null;
    let currentRows = [];

    function showError(message) {
        el.error.textContent = message;
        el.error.classList.remove("d-none");
    }

    function showVerification(result) {
        const styles = {
            verified: "alert-success",
            not_found: "alert-warning",
            register_not_published: "alert-info",
            invalid_request: "alert-warning",
            hash_mismatch: "alert-danger"
        };
        el.verification.className = `alert ${styles[result.status] || "alert-secondary"}`;
        el.verification.textContent =
            result.message || "Receipt verification could not be completed.";
    }

    function hideVerification() {
        el.verification.className = "alert d-none";
        el.verification.textContent = "";
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

    function claimsFrom(params) {
        return {
            receipt_code: params.get("receipt"),
            ballot_hash: params.get("hash"),
            option_b64: params.get("option"),
            voting_weight: params.get("weight")
        };
    }

    function hasClaims(params) {
        return ["receipt", "hash", "option", "weight"]
            .some(key => params.has(key));
    }

    async function verifyReceipt(poll, claims) {
        const result = await call("verify_published_ballot_receipt", {
            poll_name: poll || null,
            receipt_code: claims.receipt_code || null,
            ballot_hash: claims.ballot_hash || null,
            option_b64: claims.option_b64 || null,
            voting_weight: claims.voting_weight || null
        });
        showVerification(result);
        return result;
    }

    function renderRows(search = "", highlightReceipt = "") {
        const term = String(search || "").trim().toLowerCase();
        const highlight = String(highlightReceipt || "").trim().toLowerCase();
        el.rows.replaceChildren();

        currentRows.forEach(ballot => {
            const values = [
                ballot.receipt_code,
                ballot.selected_option_label,
                Number(ballot.voting_weight || 0).toFixed(3),
                ballot.ballot_hash
            ];
            if (term && !values.some(value => String(value || "").toLowerCase().includes(term))) {
                return;
            }

            const tr = document.createElement("tr");
            if (highlight && String(ballot.receipt_code).toLowerCase() === highlight) {
                tr.classList.add("matched-ballot");
            }

            values.forEach(value => {
                const td = document.createElement("td");
                td.textContent = value == null ? "" : String(value);
                tr.append(td);
            });

            el.rows.append(tr);
        });
    }

    async function openRegister(poll, claims = null) {
        el.error.classList.add("d-none");
        hideVerification();
        el.loading.classList.remove("d-none");

        try {
            // This endpoint validates the complete register before returning rows.
            const data = await call("get_published_ballot_register", {
                poll_name: poll
            });

            currentPoll = poll;
            currentRows = data.ballots || [];
            el.title.textContent = data.poll_title || data.poll;
            el.meta.textContent =
                `${data.poll} · Published ${data.published_on || ""} · ${data.ballot_count} ballot(s)`;
            el.hash.textContent = data.register_hash || "";
            const receipt = claims ? claims.receipt_code || "" : "";
            el.search.value = "";
            renderRows("", receipt);

            el.loading.classList.add("d-none");
            el.list.classList.add("d-none");
            el.detail.classList.remove("d-none");

            const params = new URLSearchParams(window.location.search);
            params.set("poll", poll);
            if (claims) {
                const values = {
                    receipt: claims.receipt_code,
                    hash: claims.ballot_hash,
                    option: claims.option_b64,
                    weight: claims.voting_weight
                };
                for (const [key, value] of Object.entries(values)) {
                    if (value) params.set(key, value);
                    else params.delete(key);
                }
            } else {
                ["receipt", "hash", "option", "weight"].forEach(key => params.delete(key));
            }
            history.replaceState(null, "", `${location.pathname}?${params}`);

            if (claims) {
                await verifyReceipt(poll, claims);
                const match = el.rows.querySelector(".matched-ballot");
                if (match) match.scrollIntoView({behavior: "smooth", block: "center"});
            }
        } catch (error) {
            el.loading.classList.add("d-none");
            if (claims) {
                el.title.textContent = poll || "Receipt verification";
                el.list.classList.add("d-none");
                el.detail.classList.remove("d-none");
                try {
                    await verifyReceipt(poll, claims);
                } catch (_) {
                    showError(error.message);
                }
            } else {
                showError(error.message);
            }
        }
    }

    async function loadRegisters() {
        const params = new URLSearchParams(window.location.search);
        const poll = params.get("poll");
        const receiptClaimsPresent = hasClaims(params);

        try {
            const registers = await call("get_published_ballot_registers");
            el.loading.classList.add("d-none");
            el.list.replaceChildren();

            if (!registers.length) {
                el.list.textContent = "No ballot registers have been published.";
            } else {
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
            }

            if (poll) {
                await openRegister(poll, receiptClaimsPresent ? claimsFrom(params) : null);
            } else if (receiptClaimsPresent) {
                await verifyReceipt(null, claimsFrom(params));
            }
        } catch (error) {
            el.loading.classList.add("d-none");
            if (receiptClaimsPresent) {
                try {
                    await verifyReceipt(poll, claimsFrom(params));
                } catch (verificationError) {
                    showError(verificationError.message);
                }
            } else {
                showError(error.message);
            }
        }
    }

    el.search.addEventListener("input", () => renderRows(el.search.value));

    el.back.addEventListener("click", () => {
        currentPoll = null;
        currentRows = [];
        el.error.classList.add("d-none");
        hideVerification();
        showRegisterList();
        history.replaceState(null, "", location.pathname);
    });

    el.csv.addEventListener("click", () => {
        if (!currentPoll) return;
        window.location.href =
            API + "download_published_ballot_register?poll_name="
            + encodeURIComponent(currentPoll);
    });

    el.pdf.addEventListener("click", () => {
        if (!currentPoll) return;
        window.location.href =
            API + "download_published_ballot_register_pdf?poll_name="
            + encodeURIComponent(currentPoll);
    });

    loadRegisters();
})();
