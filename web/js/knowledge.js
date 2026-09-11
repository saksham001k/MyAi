"use strict";
(function () {
  const el = (id) => document.getElementById(id);
  let items = [],
    editing = null;
  const showError = (e) => {
    el("knowledge-error").textContent = e.message;
    el("knowledge-error").hidden = false;
  };
  const clear = () => {
    editing = null;
    el("memory-title").value = "";
    el("memory-content").value = "";
    el("memory-project").checked = false;
    el("memory-save").textContent = "Save memory";
    el("memory-cancel").hidden = true;
  };
  async function load() {
    items = await (await api("/api/knowledge")).json();
    render();
  }
  function render() {
    const q = el("knowledge-search").value.toLowerCase();
    const root = el("knowledge-items");
    root.replaceChildren();
    const shown = items.filter((i) =>
      (i.title + " " + i.content + " " + i.scope).toLowerCase().includes(q),
    );
    if (!shown.length) {
      const p = document.createElement("p");
      p.className = "local-note";
      p.textContent = items.length
        ? "No matching saved items."
        : "Nothing saved yet. Add a memory below, or save an attached file to your library.";
      root.append(p);
    }
    for (const item of shown) {
      const card = document.createElement("article");
      card.className = "knowledge-item";
      const h = document.createElement("h3");
      h.textContent = item.title;
      const meta = document.createElement("p");
      meta.className = "local-note";
      meta.textContent =
        (item.kind === "memory" ? "Memory" : "Document") +
        " · " +
        (item.scope ? "Project: " + item.scope : "All conversations") +
        " · " +
        new Date(item.updated * 1000).toLocaleString();
      const detail = document.createElement("p");
      detail.textContent = item.kind === "memory" ? item.content : item.detail;
      const buttons = document.createElement("div");
      buttons.className = "controls";
      if (item.kind === "memory") {
        const edit = document.createElement("button");
        edit.type = "button";
        edit.textContent = "Edit";
        edit.onclick = () => {
          editing = item.id;
          el("memory-title").value = item.title;
          el("memory-content").value = item.content;
          el("memory-project").checked = Boolean(item.scope);
          el("memory-save").textContent = "Save changes";
          el("memory-cancel").hidden = false;
          el("memory-title").focus();
        };
        buttons.append(edit);
      } else {
        const view = document.createElement("button");
        view.type = "button";
        view.textContent = "View source";
        view.disabled = item.state === "missing";
        view.onclick = () => {
          el("knowledge-dialog").close();
          window
            .previewUploadedFile({
              id: item.upload_id,
              filename: item.title,
              size_bytes: null,
              extraction: { detail: item.detail },
            })
            .catch(showError);
        };
        buttons.append(view);
      }
      const forget = document.createElement("button");
      forget.type = "button";
      forget.textContent = "Forget";
      forget.onclick = async () => {
        try {
          await api("/api/knowledge/forget", "POST", { id: item.id });
          if (editing === item.id) clear();
          await load();
          window.showToast?.(
            "Removed from future saved context. Existing conversations and original files are retained.",
            "success",
          );
        } catch (e) {
          showError(e);
        }
      };
      buttons.append(forget);
      card.append(h, meta, detail, buttons);
      root.append(card);
    }
  }
  async function open() {
    el("knowledge-error").hidden = true;
    el("knowledge-dialog").showModal();
    await load().catch(showError);
  }
  el("knowledge-open").onclick = open;
  el("knowledge-close").onclick = () => el("knowledge-dialog").close();
  el("knowledge-search").oninput = render;
  el("memory-cancel").onclick = clear;
  el("memory-form").onsubmit = async (e) => {
    e.preventDefault();
    el("knowledge-error").hidden = true;
    const old = items.find((i) => i.id === editing);
    const scope = el("memory-project").checked
      ? old?.scope || el("task-project").value.trim()
      : "";
    if (el("memory-project").checked && !scope)
      return showError(
        new Error(
          "Choose a project folder in Project access first, or save for all conversations.",
        ),
      );
    try {
      await api("/api/knowledge/memory", "POST", {
        id: editing,
        title: el("memory-title").value,
        content: el("memory-content").value,
        scope,
      });
      clear();
      await load();
    } catch (e) {
      showError(e);
    }
  };
  window.saveUploadedToLibrary = async (m) => {
    await api("/api/knowledge/document", "POST", {
      upload_id: m.id,
      scope: "",
    });
    window.showToast?.(m.filename + " saved to the local library.", "success");
  };
  window.showKnowledgeEvidence = (root, sources) => {
    if (!sources?.length) return;
    const details = document.createElement("details");
    details.className = "knowledge-evidence";
    const summary = document.createElement("summary");
    summary.textContent = "Saved context used · " + sources.length;
    details.append(summary);
    for (const source of sources) {
      const p = document.createElement("p");
      p.textContent =
        "[" +
        source.citation +
        "] " +
        source.title +
        (source.page ? " · page " + source.page : "");
      details.append(p);
      if (source.text) {
        const pre = document.createElement("pre");
        pre.textContent = source.text;
        details.append(pre);
      }
    }
    root.append(details);
  };
})();
