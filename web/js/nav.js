"use strict";
(function () {
  const byId = (id) => document.getElementById(id);
  const palette = byId("command-palette");
  const search = byId("palette-search");
  const list = byId("palette-list");
  const commands = [
    [
      "Attach files",
      "Add files to this conversation",
      () => byId("attach-file").click(),
    ],
    [
      "Project access",
      "Choose the folder MyAi may work on",
      () => {
        byId("project-access").open = true;
        byId("task-project").focus();
      },
    ],
    [
      "Settings",
      "Local model and response preferences",
      () => byId("settings-toggle").click(),
    ],
    [
      "Clear conversation",
      "Start a fresh conversation",
      () => byId("new-chat").click(),
    ],
    [
      "Export markdown",
      "Download the active conversation",
      () => byId("export").click(),
    ],
  ];
  function render(filter = "") {
    list.replaceChildren();
    commands
      .filter(([name, description]) =>
        `${name} ${description}`.toLowerCase().includes(filter.toLowerCase()),
      )
      .forEach(([name, description, run]) => {
        const button = document.createElement("button");
        button.className = "palette-command";
        button.type = "button";
        button.innerHTML = `<span>${name}</span><small>${description}</small>`;
        button.onclick = () => {
          run();
          close();
        };
        list.append(button);
      });
  }
  function open() {
    render();
    palette.hidden = false;
    search.value = "";
    search.focus();
  }
  function close() {
    palette.hidden = true;
    byId("palette-open").focus();
  }
  byId("palette-open").onclick = open;
  document
    .querySelectorAll("[data-palette-close]")
    .forEach((node) => (node.onclick = close));
  search.oninput = () => render(search.value);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Tab" && !palette.hidden) {
      const focusable = [...palette.querySelectorAll("button,input")];
      const first = focusable[0],
        last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      open();
    }
    if (event.key === "Escape" && !palette.hidden) close();
  });
})();
