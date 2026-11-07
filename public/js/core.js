// Shared helpers: DOM, API, formatting, icons and small UI primitives (toast, dialog, drawer).

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
export const main = $('#main');

export const state = {
  user: null,
  updates: 0,            // applications whose status changed since the candidate last looked
  saved: new Set(),      // bookmarked ad IDs
  meta: null,
  lastJobsHash: '#jobs', // so "back to jobs" keeps the current search
};

export const isCandidate = () => state.user?.role === 'candidate';
export const isAdmin = () => state.user?.role === 'admin';
export const isCompanyAdmin = () => state.user?.role === 'company_admin';
export const isStaff = () => isAdmin() || isCompanyAdmin();

export function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ---------------------------------------------------------------- API
export async function api(path, method = 'GET', body) {
  const settings = { method, credentials: 'same-origin', headers: {} };
  if (body !== undefined) {
    settings.headers['Content-Type'] = 'application/json';
    settings.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch('/api' + path, settings);
  } catch {
    throw Object.assign(new Error('Le serveur ne répond pas. Vérifiez qu’il est bien lancé.'), { status: 0 });
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw Object.assign(new Error(data.error || 'Une erreur est survenue.'), { status: response.status });
  }
  return data;
}

export async function getMeta(force = false) {
  if (!state.meta || force) state.meta = await api('/meta');
  return state.meta;
}

export async function refreshSession() {
  const data = await api('/auth/me');
  state.user = data.user;
  state.updates = data.updates || 0;
  state.saved = new Set(data.saved || []);
  return state.user;
}

// ---------------------------------------------------------------- formatting
export function date(value) {
  return value ? globalThis.localizedDate(value) : '';
}

export function relative(value) {
  if (!value) return '';
  const seconds = (Date.now() - new Date(value).getTime()) / 1000;
  const minutes = Math.round(seconds / 60), hours = Math.round(seconds / 3600);
  const days = Math.floor(seconds / 86400);
  if (minutes < 2) return 'à l’instant';
  if (minutes < 60) return `il y a ${minutes} min`;
  if (hours < 24 && days === 0) return `il y a ${hours} h`;
  if (days <= 1) return 'hier';
  if (days < 7) return `il y a ${days} jours`;
  if (days < 14) return 'il y a 1 semaine';
  if (days < 31) return `il y a ${Math.floor(days / 7)} semaines`;
  if (days < 60) return 'il y a 1 mois';
  return `il y a ${Math.floor(days / 30)} mois`;
}

// "42–55 k€" is how salaries are usually written on French job boards.
export function salary(min, max) {
  const k = n => (n >= 1000 ? Math.round(n / 100) / 10 : n).toLocaleString('fr-FR');
  return min === max ? `${k(min)} k€` : `${k(min)}–${k(max)} k€`;
}

export const number = n => Number(n || 0).toLocaleString('fr-FR');

export function initials(name = '') {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map(p => p[0].toUpperCase()).join('') || '?';
}

export function logo(name, color, size = '') {
  const safe = /^#[0-9a-f]{6}$/i.test(color || '') ? color : '#355d50';
  return `<span class="logo ${size}" style="--logo:${safe}" aria-hidden="true">${esc((name || '?').trim()[0] || '?')}</span>`;
}

export function avatar(name, size = '') {
  return `<span class="avatar ${size}" aria-hidden="true">${esc(initials(name))}</span>`;
}

// Text with blank lines becomes paragraphs; each line of a list field becomes a bullet.
export function paragraphs(text) {
  return String(text || '').split(/\n{2,}/).map(p => `<p>${esc(p).replace(/\n/g, '<br>')}</p>`).join('');
}
export function bullets(text) {
  const lines = String(text || '').split('\n').map(l => l.replace(/^[-•*]\s*/, '').trim()).filter(Boolean);
  return lines.length > 1 ? `<ul>${lines.map(l => `<li>${esc(l)}</li>`).join('')}</ul>` : paragraphs(text);
}

// ---------------------------------------------------------------- labels
export const STATUS = {
  'Reçue': 'received', 'En cours': 'review', 'Entretien': 'interview', 'Acceptée': 'accepted', 'Refusée': 'rejected',
};
export const AD_STATUS = { draft: 'Brouillon', published: 'Publiée', closed: 'Fermée' };
export const ROLE = { candidate: 'Candidat', admin: 'Administrateur', company_admin: 'Recruteur' };

export const statusBadge = status => `<span class="badge status-${STATUS[status] || 'received'}">${esc(status)}</span>`;
export const adBadge = status => `<span class="badge ad-${esc(status)}">${AD_STATUS[status] || esc(status)}</span>`;

// ---------------------------------------------------------------- icons (24px, stroke)
const PATHS = {
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  pin: '<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21Z"/><circle cx="12" cy="9.5" r="2.5"/>',
  briefcase: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 13h18"/>',
  home: '<path d="M4 11 12 4l8 7v9a1 1 0 0 1-1 1h-5v-6h-4v6H5a1 1 0 0 1-1-1Z"/>',
  euro: '<path d="M17 6.5A6.5 6.5 0 0 0 7 12a6.5 6.5 0 0 0 10 5.5M5 10h8M5 14h8"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  bookmark: '<path d="M6 4h12v17l-6-4-6 4Z"/>',
  building: '<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2M10 21v-3h4v3"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c1-3.5 3.5-5.5 6.5-5.5s5.5 2 6.5 5.5M16 4.5a3.5 3.5 0 0 1 0 7M18 14.5c2 .7 3.2 2.5 3.8 5.5"/>',
  logout: '<path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 16l-4-4 4-4M6 12h10"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
  back: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16Z"/><path d="m13.5 6.5 4 4"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  check: '<path d="m5 12 5 5 9-10"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  filter: '<path d="M4 6h16M7 12h10M10 18h4"/>',
  grid: '<rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/><rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/>',
  inbox: '<path d="M3 13h5l1.5 3h5L16 13h5"/><path d="M5.5 5h13L21 13v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-6Z"/>',
  tag: '<path d="M3 12V4h8l10 10-8 8Z"/><circle cx="7.5" cy="8.5" r="1.5"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  phone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a1 1 0 0 1-1 1A16 16 0 0 1 4 5a1 1 0 0 1 1-1Z"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.5 3.5 5.5 3.5 9s-1 6.5-3.5 9c-2.5-2.5-3.5-5.5-3.5-9s1-6.5 3.5-9Z"/>',
  alert: '<path d="M12 3 2 20h20Z"/><path d="M12 10v4M12 17v.5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
  star: '<path d="m12 3 2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 16.8l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8Z"/>',
  send: '<path d="M21 3 3 10.5l7 2.5 2.5 7Z"/><path d="m10 13 4-4"/>',
};
export const icon = (name, cls = '') =>
  `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PATHS[name] || ''}</svg>`;

// ---------------------------------------------------------------- feedback
let toastTimer;
export function toast(message, { type = 'info', action } = {}) {
  const box = $('#toast');
  clearTimeout(toastTimer);
  box.className = `toast toast-${type}`;
  box.innerHTML = `<span>${esc(message)}</span>${action ? `<a href="${esc(action.href)}">${esc(action.label)}</a>` : ''}`;
  box.hidden = false;
  toastTimer = setTimeout(() => { box.hidden = true; }, action ? 7000 : 4500);
}

export function errorState(error, retry = true) {
  return `<div class="empty"><div class="empty-icon">${icon('alert')}</div><h3>Impossible de charger cette page</h3>
    <p>${esc(error.message)}</p>${retry ? '<button class="btn secondary" data-retry>Réessayer</button>' : ''}</div>`;
}

export function emptyState({ iconName = 'inbox', title, text = '', action = '' }) {
  return `<div class="empty"><div class="empty-icon">${icon(iconName)}</div><h3>${esc(title)}</h3>${text ? `<p>${esc(text)}</p>` : ''}${action}</div>`;
}

export const skeletonRows = (n = 4) =>
  `<ul class="job-list" aria-hidden="true">${'<li class="job-row skeleton"><span class="sk sk-logo"></span><span class="sk-lines"><span class="sk sk-title"></span><span class="sk sk-line"></span></span></li>'.repeat(n)}</ul>`;

// Modal confirmation built on <dialog>; resolves with true/false (or the form data when `fields` are given).
export function confirmDialog({ title, body = '', confirm = 'Confirmer', danger = false, fields = '' }) {
  return new Promise(resolve => {
    const dialog = document.createElement('dialog');
    dialog.className = 'dialog';
    dialog.innerHTML = `<form method="dialog"><h2>${esc(title)}</h2>${body ? `<p>${esc(body)}</p>` : ''}${fields}
      <p class="form-error" role="alert" hidden></p>
      <div class="dialog-actions"><button class="btn ghost" value="cancel" type="submit" formnovalidate>Annuler</button>
      <button class="btn ${danger ? 'danger' : ''}" value="ok" type="submit">${esc(confirm)}</button></div></form>`;
    document.body.append(dialog);
    const form = $('form', dialog);
    dialog.addEventListener('close', () => {
      const ok = dialog.returnValue === 'ok';
      resolve(ok ? (fields ? Object.fromEntries(new FormData(form)) : true) : false);
      dialog.remove();
    });
    dialog.showModal();
    ($('input', dialog) || $('[value="ok"]', dialog)).focus();
  });
}

// Side panel used by the admin editors. Returns the panel body element.
let drawerCleanup = null;
export function openDrawer({ title, subtitle = '', content, wide = false, onClose }) {
  closeDrawer(false);
  const shell = document.createElement('div');
  shell.className = 'drawer-shell';
  shell.innerHTML = `<div class="drawer-backdrop" data-close></div>
    <aside class="drawer ${wide ? 'wide' : ''}" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
      <header class="drawer-head"><div><h2 id="drawer-title">${esc(title)}</h2>${subtitle ? `<p>${subtitle}</p>` : ''}</div>
      <button class="icon-btn" data-close aria-label="Fermer">${icon('close')}</button></header>
      <div class="drawer-body">${content}</div></aside>`;
  document.body.append(shell);
  document.body.classList.add('no-scroll');
  const previous = document.activeElement;
  const onKey = e => { if (e.key === 'Escape') closeDrawer(); };
  shell.addEventListener('click', e => { if (e.target.closest('[data-close]')) closeDrawer(); });
  document.addEventListener('keydown', onKey);
  drawerCleanup = (notify = true) => {
    document.removeEventListener('keydown', onKey);
    shell.remove();
    document.body.classList.remove('no-scroll');
    if (previous?.isConnected) previous.focus();
    if (notify && onClose) onClose();
  };
  requestAnimationFrame(() => shell.classList.add('open'));
  // Forms start on their first field; read-only panels focus the panel itself.
  const first = $('.drawer-body input:not([type=hidden]), .drawer-body select, .drawer-body textarea', shell);
  (first || $('.drawer', shell)).focus({ preventScroll: true });
  return $('.drawer-body', shell);
}
export function closeDrawer(notify = true) {
  if (drawerCleanup) { const run = drawerCleanup; drawerCleanup = null; run(notify); }
}

// ---------------------------------------------------------------- forms
export function formValues(form) {
  const data = {};
  for (const [key, value] of new FormData(form)) data[key] = typeof value === 'string' ? value : '';
  return data;
}

// Disables the submit button while sending and shows the error inside the form.
export async function submitForm(form, action, submitter) {
  const button = submitter || $('[type="submit"]', form);
  const error = $('.form-error', form);
  if (button) button.disabled = true;
  if (error) error.hidden = true;
  try {
    await action(formValues(form));
  } catch (e) {
    if (error) { error.textContent = e.message; error.hidden = false; error.scrollIntoView({ block: 'nearest' }); }
    else toast(e.message, { type: 'error' });
  } finally {
    if (button?.isConnected) button.disabled = false;
  }
}

export function options(rows, selected = '', empty = '') {
  let html = empty !== null && empty !== undefined && empty !== false ? `<option value="">${esc(empty)}</option>` : '';
  for (const row of rows) {
    const value = typeof row === 'object' ? row.id : row;
    const label = typeof row === 'object' ? row.name : row;
    html += `<option value="${esc(value)}" ${String(value) === String(selected) ? 'selected' : ''}>${esc(label)}</option>`;
  }
  return html;
}

export function pagination(total, page, limit) {
  const pages = Math.ceil(total / limit);
  if (pages <= 1) return '';
  const shown = [];
  for (let n = 1; n <= pages; n++) if (n === 1 || n === pages || Math.abs(n - page) <= 1) shown.push(n);
  let html = '', previous = 0;
  for (const n of shown) {
    if (previous && n - previous > 1) html += '<span class="gap">…</span>';
    html += `<button type="button" data-page="${n}" ${n === page ? 'aria-current="page" class="active"' : ''}>${n}</button>`;
    previous = n;
  }
  return `<nav class="pagination" aria-label="Pagination">
    <button type="button" data-page="${page - 1}" ${page === 1 ? 'disabled' : ''} aria-label="Page précédente">${icon('back')}</button>
    ${html}
    <button type="button" data-page="${page + 1}" ${page === pages ? 'disabled' : ''} aria-label="Page suivante">${icon('chevron')}</button></nav>`;
}

// ---------------------------------------------------------------- routing helpers
export function parseHash() {
  const raw = location.hash.slice(1);
  const [path, query = ''] = raw.split('?');
  return { parts: (path || 'jobs').split('/'), params: new URLSearchParams(query) };
}

export function setQuery(base, params) {
  const clean = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== '' && v !== null && v !== undefined && !(k === 'page' && Number(v) === 1)) clean.set(k, v);
  const query = clean.toString();
  history.replaceState(null, '', '#' + base + (query ? '?' + query : ''));
}

export function setTitle(title) {
  document.title = title ? `${title} · HireLoop` : 'HireLoop — Offres d’emploi avec salaire affiché';
}

// Bookmarking works from any job list; guests are invited to sign in.
export async function toggleSave(button) {
  const id = Number(button.dataset.save);
  if (!state.user) {
    toast('Connectez-vous pour sauvegarder des offres.', { action: { label: 'Se connecter', href: '#login' } });
    return;
  }
  if (!isCandidate()) { toast('La sauvegarde d’offres est réservée aux comptes candidats.'); return; }
  const saved = state.saved.has(id);
  button.disabled = true;
  try {
    await api('/saved/' + id, saved ? 'DELETE' : 'PUT');
    saved ? state.saved.delete(id) : state.saved.add(id);
    for (const b of $$(`[data-save="${id}"]`)) setSaveButton(b, !saved);
    document.dispatchEvent(new CustomEvent('saved-change', { detail: { id, saved: !saved } }));
    toast(saved ? 'Offre retirée de vos favoris.' : 'Offre sauvegardée.', saved ? {} : { action: { label: 'Voir mes favoris', href: '#saved' } });
  } catch (e) {
    toast(e.message, { type: 'error' });
  } finally {
    button.disabled = false;
  }
}

export function setSaveButton(button, saved) {
  button.classList.toggle('is-saved', saved);
  button.setAttribute('aria-pressed', String(saved));
  const label = saved ? 'Retirer des favoris' : 'Sauvegarder l’offre';
  button.setAttribute('aria-label', label);
  button.setAttribute('title', label);
  const text = $('.save-text', button);
  if (text) text.textContent = saved ? 'Sauvegardée' : 'Sauvegarder';
}
