"use strict";
(function () {
  const library = document.getElementById("doc-library");
  if (!library) return;

  async function api(path, method, body) {
    const token = sessionStorage.getItem("myai-token") || "";
    const response = await fetch(path, {
      method: method || "GET",
      headers: {"Authorization": `Bearer ${token}`, "Content-Type": "application/json"},
      body: body === undefined ? undefined : JSON.stringify(body)
    });
    if (!response.ok) {
      const result = await response.json();
      throw new Error(result.error || "Request failed");
    }
    return response.json();
  }

  async function refreshDocs() {
    const state = await api("/api/documents");
    library.replaceChildren();
    if (!state.documents.length) {
      library.textContent = "No documents in this workspace yet.";
      return;
    }
    for (const doc of state.documents) {
      const row = document.createElement("div");
      row.className = "doc-row";
      const title = document.createElement("strong");
      title.textContent = doc.name;
      const meta = document.createElement("small");
      meta.textContent = `${doc.pages} page(s) · ${doc.passages} passages · ${(doc.bytes / 1024).toFixed(1)} KB`;
      row.append(title, meta);
      library.append(row);
    }
  }

  async function uploadDocs(files) {
    for (const file of files) {
      const buffer = await file.arrayBuffer();
      if (file.name.toLowerCase().endsWith(".pdf")) {
        const bytes = new Uint8Array(buffer);
        let binary = "";
        bytes.forEach(b => { binary += String.fromCharCode(b); });
        await api("/api/documents", "POST", {name: file.name, content_b64: btoa(binary)});
      } else {
        await api("/api/documents", "POST", {
          name: file.name,
          content: new TextDecoder("utf-8", {fatal: true}).decode(buffer)
        });
      }
    }
    await refreshDocs();
  }

  document.getElementById("doc-files").onchange = async event => {
    try {
      await uploadDocs([...event.target.files]);
      window.showToast?.("Document added to the local library.", "success");
    } catch (err) {
      window.showToast?.(err.message, "error");
    }
    event.target.value = "";
  };

  window.refreshDocs = refreshDocs;
  refreshDocs().catch(() => {});
})();
