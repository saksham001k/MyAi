"use strict";
(function () {
  const $ = id => document.getElementById(id);
  const maxImageBytes = 20 * 1024 * 1024;
  let currentFile = null;
  function context() {
    return document.body.dataset.mode === "studio" ? "image" : document.body.dataset.mode === "docs" ? "document" : "project";
  }
  function showChip(file) {
    const container = $("file-ingestion"), chips = $("file-chips");
    if (!container || !chips) return;
    chips.replaceChildren();
    const chip = document.createElement("div");
    chip.className = "file-chip";
    if (file.type.startsWith("image/")) {
      const image = document.createElement("img");
      image.alt = "";
      image.width = 22; image.height = 22;
      image.src = URL.createObjectURL(file);
      chip.append(image);
    }
    const name = document.createElement("span");
    name.className = "file-chip-name";
    name.textContent = file.name;
    const size = document.createElement("small");
    size.textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB`;
    const remove = document.createElement("button");
    remove.type = "button"; remove.className = "file-chip-remove";
    remove.setAttribute("aria-label", `Remove ${file.name}`); remove.textContent = "×";
    remove.onclick = () => { currentFile = null; chips.replaceChildren(); container.hidden = true; window.dispatchEvent(new CustomEvent("file-ingestion-cleared")); };
    chip.append(name, size, remove); chips.append(chip); container.hidden = false;
  }
  function accept(file) {
    if (!file) return;
    const kind = context();
    const image = ["image/png", "image/jpeg", "image/webp"].includes(file.type);
    const documentFile = file.type === "application/pdf" || file.type.startsWith("text/");
    if (kind === "image" && (!image || file.size > maxImageBytes)) return window.showToast?.("Choose a PNG, JPG, JPEG, or WebP image up to 20 MB.", "error");
    if (kind === "document" && !documentFile) return window.showToast?.("Choose a PDF or text document in Docs mode.", "error");
    currentFile = file; showChip(file);
    window.dispatchEvent(new CustomEvent("file-ingested", {detail:{file, context:kind}}));
  }
  document.addEventListener("DOMContentLoaded", () => {
    const overlay = $("global-drop-overlay");
    window.addEventListener("dragover", event => { event.preventDefault(); if (overlay) { overlay.hidden = false; $("drop-context").textContent = context() === "image" ? "Images for Studio" : context() === "document" ? "PDF or text documents for Docs" : "Files for this workspace"; } });
    window.addEventListener("dragleave", event => { if (event.clientX <= 0 || event.clientY <= 0 || event.clientX >= innerWidth || event.clientY >= innerHeight) overlay.hidden = true; });
    window.addEventListener("drop", event => { event.preventDefault(); overlay.hidden = true; accept(event.dataTransfer.files[0]); });
    $("image-file")?.addEventListener("change", event => accept(event.target.files[0]));
    window.addEventListener("file-ingested", event => { if (event.detail.context === "image") window.showSourceImage?.(event.detail.file); });
    window.addEventListener("file-ingestion-cleared", () => window.clearSourceImage?.());
  });
  window.fileIngestion = {accept};
})();
