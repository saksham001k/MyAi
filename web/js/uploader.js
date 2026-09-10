"use strict";
(function () {
  const el = (id) => document.getElementById(id),
    files = new Map();
  let scope = "draft",
    previewURL = null,
    pending = 0;
  const auth = () => ({
    Authorization: "Bearer " + (sessionStorage.getItem("myai-token") || ""),
  });
  const size = (n) =>
    n < 1048576
      ? (n / 1024).toFixed(1) + " KB"
      : (n / 1048576).toFixed(1) + " MB";
  function save() {
    sessionStorage.setItem(
      "myai-attachments-" + scope,
      JSON.stringify([...files.values()]),
    );
  }
  function render() {
    el("upload-chips").replaceChildren();
    el("attachment-area").hidden = !files.size && !pending;
    el("attachment-count").textContent = pending
      ? "Uploading " + pending + " file(s)…"
      : files.size + " attached file" + (files.size === 1 ? "" : "s");
    for (const [id, m] of files) {
      const card = document.createElement("div");
      card.className = "file-chip";
      const info = document.createElement("div");
      const name = document.createElement("strong");
      name.className = "file-chip-name";
      name.textContent = m.filename;
      const detail = document.createElement("small");
      detail.textContent =
        "Uploaded · " +
        size(m.size_bytes) +
        " · " +
        (m.extraction?.status === "ready"
          ? "Text available to KISS"
          : /\.(png|jpe?g|webp)$/i.test(m.filename)
            ? "Image available for editing"
            : "Stored only");
      info.append(name, detail);
      const view = document.createElement("button");
      view.type = "button";
      view.textContent = "View";
      view.setAttribute("aria-label", "View " + m.filename);
      view.onclick = () =>
        preview(m).catch((e) => window.showToast?.(e.message, "error"));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "×";
      remove.setAttribute("aria-label", "Detach " + m.filename);
      remove.title =
        "Remove from this conversation; stored original is retained";
      remove.onclick = () => {
        files.delete(id);
        save();
        render();
      };
      card.append(info, view, remove);
      el("upload-chips").append(card);
    }
  }
  async function preview(m) {
    const dialog = el("file-preview");
    el("preview-title").textContent = m.filename;
    el("preview-detail").textContent =
      size(m.size_bytes) +
      " · " +
      (m.extraction?.detail || "Stored on this computer.");
    el("preview-content").textContent = "Loading preview…";
    el("preview-download").disabled = true;
    dialog.showModal();
    const response = await fetch("/api/uploads/" + m.id, { headers: auth() });
    if (!response.ok)
      throw new Error(
        "This stored file is no longer available. Attach it again.",
      );
    const blob = await response.blob();
    if (previewURL) URL.revokeObjectURL(previewURL);
    previewURL = URL.createObjectURL(blob);
    el("preview-content").replaceChildren();
    if (/\.(png|jpe?g|webp|gif)$/i.test(m.filename)) {
      const image = document.createElement("img");
      image.src = previewURL;
      image.alt = m.filename;
      el("preview-content").append(image);
    } else if (/\.pdf$/i.test(m.filename)) {
      const frame = document.createElement("iframe");
      frame.title = m.filename;
      frame.setAttribute("sandbox", "");
      frame.src = previewURL;
      el("preview-content").append(frame);
      const hint = document.createElement("p");
      hint.textContent =
        "If your browser cannot display this PDF, download the original below.";
      el("preview-content").append(hint);
    } else {
      const pre = document.createElement("pre");
      pre.textContent =
        (await blob.slice(0, 200000).text()) +
        (blob.size > 200000 ? "\n[Preview limited to 200 KB]" : "");
      el("preview-content").append(pre);
    }
    el("preview-download").disabled = false;
    el("preview-download").onclick = () => {
      const a = document.createElement("a");
      a.href = previewURL;
      a.download = m.filename;
      a.click();
    };
  }
  el("preview-close").onclick = () => el("file-preview").close();
  el("file-preview").addEventListener("close", () => {
    if (previewURL) URL.revokeObjectURL(previewURL);
    previewURL = null;
    el("preview-content").replaceChildren();
  });
  async function upload(file) {
    if (files.size >= 12)
      throw new Error("Attach up to 12 files. Detach one to add another.");
    if (
      !/\.(png|jpe?g|webp|gif|py|js|ts|html|css|json|md|pdf|txt|csv)$/i.test(
        file.name,
      )
    )
      throw new Error(file.name + ": unsupported file type.");
    if (file.size > 49 * 1024 * 1024)
      throw new Error(file.name + ": maximum 49 MB per file.");
    const hash = Array.from(
      new Uint8Array(
        await crypto.subtle.digest("SHA-256", await file.arrayBuffer()),
      ),
    )
      .map((v) => v.toString(16).padStart(2, "0"))
      .join("");
    if (
      [...files.values()].some(
        (m) => m.fingerprint === hash && m.filename === file.name,
      )
    ) {
      window.showToast?.(file.name + " is already attached.", "success");
      return;
    }
    const targetScope = scope;
    const data = new FormData();
    data.append("file", file, file.name);
    const response = await fetch("/api/upload", {
      method: "POST",
      headers: auth(),
      body: data,
    });
    const manifest = await response.json();
    if (!response.ok) throw new Error(manifest.error || "Upload failed.");
    const m = { ...manifest, fingerprint: hash };
    if (scope === targetScope) {
      files.set(m.id, m);
      save();
    } else {
      const stored = JSON.parse(
        sessionStorage.getItem("myai-attachments-" + targetScope) || "[]",
      );
      stored.push(m);
      sessionStorage.setItem(
        "myai-attachments-" + targetScope,
        JSON.stringify(stored),
      );
    }
  }
  async function handle(list) {
    pending += list.length;
    render();
    for (const f of list) {
      try {
        await upload(f);
      } catch (e) {
        window.showToast?.(e.message, "error");
      } finally {
        pending--;
        render();
      }
    }
  }
  el("attach-file").onclick = () => el("global-file-input").click();
  el("global-file-input").onchange = (e) => {
    handle([...e.target.files]);
    e.target.value = "";
  };
  window.addEventListener("dragover", (e) => {
    if (!e.dataTransfer.types.includes("Files")) return;
    e.preventDefault();
    document.body.classList.add("upload-dragging");
  });
  window.addEventListener("dragleave", (e) => {
    if (!e.relatedTarget) document.body.classList.remove("upload-dragging");
  });
  window.addEventListener("drop", (e) => {
    e.preventDefault();
    document.body.classList.remove("upload-dragging");
    handle([...e.dataTransfer.files]);
  });
  window.uploadedFiles = () =>
    [...files.values()].map(({ fingerprint, ...m }) => m);
  window.uploadsPending = () => pending > 0;
  window.setAttachmentScope = (next, clear = false, carry = false) => {
    const previous = [...files.values()];
    scope = next;
    files.clear();
    let stored = [];
    try {
      stored = JSON.parse(
        sessionStorage.getItem("myai-attachments-" + scope) || "[]",
      );
    } catch {}
    for (const m of clear ? [] : carry ? previous : stored) files.set(m.id, m);
    save();
    render();
  };
  window.setAttachmentScope("draft");
})();
