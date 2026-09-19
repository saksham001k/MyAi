/* Explicit portable facts, separate from ordinary conversation history. */
(() => {
  const el = (name) => document.getElementById('shared-memory-' + name);
  const request = async (...args) => (await api(...args)).json();
  let editing = null;
  const space = () => el('space').value.trim();
  const clearAnswer = () => {
    el('answer').textContent = '';
    el('sources').replaceChildren();
  };
  function cancelEdit() {
    editing = null;
    el('text').value = '';
    el('save').textContent = 'Save fact';
    el('cancel').hidden = true;
  }
  async function operation(action) {
    el('error').hidden = true;
    const controls = [...el('dialog').querySelectorAll('button, input, textarea, select')];
    controls.forEach((control) => { control.disabled = true; });
    try { await action(); }
    catch (error) { el('error').textContent = error.message; el('error').hidden = false; }
    finally { controls.forEach((control) => { control.disabled = false; }); }
  }
  async function refresh() {
    clearAnswer();
    el('records').replaceChildren();
    const connection = await request('/api/shared-memory/status');
    el('status').textContent = connection.connected ? 'Connected to shared memory.' :
      (connection.error || 'Shared memory is not connected. Open MyAi using the Earthma launcher.');
    const state = await request('/api/status');
    const selected = el('model').value;
    el('model').replaceChildren();
    for (const model of state.models) {
      const option = new Option(model.name, model.name);
      option.selected = model.name === (selected || state.model);
      el('model').add(option);
    }
    el('model-status').textContent = state.running ? 'Loaded: ' + state.model : 'Load an installed model to ask a question.';
    if (!connection.connected) return;
    const data = await request('/api/shared-memory/records?namespace=' + encodeURIComponent(space()));
    if (!data.records.length) el('records').textContent = 'No saved facts in this space.';
    for (const record of data.records) {
      const card = document.createElement('article');
      const text = document.createElement('p');
      text.textContent = record.text;
      const detail = document.createElement('small');
      detail.textContent = 'Revision ' + record.revision + ' · ' + record.writer_app;
      const edit = document.createElement('button');
      edit.type = 'button'; edit.textContent = 'Edit';
      edit.addEventListener('click', () => {
        editing = record; el('text').value = record.text;
        el('save').textContent = 'Save changes'; el('cancel').hidden = false;
      });
      const forget = document.createElement('button');
      forget.type = 'button'; forget.textContent = 'Forget';
      forget.addEventListener('click', () => operation(async () => {
        await api('/api/shared-memory/delete', 'POST', {
          namespace: space(), id: record.id, revision: record.revision,
        });
        cancelEdit(); await refresh();
      }));
      card.append(text, detail, edit, forget); el('records').append(card);
    }
  }
  el('open').addEventListener('click', () => {
    el('dialog').showModal(); operation(refresh);
  });
  el('close').addEventListener('click', () => el('dialog').close());
  el('refresh').addEventListener('click', () => operation(async () => { cancelEdit(); await refresh(); }));
  el('space').addEventListener('change', () => operation(async () => { cancelEdit(); await refresh(); }));
  el('cancel').addEventListener('click', cancelEdit);
  el('form').addEventListener('submit', (event) => {
    event.preventDefault(); operation(async () => {
      const body = { namespace: space(), text: el('text').value };
      if (editing) Object.assign(body, { id: editing.id, revision: editing.revision });
      await api('/api/shared-memory/' + (editing ? 'edit' : 'create'), 'POST', body);
      cancelEdit(); await refresh();
    });
  });
  el('load').addEventListener('click', () => operation(async () => {
    clearAnswer(); el('model-status').textContent = 'Loading selected model…';
    await api('/api/engine/start', 'POST', { model: el('model').value, context: 2048, gpu_layers: 0 });
    await refresh();
  }));
  el('question-form').addEventListener('submit', (event) => {
    event.preventDefault(); operation(async () => {
      clearAnswer(); el('answer').textContent = 'Reading current facts…';
      try {
        const result = await request('/api/shared-memory/ask', 'POST', { namespace: space(), question: el('question').value });
        el('answer').textContent = result.answer || 'No matching saved fact. No model was called.';
        for (const source of result.sources) {
          const p = document.createElement('p');
          p.textContent = 'Source · revision ' + source.revision + ': ' + source.text;
          el('sources').append(p);
        }
      } catch (error) { clearAnswer(); throw error; }
    });
  });
})();
