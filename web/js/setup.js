"use strict";
(() => {
  const el = (id) => document.getElementById(id);
  let timer;
  const error = (e) => { el("download-status").textContent = e.message; };
  function measurement(m) {
    const parts = [];
    if (m.time_to_first_token_ms != null) parts.push(`First response: ${m.time_to_first_token_ms} ms`);
    if (m.tokens_per_second != null) parts.push(`${m.tokens_per_second.toFixed(1)} tokens/s (engine)`);
    if (m.content_events_per_second != null) parts.push(`${m.content_events_per_second} content events/s (not tokens)`);
    return parts.join(" · ") || m.note || "No measurement yet.";
  }
  window.showLocalMetrics = (metrics) => { el("local-metrics").textContent = measurement(metrics); };
  async function poll() {
    clearTimeout(timer);
    try {
      const state = await (await api("/api/catalog/download")).json();
      const active = ["starting", "downloading", "verified"].includes(state.status);
      const size = state.received == null ? "" : ` · ${(state.received / 1e6).toFixed(1)} MB${state.total ? ` of ${(state.total / 1e6).toFixed(1)} MB` : ""}`;
      el("download-status").textContent = state.status === "idle" ? "Choose a model to download. Existing models are kept." : `${state.filename}: ${state.status}${size}${state.error ? " · " + state.error : ""}`;
      el("cancel-download").hidden = !active;
      el("download-model").disabled = active;
      if (active) timer = setTimeout(poll, 1000);
      else if (state.status === "complete") await refresh();
    } catch (e) { error(e); }
  }
  async function load() {
    try {
      const [catalog, status] = await Promise.all([
        api("/api/catalog").then((r) => r.json()),
        api("/api/status").then((r) => r.json()),
      ]);
      const select = el("catalog-model");
      select.replaceChildren();
      for (const model of catalog.models) {
        const option = document.createElement("option");
        option.value = model.id;
        option.textContent = `${model.name} · ~${(model.size_bytes_approx / 1e9).toFixed(1)} GB${model.installed ? " · Installed" : ""}`;
        select.append(option);
      }
      const detail = () => {
        const model = catalog.models.find((m) => m.id === select.value);
        el("catalog-detail").textContent = model ? `License: ${model.license}. ${model.notes}` : "No models available.";
      };
      select.onchange = detail;
      detail();
      const ram = status.memory;
      el("memory-status").textContent = `RAM: ${ram.total_mb == null ? "unknown" : (ram.total_mb / 1024).toFixed(1) + " GiB total"} · ${ram.available_mb == null ? "available memory unknown" : (ram.available_mb / 1024).toFixed(1) + " GiB available estimate"}. ${catalog.recommendation.reason}`;
      if (status.metrics) window.showLocalMetrics(status.metrics);
      await poll();
    } catch (e) { error(e); }
  }
  el("model-tools").addEventListener("toggle", () => { if (el("model-tools").open) load(); });
  el("download-model").onclick = async () => {
    el("download-model").disabled = true;
    el("download-status").textContent = "Checking publisher checksum…";
    try {
      await api("/api/catalog/download", "POST", {id: el("catalog-model").value});
      await poll();
    } catch (e) { error(e); el("download-model").disabled = false; }
  };
  el("cancel-download").onclick = async () => {
    try { await api("/api/catalog/cancel", "POST", {}); await poll(); } catch (e) { error(e); }
  };
  el("measure-model").onclick = async () => {
    el("measure-model").disabled = true;
    el("local-metrics").textContent = "Measuring the loaded model…";
    try {
      window.showLocalMetrics(await (await api("/api/engine/calibrate", "POST", {})).json());
    } catch (e) { el("local-metrics").textContent = e.message; }
    finally { el("measure-model").disabled = false; }
  };
})();
