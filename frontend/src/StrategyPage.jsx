import React, { useEffect, useMemo, useRef, useState } from 'react';
import { CalendarDays, Check, CheckCircle2, Coffee, Flame, Lightbulb, Plus, Target, Utensils, WandSparkles, X } from 'lucide-react';
import { belongsToMonth, calendarMonth, dateLabel, monthLabel } from './calendar';
import './strategy.css';

function AddTaskDialog({ month, initialDate, initialTitle = '', onClose, onSubmit, busy, error }) {
  const dialog = useRef(null);
  const [date, setDate] = useState(initialDate);
  const [title, setTitle] = useState(initialTitle);
  const [type, setType] = useState('Post');
  const [objective, setObjective] = useState('');
  const [validation, setValidation] = useState('');
  const calendar = calendarMonth(month);

  useEffect(() => {
    const element = dialog.current;
    if (element && !element.open) element.showModal();
    return () => { if (element?.open) element.close(); };
  }, []);

  function submit(event) {
    event.preventDefault();
    if (!belongsToMonth(date, month)) {
      setValidation(`Choose a date in ${monthLabel(month)}.`);
      return;
    }
    if (!title.trim() || !objective.trim()) {
      setValidation('Add a task title and a clear objective.');
      return;
    }
    setValidation('');
    onSubmit({ month, date, title: title.trim(), type, objective: objective.trim() });
  }

  return <dialog ref={dialog} className="rawajTaskDialog" aria-labelledby="task-dialog-title"
    onCancel={event => { if (busy) event.preventDefault(); else onClose(); }}>
    <div className="taskDialogHead">
      <div><span className="label">MAKE ROOM FOR YOUR IDEAS</span><h2 id="task-dialog-title">Add a custom task</h2></div>
      <button type="button" className="iconBtn" aria-label="Close task dialog" onClick={onClose} disabled={busy}><X size={18}/></button>
    </div>
    <form className="taskDialogForm" onSubmit={submit}>
      <label>Task title<input autoFocus value={title} onChange={event => setTitle(event.target.value)} required maxLength={200} placeholder="Share a customer favorite"/></label>
      <div className="taskFormRow">
        <label>Date<input type="date" value={date} min={calendar?.firstDate} max={calendar?.lastDate} required onChange={event => setDate(event.target.value)}/></label>
        <label>Content format<select value={type} onChange={event => setType(event.target.value)}><option>Post</option><option>Reel</option><option>Story</option></select></label>
      </div>
      <label>Objective<textarea value={objective} onChange={event => setObjective(event.target.value)} rows={3} maxLength={500} required placeholder="What should this content help your business achieve?"/></label>
      {(validation || error) && <p className="pageInlineError" role="alert">{validation || error}</p>}
      <div className="taskDialogActions"><button type="button" className="outline" disabled={busy} onClick={onClose}>Cancel</button><button type="submit" className="primary" disabled={busy}><Plus size={16}/>{busy ? 'Saving task…' : 'Add to calendar'}</button></div>
    </form>
  </dialog>;
}

export default function StrategyPage({ restaurant, context, plan, onPlanChange, onOpenContent, api, onNotify }) {
  const [selectedDate, setSelectedDate] = useState('');
  const [filter, setFilter] = useState('all');
  const [dialog, setDialog] = useState(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const controller = useRef(null);
  const mounted = useRef(false);
  const scope = `${restaurant?.id}:${plan?.month}:${plan?.context_signature}`;
  const currentScope = useRef(scope);
  currentScope.current = scope;
  const calendar = useMemo(() => calendarMonth(plan?.month), [plan?.month]);
  const tasks = Array.isArray(plan?.tasks) ? plan.tasks : [];
  const occasions = Array.isArray(plan?.occasions) ? plan.occasions : [];
  const fallbackDate = tasks[0]?.date || calendar?.firstDate || '';
  const activeDate = belongsToMonth(selectedDate, plan?.month) ? selectedDate : fallbackDate;
  const business = restaurant?.context || {};
  const isCafe = (plan?.business_type || business.business_type) === 'cafe';
  const BusinessIcon = isCafe ? Coffee : Utensils;

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; controller.current?.abort(); };
  }, []);

  useEffect(() => {
    controller.current?.abort();
    controller.current = null;
    setBusy('');
    setError('');
    setDialog(null);
    setSelectedDate('');
  }, [scope]);

  async function mutate(key, action, success) {
    if (controller.current) return;
    const request = new AbortController();
    controller.current = request;
    const requestScope = currentScope.current;
    setBusy(key);
    setError('');
    try {
      const updated = await action(request.signal);
      if (!mounted.current || request.signal.aborted || currentScope.current !== requestScope) return;
      onPlanChange(updated);
      success?.();
    } catch (failure) {
      if (mounted.current && !request.signal.aborted && currentScope.current === requestScope) {
        setError('We couldn’t save this change. Please try again.');
      }
    } finally {
      if (controller.current === request) {
        controller.current = null;
        if (mounted.current) setBusy('');
      }
    }
  }

  if (!restaurant || !plan || !calendar) {
    return <section className="strategyPage"><div className="empty"><CalendarDays size={30}/><b>Your monthly plan will appear here.</b><p>Save your business profile on Home to prepare a plan for your business.</p></div></section>;
  }

  const completed = tasks.filter(task => task.status === 'Completed').length;
  const progress = tasks.length ? Math.round(completed * 100 / tasks.length) : 0;
  const visibleTasks = tasks;
  const dayTasks = visibleTasks.filter(task => task.date === activeDate);
  const report = context?.qualification?.result;
  const gaps = Array.isArray(report?.marketing_gaps) ? [...report.marketing_gaps].sort((a, b) => (a.priority || 0) - (b.priority || 0)) : [];
  const firstGap = gaps.find(gap => typeof gap.gap === 'string');
  const pillars = Array.isArray(plan.pillars) ? plan.pillars : [];
  const details = [isCafe ? 'Café' : 'Restaurant', restaurant.location, business.cuisine].filter(value => typeof value === 'string' && value.trim());

  return <div className="strategyPage">
    <section className="hero">
      <div><div className="eyebrow"><span className="liveDot"/>{monthLabel(plan.month).toUpperCase()}<span>·</span>YOUR MONTHLY PLAN</div><h1>A month made for <span dir="auto">{restaurant.name}.</span></h1><p>A clear direction, a practical calendar, and room for the moments that make your {isCafe ? 'café' : 'restaurant'} yours.</p><div className="contextChips">{details.map((detail, index) => <span key={`${index}-${detail}`}>{index === 0 && <BusinessIcon size={12}/>}<b dir="auto">{detail}</b></span>)}</div></div>
    </section>

    <section className="stats" aria-label="Monthly strategy overview">
      <div className="stat"><span>Strategy progress</span><strong>{progress}%</strong><div className="miniProgress" role="progressbar" aria-label="Completed actions" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><i style={{ width: `${progress}%` }}/></div><small>{completed} of {tasks.length} actions completed</small></div>
      <div className="stat"><span>Content opportunities</span><strong>{String(tasks.length).padStart(2, '0')}</strong><small><Flame size={13}/>Planned around your business goals</small></div>
      <div className="stat"><span>Primary focus</span><strong className="focus" dir="auto">{plan.focus}</strong><small>Based on your saved business profile</small></div>
    </section>

    <div className="sectionHead"><div><h2>Monthly strategy</h2><p>From your business context to a plan you can act on.</p></div><div className="pill"><BusinessIcon size={14}/>Profile-based plan</div></div>
    <section className="strategyGrid">
      <div className="strategyMain">
        <div className="goalCard"><div className="goalIcon"><Target size={22}/></div><div><span className="label">THIS MONTH’S NORTH STAR</span><h3 dir="auto">{plan.goal}</h3><p dir="auto">{plan.summary}</p></div></div>
        <div className="roadmap"><div className="roadmapHead"><h3>Strategy pillars</h3><span>{pillars.length} priorities</span></div>{pillars.map((pillar, index) => <div className="pillar" key={`${index}-${pillar.title}`}><div className="pillarNum">{String(index + 1).padStart(2, '0')}</div><div><b dir="auto">{pillar.title}</b><p dir="auto">{pillar.description}</p></div>{pillar.metric && <span className="pillarTag" dir="auto">{pillar.metric}</span>}</div>)}</div>
      </div>
      <aside className="insightCard"><div className="cardTitle"><Lightbulb size={17}/><b>{firstGap ? 'From your account analysis' : 'Your business, in focus'}</b></div><h3 dir="auto">{firstGap?.gap || `Let people experience ${restaurant.name} before they visit.`}</h3><p dir="auto">{firstGap?.recommendation_focus || (business.target_audience ? `Speak to ${business.target_audience}. Show the details that make your ${isCafe ? 'café' : 'restaurant'} a place they would choose.` : `Show the people, products, and experience that make your ${isCafe ? 'café' : 'restaurant'} recognizable.`)}</p>{(Array.isArray(business.signature_items) ? business.signature_items : []).slice(0, 3).map((item, index) => <div className="insightLine" key={`${index}-${item}`}><Check size={15}/><span dir="auto">{item}</span></div>)}{business.tone && <div className="insightLine"><Check size={15}/><span dir="auto">Your voice: {business.tone}</span></div>}<div className="insightLine"><Check size={15}/><span>{firstGap ? 'Use your saved analysis to guide each action' : 'Keep every post connected to your profile'}</span></div></aside>
    </section>

    <div className="sectionHead calendarTitle"><div><h2>Content calendar</h2><p>Choose a day to work on its content and track your progress.</p></div></div>
    {error && !dialog && <p className="pageInlineError" role="alert">{error}</p>}
    <section className="calendarLayout">
      <div className="calendar"><div className="calendarTop"><span className="monthBtn">{monthLabel(plan.month)}</span></div>
        <div className="week" aria-hidden="true">{['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'].map(day => <span key={day}>{day}</span>)}</div>
        <div className="days" role="group" aria-label={`${monthLabel(plan.month)} calendar, week starts Monday`}>
          {calendar.cells.map((date, index) => {
            if (!date) return <div className="dayBlank" key={`blank-${index}`} aria-hidden="true"/>;
            const scheduled = visibleTasks.filter(task => task.date === date);
            return <button type="button" key={date} data-date={date} className={`day ${date === activeDate ? 'chosen' : ''}`} aria-pressed={date === activeDate} aria-label={`${dateLabel(date, { weekday: 'long' })}, ${scheduled.length} tasks`} onClick={() => setSelectedDate(date)}><span>{Number(date.slice(-2))}</span>{scheduled.slice(0, 2).map(task => <i className={`violetBar ${task.status === 'Completed' ? 'completedBar' : ''}`} key={task.id}>{task.status === 'Completed' && '✓ '}{task.type}</i>)}{scheduled.length > 2 && <i className="violetBar">+{scheduled.length - 2}</i>}</button>;
          })}
        </div>
      </div>
      <div className="eventPanel" aria-live="polite"><div className="panelEyebrow">SELECTED DATE<span>{dateLabel(activeDate)}</span></div>
        {dayTasks.map(task => <article className={`eventCard ${task.status === 'Completed' ? 'eventComplete' : ''}`} key={task.id}><div className="eventIcon violetBg">{task.status === 'Completed' ? <CheckCircle2 size={18}/> : <BusinessIcon size={18}/>}</div><div className="eventBody"><div className="eventMeta"><span>{task.type.toUpperCase()}</span><span>{task.status}</span></div><h3 dir="auto">{task.title}</h3><p dir="auto">{task.objective}</p>{task.saved_idea && <div className="savedTaskHint"><Check size={13}/>Idea saved: <span dir="auto">{task.saved_idea.name}</span></div>}<div className="taskActionRow"><button type="button" className="primary small" onClick={() => onOpenContent(task.id)}><WandSparkles size={15}/>{task.saved_idea ? 'View content idea' : 'Get content ideas'}</button><button type="button" className="taskStatusButton" disabled={Boolean(busy)} onClick={() => mutate(task.id, signal => api.updateTask(restaurant.id, task.id, { month: plan.month, status: task.status === 'Completed' ? 'Planned' : 'Completed' }, { signal }), () => onNotify?.(task.status === 'Completed' ? 'Task marked as planned.' : 'Task completed.'))}>{busy === task.id ? 'Saving…' : task.status === 'Completed' ? 'Undo completion' : <><Check size={14}/>Mark complete</>}</button></div></div></article>)}
        {!dayTasks.length && <div className="empty"><CalendarDays size={28}/><b>A little breathing room.</b><p>Add an idea for this day, or leave it open for a spontaneous moment.</p><button type="button" className="outline" disabled={Boolean(busy)} onClick={() => { setError(''); setDialog({ date: activeDate }); }}><Plus size={15}/>Add task</button></div>}
      </div>
    </section>

    {dialog && <AddTaskDialog key={`${plan.month}-${dialog.date}`} month={plan.month} initialDate={dialog.date} initialTitle={dialog.title} busy={busy === 'add-task'} error={error} onClose={() => { setDialog(null); setError(''); }} onSubmit={payload => mutate('add-task', signal => api.addTask(restaurant.id, payload, { signal }), () => { setSelectedDate(payload.date); setFilter('all'); setDialog(null); onNotify?.('Task added to your calendar.'); })}/>}
  </div>;
}
