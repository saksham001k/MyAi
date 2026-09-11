"use strict";
const $ = (id) => document.getElementById(id);
const token =
  new URLSearchParams(location.hash.slice(1)).get("token") ||
  sessionStorage.getItem("myai-token");
if (token) sessionStorage.setItem("myai-token", token);
history.replaceState(null, "", "/");
let active = null,
  chats = [],
  busy = false,
  operation = null,
  mediaTimer = null,
  view = 0;
const welcome = $("messages").innerHTML;
function notice(value = "") {
  $("notice").textContent = value;
  $("notice").hidden = !value;
}
async function api(path, method = "GET", body) {
  const r = await fetch(path, {
    method,
    headers: {
      Authorization: "Bearer " + (token || ""),
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    const e = await r.json();
    throw new Error(e.error || "Request failed");
  }
  return r;
}
function setBusy(value) {
  busy = value;
  for (const id of ["send", "new-chat", "unload", "context", "gpu"])
    $(id).disabled = value;
  $("stop").hidden = !value || operation === "loading";
}
function renderContent(target, value) {
  target.replaceChildren();
  value.split(/```[^\n]*\n([\s\S]*?)```/g).forEach((part, i) => {
    if (i % 2) {
      const p = document.createElement("pre");
      p.textContent = part;
      target.append(p);
    } else
      part.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).forEach((piece) => {
        if (piece.startsWith("**")) {
          const strong = document.createElement("strong");
          strong.textContent = piece.slice(2, -2);
          target.append(strong);
        } else if (piece.startsWith("`")) {
          const code = document.createElement("code");
          code.textContent = piece.slice(1, -1);
          target.append(code);
        } else target.append(document.createTextNode(piece));
      });
  });
}
function message(role, content) {
  const row = document.createElement("article");
  row.className = "message " + role;
  const label = document.createElement("div");
  label.className = "role";
  label.textContent = role === "user" ? "YOU" : "KISS";
  const text = document.createElement("div");
  text.className = "content";
  renderContent(text, content);
  row.append(label, text);
  if (role !== "user") {
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "copy";
    copy.textContent = "Copy";
    copy.onclick = async () => {
      try {
        await navigator.clipboard.writeText(text.textContent);
        copy.textContent = "Copied";
      } catch {
        notice("Select the response text to copy it.");
      }
    };
    row.append(copy);
  }
  $("messages").append(row);
  return text;
}
function scrollMessages() {
  $("messages").scrollTop = $("messages").scrollHeight;
}
function leaveView() {
  view++;
  clearTimeout(mediaTimer);
  window.leaveTask?.();
}
function bindSuggestions() {
  document.querySelectorAll("[data-prompt]").forEach(
    (b) =>
      (b.onclick = () => {
        $("prompt").value = b.dataset.prompt;
        $("prompt").focus();
      }),
  );
}
function newChat() {
  if (busy) return;
  leaveView();
  active = null;
  sessionStorage.removeItem("kiss-active-chat");
  window.setAttachmentScope?.("draft", true);
  $("messages").innerHTML = welcome;
  $("chat-title").textContent = "What would you like to do?";
  notice();
  bindSuggestions();
  renderHistory();
}
async function openChat(id) {
  if (busy) return;
  leaveView();
  const chat = await (await api("/api/chats/" + id)).json();
  active = id;
  sessionStorage.setItem("kiss-active-chat", id);
  window.setAttachmentScope?.(id);
  $("chat-title").textContent = chat.title;
  $("messages").replaceChildren();
  for (const m of chat.messages) {
    const content = message(m.role, m.content);
    window.showKnowledgeEvidence?.(content.parentElement, m.knowledge_refs);
  }
  renderHistory();
  scrollMessages();
}
async function listChats() {
  chats = await (await api("/api/chats")).json();
  renderHistory();
}
function renderHistory() {
  $("history").replaceChildren();
  const q = $("search").value.toLowerCase();
  for (const chat of chats.filter((c) => c.title.toLowerCase().includes(q))) {
    const row = document.createElement("div");
    row.className = "chat-row" + (active === chat.id ? " active" : "");
    const b = document.createElement("button");
    b.textContent = chat.title;
    b.title = chat.title;
    b.onclick = () => openChat(chat.id).catch((e) => notice(e.message));
    row.append(b);
    $("history").append(row);
  }
  for (const b of document.querySelectorAll(
    "#task-list button,#media-list button",
  ))
    b.hidden = !b.textContent.toLowerCase().includes(q);
}
async function refresh() {
  const state = await (await api("/api/status")).json();
  $("engine-status").textContent = state.running
    ? "● Local · " + state.model
    : "○ " +
      state.models.length +
      " local model(s) · Loads automatically when you send";
  $("setup-hint").textContent =
    state.models.map((m) => m.name).join(" · ") ||
    "No local GGUF models found in models/.";
  if (!busy && state.busy) {
    operation = "external";
    setBusy(true);
  }
  return state;
}
window.refreshMyAi = () => refresh().catch((e) => notice(e.message));
async function ensureModel(route) {
  const state = await refresh();
  if (state.busy)
    throw new Error(
      "Another operation is running. Wait for it to finish or stop it first.",
    );
  if (!state.running || state.model !== route.model) {
    operation = "loading";
    setBusy(true);
    $("composer-hint").textContent = "Loading " + route.model + "…";
    await api("/api/engine/start", "POST", {
      model: route.model,
      context: Number($("context").value),
      gpu_layers: $("gpu").value === "auto" ? null : 0,
    });
  }
  await refresh();
  $("composer-hint").textContent = route.reason + " · " + route.model;
}
async function chatReply(prompt, route) {
  operation = "chat";
  setBusy(true);
  if (!active) {
    const c = await (await api("/api/chats", "POST", {})).json();
    active = c.id;
    sessionStorage.setItem("kiss-active-chat", active);
    window.setAttachmentScope?.(active, false, true);
    $("messages").replaceChildren();
  }
  message("user", prompt);
  const text = message("assistant", "");
  $("prompt").value = "";
  const r = await api("/api/generate", "POST", {
    chat_id: active,
    prompt,
    mode: route.kind === "code" ? "code" : "chat",
    uploads: window.uploadedFiles?.() || [],
    project_path: $("task-project").value.trim(),
  });
  const reader = r.body.getReader(),
    decoder = new TextDecoder();
  let pending = "",
    answer = "",
    complete = false;
  while (true) {
    const { done, value } = await reader.read();
    pending += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = pending.split("\n");
    pending = lines.pop();
    for (const line of lines) {
      if (!line) continue;
      const item = JSON.parse(line);
      if (item.knowledge)
        window.showKnowledgeEvidence?.(text.parentElement, item.knowledge);
      if (item.token) {
        answer += item.token;
        text.textContent = answer;
        scrollMessages();
      }
      if (item.error) throw new Error(item.error);
      if (item.done) complete = true;
    }
    if (done) break;
  }
  renderContent(text, answer);
  if (!complete)
    throw new Error(
      "Connection ended. Reopen the saved conversation before retrying.",
    );
  await listChats();
  const c = chats.find((c) => c.id === active);
  if (c) $("chat-title").textContent = c.title;
}
$("composer").onsubmit = async (e) => {
  e.preventDefault();
  const prompt = $("prompt").value.trim();
  if (!prompt || busy) return;
  if (window.uploadsPending()) {
    notice("Wait for your attachments to finish uploading.");
    return;
  }
  notice();
  operation = "routing";
  setBusy(true);
  try {
    const route = await (
      await api("/api/route", "POST", {
        prompt,
        project_path: $("task-project").value.trim(),
        has_image: window
          .uploadedFiles()
          .some((f) => /\.(png|jpe?g|webp)$/i.test(f.filename)),
      })
    ).json();
    $("composer-hint").textContent =
      route.reason + (route.model ? " · " + route.model : "");
    if (!route.ready) {
      if (route.needs_project) {
        $("project-access").open = true;
        $("task-project").focus();
      }
      throw new Error(route.message);
    }
    if (route.kind === "image" || route.kind === "video") {
      if (route.kind === "video" && !$("video-confirm").checked) {
        $("settings").hidden = false;
        $("settings-toggle").setAttribute("aria-expanded", "true");
        throw new Error(
          "Enable experimental video in Settings to run this request.",
        );
      }
      await startMedia(prompt, route);
      return;
    }
    await ensureModel(route);
    if (route.kind === "project" || route.kind === "research") {
      leaveView();
      active = null;
      operation = "task";
      setBusy(true);
      $("project-access").open = false;
      await window.startUnifiedTask({
        goal: prompt,
        kind: route.kind,
        project_path: $("task-project").value.trim(),
        allow_commands: $("task-allow-commands").checked,
        test_command: $("task-allow-commands").checked
          ? $("task-test").value
          : "",
        max_steps: Number($("task-steps").value),
        uploads: window.uploadedFiles(),
      });
      $("prompt").value = "";
      return;
    }
    leaveView();
    await chatReply(prompt, route);
  } catch (e) {
    notice(e.message);
  } finally {
    if (operation !== "task" && operation !== "media") {
      operation = null;
      setBusy(false);
      await refresh().catch((e) => notice(e.message));
    }
  }
};
$("prompt").onkeydown = (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    if (!busy) $("composer").requestSubmit();
  }
};
$("stop").onclick = async () => {
  try {
    if (operation === "task") await window.stopUnifiedTask();
    else if (operation === "media") await api("/api/media/cancel", "POST", {});
    else await api("/api/cancel", "POST", {});
    $("stop").textContent = "Stopping…";
  } catch (e) {
    notice(e.message);
  }
};
window.taskViewStarted = () => {
  operation = "task";
  setBusy(true);
};
window.taskViewFinished = () => {
  if (operation === "task" || operation === "external") {
    operation = null;
    setBusy(false);
    $("stop").textContent = "Stop";
    refresh().catch((e) => notice(e.message));
  }
};
window.prepareTaskView = () => {
  if (busy && operation !== "task" && operation !== "external") return false;
  clearTimeout(mediaTimer);
  active = null;
  sessionStorage.removeItem("kiss-active-chat");
  $("messages").replaceChildren();
  $("chat-title").textContent = "Your work";
  renderHistory();
  return true;
};
async function mediaList() {
  const state = await (await api("/api/media")).json();
  $("media-list").replaceChildren();
  for (const j of state.jobs) {
    const b = document.createElement("button");
    b.textContent = j.prompt.slice(0, 65);
    const s = document.createElement("small");
    s.textContent = j.kind + " · " + j.status;
    b.append(s);
    b.onclick = () => {
      if (!busy) {
        leaveView();
        active = null;
        showMedia(j.id, view).catch((e) => notice(e.message));
      }
    };
    $("media-list").append(b);
  }
  const running = state.jobs.find((j) => j.status === "running");
  if (running && (!busy || operation === "external")) {
    leaveView();
    operation = "media";
    setBusy(true);
    await showMedia(running.id, view);
  }
  return state;
}
async function startMedia(prompt, route) {
  const payload = {
    preset: route.preset,
    prompt,
    steps: 20,
    seed: Math.floor(Math.random() * 2147483647),
    experimental: $("video-confirm").checked,
  };
  if (route.image_edit) {
    const f = window
      .uploadedFiles()
      .find((f) => /\.(png|jpe?g|webp)$/i.test(f.filename));
    const blob = await (await api("/api/uploads/" + f.id)).blob();
    payload.image = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
    payload.strength = 0.65;
  }
  const j = await (
    await api(
      route.image_edit ? "/api/studio/img2img" : "/api/media/start",
      "POST",
      payload,
    )
  ).json();
  leaveView();
  active = null;
  operation = "media";
  setBusy(true);
  $("prompt").value = "";
  await showMedia(j.id, view);
  await mediaList();
}
async function showMedia(id, generation) {
  const state = await (await api("/api/media")).json();
  if (generation !== view) return;
  const j = state.jobs.find((j) => j.id === id);
  if (!j) throw new Error("Creation not found.");
  $("chat-title").textContent = "Your creation";
  $("messages").replaceChildren();
  message("user", j.prompt);
  const answer = message(
    "assistant",
    j.status === "running"
      ? "Creating locally… " + (j.progress?.stage || "")
      : j.error || "Creation " + j.status,
  );
  if (j.status === "complete") {
    const blob = await (await api("/api/media/result/" + id)).blob();
    if (generation !== view) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "KISS-" + id + (j.kind === "image" ? ".png" : ".avi");
    a.textContent = "Download " + j.kind;
    answer.append(document.createElement("br"), a);
    if (j.kind === "image") {
      const img = document.createElement("img");
      img.src = url;
      img.alt = j.prompt;
      img.className = "result-image";
      answer.append(img);
    }
    setTimeout(() => URL.revokeObjectURL(url), 300000);
  }
  if (j.status === "running") {
    operation = "media";
    setBusy(true);
    mediaTimer = setTimeout(
      () =>
        showMedia(id, generation).catch((e) => {
          notice(e.message);
          operation = null;
          setBusy(false);
        }),
      2500,
    );
  } else {
    operation = null;
    setBusy(false);
    refresh().catch((e) => notice(e.message));
  }
}
$("search").oninput = renderHistory;
$("new-chat").onclick = newChat;
$("sidebar-toggle").onclick = () => {
  const v = document.body.classList.toggle("sidebar-collapsed");
  $("sidebar-toggle").setAttribute("aria-expanded", String(!v));
};
$("settings-toggle").onclick = () => {
  $("settings").hidden = !$("settings").hidden;
  $("settings-toggle").setAttribute(
    "aria-expanded",
    String(!$("settings").hidden),
  );
};
$("task-allow-commands").onchange = () => {
  $("task-test").disabled = !$("task-allow-commands").checked;
};
$("task-project").value = sessionStorage.getItem("myai-project") || "";
$("task-project").oninput = () => {
  sessionStorage.setItem("myai-project", $("task-project").value);
  $("project-selected").textContent = $("task-project").value.trim()
    ? "· " + $("task-project").value.trim().split("/").filter(Boolean).pop()
    : "";
};
$("task-project").oninput();
$("unload").onclick = async () => {
  try {
    await api("/api/engine/stop", "POST", {});
    await refresh();
  } catch (e) {
    notice(e.message);
  }
};
$("save-preferences").onclick = async () => {
  try {
    await api("/api/preferences", "POST", {
      instructions: $("personal-instructions").value,
      max_output_tokens: Number($("output-tokens").value),
    });
    sessionStorage.setItem("myai-context", $("context").value);
    window.showToast?.("Preferences saved locally.", "success");
  } catch (e) {
    notice(e.message);
  }
};
$("context").value = sessionStorage.getItem("myai-context") || "8192";
$("export").onclick = async () => {
  if (!active)
    return notice(
      "Open a conversation to export it. Work reports have their own Download report button.",
    );
  try {
    const c = await (await api("/api/chats/" + active)).json();
    const u = URL.createObjectURL(
      new Blob(
        [
          "# " +
            c.title +
            "\n\n" +
            c.messages
              .map((m) => "## " + m.role + "\n\n" + m.content)
              .join("\n\n"),
        ],
        { type: "text/markdown" },
      ),
    );
    const a = document.createElement("a");
    a.href = u;
    a.download = "KISS-conversation.md";
    a.click();
    setTimeout(() => URL.revokeObjectURL(u), 1000);
  } catch (e) {
    notice(e.message);
  }
};
bindSuggestions();
Promise.all([
  refresh(),
  listChats().then(async () => {
    const id = sessionStorage.getItem("kiss-active-chat");
    if (id && chats.some((c) => c.id === id) && !busy) await openChat(id);
  }),
  mediaList(),
  api("/api/preferences")
    .then((r) => r.json())
    .then((p) => {
      $("personal-instructions").value = p.instructions;
      $("output-tokens").value = String(p.max_output_tokens);
    }),
]).catch((e) => notice(e.message));
