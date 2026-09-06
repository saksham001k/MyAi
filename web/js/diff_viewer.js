"use strict";
(function () {
  window.renderDiffFiles = function (container, files, onAccept, onRevert) {
    container.replaceChildren();
    files.forEach(file => {
      const details = document.createElement("details"); details.className = "diff-file"; details.open = true;
      const summary = document.createElement("summary"); summary.textContent = file.path;
      const pre = document.createElement("pre"); pre.className = "diff-content";
      file.diff.split("\n").forEach(line => {
        const row = document.createElement("span");
        row.className = line.startsWith("+") && !line.startsWith("+++") ? "diff-add" : line.startsWith("-") && !line.startsWith("---") ? "diff-remove" : "diff-context";
        row.textContent = line; pre.append(row, "\n");
      });
      const actions = document.createElement("div"); actions.className = "diff-actions";
      const accept = document.createElement("button"); accept.type = "button"; accept.className = "primary"; accept.textContent = "Accept changes"; accept.onclick = () => onAccept(file);
      const revert = document.createElement("button"); revert.type = "button"; revert.textContent = "Revert file"; revert.onclick = () => onRevert(file);
      actions.append(accept, revert); details.append(summary, pre, actions); container.append(details);
    });
  };
})();
