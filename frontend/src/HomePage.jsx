import React, { useState } from 'react';
import { ArrowRight, Check, Coffee, RefreshCw, Save, Sparkles, Target, UtensilsCrossed } from 'lucide-react';

const textList = value => Array.isArray(value) ? value.join(', ') : String(value || '');
const asList = value => value.split(/[,،\n]/).map(item => item.trim()).filter(Boolean);

export default function HomePage({ restaurant, context, plan, user, isCreating, saving, onSave, onCancel, onCreate, onAnalyze, analysisStarting, onNavigate }) {
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
  const gaps = context?.qualification?.result?.marketing_gaps || [];

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

  return <section className="homePageBlank" aria-label="Blank home workspace" />;
}
