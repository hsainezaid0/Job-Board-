// Entry point: header, hash router and start-up.
import { $, $$, main, state, api, esc, icon, avatar, parseHash, errorState, toast, closeDrawer, refreshSession, isCandidate, isStaff, ROLE } from './core.js';
import { renderJobs, renderJob, renderCompanies, renderCompany } from './jobs.js';
import { renderAuth, renderSpace } from './account.js';
import { renderAdmin } from './admin.js';

// ---------------------------------------------------------------- header
function updateHeader() {
  const box = $('#auth-nav');
  const user = state.user;
  if (!user) {
    box.innerHTML = '<a class="btn ghost" href="#login">Se connecter</a><a class="btn" href="#register">Créer un compte</a>';
  } else {
    const links = isCandidate()
      ? [['#applications', 'Mes candidatures', 'inbox', state.updates], ['#saved', 'Offres sauvegardées', 'bookmark', 0], ['#account', 'Mon profil', 'user', 0]]
      : [['#admin', 'Espace recruteur', 'grid', 0], ['#account', 'Mon profil', 'user', 0]];
    box.innerHTML = `${isStaff() ? `<a class="btn secondary header-console" href="#admin">${icon('grid')}<span>Espace recruteur</span></a>` : ''}
      <div class="account-menu">
        <button type="button" class="account-button" aria-haspopup="true" aria-expanded="false" aria-controls="account-dropdown">
          ${avatar(user.name, 'sm')}<span class="account-name" translate="no">${esc(user.name.split(' ')[0])}</span>${state.updates ? `<span class="dot-badge" title="Nouveautés sur vos candidatures"></span>` : ''}${icon('down')}
        </button>
        <div class="dropdown" id="account-dropdown" hidden>
          <div class="dropdown-head"><strong translate="no">${esc(user.name)}</strong><small translate="no">${esc(user.email)}</small><small>${ROLE[user.role]}</small></div>
          ${links.map(([href, label, iconName, badge]) => `<a href="${href}">${icon(iconName)}<span>${label}</span>${badge ? `<span class="pill">${badge}</span>` : ''}</a>`).join('')}
          <button type="button" id="logout">${icon('logout')}<span>Se déconnecter</span></button>
        </div>
      </div>`;
    $('.account-button', box).onclick = e => { e.stopPropagation(); setMenu($('#account-dropdown').hidden); };
    $('#account-dropdown').onclick = e => { if (e.target.closest('a')) setMenu(false); };
    $('#logout').onclick = async () => {
      try {
        await api('/auth/logout', 'POST', {});
        state.user = null; state.saved = new Set(); state.updates = 0;
        updateHeader();
        location.hash = 'jobs';
        toast('Vous êtes déconnecté.');
      } catch (e) { toast(e.message, { type: 'error' }); }
    };
  }
  const applications = $('[data-nav="applications"]');
  applications.hidden = !isCandidate();
  $('.nav-badge-top', applications).hidden = !state.updates;
  $('.nav-badge-top', applications).textContent = state.updates;
}

function setMenu(open) {
  const menu = $('#account-dropdown');
  if (!menu) return;
  menu.hidden = !open;
  $('.account-button').setAttribute('aria-expanded', String(open));
}
document.addEventListener('click', e => { if (!e.target.closest('.account-menu')) setMenu(false); });
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && $('#account-dropdown') && !$('#account-dropdown').hidden) { setMenu(false); $('.account-button').focus(); }
});

// Mobile navigation drawer.
$('.menu-toggle').addEventListener('click', () => {
  const open = !document.body.classList.contains('nav-open');
  document.body.classList.toggle('nav-open', open);
  $('.menu-toggle').setAttribute('aria-expanded', String(open));
});

// ---------------------------------------------------------------- router
let sequence = 0;
let previousPage = null;
async function route() {
  const current = ++sequence;
  const { parts, params } = parseHash();
  const [page, id, extra] = parts;
  closeDrawer(false);
  document.body.classList.remove('nav-open', 'no-scroll');
  if (page !== 'login' && page !== 'register') state.afterAuth = null;
  for (const link of $$('[data-nav]')) {
    const active = link.dataset.nav === page || (link.dataset.nav === 'jobs' && page === 'job') || (link.dataset.nav === 'companies' && page === 'company');
    link.classList.toggle('active', active);
    active ? link.setAttribute('aria-current', 'page') : link.removeAttribute('aria-current');
  }
  document.body.classList.toggle('is-console', page === 'admin');
  // Within the admin console the sidebar stays in place; elsewhere show a loader.
  const stayInConsole = page === 'admin' && previousPage === 'admin';
  if (!stayInConsole) {
    main.innerHTML = '<div class="loading">Chargement…</div>';
    if (!(page === 'jobs' && previousPage === 'jobs')) window.scrollTo(0, 0);
  }
  previousPage = page;
  try {
    if (page === 'jobs') await renderJobs(params);
    else if (page === 'job' && /^\d+$/.test(id)) await renderJob(id, extra === 'apply');
    else if (page === 'companies') await renderCompanies();
    else if (page === 'company' && /^\d+$/.test(id)) await renderCompany(id);
    else if (page === 'login' || page === 'register') {
      if (state.user) { location.hash = isStaff() ? 'admin' : 'jobs'; return; }
      renderAuth(page === 'register', updateHeader);
    }
    else if (page === 'account') await renderSpace(id === 'security' ? 'security' : 'account', updateHeader);
    else if (page === 'security') await renderSpace('security', updateHeader);
    else if (page === 'applications' || page === 'saved') await renderSpace(page, updateHeader);
    else if (page === 'admin') await renderAdmin(id || 'dashboard', extra, params);
    else {
      main.innerHTML = `<div class="container page"><div class="empty"><div class="empty-icon">${icon('search')}</div><h3>Cette page n’existe pas.</h3><p>Le lien est peut-être incomplet, ou l’offre a été supprimée.</p><a class="btn" href="#jobs">Voir les offres</a></div></div>`;
    }
  } catch (e) {
    if (current !== sequence) return;
    if (e.status === 401) { await refreshSession().catch(() => {}); updateHeader(); }
    main.innerHTML = `<div class="container page">${errorState(e)}</div>`;
    $('[data-retry]')?.addEventListener('click', route);
  }
}
window.addEventListener('hashchange', route);

async function start() {
  try {
    await refreshSession();
  } catch (e) {
    main.innerHTML = `<div class="container page">${errorState(e)}</div>`;
    $('[data-retry]').onclick = () => location.reload();
    return;
  }
  updateHeader();
  await route();
}
start();
