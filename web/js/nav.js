"use strict";
(function () {
  const byId = id => document.getElementById(id);
  const palette = byId("command-palette");
  const search = byId("palette-search");
  const list = byId("palette-list");
  const commands = [
    ["Chat", "Switch to Chat", () => switchMode("chat")],
    ["Code", "Switch to Code", () => switchMode("code")],
    ["Studio", "Open image generation", () => switchMode("image")],
    ["Docs", "Open document workspace", () => switchMode("docs")],
    ["Autonomous agent", "Run a multi-step goal", () => switchMode("agent")],
    ["Auto-approve actions", "Toggle autonomous execution approval", () => { const input = byId("auto-approve"); input.checked = !input.checked; input.dispatchEvent(new Event("change")); }],
    ["Clear conversation", "Start a fresh conversation", () => byId("new-chat").click()],
    ["Export markdown", "Download the active conversation", () => byId("export").click()]
  ];
  function switchMode(mode) {
    const button = document.querySelector(`[data-workspace="${mode}"]`);
    if (button) button.click();
  }
  function render(filter = "") {
    list.replaceChildren();
    commands.filter(([name, description]) => `${name} ${description}`.toLowerCase().includes(filter.toLowerCase())).forEach(([name, description, run]) => {
      const button = document.createElement("button");
      button.className = "palette-command";
      button.type = "button";
      button.innerHTML = `<span>${name}</span><small>${description}</small>`;
      button.onclick = () => { run(); close(); };
      list.append(button);
    });
  }
  function open() { render(); palette.hidden = false; search.value = ""; search.focus(); }
  function close() { palette.hidden = true; }
  byId("palette-open").onclick = open;
  document.querySelectorAll("[data-palette-close]").forEach(node => node.onclick = close);
  search.oninput = () => render(search.value);
  document.addEventListener("keydown", event => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); open(); }
    if (event.key === "Escape" && !palette.hidden) close();
  });
})();
