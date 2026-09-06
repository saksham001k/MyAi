"use strict";

class ProgressManager {
  constructor(root) {
    this.root = root;
    this.mode = "chat";
    this.steps = [];
  }

  start(mode) {
    this.mode = mode || "chat";
    this.steps = [];
    this.root.hidden = false;
    this.root.className = `progress progress-${this.mode}`;
    this.root.replaceChildren();
    const visual = document.createElement("div");
    visual.className = "progress-visual";
    const fill = document.createElement("div");
    fill.className = "progress-fill";
    visual.append(fill);
    const label = document.createElement("div");
    label.className = "progress-label";
    label.textContent = "Getting ready…";
    this.root.append(visual, label);
    this.fill = fill;
    this.label = label;
    this.stepsRoot = document.createElement("div");
    this.stepsRoot.className = "progress-steps";
    this.root.append(this.stepsRoot);
  }

  update(event) {
    if (!event || event.type !== "progress") return;
    this.mode = event.mode || this.mode;
    this.root.className = `progress progress-${this.mode}`;
    this.fill.style.width = `${event.percentage}%`;
    this.label.textContent = `${event.percentage}% - ${event.stage}`;
    if (event.details) this.label.title = event.details;
  }

  addStep(event) {
    const step = document.createElement("details");
    step.className = "progress-step";
    step.open = true;
    const summary = document.createElement("summary");
    summary.textContent = event.tool ? `${event.type} · ${event.tool}` : event.type;
    const details = document.createElement("pre");
    details.textContent = JSON.stringify(event, null, 2);
    step.append(summary, details);
    this.stepsRoot.append(step);
  }

  finish() {
    if (this.fill) this.fill.style.width = "100%";
    this.root.classList.add("progress-finished");
    setTimeout(() => { this.root.hidden = true; }, 450);
  }
}

window.ProgressManager = ProgressManager;
