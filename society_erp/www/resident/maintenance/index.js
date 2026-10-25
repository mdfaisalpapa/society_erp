frappe.ready(function () {
  const API = "society_erp.api.maintenance_portal.";
  let currentStatus = "Active";
  let currentStart = 0;
  const pageLength = 10;
  let currentTotal = 0;

  function alertMessage(message, kind = "info") {
    $("#maintenance-alert").empty().append(
      $("<div>").addClass("alert alert-" + kind).text(message)
    );
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function call(method, args) {
    return new Promise((resolve, reject) => {
      frappe.call({
        method: API + method,
        args: args || {},
        callback: function (r) {
          if (r && !r.exc && r.message !== undefined) resolve(r.message);
          else reject(new Error((r && r._server_messages) || "The request failed."));
        },
        error: function (err) {
          reject(err || new Error("The request failed."));
        }
      });
    });
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      if (!file) return resolve(null);
      if (!/^image\/(jpeg|png|gif|webp)$/.test(file.type)) {
        return reject(new Error("Please choose a JPG, PNG, GIF or WEBP image."));
      }
      if (file.size > 5 * 1024 * 1024) return reject(new Error("Image must be smaller than 5 MB."));
      const reader = new FileReader();
      reader.onload = () => resolve({
        data: String(reader.result).split(",")[1],
        name: file.name
      });
      reader.onerror = () => reject(new Error("Could not read the selected image."));
      reader.readAsDataURL(file);
    });
  }

  function makeButton(label, css, attrs) {
    const b = $("<button type='button'>").addClass("btn btn-sm " + css).text(label);
    Object.keys(attrs || {}).forEach(k => b.attr(k, attrs[k]));
    return b;
  }

  function renderTickets(result) {
    const tickets = result.tickets || [];
    currentTotal = Number(result.total || 0);
    $("#ticket-count").text(currentTotal + " ticket(s)");
    $("#ticket-page-label").text("Page " + (Math.floor(currentStart / pageLength) + 1));
    $("#tickets-prev").prop("disabled", currentStart <= 0);
    $("#tickets-next").prop("disabled", currentStart + pageLength >= currentTotal);

    const tbody = $("#ticket-list").empty();
    if (!tickets.length) {
      tbody.append($("<tr>").append($("<td colspan='5'>").addClass("text-center text-muted py-4").text("No tickets found for this view.")));
      return;
    }

    tickets.forEach(t => {
      const idCell = $("<td>").append($("<strong>").text(t.name))
        .append($("<br>")).append($("<small>").addClass("text-muted").text((t.creation || "").slice(0, 10)));
      const desc = $("<td>").text(t.description || "");
      if (t.photo) desc.append($("<br>")).append($("<a>").attr({ href: t.photo, target: "_blank", rel: "noopener" }).text("View photo"));
      const status = $("<td>").append($("<span>").addClass("badge badge-" +
        (["Open", "Pending"].includes(t.status) ? "warning" :
         ["Assigned", "In Progress"].includes(t.status) ? "info" : "success")).text(t.status || "Unknown"));
      const actions = $("<td>").append(makeButton("Details", "btn-outline-primary mr-1", { "data-ticket-view": t.name }));
      tbody.append($("<tr>").append(idCell, $("<td>").text(t.category || ""), desc, status, actions));
    });
  }

  async function loadTickets() {
    $("#ticket-list").empty().append($("<tr>").append($("<td colspan='5'>").addClass("text-center").text("Loading tickets…")));
    try {
      const result = await call("get_tickets", { status: currentStatus, start: currentStart, page_length: pageLength });
      renderTickets(result);
    } catch (e) {
      $("#ticket-list").empty().append($("<tr>").append($("<td colspan='5'>").addClass("text-danger").text("Unable to load tickets. Please refresh or contact the Estate Office.")));
      alertMessage("Unable to load maintenance tickets.", "danger");
    }
  }

  function renderDetails(t) {
    const body = $("#ticket-details-body").empty();
    body.append($("<p>").append($("<strong>").text("Category: ")).append(document.createTextNode(t.category || "-")));
    body.append($("<p>").append($("<strong>").text("Status: ")).append(document.createTextNode(t.status || "-")));
    body.append($("<p>").append($("<strong>").text("Raised: ")).append(document.createTextNode((t.creation || "").slice(0, 19))));
    body.append($("<h6>").text("Description"));
    body.append($("<p>").text(t.description || "-"));

    const files = t.attachments || [];
    if (t.photo) files.unshift({ file_name: "Ticket photo", file_url: t.photo });
    if (files.length) {
      body.append($("<h6>").text("Attachments"));
      const list = $("<ul>");
      files.forEach(f => {
        if (f.file_url) list.append($("<li>").append($("<a>").attr({ href: f.file_url, target: "_blank", rel: "noopener" }).text(f.file_name || "View attachment")));
      });
      body.append(list);
    }

    body.append($("<hr>"), $("<h6>").text("Comments and updates"));
    const comments = t.comments || [];
    if (!comments.length) body.append($("<p>").addClass("text-muted").text("No comments yet."));
    comments.forEach(c => {
      body.append($("<div>").addClass("border rounded p-2 mb-2")
        .append($("<div>").addClass("small text-muted").text((c.comment_by || "User") + " · " + (c.creation || "").slice(0, 16)))
        .append($("<div>").text(c.content || "")));
    });

    const commentBox = $("<textarea>").addClass("form-control mb-2").attr({ id: "ticket-comment", rows: 2, maxlength: 3000, placeholder: "Add a comment or update…" });
    body.append($("<label for='ticket-comment'>").text("Add comment"), commentBox);
    body.append(makeButton("Add Comment", "btn-outline-primary mr-2", { id: "ticket-add-comment" }));

    if (["Open", "Assigned", "Pending", "In Progress"].includes(t.status)) {
      body.append(makeButton("Mark Resolved", "btn-success mr-2", { id: "ticket-close" }));
      body.append(makeButton("Attach Photo", "btn-outline-secondary", { id: "ticket-add-photo" }));
      body.append($("<input type='file'>").attr({ id: "ticket-photo-input", accept: "image/jpeg,image/png,image/gif,image/webp" }).addClass("d-none"));
    } else if (["Resolved", "Closed"].includes(t.status)) {
      body.append($("<div>").addClass("form-group mt-3")
        .append($("<label for='ticket-reopen-reason'>").text("Reason for reopening (required)"))
        .append($("<textarea>").addClass("form-control").attr({ id: "ticket-reopen-reason", rows: 2, maxlength: 3000 })));
      body.append(makeButton("Reopen Ticket", "btn-warning mt-2", { id: "ticket-reopen" }));
    }
    $("#ticketDetailsModal").data("ticket-name", t.name).modal("show");
  }

  $(document).on("click", "[data-ticket-view]", async function () {
    const name = $(this).attr("data-ticket-view");
    $("#ticket-details-body").empty().text("Loading ticket details…");
    $("#ticketDetailsModal").data("ticket-name", name).modal("show");
    try {
      const t = await call("get_ticket_details", { ticket_name: name });
      renderDetails(t);
    } catch (e) {
      $("#ticket-details-body").text("Could not load this ticket.");
    }
  });

  $(document).on("click", ".ticket-tab", function () {
    $(".ticket-tab").removeClass("active");
    $(this).addClass("active");
    currentStatus = $(this).data("status");
    currentStart = 0;
    loadTickets();
  });
  $("#tickets-prev").on("click", function () { currentStart = Math.max(0, currentStart - pageLength); loadTickets(); });
  $("#tickets-next").on("click", function () { if (currentStart + pageLength < currentTotal) { currentStart += pageLength; loadTickets(); } });

  $("#create-ticket-form").on("submit", async function (e) {
    e.preventDefault();
    const button = $("#ticket-submit-btn");
    button.prop("disabled", true).text("Submitting…");
    try {
      const file = $("#ticket_photo")[0].files[0];
      const photo = await fileToBase64(file);
      const result = await call("create_ticket", {
        category: $("#ticket_category").val(),
        description: $("#ticket_description").val(),
        photo_data: photo ? photo.data : null,
        photo_name: photo ? photo.name : null
      });
      $("#createTicketModal").modal("hide");
      this.reset();
      alertMessage((result && result.message) || "Ticket created successfully.", "success");
      currentStatus = "Active"; currentStart = 0;
      $(".ticket-tab").removeClass("active").filter('[data-status="Active"]').addClass("active");
      await loadTickets();
    } catch (err) {
      alertMessage(err.message || "Could not create ticket.", "danger");
    } finally {
      button.prop("disabled", false).text("Submit Ticket");
    }
  });

  $(document).on("click", "#ticket-add-comment", async function () {
    const name = $("#ticketDetailsModal").data("ticket-name");
    const comment = $("#ticket-comment").val();
    const button = $(this).prop("disabled", true);
    try {
      await call("add_comment", { ticket_name: name, comment: comment });
      const t = await call("get_ticket_details", { ticket_name: name });
      renderDetails(t);
      alertMessage("Comment added.", "success");
    } catch (e) { alertMessage(e.message || "Could not add comment.", "danger"); }
    finally { button.prop("disabled", false); }
  });

  $(document).on("click", "#ticket-close", async function () {
    const name = $("#ticketDetailsModal").data("ticket-name");
    if (!confirm("Mark this ticket as resolved?")) return;
    try {
      const r = await call("close_ticket", { ticket_name: name });
      $("#ticketDetailsModal").modal("hide");
      alertMessage(r.message || "Ticket resolved.", "success");
      await loadTickets();
    } catch (e) { alertMessage(e.message || "Could not resolve ticket.", "danger"); }
  });

  $(document).on("click", "#ticket-reopen", async function () {
    const name = $("#ticketDetailsModal").data("ticket-name");
    const reason = $("#ticket-reopen-reason").val();
    try {
      const r = await call("reopen_ticket", { ticket_name: name, reason: reason });
      $("#ticketDetailsModal").modal("hide");
      alertMessage(r.message || "Ticket reopened.", "success");
      currentStatus = "Active"; currentStart = 0;
      $(".ticket-tab").removeClass("active").filter('[data-status="Active"]').addClass("active");
      await loadTickets();
    } catch (e) { alertMessage(e.message || "Could not reopen ticket.", "danger"); }
  });

  $(document).on("click", "#ticket-add-photo", function () { $("#ticket-photo-input").trigger("click"); });
  $(document).on("change", "#ticket-photo-input", async function () {
    const input = this;
    if (!input.files || !input.files[0]) return;
    const name = $("#ticketDetailsModal").data("ticket-name");
    try {
      const photo = await fileToBase64(input.files[0]);
      const r = await call("add_photo", { ticket_name: name, photo_data: photo.data, photo_name: photo.name });
      alertMessage(r.message || "Photo attached.", "success");
      renderDetails(await call("get_ticket_details", { ticket_name: name }));
    } catch (e) { alertMessage(e.message || "Photo upload failed.", "danger"); }
    finally { $(input).val(""); }
  });

  loadTickets();
});
