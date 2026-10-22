/* Tokens stay in memory: refreshing the page requires signing in again. */
let token = null, user = null, authMode = 'login', currentPage = 1;
const app = document.querySelector('#app');
const notice = document.querySelector('#notice');
const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const instructor = () => user && ['instructor', 'admin'].includes(user.role);
const clearNotice = () => { notice.hidden = true; };
function showError(error) { notice.textContent = error.message || String(error); notice.hidden = false; notice.focus(); }
function explain(value) {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(explain).join(' ');
  return Object.entries(value).map(([key, val]) => `${key}: ${explain(val)}`).join('\n');
}
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {'Content-Type':'application/json', ...(token ? {'Authorization':`Token ${token}`} : {}), ...options.headers}});
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({detail:'The server returned an unexpected response.'}));
  if (!response.ok) {
    if (response.status === 401 && token) { token = null; user = null; renderAuth(); }
    throw new Error(explain(data));
  }
  return data;
}
function bind(id, event, callback) {
  const element = document.getElementById(id);
  if (element) element.addEventListener(event, async e => { try { await callback(e); } catch (error) { showError(error); } });
}
function nav() {
  document.querySelector('#nav').innerHTML = user ? `<span class="identity">${esc(user.username)} · ${esc(user.role)}</span><button id="browse-nav" class="quiet">Quizzes</button><button id="history-nav" class="quiet">My results</button>${instructor() ? '<button id="create-nav" class="primary">+ Create quiz</button>' : ''}<button id="logout-nav" class="quiet">Log out</button>` : '<span class="small">Your next learning habit.</span>';
  bind('browse-nav','click',() => browse());
  bind('history-nav','click',() => history());
  bind('create-nav','click',() => builder());
  bind('logout-nav','click',async () => { await api('/api/auth/logout/', {method:'POST'}); token=null; user=null; renderAuth(); });
}
function renderAuth() {
  clearNotice(); nav();
  const register = authMode === 'register';
  app.innerHTML = `<div class="auth-layout"><section><span class="eyebrow">Small steps. Sharper skills.</span><h1>A little practice.<br>A lot of progress.</h1><p>Test what you know, discover what you don't, and turn every quiz into your next breakthrough.</p><div class="actions"><span class="tag">Instant feedback</span><span class="tag">Personal progress</span><span class="tag">Made for learning</span></div></section><section class="auth-card"><div class="auth-tabs"><button id="login-tab" class="${!register?'active':''}">Sign in</button><button id="register-tab" class="${register?'active':''}">Create account</button></div><h2>${register?'Start your next chapter.':'Welcome back.'}</h2><p class="small">${register?'Create a learner account to get started.':'Sign in to find your next challenge.'}</p><form id="auth-form"><label for="username">Username</label><input id="username" name="username" autocomplete="username" maxlength="150" required>${register?'<label for="email">Email</label><input id="email" name="email" type="email" autocomplete="email" required>':''}<label for="password">Password</label><input id="password" name="password" type="password" autocomplete="${register?'new-password':'current-password'}" maxlength="128" ${register?'minlength="8"':''} required>${register?'<p class="small">Use at least 8 characters. Avoid common passwords and personal information.</p>':''}<button class="primary full" type="submit">${register?'Create account':'Sign in'} →</button></form><p class="small">Your sign-in lasts until you refresh or close this page. Instructors are appointed by an administrator.</p></section></div>`;
  bind('login-tab','click',() => { authMode='login'; renderAuth(); });
  bind('register-tab','click',() => { authMode='register'; renderAuth(); });
  bind('auth-form','submit',async e => {
    e.preventDefault(); clearNotice(); const button=e.target.querySelector('button[type=submit]'); button.disabled=true;
    try { const payload=Object.fromEntries(new FormData(e.target)); const result=await api(`/api/auth/${register?'register':'login'}/`, {method:'POST',body:JSON.stringify(payload)}); token=result.token; user=result.user; await browse(); }
    finally { button.disabled=false; }
  });
}
function pager(data, callback) {
  document.querySelector('#pagination').innerHTML = `${data.previous?'<button id="prev">← Previous</button>':''}${data.next?'<button id="next">Next →</button>':''}`;
  bind('prev','click',() => callback(currentPage-1)); bind('next','click',() => callback(currentPage+1));
}
async function browse(page=1, search='', mine=false) {
  clearNotice(); nav(); app.innerHTML='<p class="loading">Finding your next challenge…</p>';
  const data=await api(`/api/quizzes/?page=${page}&search=${encodeURIComponent(search)}${mine?'&mine=true':''}`); currentPage=page;
  app.innerHTML=`<section class="hero"><div><span class="eyebrow">The practice room</span><h1>Stay curious.<br>Keep growing.</h1><p>Pick a topic, put your knowledge to work, and learn something along the way.</p><span class="tag">${data.count} quiz${data.count===1?'':'zes'} to explore</span></div><div class="hero-art" aria-hidden="true"><b>Q.</b><span>MAKE KNOWLEDGE STICK</span></div></section><div class="toolbar"><h2>${mine?'Your quizzes':'Find your next challenge'}</h2><form id="search-form"><input aria-label="Search quizzes" name="search" placeholder="Search by topic or title" value="${esc(search)}"><button type="submit">Search</button>${instructor()?`<button type="button" id="mine-toggle">${mine?'All quizzes':'My quizzes'}</button>`:''}</form></div><div class="grid">${data.results.map(q=>`<article class="quiz-card"><span class="tag ${q.is_published?'':'draft'}">${q.is_published?esc(q.category):'Draft'}</span><h3>${esc(q.title)}</h3><p>${esc(q.description || 'A fresh opportunity to put your knowledge to the test.')}</p><div class="card-bottom"><span class="meta">${q.question_count} questions · ${esc(q.owner)}</span><button class="primary" data-quiz="${q.id}">${q.is_published?'Take quiz →':'Edit draft →'}</button></div></article>`).join('') || '<div class="empty"><h3>No quizzes here yet.</h3><p>Try another search or ask an instructor to publish a quiz.</p></div>'}</div><div class="pagination" id="pagination"></div>`;
  bind('search-form','submit',e=>{e.preventDefault();return browse(1,new FormData(e.target).get('search'),mine);});
  bind('mine-toggle','click',()=>browse(1,search,!mine));
  document.querySelectorAll('[data-quiz]').forEach(b=>b.addEventListener('click',()=>openQuiz(b.dataset.quiz).catch(showError)));
  pager(data,p=>browse(p,search,mine));
}
async function openQuiz(id) {
  clearNotice(); const quiz=await api(`/api/quizzes/${id}/`);
  if (!quiz.is_published && quiz.can_edit) return builder(quiz);
  app.innerHTML=`<div class="narrow"><button class="quiet back" id="back">← All quizzes</button><div class="eyebrow">${esc(quiz.category)} · ${quiz.question_count} questions</div><h1>${esc(quiz.title)}</h1><p>${esc(quiz.description)}</p><p class="small">Choose one answer for every question. You can retake this practice quiz.</p><form id="quiz-form">${quiz.questions.map((q,i)=>`<section class="question"><span class="eyebrow">Question ${i+1}</span><h3>${esc(q.text)}</h3><div class="choices">${q.choices.map(c=>`<label class="choice"><input type="radio" name="q-${q.id}" value="${c.id}" required><span>${esc(c.text)}</span></label>`).join('')}</div></section>`).join('')}<button class="primary full" type="submit">Submit answers →</button></form></div>`;
  bind('back','click',()=>browse());
  bind('quiz-form','submit',async e=>{
    e.preventDefault(); clearNotice(); const button=e.target.querySelector('button[type=submit]');button.disabled=true;
    try {const form=new FormData(e.target);const answers=quiz.questions.map(q=>({question_id:q.id,choice_id:Number(form.get(`q-${q.id}`))}));const result=await api(`/api/quizzes/${quiz.id}/submit/`,{method:'POST',body:JSON.stringify({answers})});renderResult(result);}
    finally{button.disabled=false;}
  });
}
function renderResult(result) {
  clearNotice();app.innerHTML=`<div class="narrow"><div class="score"><span class="eyebrow">Practice complete</span><h2>${esc(result.quiz_title)}</h2><strong>${result.score}<span style="font-size:30px"> / ${result.total}</span></strong><p>${result.percentage}% correct. Every question is a chance to learn.</p></div><h2>Let's look at your answers.</h2>${result.review.map((r,i)=>`<section class="question ${r.is_correct?'correct':'incorrect'}"><span class="eyebrow">${i+1} · ${r.is_correct?'Correct':'Keep practicing'}</span><h3>${esc(r.question)}</h3><p>Your answer: <b>${esc(r.selected_answer)}</b></p>${r.is_correct?'':`<p>Correct answer: <b>${esc(r.correct_answer)}</b></p>`}</section>`).join('')}<div class="actions"><button class="primary" id="more-quizzes">Explore more quizzes →</button>${result.quiz_available ? '<button id="retake">Try again</button>' : ''}<button id="results">My results</button></div></div>`;
  bind('more-quizzes','click',()=>browse());bind('retake','click',()=>openQuiz(result.quiz));bind('results','click',()=>history());
}
async function history(page=1) {
  clearNotice();nav();const data=await api(`/api/attempts/?page=${page}`);currentPage=page;
  app.innerHTML=`<div class="narrow"><span class="eyebrow">Your learning journal</span><h1>Progress, one quiz<br>at a time.</h1><p>${data.count} completed attempt${data.count===1?'':'s'}. Revisit your answers and keep building.</p>${data.results.map(r=>`<article class="history-row"><div><h3>${esc(r.quiz_title)}</h3><span class="meta">${esc(new Date(r.submitted_at).toLocaleString())}</span></div><div class="actions"><span class="tag">${r.score} / ${r.total} · ${r.percentage}%</span><button data-result="${r.id}">Review →</button></div></article>`).join('') || '<div class="empty"><h3>Your story starts here.</h3><p>Complete a quiz to see your results.</p><button id="start" class="primary">Find a quiz</button></div>'}<div class="pagination" id="pagination"></div></div>`;
  bind('start','click',()=>browse());pager(data,p=>history(p));
  document.querySelectorAll('[data-result]').forEach(b=>b.addEventListener('click',async()=>{try{renderResult(await api(`/api/attempts/${b.dataset.result}/`));}catch(error){showError(error);}}));
}
function builder(quiz=null) {
  clearNotice();nav();
  app.innerHTML=`<div class="narrow"><span class="eyebrow">Instructor studio</span><h1>${quiz?'Shape your quiz.':'Share what you know.'}</h1><p>Create single-answer questions with 2–6 choices. Published quizzes are locked to preserve results.</p><form id="builder-form"><section class="panel"><label for="title">Quiz title</label><input id="title" maxlength="160" value="${esc(quiz?.title || '')}" required><label for="category">Category</label><input id="category" maxlength="60" value="${esc(quiz?.category || 'General')}" required><label for="description">Description</label><textarea id="description" maxlength="2000">${esc(quiz?.description || '')}</textarea></section><div id="question-editor"></div><button id="add-question" type="button">+ Add question</button><p class="small">Select the radio button beside the correct answer for each question.</p><label class="choice"><input id="publish" type="checkbox">Publish now (this permanently locks the quiz)</label><div class="actions"><button class="primary" type="submit">Save quiz →</button><button id="cancel" type="button">Cancel</button>${quiz?'<button id="delete-draft" type="button">Delete draft</button>':''}</div></form></div>`;
  let serial=0;
  function addQuestion(data={text:'',choices:[{text:'',is_correct:true},{text:'',is_correct:false}]}) {
    const editor=document.querySelector('#question-editor'); if(editor.children.length>=50) throw new Error('A quiz supports up to 50 questions.');
    const number=++serial;const section=document.createElement('section');section.className='question';
    section.innerHTML=`<div class="flex"><span class="eyebrow">Question</span><button class="remove-question" type="button">Remove question</button></div><label for="question-${number}">Question text</label><textarea id="question-${number}" class="question-text" maxlength="1000" required>${esc(data.text)}</textarea><div class="editor-choices"></div><button class="add-choice" type="button" style="margin-top:12px">+ Add choice</button>`;
    function addChoice(choice={text:'',is_correct:false}) {
      const choices=section.querySelector('.editor-choices');if(choices.children.length>=6) throw new Error('Each question supports up to 6 choices.');
      const row=document.createElement('div');row.className='builder-choice';row.innerHTML=`<input type="radio" name="correct-${number}" aria-label="Mark as correct answer" ${choice.is_correct?'checked':''} required><input class="choice-text" aria-label="Answer choice" maxlength="500" value="${esc(choice.text)}" required><button type="button" aria-label="Remove choice">×</button>`;
      row.querySelector('button').onclick=()=>{if(choices.children.length<=2){showError(new Error('Keep at least two choices.'));return;}row.remove();};choices.append(row);
    }
    data.choices.forEach(addChoice);section.querySelector('.add-choice').onclick=()=>{try{addChoice();}catch(error){showError(error);}};section.querySelector('.remove-question').onclick=()=>section.remove();editor.append(section);
  }
  (quiz?.questions || [{text:'',choices:[{text:'',is_correct:true},{text:'',is_correct:false}]}]).forEach(addQuestion);
  bind('add-question','click',()=>addQuestion());bind('cancel','click',()=>browse());
  bind('delete-draft','click',async()=>{if(confirm('Delete this draft?')){await api(`/api/quizzes/${quiz.id}/`,{method:'DELETE'});await browse();}});
  bind('builder-form','submit',async e=>{
    e.preventDefault();clearNotice();const button=e.target.querySelector('button[type=submit]');button.disabled=true;
    try {
      const questions=[...document.querySelectorAll('#question-editor > section')].map(section=>({text:section.querySelector('.question-text').value,choices:[...section.querySelectorAll('.builder-choice')].map(row=>({text:row.querySelector('.choice-text').value,is_correct:row.querySelector('[type=radio]').checked}))}));
      const payload={title:document.querySelector('#title').value,category:document.querySelector('#category').value,description:document.querySelector('#description').value,is_published:document.querySelector('#publish').checked,questions};
      await api(quiz?`/api/quizzes/${quiz.id}/`:'/api/quizzes/',{method:quiz?'PUT':'POST',body:JSON.stringify(payload)});await browse(1,'',true);
    } finally{button.disabled=false;}
  });
}
renderAuth();
