// Public pages: job search, job detail with the application form, companies.
import {
  $, $$, main, state, api, esc, icon, logo, salary, relative, date, paragraphs, bullets, statusBadge,
  emptyState, errorState, skeletonRows, pagination, options, setQuery, setTitle, getMeta, toast,
  toggleSave, setSaveButton, submitForm, isCandidate, isStaff, avatar,
} from './core.js';

const FILTER_KEYS = ['q', 'location', 'category_id', 'contract', 'work_mode', 'min_salary', 'sort', 'page'];
const SALARY_STEPS = [30000, 40000, 50000, 60000];

// ---------------------------------------------------------------- shared job row
export function jobRow(job, { compact = false } = {}) {
  const saved = state.saved.has(job.id);
  const label = saved ? 'Retirer des favoris' : 'Sauvegarder l’offre';
  return `<li class="job-row ${compact ? 'compact' : ''} ${job.status === 'closed' ? 'is-closed' : ''}">
    ${logo(job.company_name, job.company_color)}
    <div class="job-main">
      <h3><a class="job-link" href="#job/${job.id}" translate="no">${esc(job.title)}</a></h3>
      <p class="job-company"><span translate="no">${esc(job.company_name)}</span><span class="dot" aria-hidden="true">·</span><span>${esc(job.location)}</span></p>
      ${compact ? '' : `<div class="tags"><span class="tag">${esc(job.contract)}</span><span class="tag">${esc(job.work_mode)}</span>${job.featured ? `<span class="tag tag-featured">${icon('star')}<span>Mise en avant</span></span>` : ''}${job.status === 'closed' ? '<span class="tag tag-closed">Fermée</span>' : ''}</div>`}
    </div>
    <div class="job-side">
      <p class="job-salary">${salary(job.salary_min, job.salary_max)}</p>
      <p class="job-date"><time datetime="${esc(job.created_at)}">${relative(job.created_at)}</time></p>
    </div>
    <button type="button" class="save-btn ${saved ? 'is-saved' : ''}" data-save="${job.id}" aria-pressed="${saved}" aria-label="${label}" title="${label}">${icon('bookmark')}</button>
  </li>`;
}

export function bindSaveButtons(root = main) {
  for (const button of $$('[data-save]', root)) button.onclick = () => toggleSave(button);
}

// ---------------------------------------------------------------- job search
export async function renderJobs(params) {
  setTitle('Offres d’emploi');
  const filters = Object.fromEntries(FILTER_KEYS.map(k => [k, params.get(k) || '']));
  filters.sort ||= 'relevant';
  filters.page = Number(filters.page) || 1;

  const [meta, stats, latest] = await Promise.all([getMeta(), api('/stats'), api('/ads?sort=recent&limit=4')]);
  const radio = (name, values) => [['', 'Tous'], ...values.map(v => [v, v])].map(([value, label]) =>
    `<label class="choice"><input type="radio" name="${name}" value="${esc(value)}" ${filters[name] === value ? 'checked' : ''}><span>${esc(label)}</span></label>`).join('');

  main.innerHTML = `
  <section class="hero">
    <div class="container hero-grid">
      <div class="hero-copy">
        <h1>Des offres d’emploi claires, avec le salaire affiché.</h1>
        <p class="lead"><strong>${stats.ads}</strong> postes ouverts dans <strong>${stats.companies}</strong> entreprises. Chaque annonce précise la fourchette de salaire, le contrat et la part de télétravail.</p>
        <form id="search" class="searchbar" role="search">
          <label class="search-field">${icon('search')}<span class="sr-only">Métier, mot-clé ou entreprise</span>
            <input name="q" value="${esc(filters.q)}" placeholder="Métier, compétence ou entreprise" autocomplete="off"></label>
          <label class="search-field">${icon('pin')}<span class="sr-only">Ville</span>
            <select name="location">${options(meta.locations, filters.location, 'Toutes les villes')}</select></label>
          <button class="btn" type="submit">Rechercher</button>
        </form>
        <div class="quick-cats" aria-label="Domaines">
          ${meta.categories.filter(c => c.count).map(c => `<button type="button" class="chip ${String(c.id) === filters.category_id ? 'active' : ''}" data-category="${c.id}"><span>${esc(c.name)}</span><span class="chip-count">${c.count}</span></button>`).join('')}
        </div>
      </div>
      <aside class="hero-latest card" aria-labelledby="latest-title">
        <h2 id="latest-title">Publiées récemment</h2>
        <ul>${latest.items.map(job => `<li><a href="#job/${job.id}">${logo(job.company_name, job.company_color, 'sm')}<span><strong translate="no">${esc(job.title)}</strong><small><span translate="no">${esc(job.company_name)}</span> · <span>${relative(job.created_at)}</span></small></span></a></li>`).join('')}</ul>
      </aside>
    </div>
  </section>
  <section class="container board" id="board">
    <aside class="filters" id="filters" aria-label="Filtres">
      <div class="filters-head"><h2>Filtres</h2><button type="button" class="link" id="reset">Tout effacer</button>
        <button type="button" class="icon-btn filters-close" aria-label="Fermer les filtres">${icon('close')}</button></div>
      <fieldset><legend>Contrat</legend>${radio('contract', meta.contracts)}</fieldset>
      <fieldset><legend>Mode de travail</legend>${radio('work_mode', meta.work_modes)}</fieldset>
      <label class="field"><span>Domaine</span><select name="category_id">${options(meta.categories, filters.category_id, 'Tous les domaines')}</select></label>
      <label class="field"><span>Salaire maximum d’au moins</span><select name="min_salary">${options(SALARY_STEPS.map(n => ({ id: n, name: `${n / 1000} k€ brut / an` })), filters.min_salary, 'Indifférent')}</select></label>
      <button type="button" class="btn full filters-apply">Voir les offres</button>
    </aside>
    <div class="results">
      <div class="results-bar">
        <p id="result-count" aria-live="polite"><span class="sk sk-inline"></span></p>
        <div class="results-tools">
          <button type="button" class="btn secondary small filters-toggle" aria-controls="filters" aria-expanded="false">${icon('filter')}<span>Filtres</span><span class="filter-count" hidden></span></button>
          <label class="sort"><span>Trier par</span><select id="sort">${options([{ id: 'relevant', name: 'Pertinence' }, { id: 'recent', name: 'Date de publication' }, { id: 'salary', name: 'Salaire' }], filters.sort, null)}</select></label>
        </div>
      </div>
      <div id="active-filters" class="active-filters"></div>
      <div id="jobs-list">${skeletonRows(6)}</div>
      <div id="jobs-pagination"></div>
    </div>
  </section>`;

  const update = (changes, scroll = false) => {
    Object.assign(filters, changes);
    if (!('page' in changes)) filters.page = 1;
    syncControls();
    loadJobs(filters, meta, update);
    if (scroll) $('#board').scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  const syncControls = () => {
    for (const input of $$('#filters input[type=radio]')) input.checked = filters[input.name] === input.value;
    for (const select of $$('#filters select')) select.value = filters[select.name];
    for (const chip of $$('[data-category]')) chip.classList.toggle('active', chip.dataset.category === filters.category_id);
    $('#search [name=q]').value = filters.q;
    $('#search [name=location]').value = filters.location;
  };

  $('#search').onsubmit = e => {
    e.preventDefault();
    update({ q: e.currentTarget.q.value.trim(), location: e.currentTarget.location.value }, true);
  };
  for (const input of $$('#filters input, #filters select')) input.onchange = () => update({ [input.name]: input.value });
  for (const chip of $$('[data-category]')) chip.onclick = () => update({ category_id: chip.classList.contains('active') ? '' : chip.dataset.category }, true);
  $('#sort').onchange = e => update({ sort: e.target.value });
  $('#reset').onclick = () => update({ q: '', location: '', category_id: '', contract: '', work_mode: '', min_salary: '' });
  // Mobile: the filters open as a sheet.
  const toggle = $('.filters-toggle');
  const setOpen = open => { $('#filters').classList.toggle('open', open); toggle.setAttribute('aria-expanded', String(open)); document.body.classList.toggle('no-scroll', open); };
  toggle.onclick = () => setOpen(true);
  $('.filters-close').onclick = () => setOpen(false);
  $('.filters-apply').onclick = () => setOpen(false);

  await loadJobs(filters, meta, update);
}

let listSequence = 0;
async function loadJobs(filters, meta, update) {
  const sequence = ++listSequence;
  setQuery('jobs', filters);
  state.lastJobsHash = location.hash || '#jobs';
  const list = $('#jobs-list');
  list.classList.add('is-loading');
  try {
    const query = new URLSearchParams({ ...filters, limit: 8 });
    const data = await api('/ads?' + query);
    if (sequence !== listSequence || !$('#jobs-list')) return;
    $('#result-count').innerHTML = `<strong>${data.total}</strong> <span>${data.total > 1 ? 'offres' : 'offre'}</span>`;
    list.innerHTML = data.items.length
      ? `<ul class="job-list">${data.items.map(job => jobRow(job)).join('')}</ul>`
      : emptyState({ iconName: 'search', title: 'Aucune offre ne correspond à votre recherche.', text: 'Essayez avec moins de filtres ou un autre mot-clé.', action: '<button class="btn secondary" type="button" id="empty-reset">Effacer les filtres</button>' });
    $('#jobs-pagination').innerHTML = pagination(data.total, data.page, data.limit);
    for (const b of $$('#jobs-pagination [data-page]')) b.onclick = () => update({ page: Number(b.dataset.page) }, true);
    $('#empty-reset')?.addEventListener('click', () => $('#reset').click());
    bindSaveButtons(list);
    renderActiveFilters(filters, meta, update);
  } catch (e) {
    if (sequence !== listSequence || !$('#jobs-list')) return;
    list.innerHTML = errorState(e);
    $('[data-retry]', list).onclick = () => loadJobs(filters, meta, update);
  } finally {
    list.classList.remove('is-loading');
  }
}

function renderActiveFilters(filters, meta, update) {
  const chips = [];
  if (filters.q) chips.push(['q', `« ${filters.q} »`]);
  if (filters.location) chips.push(['location', filters.location]);
  if (filters.contract) chips.push(['contract', filters.contract]);
  if (filters.work_mode) chips.push(['work_mode', filters.work_mode]);
  if (filters.category_id) chips.push(['category_id', meta.categories.find(c => String(c.id) === filters.category_id)?.name || '']);
  if (filters.min_salary) chips.push(['min_salary', `≥ ${Number(filters.min_salary) / 1000} k€`]);
  $('#active-filters').innerHTML = chips.map(([key, label]) =>
    `<button type="button" class="chip removable" data-remove="${key}"><span>${esc(label)}</span>${icon('close')}<span class="sr-only">Retirer ce filtre</span></button>`).join('');
  for (const b of $$('[data-remove]')) b.onclick = () => update({ [b.dataset.remove]: '' });
  const count = chips.filter(([k]) => k !== 'q' && k !== 'location').length;
  const badge = $('.filter-count');
  if (badge) { badge.hidden = !count; badge.textContent = count; }
}

// ---------------------------------------------------------------- job detail
export async function renderJob(id, scrollToApply) {
  const job = await api('/ads/' + id);
  setTitle(job.title);
  const viewer = job.viewer || {};
  const saved = state.saved.has(job.id);
  main.innerHTML = `
  <div class="container detail">
    <a class="back-link" href="${esc(state.lastJobsHash)}">${icon('back')}<span>Retour aux offres</span></a>
    ${job.status === 'draft' ? `<div class="notice notice-warn">${icon('eye')}<p><strong>Aperçu d’un brouillon.</strong> Cette offre n’est pas visible par les candidats.</p><a class="btn small secondary" href="#admin/ads/${job.id}">Modifier</a></div>` : ''}
    ${job.status === 'closed' ? `<div class="notice">${icon('info')}<p>Cette offre est fermée et n’accepte plus de candidatures.</p></div>` : ''}
    <header class="detail-head">
      ${logo(job.company_name, job.company_color, 'lg')}
      <div class="detail-title">
        <p class="detail-company"><a href="#company/${job.company_id}" translate="no">${esc(job.company_name)}</a><span class="dot">·</span><span>${esc(job.industry)}</span></p>
        <h1 translate="no">${esc(job.title)}</h1>
        <ul class="detail-meta">
          <li>${icon('pin')}<span>${esc(job.location)}</span></li>
          <li>${icon('briefcase')}<span>${esc(job.contract)}</span></li>
          <li>${icon('home')}<span>${esc(job.work_mode)}</span></li>
          <li>${icon('euro')}<span>${salary(job.salary_min, job.salary_max)}</span> <span class="muted">brut / an</span></li>
          <li>${icon('clock')}<span>Publiée</span> <time datetime="${esc(job.created_at)}">${relative(job.created_at)}</time></li>
        </ul>
      </div>
      <div class="detail-actions">
        ${job.status === 'published' && !viewer.application && !isStaff() ? '<a class="btn" href="#apply" id="go-apply">Postuler</a>' : ''}
        ${viewer.can_manage ? `<a class="btn secondary" href="#admin/ads/${job.id}">${icon('edit')}<span>Modifier l’offre</span></a>` : ''}
        <button type="button" class="btn secondary save-wide ${saved ? 'is-saved' : ''}" data-save="${job.id}" aria-pressed="${saved}">${icon('bookmark')}<span class="save-text">${saved ? 'Sauvegardée' : 'Sauvegarder'}</span></button>
        <button type="button" class="icon-btn" id="copy-link" aria-label="Copier le lien de l’offre" title="Copier le lien de l’offre">${icon('link')}</button>
      </div>
    </header>
    <div class="detail-grid">
      <article class="detail-body">
        <p class="detail-summary" translate="no">${esc(job.summary)}</p>
        <section><h2>Le poste</h2><div class="prose">${paragraphs(job.description)}</div></section>
        <section><h2>Profil recherché</h2><div class="prose">${bullets(job.requirements)}</div></section>
        <section id="apply" class="apply-card" tabindex="-1"></section>
      </article>
      <aside class="detail-aside">
        <div class="card facts">
          <h2>En bref</h2>
          <dl>
            <div><dt>Contrat</dt><dd>${esc(job.contract)}</dd></div>
            <div><dt>Mode de travail</dt><dd>${esc(job.work_mode)}</dd></div>
            <div><dt>Temps de travail</dt><dd>${esc(job.working_time)}</dd></div>
            <div><dt>Salaire</dt><dd><span>${salary(job.salary_min, job.salary_max)}</span> <span class="muted">brut / an</span></dd></div>
            <div><dt>Lieu</dt><dd>${esc(job.location)}</dd></div>
            <div><dt>Domaine</dt><dd>${esc(job.category_name)}</dd></div>
          </dl>
        </div>
        <div class="card company-mini">
          <div class="company-mini-head">${logo(job.company_name, job.company_color)}<div><strong translate="no">${esc(job.company_name)}</strong><small><span>${esc(job.industry)}</span> · <span>${esc(job.company_location)}</span></small></div></div>
          <p translate="no">${esc(job.company_description)}</p>
          <div class="company-mini-links"><a href="#company/${job.company_id}">Toutes leurs offres</a>${job.company_website ? `<a href="${esc(job.company_website)}" target="_blank" rel="noopener noreferrer">Site web ${icon('external')}</a>` : ''}</div>
        </div>
      </aside>
    </div>
    <section class="similar" id="similar" hidden><h2>Offres similaires</h2><div></div></section>
  </div>`;

  renderApply(job);
  bindSaveButtons();
  $('#go-apply')?.addEventListener('click', e => { e.preventDefault(); focusApply(); });
  $('#copy-link').onclick = async () => {
    const url = location.href.split('#')[0] + '#job/' + job.id;
    try { await navigator.clipboard.writeText(url); toast('Lien copié.'); } catch { toast(url); }
  };
  if (scrollToApply) focusApply();
  api(`/ads/${job.id}/similar`).then(data => {
    const box = $('#similar');
    if (!box || !data.items.length) return;
    box.hidden = false;
    $('div', box).innerHTML = `<ul class="job-list">${data.items.map(j => jobRow(j)).join('')}</ul>`;
    bindSaveButtons(box);
  }).catch(() => {});
}

function focusApply() {
  const section = $('#apply');
  section.scrollIntoView({ behavior: 'smooth', block: 'start' });
  ($('textarea', section) || section).focus({ preventScroll: true });
}

function renderApply(job) {
  const box = $('#apply');
  const viewer = job.viewer || {};
  if (viewer.application) {
    box.innerHTML = `<h2>Votre candidature</h2>
      <div class="applied"><div>${icon('check')}</div><p>Vous avez postulé le <strong>${date(viewer.application.created_at)}</strong>.</p>${statusBadge(viewer.application.status)}</div>
      <a class="link" href="#applications">Suivre mes candidatures</a>`;
    return;
  }
  if (job.status !== 'published') { box.remove(); return; }
  if (!state.user) {
    state.afterAuth = `job/${job.id}/apply`;
    box.innerHTML = `<h2>Postuler</h2>
      <p>Pour postuler, connectez-vous ou créez un compte. Votre nom, votre e-mail et votre téléphone seront repris automatiquement.</p>
      <div class="actions"><a class="btn" href="#login">Se connecter</a><a class="btn secondary" href="#register">Créer un compte</a></div>`;
    return;
  }
  if (!isCandidate()) {
    box.innerHTML = `<h2>Postuler</h2><p class="muted">Vous êtes connecté avec un compte recruteur. Les candidatures sont réservées aux comptes candidats.</p>`;
    return;
  }
  const user = state.user;
  const draftKey = 'hireloop-draft-' + job.id;
  let draft = '';
  try { draft = localStorage.getItem(draftKey) || ''; } catch { /* storage unavailable */ }
  box.innerHTML = `<h2>Postuler</h2>
    <div class="applicant">${avatar(user.name)}<div><strong translate="no">${esc(user.name)}</strong>
      <small translate="no">${esc(user.email)}${user.phone ? ' · ' + esc(user.phone) : ''}</small>
      ${user.headline ? `<small translate="no">${esc(user.headline)}</small>` : ''}</div>
      <a class="link" href="#account">Modifier</a></div>
    <form id="apply-form" novalidate>
      <label class="field"><span>Message au recruteur</span>
        <textarea name="message" rows="7" required minlength="20" maxlength="12000" placeholder="Quelques lignes sur votre parcours et ce qui vous intéresse dans ce poste.">${esc(draft)}</textarea>
        <span class="hint"><span id="char-count">0</span> / 20 caractères minimum</span></label>
      <p class="form-error" role="alert" hidden></p>
      <div class="actions"><button class="btn" type="submit">${icon('send')}<span>Envoyer ma candidature</span></button>
        <span class="hint">Votre profil et ce message sont transmis à <span translate="no">${esc(job.company_name)}</span>.</span></div>
    </form>`;
  const textarea = $('textarea', box);
  const counter = () => {
    const n = textarea.value.trim().length;
    $('#char-count').textContent = n;
    $('#char-count').parentElement.classList.toggle('ok', n >= 20);
    try { textarea.value ? localStorage.setItem(draftKey, textarea.value) : localStorage.removeItem(draftKey); } catch { /* optional */ }
  };
  textarea.addEventListener('input', counter);
  counter();
  $('#apply-form').onsubmit = e => {
    e.preventDefault();
    const form = e.currentTarget;
    submitForm(form, async data => {
      if (data.message.trim().length < 20) throw new Error('Votre message doit contenir entre 20 et 12 000 caractères.');
      const result = await api(`/ads/${job.id}/applications`, 'POST', { message: data.message });
      try { localStorage.removeItem(draftKey); } catch { /* optional */ }
      box.innerHTML = `<div class="success" role="status"><div class="success-icon">${icon('check')}</div>
        <h2>Candidature envoyée</h2><p>${esc(result.message)}</p>
        <div class="actions"><a class="btn secondary" href="#applications">Suivre mes candidatures</a><a class="link" href="${esc(state.lastJobsHash)}">Voir d’autres offres</a></div></div>`;
      $('#go-apply')?.remove();
      box.focus();
    });
  };
}

// ---------------------------------------------------------------- companies
export async function renderCompanies() {
  setTitle('Entreprises');
  const { items } = await api('/directory/companies');
  const hiring = items.filter(c => c.open_ads).length;
  main.innerHTML = `<div class="container page">
    <header class="page-head"><div><h1>Entreprises</h1><p><strong>${hiring}</strong> entreprises recrutent en ce moment.</p></div>
      <label class="search-inline">${icon('search')}<span class="sr-only">Filtrer les entreprises</span><input id="company-filter" placeholder="Filtrer par nom, secteur ou ville" autocomplete="off"></label></header>
    <ul class="company-grid" id="company-grid">${items.map(companyCard).join('')}</ul>
    <div id="company-empty" hidden>${emptyState({ iconName: 'building', title: 'Aucune entreprise ne correspond.' })}</div>
  </div>`;
  $('#company-filter').oninput = e => {
    const term = e.target.value.trim().toLowerCase();
    let shown = 0;
    for (const card of $$('#company-grid > li')) {
      const match = !term || card.dataset.search.includes(term);
      card.hidden = !match;
      shown += match;
    }
    $('#company-empty').hidden = shown > 0;
  };
}

function companyCard(c) {
  return `<li class="company-card card" data-search="${esc(`${c.name} ${c.industry} ${c.location}`.toLowerCase())}">
    <div class="company-card-head">${logo(c.name, c.color)}<div><h2><a href="#company/${c.id}" translate="no">${esc(c.name)}</a></h2><p><span>${esc(c.industry)}</span> · <span>${esc(c.location)}</span></p></div></div>
    <p class="company-card-text" translate="no">${esc(c.description)}</p>
    <p class="company-card-foot">${c.open_ads ? `<strong>${c.open_ads}</strong> <span>${c.open_ads > 1 ? 'offres ouvertes' : 'offre ouverte'}</span>` : '<span class="muted">Pas d’offre en ce moment</span>'}</p>
  </li>`;
}

export async function renderCompany(id) {
  const company = await api('/directory/companies/' + id);
  setTitle(company.name);
  main.innerHTML = `<div class="company-banner" style="--logo:${/^#[0-9a-f]{6}$/i.test(company.color) ? company.color : '#355d50'}"></div>
  <div class="container page company-page">
    <a class="back-link" href="#companies">${icon('back')}<span>Toutes les entreprises</span></a>
    <header class="company-head">${logo(company.name, company.color, 'xl')}
      <div><h1 translate="no">${esc(company.name)}</h1>
        <p class="company-facts"><span>${icon('building')}${esc(company.industry)}</span><span>${icon('pin')}${esc(company.location)}</span>
        ${company.website ? `<a href="${esc(company.website)}" target="_blank" rel="noopener noreferrer">${icon('globe')}<span>Site web</span></a>` : ''}</p></div></header>
    <div class="company-layout">
      <section class="card company-about"><h2>À propos</h2><p translate="no">${esc(company.description)}</p></section>
      <section class="company-jobs"><h2><span>Offres ouvertes</span> <span class="count">${company.ads.length}</span></h2>
        ${company.ads.length ? `<ul class="job-list">${company.ads.map(j => jobRow(j)).join('')}</ul>` : emptyState({ iconName: 'briefcase', title: 'Pas d’offre ouverte en ce moment.', text: 'Revenez bientôt, ou parcourez les offres des autres entreprises.', action: '<a class="btn secondary" href="#jobs">Voir toutes les offres</a>' })}
      </section>
    </div>
  </div>`;
  bindSaveButtons();
}
