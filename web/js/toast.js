"use strict";
(function () {
  const region = document.getElementById("toast-region");
  const icons = {success:"✓", warning:"!", error:"×"};
  function show(message, type = "warning", duration = 4200) {
    if (!region || !message) return;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.setAttribute("role", type === "error" ? "alert" : "status");
    const icon = document.createElement("span");
    icon.className = "toast-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = icons[type] || "i";
    const text = document.createElement("span");
    text.className = "toast-text";
    text.textContent = message;
    const close = document.createElement("button");
    close.type = "button";
    close.className = "toast-close";
    close.setAttribute("aria-label", "Dismiss notification");
    close.textContent = "×";
    close.onclick = () => toast.remove();
    toast.append(icon, text, close);
    region.append(toast);
    window.setTimeout(() => toast.remove(), duration);
  }
  window.showToast = show;
  window.confirmToast = function (message) {
    return new Promise(resolve => {
      const toast = document.createElement("div");
      toast.className = "toast toast-warning";
      toast.setAttribute("role", "alertdialog");
      toast.innerHTML = `<span class="toast-icon">!</span><span class="toast-text"></span><button type="button" class="primary">Confirm</button><button type="button" class="toast-close" aria-label="Cancel">×</button>`;
      toast.querySelector(".toast-text").textContent = message;
      const finish = value => { toast.remove(); resolve(value); };
      toast.querySelector(".primary").onclick = () => finish(true);
      toast.querySelector(".toast-close").onclick = () => finish(false);
      region.append(toast);
    });
  };
})();
