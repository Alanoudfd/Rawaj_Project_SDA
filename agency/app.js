import {icon,esc,toast} from './components/ui.js';
import {dashboard} from './pages/dashboard.js';
import {prospects,detail} from './pages/prospects.js';
import {outreach} from './pages/outreach.js';
import {strategies,feedback} from './pages/relationships.js';
const pages={dashboard,prospects,outreach,strategies,feedback};
const names={dashboard:'Dashboard',prospects:'Prospects',outreach:'Outreach',strategies:'Strategies',feedback:'Feedback'};
let revision=0;
async function render(){
 const turn=++revision,[path,query='']=(location.hash.slice(1)||'/dashboard').split('?'),parts=path.split('/').filter(Boolean),page=parts[0]||'dashboard';
 document.querySelector('#navigation').innerHTML=Object.entries(names).map(([key,label])=>`<a href="#/${key}" class="${page===key?'active':''}" ${page===key?'aria-current="page"':''}>${icon(key)}${label}</a>`).join('');
 document.querySelector('#breadcrumb').textContent=names[page]||'Workspace';
 document.title=`Rawaj · ${names[page]||'Agency'}`;
 const main=document.querySelector('#main');main.innerHTML='<div class="loading" role="status"><div class="spinner"></div>Loading your workspace…</div>';
 try{
 const result=page==='prospects'&&/^\d+$/.test(parts[1])?await detail(parts[1]):await (pages[page]||dashboard)(new URLSearchParams(query));
 if(turn!==revision)return;
 main.innerHTML=result.html;result.bind?.();
 document.querySelector('#sync-label').textContent='Updated '+new Date().toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'});
 }catch(e){if(turn!==revision)return;main.innerHTML=`<div class="notice error" role="alert"><strong>We couldn’t load this view.</strong><p>${esc(e.message)}</p><button class="button secondary" id="retry" style="margin-top:15px">Try again</button></div>`;document.querySelector('#retry').onclick=render;}
}
window.addEventListener('hashchange',()=>{document.querySelector('#dialog').close();render();window.scrollTo(0,0);});
window.addEventListener('agency-refresh',render);
document.querySelector('#refresh').onclick=()=>render();
document.querySelector('.skip').onclick=e=>{e.preventDefault();document.querySelector('#main').focus();};
// Refresh visibility-sensitive data when returning to the workspace, without interrupting a review.
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!document.querySelector('#dialog').open)document.querySelector('#sync-label').textContent='Refresh for the latest activity';});
render();
