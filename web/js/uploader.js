"use strict";
(function () {
  const input = document.getElementById("global-file-input");
  const attach = document.getElementById("attach-file");
  const chips = document.getElementById("upload-chips");
  const allowed = /\.(png|jpe?g|webp|gif|py|js|ts|html?|css|json|md|pdf|txt|csv)$/i;
  const files = new Map();
  const token = () => sessionStorage.getItem("myai-token") || "";
  const size = value => value < 1024 * 1024 ? `${(value / 1024).toFixed(1)} KB` : `${(value / 1024 / 1024).toFixed(1)} MB`;
  function render() {
    chips.replaceChildren();
    for (const [id, item] of files) {
      const chip = document.createElement("div"); chip.className = "file-chip";
      const icon = document.createElement("span"); icon.setAttribute("aria-hidden", "true"); icon.textContent = item.file.type.startsWith("image/") ? "▧" : "◇";
      const name = document.createElement("span"); name.className = "file-chip-name"; name.textContent = item.manifest.filename;
      const meta = document.createElement("small"); meta.textContent = size(item.manifest.size_bytes);
      const remove = document.createElement("button"); remove.type = "button"; remove.className = "file-chip-remove"; remove.setAttribute("aria-label", `Remove ${item.manifest.filename}`); remove.textContent = "×";
      remove.onclick = () => { files.delete(id); render(); };
      chip.append(icon, name, meta, remove); chips.append(chip);
    }
  }
  async function upload(file) {
    if (!allowed.test(file.name)) throw new Error("That file type is not supported.");
    if (file.size > 50 * 1024 * 1024) throw new Error("Files must be 50 MB or smaller.");
    const data = new FormData(); data.append("file", file, file.name);
    const response = await fetch("/api/upload", {method: "POST", headers: {Authorization: `Bearer ${token()}`}, body: data});
    const manifest = await response.json();
    if (!response.ok) throw new Error(manifest.error || "Upload failed.");
    files.set(manifest.id, {file, manifest}); render();
  }
  async function handle(list) {
    for (const file of list) {
      try { await upload(file); } catch (error) { window.showToast?.(error.message, "error"); }
    }
  }
  attach?.addEventListener("click", () => input.click());
  input?.addEventListener("change", event => { handle(event.target.files); input.value = ""; });
  document.getElementById("prompt")?.addEventListener("input", async event => {
    const value = event.target.value;
    const match = value.match(/@([A-Za-z0-9_./ -]*)$/);
    if (!match) return;
    try {
      const response = await fetch(`/api/index?q=${encodeURIComponent(match[1])}`, {headers: {Authorization: `Bearer ${token()}`}});
      if (!response.ok) return;
      const result = await response.json();
      const suggestions = document.getElementById("file-suggestions");
      suggestions.replaceChildren(...result.files.map(file => {
        const option = document.createElement("option"); option.value = `@${file.path}`; return option;
      }));
    } catch { /* Suggestions are optional; sending remains available. */ }
  });
  window.addEventListener("dragover", event => { event.preventDefault(); event.stopPropagation(); document.body.classList.add("upload-dragging"); });
  window.addEventListener("dragleave", event => { event.preventDefault(); event.stopPropagation(); if (!event.relatedTarget) document.body.classList.remove("upload-dragging"); });
  window.addEventListener("drop", event => { event.preventDefault(); event.stopPropagation(); document.body.classList.remove("upload-dragging"); handle(event.dataTransfer.files); });
  window.uploadedFiles = () => [...files.values()].map(item => item.manifest);
})();
