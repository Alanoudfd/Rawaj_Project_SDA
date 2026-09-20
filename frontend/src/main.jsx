import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowRight, CalendarDays, Coffee, Home, LogOut, RefreshCw, Sparkles, Target, UtensilsCrossed, X } from 'lucide-react';
import { api } from './api';
import HomePage from './HomePage';
import SignIn from './SignIn';
import StrategyPage from './StrategyPage';
import ContentPage from './ContentPage';
import './index.css';
import './workspace.css';

const SESSION_KEY = 'rawaj.preview-session';
const RESTAURANT_KEY = 'rawaj.restaurant-id';
const navigation = [{ id: 'home', label: 'Home', icon: Home }, { id: 'strategy', label: 'Monthly Strategy', icon: Target }, { id: 'content', label: 'Content Creation', icon: Sparkles }];
const currentMonth = () => { const date = new Date(); return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`; };
const readSession = () => { try { const value = JSON.parse(sessionStorage.getItem(SESSION_KEY)); return value?.email && value?.name ? value : null; } catch { return null; } };
const readRestaurant = () => { try { return Number(localStorage.getItem(RESTAURANT_KEY)) || null; } catch { return null; } };
const routeFromHash = () => window.location.hash.replace(/^#\//, '') || 'home';
const initials = name => (name || 'Rawaj').split(/\s+/).map(word => word[0]).slice(0, 2).join('').toUpperCase();

function App() {
  const [user, setUser] = useState(readSession);
  const [route, setRoute] = useState(routeFromHash);
  const [restaurants, setRestaurants] = useState([]);
  const [selectedId, setSelectedId] = useState(readRestaurant);
  const [context, setContext] = useState(null);
  const [listLoading, setListLoading] = useState(true);
  const [contextLoading, setContextLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [reload, setReload] = useState(0);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [month, setMonth] = useState(currentMonth);
  const [plan, setPlan] = useState(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState('');
  const [planReload, setPlanReload] = useState(0);
  const [initialTaskId, setInitialTaskId] = useState(null);
  const [analysisStarting, setAnalysisStarting] = useState(false);
  const [toast, setToast] = useState('');
  const selectedRef = useRef(selectedId);
  selectedRef.current = selectedId;
  const restaurant = context?.restaurant?.id === selectedId ? context.restaurant : null;
  const activePage = navigation.find(item => item.id === route) || navigation[0];
  const jobId = context?.latest_job?.id;

  function navigate(page) { window.location.hash = `/${page}`; setRoute(page); }
  function notify(message) { setToast(message); }
  function chooseRestaurant(id) { setContext(null); setPlan(null); setPlanError(''); setInitialTaskId(null); setCreating(false); setSelectedId(id); try { localStorage.setItem(RESTAURANT_KEY, String(id)); } catch {} }

  useEffect(() => { const handler = () => setRoute(routeFromHash()); window.addEventListener('hashchange', handler); return () => window.removeEventListener('hashchange', handler); }, []);
  useEffect(() => { if (!user && route !== 'sign-in') navigate('sign-in'); else if (user && !navigation.some(item => item.id === route)) navigate('home'); }, [user, route]);
  useEffect(() => { if (!toast) return; const timeout = setTimeout(() => setToast(''), 5500); return () => clearTimeout(timeout); }, [toast]);

  useEffect(() => {
    if (!user) return;
    const controller = new AbortController();
    setListLoading(true); setLoadError('');
    (async () => {
      try {
        const items = [];
        let offset = 0;
        while (true) {
          const page = await api.listRestaurants({ offset, limit: 100, signal: controller.signal });
          items.push(...page.items); offset += page.items.length;
          if (!page.items.length || offset >= page.total) break;
        }
        if (controller.signal.aborted) return;
        setRestaurants(items);
        setSelectedId(previous => items.some(item => item.id === previous) ? previous : items[0]?.id || null);
        setCreating(!items.length);
      } catch (error) { if (!controller.signal.aborted) setLoadError(error.message); }
      finally { if (!controller.signal.aborted) setListLoading(false); }
    })();
    return () => controller.abort();
  }, [user, reload]);

  useEffect(() => {
    if (!user || !selectedId) { setContext(null); return; }
    const controller = new AbortController();
    setContextLoading(true); setLoadError('');
    api.getRestaurantContext(selectedId, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setContext(value); })
      .catch(error => { if (!controller.signal.aborted) setLoadError(error.message); })
      .finally(() => { if (!controller.signal.aborted) setContextLoading(false); });
    return () => controller.abort();
  }, [user, selectedId, reload]);

  useEffect(() => {
    if (!user || !restaurant || creating) { setPlan(null); return; }
    const controller = new AbortController();
    setPlan(null); setPlanLoading(true); setPlanError('');
    (async () => {
      try {
        let result;
        try { result = await api.getStrategy(restaurant.id, month, { signal: controller.signal }); }
        catch (error) {
          if (error.status !== 404 || controller.signal.aborted) throw error;
          result = await api.createStrategy(restaurant.id, { month }, { signal: controller.signal });
        }
        if (!controller.signal.aborted) setPlan(result);
      } catch (error) { if (!controller.signal.aborted) setPlanError(error.message); }
      finally { if (!controller.signal.aborted) setPlanLoading(false); }
    })();
    return () => controller.abort();
  }, [user, restaurant?.id, restaurant?.updated_at, context?.qualification?.id, context?.research?.id, month, creating, planReload]);

  useEffect(() => {
    if (!user || !jobId || !['queued', 'running'].includes(context?.latest_job?.status)) return;
    const controller = new AbortController();
    const restaurantId = selectedId;
    (async () => {
      try {
        await api.waitForJob(jobId, {
          signal: controller.signal,
          onUpdate: job => { if (!controller.signal.aborted) setContext(previous => previous?.restaurant.id === restaurantId ? { ...previous, latest_job: job } : previous); },
        });
        if (!controller.signal.aborted) {
          const fresh = await api.getRestaurantContext(restaurantId, { signal: controller.signal });
          if (!controller.signal.aborted) { setContext(fresh); notify('Research completed. Your marketing insights are ready.'); }
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          notify(error.message);
          try {
            const fresh = await api.getRestaurantContext(restaurantId, { signal: controller.signal });
            if (!controller.signal.aborted) setContext(fresh);
          } catch (refreshError) { if (!controller.signal.aborted) notify(refreshError.message); }
        }
      }
    })();
    return () => controller.abort();
  }, [jobId, selectedId, user]);

  function signIn(profile) { try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(profile)); } catch {} setUser(profile); navigate('home'); }
  function signOut() { try { sessionStorage.removeItem(SESSION_KEY); } catch {} setUser(null); setContext(null); setPlan(null); setRestaurants([]); navigate('sign-in'); }
  async function saveRestaurant(data) {
    setSaving(true);
    try {
      const result = creating || !restaurant ? await api.createRestaurant(data) : await api.updateRestaurant(restaurant.id, data);
      setRestaurants(previous => previous.some(item => item.id === result.id) ? previous.map(item => item.id === result.id ? result : item) : [...previous, result]);
      const fresh = await api.getRestaurantContext(result.id);
      setContext(fresh); setSelectedId(result.id); setCreating(false); setPlan(null); setInitialTaskId(null);
      try { localStorage.setItem(RESTAURANT_KEY, String(result.id)); } catch {}
      notify('Restaurant context saved. Your plan will reflect these details.');
    } finally { setSaving(false); }
  }
  async function analyze() {
    if (!restaurant) return;
    const restaurantId = restaurant.id;
    setAnalysisStarting(true);
    try {
      const job = await api.analyzeRestaurant(restaurantId);
      if (selectedRef.current === restaurantId) setContext(previous => ({ ...previous, latest_job: job }));
      notify('Instagram research started. You can follow its progress here.');
    } catch (error) { notify(error.message); }
    finally { setAnalysisStarting(false); }
  }
  function openContent(taskId) { setInitialTaskId(taskId); navigate('content'); }
  function startCreate() { setCreating(true); navigate('home'); }

  if (!user) return <SignIn onSignIn={signIn} />;

  return <div className="app">
    <aside className="sidebar"><a className="brand" href="#/home"><div className="brandMark">✦</div><div><b>Rawaj</b><span>Growth for Local Flavors</span></div></a>
      <div className="workspace"><div className="avatar">{initials(restaurant?.name)}</div><div className="workspacePicker"><label htmlFor="restaurant-select">Your workspace</label><select id="restaurant-select" value={selectedId || ''} disabled={listLoading || saving || !restaurants.length} onChange={event => chooseRestaurant(Number(event.target.value))}>{!restaurants.length && <option value="">Add a restaurant</option>}{restaurants.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div></div>
      <nav aria-label="Main navigation">{navigation.map(({ id, label, icon: Icon }) => <a key={id} href={`#/${id}`} className={activePage.id === id ? 'nav active' : 'nav'} aria-current={activePage.id === id ? 'page' : undefined} onClick={() => setCreating(false)}><Icon size={18} /><span>{label}</span></a>)}</nav>
      <div className="workspaceNote"><div className="trialTop"><span>Rooted in your story.</span><Sparkles size={16} /></div><p>Your restaurant’s context connects every part of your workspace.</p><span className="workspaceType">{restaurant?.context?.business_type === 'cafe' ? <Coffee size={15} /> : <UtensilsCrossed size={15} />}{restaurant?.context?.business_type === 'cafe' ? 'Café workspace' : 'Restaurant workspace'}</span></div><div className="sidebarFoot">© {new Date().getFullYear()} Rawaj</div>
    </aside>
    <main className="main"><header className="topbar"><div className="crumb">Workspace <span>/</span> <b>{activePage.label}</b></div><div className="topActions"><div className="userMini"><div className="avatar">{initials(user.name)}</div><span>{user.name}</span></div><button className="iconBtn" onClick={signOut} aria-label="Sign out" title="Sign out" disabled={saving}><LogOut size={17} /></button></div></header>
      {loadError ? <div className="errorState" role="alert"><h2>Let’s reconnect your workspace.</h2><p>{loadError}</p><button className="outline" onClick={() => setReload(value => value + 1)}><RefreshCw size={15} />Try again</button></div> : listLoading || contextLoading ? <div className="workspaceLoading" role="status"><RefreshCw className="spin" size={25} /><h2>Opening your workspace…</h2><p>Bringing your restaurant’s details together.</p></div> : activePage.id === 'home' ? <HomePage key={`${creating ? 'new' : restaurant?.id}:${restaurant?.updated_at}`} restaurant={creating ? null : restaurant} context={creating ? null : context} plan={plan} user={user} isCreating={creating} saving={saving} onSave={saveRestaurant} onCancel={() => setCreating(false)} onCreate={startCreate} onAnalyze={analyze} analysisStarting={analysisStarting} onNavigate={navigate} onOpenContent={openContent} /> : !restaurant ? <div className="empty workspaceLoading"><Coffee size={36} /><h2>Your story comes first.</h2><p>Add your restaurant or café to create its monthly plan and content calendar.</p><button className="primary" onClick={startCreate}>Set up your restaurant <ArrowRight size={16} /></button></div> : <>
        <div className="pageContextBar"><span className="contextChip">{restaurant.context.business_type === 'cafe' ? <Coffee size={16} /> : <UtensilsCrossed size={16} />}<b>{restaurant.name}</b><span>· {restaurant.context.business_type === 'cafe' ? 'Café' : 'Restaurant'}</span></span><label className="monthControl"><CalendarDays size={16} /><span>Planning month</span><input aria-label="Planning month" type="month" value={month} min="2020-01" max="2100-12" required onChange={event => { if (/^\d{4}-(0[1-9]|1[0-2])$/.test(event.target.value)) { setMonth(event.target.value); setInitialTaskId(null); } }} /></label></div>
        {planLoading ? <div className="workspaceLoading" role="status"><RefreshCw className="spin" size={25} /><h2>Shaping your monthly direction…</h2><p>Using the details saved for {restaurant.name}.</p></div> : planError ? <div className="errorState" role="alert"><h2>Your plan needs another moment.</h2><p>{planError}</p><button className="outline" onClick={() => setPlanReload(value => value + 1)}>Try again</button></div> : plan && (activePage.id === 'strategy' ? <StrategyPage key={`${restaurant.id}:${month}:${plan.context_signature}`} restaurant={restaurant} context={context} plan={plan} api={api} onPlanChange={setPlan} onOpenContent={openContent} onNotify={notify} /> : <ContentPage key={`${restaurant.id}:${month}:${plan.context_signature}`} restaurant={restaurant} context={context} plan={plan} api={api} initialTaskId={initialTaskId} onPlanChange={setPlan} onNotify={notify} />)}
      </>}
      <footer><span>Rawaj · Your strategy, made actionable.</span><span>Made for restaurants & cafés</span></footer>
    </main>{toast && <div className="toast" role="status"><span>{toast}</span><button aria-label="Dismiss notification" onClick={() => setToast('')}><X size={16} /></button></div>}
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
