import React, { useEffect, useRef, useState } from 'react';
import { CalendarDays, Check, CheckCircle2, ChevronRight, Clock3, Coffee, Sparkles, Utensils, WandSparkles } from 'lucide-react';
import { dateLabel, monthLabel } from './calendar';
import './strategy.css';

function IdeaWorkspace({ restaurant, plan, task, onPlanChange, api, onNotify }) {
  const [ideas, setIdeas] = useState([]);
  const [selectedIdea, setSelectedIdea] = useState(null);
  const [feedback, setFeedback] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [failedAction, setFailedAction] = useState('');
  const request = useRef(null);
  const mounted = useRef(false);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; request.current?.abort(); };
  }, []);

  async function generate() {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy('generate');
    setError('');
    setFailedAction('');
    setSelectedIdea(null);
    try {
      const result = await api.generateIdeas(restaurant.id, {
        month: plan.month,
        task_id: task.id,
        previous_ideas: ideas,
        feedback: feedback.trim(),
      }, { signal: controller.signal });
      if (!mounted.current || controller.signal.aborted) return;
      if (!Array.isArray(result?.ideas) || result.ideas.length === 0) {
        setError('No ideas were returned. Please try generating again.');
        setFailedAction('generate');
        return;
      }
      setIdeas(result.ideas);
      onNotify?.('Your content ideas are ready.');
    } catch (failure) {
      if (mounted.current && !controller.signal.aborted) {
        setError('We couldn’t generate your ideas. Please try again in a moment.');
        setFailedAction('generate');
      }
    } finally {
      if (request.current === controller) {
        request.current = null;
        if (mounted.current) setBusy('');
      }
    }
  }

  async function save() {
    if (!selectedIdea || request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy('save');
    setError('');
    setFailedAction('');
    try {
      const updated = await api.updateTask(restaurant.id, task.id, {
        month: plan.month, saved_idea: selectedIdea,
      }, { signal: controller.signal });
      if (!mounted.current || controller.signal.aborted) return;
      onPlanChange(updated);
      setSelectedIdea(null);
      onNotify?.('Idea saved to your calendar task.');
    } catch (failure) {
      if (mounted.current && !controller.signal.aborted) {
        setError('We couldn’t save this idea. Your selection is still here; please try again.');
        setFailedAction('save');
      }
    } finally {
      if (request.current === controller) {
        request.current = null;
        if (mounted.current) setBusy('');
      }
    }
  }

  return <>
    <section className="selectedTaskCard">
      <div className="selectedTaskIcon"><CalendarDays size={21}/></div><div className="selectedTaskBody"><div className="selectedTaskMeta"><span>{task.type}</span><span>{dateLabel(task.date)}</span><span>{task.status}</span></div><h2 dir="auto">{task.title}</h2><p dir="auto">{task.objective}</p></div>
    </section>

    {task.saved_idea && <section className="savedContentCard" aria-label="Saved content idea"><div className="savedContentHeading"><CheckCircle2 size={19}/><span>SAVED TO THIS CALENDAR TASK</span></div><h3 dir="auto">{task.saved_idea.name}</h3><p dir="auto">{task.saved_idea.description}</p>{task.saved_idea.hook && <blockquote dir="auto">{task.saved_idea.hook}</blockquote>}<div className="chips"><span>{task.saved_idea.content_format || task.type}</span>{task.saved_idea.angle && <span dir="auto">{task.saved_idea.angle}</span>}</div></section>}

    <section className="ideasSection">
      <div className="ideasHeader"><div><div className="eyebrow"><Sparkles size={14}/> CONTENT STUDIO</div><h2>Find your next creative direction.</h2><p>Ideas are shaped by <b dir="auto">{restaurant.name}</b>’s profile, monthly strategy, and this calendar task.</p></div></div>
      <div className="ideaGenerationControls"><label htmlFor="content-feedback">Guide the ideas <span>(optional)</span></label><textarea id="content-feedback" value={feedback} onChange={event => setFeedback(event.target.value)} rows={3} maxLength={1500} placeholder="For example: keep it playful, feature our signature item, and make it easy to film on a phone." disabled={Boolean(busy)}/><div className="generationAction"><p>Turn an idea into your own photos, video, and voice.</p><button type="button" className="primary" onClick={generate} disabled={Boolean(busy)}><WandSparkles size={16}/>{busy === 'generate' ? 'Generating ideas…' : ideas.length ? 'Generate another set' : 'Generate content ideas'}</button></div></div>

      {busy === 'generate' && <div className="empty generationLoading" role="status"><Clock3 size={28}/><b>Finding ideas that fit your business…</b><p>Matching the direction to your audience and {task.type.toLowerCase()} format.</p></div>}
      {error && <div className="contentError" role="alert"><p>{error}</p><button type="button" className="outline" disabled={Boolean(busy)} onClick={failedAction === 'save' ? save : generate}>Try again</button></div>}
      {!busy && ideas.length === 0 && !error && <div className="contentStartingPoint"><div className="contentStartIcon"><Sparkles size={24}/></div><div><h3>A good post starts with a clear idea.</h3><p>Generate a few directions, choose your favorite, and save it to this task. Your saved idea stays with your calendar.</p></div></div>}
      {busy !== 'generate' && ideas.length > 0 && <>
        <div className="ideaResultHeading"><h3>Choose a direction</h3><span>{ideas.length} fresh ideas · {task.type}</span></div>
        <div className="ideaGrid">{ideas.map((idea, index) => <button type="button" key={`${idea.id}-${index}-${idea.name}`} className={`ideaCard ${selectedIdea === idea ? 'selectedIdea' : ''}`} aria-pressed={selectedIdea === idea} disabled={busy === 'save'} onClick={() => { setSelectedIdea(idea); setError(''); }}><div className={`ideaVisual ideaVisual${index % 3}`}><span>{String(index + 1).padStart(2, '0')}</span>{selectedIdea === idea ? <CheckCircle2 size={22}/> : <WandSparkles size={21}/>}</div><div className="ideaBody"><div className="ideaMeta"><span dir="auto">{idea.label}</span>{idea.effort && <span>{idea.effort} effort</span>}</div><h3 dir="auto">{idea.name}</h3><p dir="auto">{idea.description}</p><div className="ideaBottom"><span dir="auto">{idea.angle || idea.content_format || task.type}</span><ChevronRight size={16}/></div></div></button>)}</div>
        {selectedIdea && <div className="selectedIdeaPanel"><div><span className="label">YOUR SELECTED DIRECTION</span><h3 dir="auto">{selectedIdea.name}</h3>{selectedIdea.hook && <p className="ideaHook" dir="auto">{selectedIdea.hook}</p>}<div className="chips"><span>{selectedIdea.content_format || task.type}</span><span>AI-generated idea</span></div>{selectedIdea.why_it_fits && <p className="whyItFits" dir="auto">{selectedIdea.why_it_fits}</p>}</div><button type="button" className="primary" onClick={save} disabled={Boolean(busy)}><Check size={16}/>{busy === 'save' ? 'Saving idea…' : task.saved_idea ? 'Replace saved idea' : 'Use this idea'}</button></div>}
      </>}
    </section>
  </>;
}

export default function ContentPage({ restaurant, context, plan, onPlanChange, initialTaskId, api, onNotify }) {
  const [taskId, setTaskId] = useState(initialTaskId || '');
  const tasks = Array.isArray(plan?.tasks) ? plan.tasks : [];
  const task = tasks.find(item => item.id === taskId) || tasks.find(item => item.id === initialTaskId) || tasks[0];
  const business = restaurant?.context || context?.restaurant?.context || {};
  const isCafe = (plan?.business_type || business.business_type) === 'cafe';
  const BusinessIcon = isCafe ? Coffee : Utensils;
  const scope = `${restaurant?.id}:${plan?.month}:${plan?.context_signature}`;

  useEffect(() => { setTaskId(initialTaskId || ''); }, [initialTaskId, scope]);

  return <div className="contentPage">
    <section className="hero"><div><div className="eyebrow"><span className="liveDot"/>CONTENT CREATION{plan?.month && <><span>·</span>{monthLabel(plan.month).toUpperCase()}</>}</div><h1>Bring your brand <span>to life.</span></h1><p>Content that sounds like you, looks like your business, and gives people a reason to stop scrolling.</p></div><div className="contentBusinessBadge"><BusinessIcon size={20}/><div><b dir="auto">{restaurant?.name || 'Your business'}</b><span>{isCafe ? 'Café' : 'Restaurant'}{restaurant?.location ? ` · ${restaurant.location}` : ''}</span></div></div></section>

    {restaurant && <section className="contentContextStrip" aria-label="Business context"><div><span className="label">CREATED AROUND</span><b dir="auto">{business.cuisine || (isCafe ? 'Your café experience' : 'Your dining experience')}</b></div>{business.target_audience && <div><span className="label">YOUR AUDIENCE</span><b dir="auto">{business.target_audience}</b></div>}{business.tone && <div><span className="label">YOUR VOICE</span><b dir="auto">{business.tone}</b></div>}{business.language && <div><span className="label">CONTENT LANGUAGE</span><b>{business.language}</b></div>}</section>}

    {!task ? <section className="ideasSection"><div className="empty"><CalendarDays size={30}/><b>Start with your monthly calendar.</b><p>Save your profile on Home, then open Monthly Strategy to prepare or add a content task.</p></div></section> : <>
      <div className="contentTaskSelector"><div><h2>What are we creating?</h2><p>Choose a task from your monthly plan.</p></div><label htmlFor="content-task">Calendar task<select id="content-task" value={task.id} onChange={event => setTaskId(event.target.value)}>{tasks.map(item => <option key={item.id} value={item.id}>{dateLabel(item.date, { weekday: undefined })} · {item.type} · {item.title}</option>)}</select></label></div>
      <IdeaWorkspace key={`${scope}:${task.id}`} restaurant={restaurant} plan={plan} task={task} api={api} onPlanChange={onPlanChange} onNotify={onNotify}/>
    </>}
  </div>;
}
