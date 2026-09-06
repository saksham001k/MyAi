"use strict";
(function () {
  const messages = document.getElementById("messages");
  const observer = new MutationObserver(() => {
    messages.querySelectorAll("details:not([data-enhanced])").forEach(block => {
      block.dataset.enhanced = "true";
      block.classList.add("agent-event");
      const summary = block.querySelector("summary");
      if (summary && /action/i.test(summary.textContent)) block.dataset.state = "action";
      if (summary && /observation/i.test(summary.textContent)) block.dataset.state = "observation";
    });
    messages.querySelectorAll("pre:not([data-enhanced])").forEach(pre => {
      pre.dataset.enhanced = "true";
      pre.setAttribute("tabindex", "0");
    });
  });
  observer.observe(messages, {childList: true, subtree: true});
})();
