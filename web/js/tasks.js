"use strict";
(function () {
  const el = id => document.getElementById(id);
  let current = null, timer = null, pollGeneration = 0;
  const activeStates = new Set(['queued', 'running', 'cancelling']);
  const labels = {queued:'Queued',running:'Working locally',cancelled:'Cancelled — outputs preserved',interrupted:'Interrupted by restart',failed:'Task failed',budget_exhausted:'Step budget reached',review_ready:'Changes ready for review',answered:'Response ready — inspect the evidence',verification_failed:'Tests failed — changes need review',report_ready:'Cited report ready for review',unverified:'Report needs source verification'};
  const req = async (path, method='GET', body) => {
    const r = await fetch(path,{method,headers:{Authorization:'Bearer '+(sessionStorage.getItem('myai-token') || ''),'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
    if(!r.ok){const e=await r.json();throw new Error(e.error||'Request failed');}return r;
  };
  const error = e => {el('task-error').hidden=false;el('task-error').textContent=e.message;};
  const clearError = () => {el('task-error').hidden=true;};
  function kind(){const project=el('task-kind').value==='project';el('task-project-options').hidden=!project;el('task-command-options').hidden=!project;el('task-goal').placeholder=project?'Describe the change or problem. MyAi will work in a copy and show you the result.':'What should I research? You can include a public source URL.';}
  el('task-kind').onchange=kind;
  el('task-allow-commands').onchange=()=>{el('task-test').disabled=!el('task-allow-commands').checked;};
  el('task-form').onsubmit=async e=>{
    e.preventDefault();clearError();el('task-start').disabled=true;
    try {
      const data=await (await req('/api/tasks','POST',{goal:el('task-goal').value,kind:el('task-kind').value,project_path:el('task-project').value,allow_commands:el('task-allow-commands').checked,test_command:el('task-allow-commands').checked?el('task-test').value:'',max_steps:Number(el('task-steps').value)})).json();
      await select(data.id);await list();
    }catch(e){error(e);el('task-start').disabled=false;}
  };
  async function list(){
    const tasks=await (await req('/api/tasks')).json();el('task-list').replaceChildren();
    for(const task of tasks){const b=document.createElement('button');b.type='button';b.textContent=task.goal.slice(0,70);const s=document.createElement('small');s.textContent=labels[task.status]||task.status;b.append(s);b.onclick=()=>select(task.id).catch(error);el('task-list').append(b);}
    el('task-start').disabled=tasks.some(t=>activeStates.has(t.status));
    if(!current && tasks.length)await select(tasks[0].id);
  }
  async function select(id){current=id;const generation=++pollGeneration;clearTimeout(timer);el('task-result').hidden=false;await poll(generation);}
  function text(tag,value,className){const n=document.createElement(tag);n.textContent=value;if(className)n.className=className;return n;}
  async function poll(generation){
    try{
      const task=await (await req('/api/tasks/'+current)).json();if(generation!==pollGeneration)return;
      render(task);
      if(activeStates.has(task.status))timer=setTimeout(()=>poll(generation),1200);
      else {await list();window.refreshMyAi?.();}
    }catch(e){error(e);if(generation===pollGeneration)timer=setTimeout(()=>poll(generation),4000);}
  }
  function render(task){
    const root=el('task-result');root.replaceChildren();
    root.append(text('h3',task.goal),text('p',labels[task.status]||task.status,'task-status'));
    root.append(text('p',task.verification,'task-warning'));
    if(task.review?.status === 'applied')root.append(text('p','Reviewed changes have been applied to originals.','task-status'));
    if(task.review?.status === 'undone')root.append(text('p','Changes were undone. Originals restored.','task-status'));
    if(task.project)root.append(text('p','Original: '+task.project.source+'\nWorking copy: '+task.project.working_copy,'task-output'));
    if(task.error)root.append(text('p',task.error,'task-warning'));
    const buttons=text('div','','task-buttons');
    if(activeStates.has(task.status)){
      const stop=text('button','Stop task');stop.type='button';stop.onclick=async()=>{stop.disabled=true;stop.textContent='Stopping…';try{await req('/api/tasks/'+task.id+'/cancel','POST',{});}catch(e){error(e);stop.disabled=false;}};buttons.append(stop);
      root.append(text('p','You can leave this page and return. Stop also unloads the owned local model.','local-note'));
    }else if(task.output_path){
      const download=text('button','Download report');download.type='button';download.onclick=async()=>{try{const r=await req('/api/tasks/'+task.id+'/report');const u=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=u;a.download='MyAi-'+task.id.slice(0,8)+'.md';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}catch(e){error(e);}};buttons.append(download);
      root.append(text('p','Saved locally: '+task.output_path,'task-output'));
    }
    root.append(buttons);
    if(task.answer)root.append(text('p',task.answer,'task-answer'));
    if(task.sources?.length){const sources=document.createElement('details');sources.append(text('summary','Retrieved sources and evidence'));for(const source of task.sources){const a=text('a',source.id+' · '+source.url);a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';sources.append(a,text('pre',source.text));}root.append(sources);}
    if(task.review?.files?.length){
      const review=text('section');review.append(text('h4','Review all '+task.review.files.length+' changed files'));
      for(const file of task.review.files){const d=text('details','','task-file');d.append(text('summary',file.path+(file.before===null?' · new':file.after===null?' · deleted':'')),text('pre',file.diff));review.append(d);}
      if(!activeStates.has(task.status)){
        const applied=task.review.status==='applied', draft=task.review.status==='draft';
        if(applied||draft){const apply=text('button',applied?'Undo applied changes':'Apply reviewed changes to originals');apply.type='button';apply.onclick=async()=>{apply.disabled=true;try{await req('/api/tasks/'+task.id+(applied?'/undo':'/apply'),'POST',{review_id:task.review.review_id});await poll(pollGeneration);}catch(e){error(e);apply.disabled=false;}};review.append(apply);}
        review.append(text('p','Apply writes only this reviewed file set. It does not commit or push. Originals are checked for conflicts; Undo is available after applying.','local-note'));
      }root.append(review);
    }
    if(task.test_result)root.append(text('h4','Test output'),text('pre',task.test_result.output));
    const events=document.createElement('details');events.className='task-events';events.append(text('summary','Activity · '+task.events.length+' saved events'));
    for(const e of task.events){const d=document.createElement('details');d.append(text('summary',e.sequence+' · '+(e.tool||e.type)),text('pre',JSON.stringify(e.observation||e.args||e.content||{},null,2)));events.append(d);}root.append(events);
  }
  window.showTasks=()=>list().catch(error);
  kind();
})();
