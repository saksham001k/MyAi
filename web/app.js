"use strict";
const $ = id => document.getElementById(id);
const token = new URLSearchParams(location.hash.slice(1)).get("token") || sessionStorage.getItem("myai-token");
if (token) sessionStorage.setItem("myai-token", token);
history.replaceState(null, "", "/");
let active = null, chats = [], busy = false, running = false;
const welcome = $("messages").innerHTML;

function notice(message = "") { $("notice").textContent = message; $("notice").hidden = !message; }
async function api(path, method = "GET", body) {
  const response = await fetch(path, {method, headers: {"Authorization": `Bearer ${token || ""}`, "Content-Type": "application/json"}, body: body === undefined ? undefined : JSON.stringify(body)});
  if (!response.ok) { const result = await response.json(); throw new Error(result.error || "Request failed"); }
  return response;
}
function setBusy(value) {
  busy = value;
  for (const id of ["load", "unload", "new-chat", "model", "context", "gpu", "export"]) $(id).disabled = value;
  $("send").disabled = value || !running;
  $("prompt").disabled = value;
}
async function refresh() {
  const state = await (await api("/api/status")).json();
  running = state.running;
  const selected = $("model").value;
  $("model").replaceChildren();
  for (const model of state.models) {
    const option = new Option(`${model.name} · ${(model.bytes / 1024 ** 3).toFixed(1)} GB`, model.name);
    $("model").add(option);
  }
  if (!state.models.length) $("model").add(new Option("No GGUF models found", ""));
  if (state.models.some(m => m.name === selected)) $("model").value = selected;
  $("engine-status").textContent = running ? `● Ready · ${state.model}` : "○ No model loaded · local workspace";
  $("setup-hint").textContent = !state.runtime_found ? `Setup: put llama-server and its companion libraries in runtime/${state.platform}/. See docs/SETUP.md.` : !state.models.length ? "Add a compatible .gguf file to the models folder, then reload this page." : "Start with CPU and 4096 context. GPU mode needs a matching runtime. Larger context uses more memory.";
  $("composer-hint").textContent = running ? "Local only · Enter to send · Shift+Enter for a new line" : "Load a model to begin · Shift+Enter for a new line";
  $("send").disabled = busy || !running;
}
async function listChats() { chats = await (await api("/api/chats")).json(); renderHistory(); }
function renderHistory() {
  $("history").replaceChildren();
  for (const chat of chats.filter(c => c.title.toLowerCase().includes($("search").value.toLowerCase()))) {
    const row = document.createElement("div"); row.className = `chat-row ${active === chat.id ? "active" : ""}`;
    const button = document.createElement("button"); button.textContent = chat.title; button.title = chat.title;
    button.onclick = () => { if (!busy) openChat(chat.id).catch(e => notice(e.message)); };
    const remove = document.createElement("button"); remove.textContent = "×"; remove.className = "delete"; remove.setAttribute("aria-label", `Delete ${chat.title}`);
    remove.onclick = async () => {
      if (busy || !confirm("Delete this conversation? This cannot be undone.")) return;
      try { await api(`/api/chats/${chat.id}`, "DELETE"); if (active === chat.id) newChat(); await listChats(); } catch(e) { notice(e.message); }
    };
    row.append(button, remove); $("history").append(row);
  }
}
function message(role, content, status = "complete") {
  const article = document.createElement("article"); article.className = `message ${role}`;
  const label = document.createElement("div"); label.className = "role"; label.textContent = role === "user" ? "YOU" : "MYAI";
  const text = document.createElement("div"); text.className = "content"; renderContent(text, content);
  article.append(label, text);
  if (status !== "complete") { const hint = document.createElement("small"); hint.textContent = `Response ${status}`; article.append(hint); }
  const copy = document.createElement("button"); copy.className = "copy"; copy.textContent = "Copy";
  copy.onclick = async () => { try { await navigator.clipboard.writeText(text.textContent); copy.textContent = "Copied"; } catch { notice("Select the response text to copy it."); } };
  article.append(copy); $("messages").append(article); return text;
}
async function openChat(id) {
  const chat = await (await api(`/api/chats/${id}`)).json(); active = id;
  $("chat-title").textContent = chat.title; $("messages").replaceChildren();
  for (const m of chat.messages) message(m.role, m.content, m.status);
  renderHistory(); scrollMessages();
}
function newChat() { active = null; $("chat-title").textContent = "A little space for big ideas."; $("messages").innerHTML = welcome; renderHistory(); bindSuggestions(); notice(); }
function scrollMessages() { $("messages").scrollTop = $("messages").scrollHeight; }
function bindSuggestions() { document.querySelectorAll("[data-prompt]").forEach(button => button.onclick = () => { $("prompt").value = button.dataset.prompt; $("prompt").focus(); }); }
$("search").oninput = renderHistory;
$("new-chat").onclick = newChat;
$("settings-toggle").onclick = () => { $("settings").hidden = !$("settings").hidden; $("settings-toggle").setAttribute("aria-expanded", String(!$("settings").hidden)); };
$("load").onclick = async () => {
  notice(); setBusy(true); $("engine-status").textContent = "Loading model… larger models may take a few minutes.";
  try { await api("/api/engine/start", "POST", {model: $("model").value, context: Number($("context").value), gpu_layers: Number($("gpu").value)}); }
  catch(e) { notice(e.message); }
  finally { setBusy(false); await refresh().catch(e => notice(e.message)); }
};
$("unload").onclick = async () => { setBusy(true); try { await api("/api/engine/stop", "POST", {}); await refresh(); } catch(e) { notice(e.message); } finally { setBusy(false); } };
$("stop").onclick = async () => { try { await api("/api/cancel", "POST", {}); $("stop").textContent = "Stopping…"; $("stop").disabled = true; } catch(e) { notice(e.message); } };
$("prompt").onkeydown = event => { if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!busy && running) $("composer").requestSubmit(); } };
$("composer").onsubmit = async event => {
  event.preventDefault(); const prompt = $("prompt").value.trim(); if (!prompt || busy || !running) return;
  notice(); setBusy(true); let responseText = null, complete = false;
  try {
    if (!active) { const chat = await (await api("/api/chats", "POST", {})).json(); active = chat.id; $("messages").replaceChildren(); }
    message("user", prompt); responseText = message("assistant", ""); $("prompt").value = "";
    $("stop").hidden = false; $("stop").disabled = false; $("stop").textContent = "Stop response";
    const response = await api("/api/generate", "POST", {chat_id: active, prompt, mode: workspaceMode});
    const reader = response.body.getReader(), decoder = new TextDecoder(); let pending = "";
    while (true) {
      const {done, value} = await reader.read();
      pending += decoder.decode(value || new Uint8Array(), {stream: !done});
      const lines = pending.split("\n"); pending = lines.pop();
      for (const line of lines) {
        if (!line) continue; const item = JSON.parse(line);
        if (item.token) { responseText.textContent += item.token; scrollMessages(); }
        if (item.error) notice(item.error);
        if (item.done) complete = true;
      }
      if (done) break;
    }
    if (!complete) throw new Error("Connection ended before completion. Check the saved conversation before retrying.");
    await openChat(active);
  } catch(e) { notice(e.message); if (responseText && !responseText.textContent) responseText.textContent = "Response unavailable. Your message may already be saved; reopen this conversation before retrying."; }
  finally { $("stop").hidden = true; setBusy(false); await listChats().catch(e => notice(e.message)); $("prompt").focus(); }
};
$("export").onclick = async () => {
  if (!active) return notice("Open a conversation to export it.");
  try { const chat = await (await api(`/api/chats/${active}`)).json(); const text = `# ${chat.title}\n\n` + chat.messages.map(m => `## ${m.role === "user" ? "You" : "MyAi"}${m.status !== "complete" ? ` (${m.status})` : ""}\n\n${m.content}`).join("\n\n"); const url = URL.createObjectURL(new Blob([text], {type: "text/markdown"})); const a = document.createElement("a"); a.href = url; a.download = `MyAi-${active.slice(0,8)}.md`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); } catch(e) { notice(e.message); }
};
bindSuggestions();
Promise.all([refresh(), listChats()]).catch(e => notice(e.message));

let workspaceMode = "chat", mediaKind = "image", mediaPoll = null;
const mediaURLs = [];
function clearMediaURLs() { for (const url of mediaURLs.splice(0)) URL.revokeObjectURL(url); }
document.querySelectorAll("[data-workspace]").forEach(button => button.onclick = async () => {
  if (busy) return notice("Wait for the active operation to finish.");
  const mode = button.dataset.workspace; const studio = mode === "image" || mode === "video";
  document.querySelectorAll("[data-workspace]").forEach(b => b.classList.toggle("primary", b === button));
  $("studio").hidden = !studio; $("messages").hidden = studio; document.querySelector("footer").hidden = studio;
  document.querySelector(".engine-bar").hidden = studio; $("settings").hidden = studio;
  if (studio) { mediaKind = mode; $("video-opt-in").hidden = mode !== "video"; await refreshMedia().catch(e => notice(e.message)); }
  else { workspaceMode = mode; $("prompt").placeholder = mode === "code" ? "Paste code, describe a bug, or ask for an implementation…" : "Ask anything. Keep it yours."; await refresh().catch(e => notice(e.message)); }
});
async function refreshMedia() {
  const state = await (await api("/api/media")).json();
  const selected = $("media-preset").value; $("media-preset").replaceChildren();
  for (const p of state.presets.filter(p => p.kind === mediaKind)) $("media-preset").add(new Option(p.name + (p.ready ? " · installed" : " · setup needed"), p.id));
  if (state.presets.some(p => p.id === selected && p.kind === mediaKind)) $("media-preset").value = selected;
  $("studio-hint").textContent = "Generation unloads the chat model to free memory. " + (state.runtime_found ? "Missing models can be installed with scripts/setup_models.py; see docs/STUDIO.md." : "Diffusion runtime setup is required; see docs/STUDIO.md.");
  const current = state.jobs.find(j => j.status === "running");
  $("media-status").textContent = current ? "Generating locally… This may take several minutes. You can leave this tab open or return later." : "Ready for your next creation.";
  $("media-generate").disabled = Boolean(current);
  $("media-stop").disabled = !current;
  $("creations").replaceChildren(); clearMediaURLs();
  for (const job of state.jobs.filter(j => j.kind === mediaKind)) {
    const card = document.createElement("article"); card.className = "creation";
    const title = document.createElement("p"); title.textContent = job.prompt;
    const detail = document.createElement("small"); detail.textContent = `${job.status} · seed ${job.seed} · ${job.seconds || 0}s` + (job.error ? ` · ${job.error}` : ""); card.append(title, detail);
    if (job.status === "complete") {
      const button = document.createElement("button"); button.textContent = job.kind === "video" ? "Download video (AVI)" : "View / download image";
      button.onclick = async () => { try { const blob = await (await api(`/api/media/result/${job.id}`)).blob(); const url = URL.createObjectURL(blob); mediaURLs.push(url); if(job.kind === "image") {const img = document.createElement("img"); img.src = url; img.alt = job.prompt; card.append(img);} const link = document.createElement("a"); link.href = url; link.download = `MyAi-${job.id}.${job.kind === "video" ? "avi" : "png"}`; link.textContent = "Save file ↓"; card.append(link); if (job.kind === "video") link.click(); button.disabled = true; } catch(e) { notice(e.message); } }; card.append(button);
    }
    $("creations").append(card);
  }
  clearTimeout(mediaPoll); if (current) mediaPoll = setTimeout(() => refreshMedia().catch(e => notice(e.message)), 2500);
}
$("media-generate").onclick = async () => {
  $("media-generate").disabled = true; notice();
  try { await api("/api/media/start", "POST", {preset: $("media-preset").value, prompt: $("media-prompt").value, steps: Number($("media-steps").value), seed: Number($("media-seed").value), experimental: $("video-confirm").checked}); } catch(e) { notice(e.message); }
  await refreshMedia().catch(e => notice(e.message));
};
$("media-stop").onclick = async () => { try {await api("/api/media/cancel", "POST", {}); await refreshMedia();} catch(e) {notice(e.message);} };

function renderContent(target, value) {
  target.replaceChildren();
  const blocks = value.split(/```[^\n]*\n([\s\S]*?)```/g);
  blocks.forEach((part, index) => {
    if (index % 2) { const pre = document.createElement("pre"), code = document.createElement("code"); code.textContent = part; pre.append(code); target.append(pre); }
    else { part.split(/\*\*([^*]+)\*\*/g).forEach((piece, i) => { if(i % 2) { const strong = document.createElement("strong"); strong.textContent = piece; target.append(strong); } else target.append(document.createTextNode(piece)); }); }
  });
}
