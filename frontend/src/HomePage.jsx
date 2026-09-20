import React, { useMemo, useState } from 'react';
import { ArrowRight, CalendarDays, Check, Coffee, RefreshCw, Save, Sparkles, Target, UtensilsCrossed } from 'lucide-react';
import { summarizeTasksForHome } from './homeTaskUtils';

const textList = value => Array.isArray(value) ? value.join(', ') : String(value || '');
const asList = value => value.split(/[,،\n]/).map(item => item.trim()).filter(Boolean);

export default function HomePage({ restaurant, context, plan, user, isCreating, saving, onSave, onCancel, onCreate, onAnalyze, analysisStarting, onNavigate, onOpenContent }) {
  const saved = restaurant?.context || {};
  const [form, setForm] = useState({
    name: restaurant?.name || '', instagram_username: restaurant?.instagram_username || '',
    email: restaurant?.email || '', location: restaurant?.location || '',
    business_type: saved.business_type === 'cafe' ? 'cafe' : 'restaurant', cuisine: textList(saved.cuisine),
    target_audience: textList(saved.target_audience), signature_items: textList(saved.signature_items),
    goals: textList(saved.goals), tone: textList(saved.tone) || 'Warm and authentic', language: saved.language || 'English',
  });
  const [error, setError] = useState('');
  const update = event => setForm(current => ({ ...current, [event.target.name]: event.target.value }));
  const job = context?.latest_job;
  const analyzing = analysisStarting || ['queued', 'running'].includes(job?.status);
  const isCafe = restaurant?.context?.business_type === 'cafe';
  const profile = context?.research?.result?.profile;
  const rawGaps = Array.isArray(context?.qualification?.result?.marketing_gaps) ? context.qualification.result.marketing_gaps : [];
  const gaps = rawGaps.map((item, index) => {
    if (typeof item === 'string') return { gap: item, priority: index + 1, severity: 'medium' };
    return {
      gap: item?.gap || item?.title || 'Growth opportunity',
      priority: item?.priority ?? index + 1,
      severity: item?.severity || 'medium',
      reason: item?.recommendation_focus || item?.reason || item?.why_it_matters || 'Keep improving the customer experience.',
      evidence: Array.isArray(item?.evidence) ? item.evidence : (Array.isArray(item?.signals) ? item.signals : []),
    };
  });
  const taskCards = useMemo(() => summarizeTasksForHome(plan?.tasks || [], 3), [plan?.tasks]);

  async function save(event) {
    event.preventDefault();
    setError('');
    const data = {
      name: form.name.trim(), email: form.email.trim() || null, location: form.location.trim() || null,
      context: { ...saved, business_type: form.business_type, cuisine: form.cuisine.trim(),
        target_audience: form.target_audience.trim(), signature_items: asList(form.signature_items),
        goals: asList(form.goals), tone: form.tone.trim(), language: form.language },
    };
    if (isCreating || !restaurant) data.instagram_username = form.instagram_username.trim();
    try { await onSave(data); } catch (err) { setError(err.message); }
  }

  return <section className="homePageBlank" aria-label="Home workspace overview">
    <div className="homeHero">
      <div className="eyebrow"><span className="liveDot" /> YOUR GROWTH SNAPSHOT</div>
      <h1>Keep your next move <span>in view.</span></h1>
      <p>Everything that matters for {restaurant?.name || 'your restaurant'} is gathered here, from the plan to the next content ideas on the calendar.</p>
    </div>

    <div className="homeQuickLinks">
      <button type="button" className="workspaceAction lavender" onClick={() => onNavigate?.('strategy')}>
        <Target size={22} />
        <div>
          <b>Monthly strategy</b>
          <span>{plan?.goal || 'Open the plan and review the month’s direction.'}</span>
        </div>
        <ArrowRight size={18} />
      </button>
      <button type="button" className="workspaceAction" onClick={() => onNavigate?.('content')}>
        <Sparkles size={22} />
        <div>
          <b>Content studio</b>
          <span>{taskCards[0]?.title ? `Next task: ${taskCards[0].title}` : 'Pick a task and turn it into content ideas.'}</span>
        </div>
        <ArrowRight size={18} />
      </button>
    </div>

    <div className="profileLayout">
      <div className="profileForm">
        <div className="sectionHead compact">
          <div>
            <h2>Business profile</h2>
            <p>Keep your restaurant context clear and easy to act on.</p>
          </div>
          <span className="pill">{isCafe ? 'Café' : 'Restaurant'}</span>
        </div>

        <form onSubmit={save}>
          <fieldset>
            <div className="formGrid">
              <label>Restaurant name<input name="name" value={form.name} onChange={update} placeholder="3Brews" /></label>
              <label>Instagram handle<input name="instagram_username" value={form.instagram_username} onChange={update} placeholder="@3brews" disabled={!isCreating && !!restaurant} /></label>
              <label>Business type<select name="business_type" value={form.business_type} onChange={update}><option value="restaurant">Restaurant</option><option value="cafe">Café</option></select></label>
              <label>Location<input name="location" value={form.location} onChange={update} placeholder="Jeddah" /></label>
              <label className="spanTwo">Cuisine<input name="cuisine" value={form.cuisine} onChange={update} placeholder="Middle Eastern, coffee, brunch" /></label>
              <label className="spanTwo">Target audience<input name="target_audience" value={form.target_audience} onChange={update} placeholder="Local families, young professionals" /></label>
              <label className="spanTwo">Signature items<input name="signature_items" value={form.signature_items} onChange={update} placeholder="Signature espresso, grilled mezze, dessert platter" /></label>
              <label className="spanTwo">Goals<textarea name="goals" value={form.goals} onChange={update} rows={3} placeholder="Drive visits, improve repeat orders, build community" /></label>
              <label>Tone<input name="tone" value={form.tone} onChange={update} placeholder="Warm and authentic" /></label>
              <label>Language<select name="language" value={form.language} onChange={update}><option value="English">English</option><option value="Arabic">Arabic</option><option value="Arabic + English">Arabic + English</option></select></label>
              <label>Email<input name="email" type="email" value={form.email} onChange={update} placeholder="hello@restaurant.com" /></label>
            </div>

            {error && <div className="errorBanner" role="alert">{error}</div>}
            <div className="formActions">
              <button type="button" className="outline" onClick={onCancel} disabled={saving}>{isCreating ? 'Cancel' : 'Reset'}</button>
              <button type="submit" className="primary" disabled={saving}>
                {saving ? <><RefreshCw size={15} className="spin" />Saving…</> : <><Save size={15} />Save profile</>}
              </button>
              <span><Check size={12} />{restaurant ? 'Updated for your workspace' : 'This will create your workspace'}</span>
            </div>
          </fieldset>
        </form>
      </div>

      <aside className="homeAside">
        <article className="researchCard">
          <div className="cardTitle"><Sparkles size={17} /><b>Your next direction</b></div>
          <p>{profile ? `Your audience is shaped around ${profile.target_audience || 'local guests'}.` : 'Build a stronger brand story with clearer audience signals and sharper monthly themes.'}</p>
          {gaps.length ? <div className="homeGapCards">
            {gaps.slice(0, 3).map((gap, index) => (
              <div key={`${gap.gap}-${index}`} className="homeGapCard">
                <div className="homeGapMeta">
                  <span className="homeGapPriority">P{gap.priority}</span>
                  <span className={`homeGapSeverity ${gap.severity}`}>{gap.severity}</span>
                </div>
                <h4>{gap.gap}</h4>
                <p>{gap.reason}</p>
                {gap.evidence?.length ? <ul>{gap.evidence.slice(0, 2).map((item, i) => <li key={`${gap.gap}-e-${i}`}>{item}</li>)}</ul> : null}
              </div>
            ))}
          </div> : null}
          <button type="button" className="primary" onClick={onAnalyze} disabled={analyzing}>
            {analyzing ? 'Researching…' : 'Run research'}
          </button>
          {job && <div className={`jobStatus ${job.status === 'failed' ? 'failed' : ''}`}><strong>{job.status}</strong><br />{job.error || 'Research is shaping the insights for this workspace.'}</div>}
        </article>

        <article className="researchCard">
          <div className="cardTitle"><CalendarDays size={17} /><b>Upcoming tasks</b></div>
          {taskCards.length ? (
            <div className="miniTaskList">
              {taskCards.map(task => (
                <button type="button" key={task.id} className="miniTask" onClick={() => onOpenContent ? onOpenContent(task.id) : onNavigate?.('content')}>
                  <span className="miniTaskDate">{task.dateLabel}</span>
                  <strong>{task.label}</strong>
                  <b>{task.title}</b>
                </button>
              ))}
            </div>
          ) : (
            <p>No tasks in the current plan yet. Open your strategy calendar and add one.</p>
          )}
        </article>
      </aside>
    </div>
  </section>;
}
