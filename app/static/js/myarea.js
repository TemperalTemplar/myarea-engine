/**
 * MyArea — Core JavaScript
 * Handles: SocketIO real-time notifications, stat refresh, HTMX helpers
 */

(function () {
  "use strict";

  // ── SocketIO connection ──────────────────────────────────
  let socket = null;

  function initSocket() {
    if (typeof io === "undefined") return;

    socket = io({
      transports: ["websocket", "polling"],
      reconnectionAttempts: 5,
      reconnectionDelay: 2000,
    });

    socket.on("connect", () => {
      console.debug("[MyArea] Socket connected:", socket.id);
    });

    socket.on("notification", (data) => {
      showToast(data.title, data.message, data.type || "info");
      incrementNotifBadge();
    });

    socket.on("stat_update", (data) => {
      updateStatDisplay(data);
    });

    socket.on("disconnect", () => {
      console.debug("[MyArea] Socket disconnected");
    });
  }

  // ── Toast notifications ──────────────────────────────────
  function showToast(title, message, type = "info") {
    let container = document.getElementById("notif-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "notif-container";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = "ma-toast";

    const icons = { attack: "⚔️", property: "🏢", system: "🔔", gang: "🤝", info: "💬" };
    const icon = icons[type] || icons.info;

    toast.innerHTML = `
      <div style="display:flex; gap:0.5rem; align-items:flex-start;">
        <span style="font-size:1.1rem;">${icon}</span>
        <div>
          <div style="font-weight:500; color:#e8ecf0; margin-bottom:2px;">${escHtml(title)}</div>
          <div style="color:var(--ma-text-muted);">${escHtml(message)}</div>
        </div>
      </div>`;

    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5500);
  }

  // ── Notification badge ───────────────────────────────────
  function incrementNotifBadge() {
    const badge = document.getElementById("notif-badge");
    if (!badge) return;
    const current = parseInt(badge.textContent, 10) || 0;
    badge.textContent = current + 1;
    badge.classList.remove("d-none");
  }

  // ── Stat display update ──────────────────────────────────
  function updateStatDisplay(data) {
    const fields = ["energy", "stamina", "health", "cash"];
    fields.forEach((field) => {
      if (data[field] !== undefined) {
        const el = document.getElementById(`stat-${field}`);
        if (el) {
          if (field === "cash") {
            el.textContent = Number(data[field]).toLocaleString();
          } else {
            el.textContent = data[field];
          }
        }
      }
    });
  }

  // ── Stat progress bars ───────────────────────────────────
  function updateProgressBars() {
    document.querySelectorAll("[data-stat-bar]").forEach((bar) => {
      const current = parseInt(bar.dataset.current, 10);
      const max = parseInt(bar.dataset.max, 10);
      const fill = bar.querySelector(".fill");
      if (fill && max > 0) {
        fill.style.width = Math.min(100, (current / max) * 100) + "%";
      }
    });
  }

  // ── HTMX helpers ─────────────────────────────────────────
  document.addEventListener("htmx:afterRequest", function (evt) {
    // Re-init Bootstrap tooltips after HTMX swaps
    initTooltips();
  });

  document.addEventListener("htmx:responseError", function (evt) {
    const status = evt.detail.xhr.status;
    if (status === 403) {
      showToast("Error", "Not enough energy or stamina.", "system");
    } else if (status === 429) {
      showToast("Slow down", "Too many requests. Take a breath.", "system");
    }
  });

  // ── Bootstrap tooltips ───────────────────────────────────
  function initTooltips() {
    const tooltipEls = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipEls.forEach((el) => {
      if (!el._bsTooltip) {
        new bootstrap.Tooltip(el);
      }
    });
  }

  // ── Confirm dialogs for dangerous actions ────────────────
  document.addEventListener("click", function (e) {
    const btn = e.target.closest("[data-confirm]");
    if (!btn) return;
    const msg = btn.dataset.confirm || "Are you sure?";
    if (!confirm(msg)) e.preventDefault();
  });

  // ── Format cash values ───────────────────────────────────
  function formatCash(amount) {
    if (amount >= 1_000_000) return "$" + (amount / 1_000_000).toFixed(1) + "M";
    if (amount >= 1_000)     return "$" + (amount / 1_000).toFixed(1) + "K";
    return "$" + amount.toLocaleString();
  }

  // ── Escape HTML ──────────────────────────────────────────
  function escHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  // ── Init on DOM ready ────────────────────────────────────
  document.addEventListener("DOMContentLoaded", function () {
    initSocket();
    updateProgressBars();
    initTooltips();
  });

  // Expose utilities globally for inline use
  window.MyArea = { showToast, formatCash, updateStatDisplay };
})();
