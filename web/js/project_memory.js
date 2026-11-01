/* Persistent project selection, revisioned decisions and source-grounded recall. */
(() => {
  const el = name => document.getElementById('project-memory-' + name);
  const request = async (...args) => (await api(...args)).json();
  let selected = sessionStorage.getItem('myai-shared-project') || '';
  let context = null;
  window.selectedSharedProject = () => selected;
  async function operation(action) {
    el('error').hidden = true;
    const controls = [...el('dialog').querySelectorAll('button,input,textarea,select')];
    controls.forEach(control => { control.disabled = true; });
    try { await action(); }
    catch (error) { el('error').textContent = error.message; el('error').hidden = false; }
    finally { controls.forEach(control => { control.disabled = false; }); }
  }
  function paragraph(parent, value) {
    const p = document.createElement('p');
    p.textContent = value;
    parent.append(p);
  }
  async function show() {
    context = null;
    el('current').replaceChildren();
    el('answer').textContent = '';
    el('workspace').readOnly = !!selected;
    el('save').textContent = selected ? 'Save project brief' : 'Create shared project';
    if (!selected) { el('status').textContent = 'No shared project linked.'; el('form').reset(); return; }
    context = await request('/api/powerhouse/projects/' + selected);
    const project = context.project;
    el('name').value = project.name;
    el('workspace').value = project.workspace;
    el('goal').value = project.goal;
    el('acceptance').value = project.acceptance.join('\n');
    el('status').textContent = project.name + ' · revision ' + project.revision + ' · linked to project tasks';
    if (project.workspace) document.getElementById('task-project').value = project.workspace;
    paragraph(el('current'), 'Goal: ' + project.goal);
    paragraph(el('current'), 'Acceptance: ' + project.acceptance.join('; '));
    paragraph(el('current'), 'Current state: ' + (project.state || 'No current handoff yet.'));
    if (project.next_action) paragraph(el('current'), 'Next: ' + project.next_action);
    if (context.handoff_stale) paragraph(el('current'), 'Earlier handoff excluded because the project changed.');
    for (const conflict of context.conflicts) paragraph(el('current'), 'Unresolved conflict: ' + conflict.key);
    for (const decision of context.decisions) {
      const row = document.createElement('article');
      paragraph(row, decision.key + ': ' + decision.value);
      const edit = document.createElement('button'); edit.type = 'button'; edit.textContent = 'Correct';
      edit.onclick = () => operation(async () => {
        const value = window.prompt('Correct this decision', decision.value);
        if (value === null) return;
        await request('/api/powerhouse/projects/' + selected + '/decision', 'POST', {
          action: 'edit', id: decision.id, revision: context.project.revision,
          decision_revision: decision.revision, value,
        });
        await show();
      });
      const forget = document.createElement('button'); forget.type = 'button'; forget.textContent = 'Forget';
      forget.onclick = () => operation(async () => {
        await request('/api/powerhouse/projects/' + selected + '/decision', 'POST', {
          action: 'forget', id: decision.id, revision: context.project.revision, decision_revision: decision.revision,
        });
        await show();
      });
      row.append(edit, forget); el('current').append(row);
    }
  }
  async function refresh() {
    const result = await request('/api/powerhouse/projects');
    if (selected && !result.projects.some(project => project.id === selected)) selected = '';
    sessionStorage.setItem('myai-shared-project', selected);
    el('select').replaceChildren(new Option('No linked project', ''));
    for (const project of result.projects) el('select').add(new Option(project.name, project.id));
    el('select').value = selected;
    await show();
  }
  el('open').onclick = () => { el('dialog').showModal(); operation(refresh); };
  el('close').onclick = () => el('dialog').close();
  el('refresh').onclick = () => operation(refresh);
  el('select').onchange = () => operation(async () => {
    selected = el('select').value;
    sessionStorage.setItem('myai-shared-project', selected);
    await show();
  });
  el('form').onsubmit = event => {
    event.preventDefault(); operation(async () => {
      const body = {
        name: el('name').value, workspace: el('workspace').value.trim(), goal: el('goal').value,
        acceptance: el('acceptance').value.split('\n').map(value => value.trim()).filter(Boolean),
      };
      if (selected) body.revision = context.project.revision;
      const project = await request('/api/powerhouse/projects' + (selected ? '/' + selected : ''), 'POST', body);
      selected = project.id; await refresh();
    });
  };
  el('decision-form').onsubmit = event => {
    event.preventDefault(); operation(async () => {
      if (!context) throw new Error('Select a project first.');
      await request('/api/powerhouse/projects/' + selected + '/decision', 'POST', {
        revision: context.project.revision, key: el('key').value.trim(), value: el('value').value,
      });
      el('key').value = ''; el('value').value = ''; await show();
    });
  };
  el('question-form').onsubmit = event => {
    event.preventDefault(); operation(async () => {
      if (!selected) throw new Error('Select a project first.');
      el('answer').textContent = '';
      const result = await request('/api/powerhouse/ask', 'POST', { project_id: selected, question: el('question').value });
      el('answer').textContent = result.answer;
    });
  };
})();
