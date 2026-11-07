// Recruiter and project-admin console.
// Project admins manage everything; company admins see their company, its ads and the applications received.
import {
  $, $$, main, state, api, esc, icon, logo, avatar, date, relative, salary, number, statusBadge, adBadge,
  emptyState, errorState, pagination, options, toast, confirmDialog, openDrawer, closeDrawer, submitForm,
  setTitle, getMeta, isAdmin, isCompanyAdmin, isStaff, refreshSession, AD_STATUS, ROLE, STATUS,
} from './core.js';

const APPLICATION_STATUSES = ['Reçue', 'En cours', 'Entretien', 'Acceptée', 'Refusée'];
const filters = {
  ads: { status: '', q: '', company_id: '', page: 1 },
  applications: { status: '', q: '', ad_id: '', page: 1 },
  people: { role: '', q: '', page: 1 },
  companies: { q: '', page: 1 },
};
let company = null; // the company of a company admin

function sections() {
  return isAdmin()
    ? [['dashboard', 'Tableau de bord', 'grid'], ['ads', 'Offres', 'briefcase'], ['applications', 'Candidatures', 'inbox'],
       ['companies', 'Entreprises', 'building'], ['categories', 'Catégories', 'tag'], ['people', 'Utilisateurs', 'users']]
    : [['dashboard', 'Tableau de bord', 'grid'], ['ads', 'Offres', 'briefcase'], ['applications', 'Candidatures', 'inbox'],
       ['company', 'Profil de l’entreprise', 'building']];
}

const query = params => new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined));
const goTo = hash => history.replaceState(null, '', '#' + hash);

// ---------------------------------------------------------------- shell
export async function renderAdmin(section = 'dashboard', id, params = new URLSearchParams()) {
  if (!state.user) { state.afterAuth = 'admin'; location.hash = 'login'; return; }
  if (!isStaff()) {
    setTitle('Accès réservé');
    main.innerHTML = `<div class="container page">${emptyState({ iconName: 'lock', title: 'Cet espace est réservé aux recruteurs.', text: 'Connectez-vous avec un compte recruteur ou administrateur.', action: '<a class="btn" href="#jobs">Retour aux offres</a>' })}</div>`;
    return;
  }
  const available = sections();
  if (!available.some(([key]) => key === section)) section = 'dashboard';
  if (isCompanyAdmin() && (!company || company.id !== state.user.company_id)) company = await api('/admin/companies/' + state.user.company_id);
  if (!$('.console', main) || main.dataset.consoleUser !== String(state.user.id)) {
    main.innerHTML = `<div class="console">
      <aside class="console-nav">
        <div class="console-org">${isAdmin()
          ? '<span class="logo" style="--logo:#244c3e" aria-hidden="true">h</span><div><strong>HireLoop</strong><small>Administration</small></div>'
          : `${logo(company.name, company.color)}<div><strong translate="no">${esc(company.name)}</strong><small>Espace recruteur</small></div>`}</div>
        <nav aria-label="Espace recruteur">${available.map(([key, label, iconName]) => `<a href="#admin/${key}" data-section="${key}">${icon(iconName)}<span>${label}</span>${key === 'applications' ? '<span class="pill nav-badge" hidden></span>' : ''}</a>`).join('')}</nav>
        <a class="console-site" href="#jobs">${icon('external')}<span>Voir le site public</span></a>
      </aside>
      <section class="console-main" id="console-main"></section></div>`;
    main.dataset.consoleUser = String(state.user.id);
  }
  for (const link of $$('[data-section]', main)) {
    const active = link.dataset.section === section;
    link.classList.toggle('active', active);
    active ? link.setAttribute('aria-current', 'page') : link.removeAttribute('aria-current');
  }
  setTitle(Object.fromEntries(available.map(([k, l]) => [k, l]))[section]);
  refreshBadge();
  const box = $('#console-main');
  box.innerHTML = '<div class="loading">Chargement…</div>';
  const renderers = { dashboard, ads: adsSection, applications: applicationsSection, companies: companiesSection, company: companyProfile, categories: categoriesSection, people: peopleSection };
  try {
    await renderers[section](box, id, params);
  } catch (e) {
    box.innerHTML = errorState(e);
    $('[data-retry]', box).onclick = () => renderAdmin(section, id, params);
  }
}

async function refreshBadge() {
  try {
    const { total } = await api('/admin/applications?status=Re%C3%A7ue&limit=1');
    const badge = $('.nav-badge');
    if (badge) { badge.hidden = !total; badge.textContent = total; badge.title = 'Candidatures à traiter'; }
  } catch { /* the badge is optional */ }
}

function head(title, text = '', actions = '') {
  return `<header class="console-head"><div><h1>${esc(title)}</h1>${text ? `<p>${text}</p>` : ''}</div>${actions ? `<div class="console-actions">${actions}</div>` : ''}</header>`;
}

function tabs(items, active, facets = null) {
  const total = facets ? Object.values(facets).reduce((a, b) => a + b, 0) : null;
  return `<div class="segmented" role="group">${items.map(([value, label]) => {
    const count = facets ? (value ? facets[value] || 0 : total) : null;
    return `<button type="button" data-tab="${esc(value)}" class="${value === active ? 'active' : ''}" aria-pressed="${value === active}"><span>${esc(label)}</span>${count !== null ? ` <span class="count">${count}</span>` : ''}</button>`;
  }).join('')}</div>`;
}

function searchBox(value, placeholder) {
  return `<label class="search-inline">${icon('search')}<span class="sr-only">Rechercher</span><input type="search" data-search value="${esc(value)}" placeholder="${esc(placeholder)}" autocomplete="off"></label>`;
}

// Debounced search input + tabs + pagination shared by every list.
function bindListControls(box, key, reload) {
  const f = filters[key];
  let timer;
  const input = $('[data-search]', box);
  if (input) input.oninput = () => { clearTimeout(timer); timer = setTimeout(() => { f.q = input.value.trim(); f.page = 1; reload(); }, 250); };
  for (const b of $$('[data-tab]', box)) b.onclick = () => { f[key === 'people' ? 'role' : 'status'] = b.dataset.tab; f.page = 1; reload(); };
  for (const b of $$('.pagination [data-page]', box)) b.onclick = () => { f.page = Number(b.dataset.page); reload(); };
}

const cell = (html, cls = '', label = '') => `<td class="${cls}"${label ? ` data-label="${esc(label)}"` : ''}>${html}</td>`;

// ---------------------------------------------------------------- dashboard
async function dashboard(box) {
  const d = await api('/admin/dashboard');
  const first = state.user.name.split(' ')[0];
  const pending = d.applications['Reçue'];
  const max = Math.max(4, ...d.timeline.map(t => t.count));
  const totalApps = d.applications_total || 1;
  box.innerHTML = `${head(`Bonjour ${first}`,
      pending ? `<a href="#admin/applications?status=Re%C3%A7ue"><strong>${pending}</strong> <span>${pending > 1 ? 'candidatures attendent une réponse.' : 'candidature attend une réponse.'}</span></a>` : 'Aucune candidature en attente. Tout est à jour.',
      `<a class="btn" href="#admin/ads/new">${icon('plus')}<span>Nouvelle offre</span></a>`)}
    <div class="kpis">
      <a class="kpi card" href="#admin/ads"><span class="kpi-label">Offres publiées</span><strong>${d.ads.published}</strong>
        <span class="kpi-sub"><span>${d.ads.draft}</span> <span>${d.ads.draft > 1 ? 'brouillons' : 'brouillon'}</span> · <span>${d.ads.closed}</span> <span>${d.ads.closed > 1 ? 'fermées' : 'fermée'}</span></span></a>
      <a class="kpi card" href="#admin/applications"><span class="kpi-label">Candidatures</span><strong>${d.applications_total}</strong>
        <span class="kpi-sub ${d.applications_week ? 'up' : ''}"><span>+${d.applications_week}</span> <span>ces 7 derniers jours</span></span></a>
      <a class="kpi card ${pending ? 'attention' : ''}" href="#admin/applications?status=Re%C3%A7ue"><span class="kpi-label">À traiter</span><strong>${pending}</strong>
        <span class="kpi-sub">statut « Reçue »</span></a>
      <div class="kpi card"><span class="kpi-label">Vues des offres</span><strong>${number(d.views)}</strong>
        <span class="kpi-sub">visiteurs non connectés en tant que recruteur</span></div>
    </div>
    <div class="dash-grid">
      <section class="card chart-card">
        <h2>Candidatures reçues</h2><p class="muted">14 derniers jours</p>
        <div class="bars" role="img" aria-label="Candidatures par jour sur 14 jours">${d.timeline.map(t => `<div class="bar" title="${esc(date(t.day))} : ${t.count}"><span style="height:${Math.round(t.count / max * 100)}%"></span><small>${Number(t.day.slice(8))}</small></div>`).join('')}</div>
      </section>
      <section class="card pipeline-card">
        <h2>Où en sont les candidatures</h2>
        <div class="stack" aria-hidden="true">${APPLICATION_STATUSES.map(s => d.applications[s] ? `<span class="status-${STATUS[s]}" style="flex:${d.applications[s]}"></span>` : '').join('')}</div>
        <ul class="legend">${APPLICATION_STATUSES.map(s => `<li><a href="#admin/applications?status=${encodeURIComponent(s)}"><span class="legend-dot status-${STATUS[s]}"></span><span>${esc(s)}</span><strong>${d.applications[s]}</strong><small>${Math.round(d.applications[s] / totalApps * 100)} %</small></a></li>`).join('')}</ul>
      </section>
      <section class="card">
        <div class="card-head"><h2>Dernières candidatures</h2><a class="link" href="#admin/applications">Tout voir</a></div>
        ${d.recent_applications.length ? `<ul class="recent">${d.recent_applications.map(a => `<li><a href="#admin/applications/${a.id}">${avatar(a.applicant_name, 'sm')}<span class="recent-main"><strong translate="no">${esc(a.applicant_name)}</strong><small translate="no">${esc(a.ad_title)}</small></span><span class="recent-side">${statusBadge(a.status)}<small>${relative(a.created_at)}</small></span></a></li>`).join('')}</ul>` : '<p class="muted">Pas encore de candidature.</p>'}
      </section>
      <section class="card">
        <div class="card-head"><h2>Offres les plus suivies</h2><a class="link" href="#admin/ads">Gérer les offres</a></div>
        ${d.top_ads.length ? `<table class="mini-table"><thead><tr><th>Offre</th><th class="num">Vues</th><th class="num">Candidatures</th></tr></thead><tbody>${d.top_ads.map(a => `<tr><td><a href="#admin/ads/${a.id}" translate="no">${esc(a.title)}</a> ${a.status !== 'published' ? adBadge(a.status) : ''}</td><td class="num">${number(a.views)}</td><td class="num">${a.applications_count}${a.new_applications ? ` <span class="pill" title="Nouvelles">+${a.new_applications}</span>` : ''}</td></tr>`).join('')}</tbody></table>` : '<p class="muted">Aucune offre pour le moment.</p>'}
      </section>
      ${d.people ? `<section class="card accounts-card"><div class="card-head"><h2>Comptes</h2><a class="link" href="#admin/people">Gérer</a></div>
        <ul class="figures"><li><strong>${d.people.candidate || 0}</strong><span>candidats</span></li><li><strong>${d.people.company_admin || 0}</strong><span>recruteurs</span></li><li><strong>${d.people.admin || 0}</strong><span>administrateurs</span></li><li><strong>${d.companies}</strong><span>entreprises</span></li></ul></section>` : ''}
    </div>`;
}

// ---------------------------------------------------------------- ads
async function adsSection(box, id) {
  const f = filters.ads;
  const meta = await getMeta();
  box.innerHTML = `${head('Offres', isAdmin() ? 'Toutes les offres de la plateforme.' : 'Les offres de votre entreprise. Les brouillons ne sont visibles que par votre équipe.',
      `<button type="button" class="btn" id="new-ad">${icon('plus')}<span>Nouvelle offre</span></button>`)}
    <div class="toolbar"><div id="ad-tabs"></div><div class="toolbar-right">${isAdmin() ? `<select id="ad-company" aria-label="Entreprise">${options(meta.companies, f.company_id, 'Toutes les entreprises')}</select>` : ''}${searchBox(f.q, 'Rechercher une offre')}</div></div>
    <div id="ad-table"></div>`;
  const reload = async () => {
    const data = await api('/admin/ads?' + query({ ...f, limit: 10 }));
    $('#ad-tabs', box).innerHTML = tabs([['', 'Toutes'], ['published', 'Publiées'], ['draft', 'Brouillons'], ['closed', 'Fermées']], f.status, data.facets);
    $('#ad-table', box).innerHTML = data.items.length ? `<div class="table-wrap card"><table class="data-table">
      <thead><tr><th>Offre</th><th>Statut</th><th class="num">Candidatures</th><th class="num">Vues</th><th>Publiée</th><th><span class="sr-only">Actions</span></th></tr></thead>
      <tbody>${data.items.map(ad => `<tr>
        ${cell(`<div class="cell-main">${logo(ad.company_name, ad.company_color, 'sm')}<div><button type="button" class="row-title" data-edit="${ad.id}" translate="no">${esc(ad.title)}</button><small><span translate="no">${esc(ad.company_name)}</span> · ${esc(ad.location)} · ${esc(ad.contract)}${ad.featured ? ` · <span class="featured-mark">${icon('star')}<span>Mise en avant</span></span>` : ''}</small></div></div>`)}
        ${cell(adBadge(ad.status))}
        ${cell(`<a href="#admin/applications?ad_id=${ad.id}">${ad.applications_count}</a>${ad.new_applications ? ` <span class="pill" title="Nouvelles">+${ad.new_applications}</span>` : ''}`, 'num', 'Candidatures')}
        ${cell(number(ad.views), 'num', 'Vues')}
        ${cell(`<span title="${esc(date(ad.created_at))}">${ad.status === 'draft' ? '—' : relative(ad.created_at)}</span>`, 'nowrap')}
        ${cell(`<div class="row-actions">
          ${ad.status === 'draft' ? `<button type="button" class="btn small secondary" data-status="published" data-id="${ad.id}">Publier</button>` : ''}
          ${ad.status === 'published' ? `<button type="button" class="btn small ghost" data-status="closed" data-id="${ad.id}">Fermer</button>` : ''}
          ${ad.status === 'closed' ? `<button type="button" class="btn small ghost" data-status="published" data-id="${ad.id}">Rouvrir</button>` : ''}
          <a class="icon-btn" href="#job/${ad.id}" title="Voir l’annonce" aria-label="Voir l’annonce">${icon('eye')}</a>
          <button type="button" class="icon-btn" data-edit="${ad.id}" title="Modifier" aria-label="Modifier">${icon('edit')}</button>
          <button type="button" class="icon-btn danger" data-delete="${ad.id}" data-title="${esc(ad.title)}" data-count="${ad.applications_count}" title="Supprimer" aria-label="Supprimer">${icon('trash')}</button></div>`, 'cell-actions')}
      </tr>`).join('')}</tbody></table></div>${pagination(data.total, data.page, data.limit)}`
      : emptyState({ iconName: 'briefcase', title: f.q || f.status ? 'Aucune offre ne correspond.' : 'Aucune offre pour le moment.', text: f.q || f.status ? '' : 'Créez votre première offre : vous pourrez la garder en brouillon avant de la publier.' });
    bindListControls(box, 'ads', reload);
    for (const b of $$('[data-edit]', box)) b.onclick = () => openAd(Number(b.dataset.edit), reload);
    for (const b of $$('[data-status]', box)) b.onclick = async () => {
      b.disabled = true;
      try {
        await api('/ads/' + b.dataset.id, 'PATCH', { status: b.dataset.status });
        state.meta = null;
        toast(b.dataset.status === 'published' ? 'Offre publiée.' : 'Offre fermée aux candidatures.', { type: 'success' });
        reload();
      } catch (e) { toast(e.message, { type: 'error' }); b.disabled = false; }
    };
    for (const b of $$('[data-delete]', box)) b.onclick = async () => {
      const count = Number(b.dataset.count);
      const ok = await confirmDialog({ title: 'Supprimer cette offre ?', body: `« ${b.dataset.title} » sera supprimée${count ? ` avec ses ${count} candidature(s)` : ''}. Pour simplement arrêter les candidatures, fermez-la plutôt.`, confirm: 'Supprimer', danger: true });
      if (!ok) return;
      try { await api('/ads/' + b.dataset.delete, 'DELETE'); state.meta = null; toast('Offre supprimée.'); reload(); refreshBadge(); }
      catch (e) { toast(e.message, { type: 'error' }); }
    };
  };
  $('#new-ad', box).onclick = () => openAd(null, reload);
  const companySelect = $('#ad-company', box);
  if (companySelect) companySelect.onchange = () => { f.company_id = companySelect.value; f.page = 1; reload(); };
  await reload();
  if (id === 'new') openAd(null, reload);
  else if (id) openAd(Number(id), reload);
}

async function openAd(id, reload) {
  const [meta, ad, staff] = await Promise.all([
    getMeta(),
    id ? api('/admin/ads/' + id) : Promise.resolve(null),
    isAdmin() ? Promise.all([api('/admin/people?role=admin&limit=100'), api('/admin/people?role=company_admin&limit=100')]).then(([a, b]) => [...a.items, ...b.items]) : Promise.resolve([]),
  ]).catch(e => { toast(e.message, { type: 'error' }); return []; });
  if (!meta) return;
  const v = ad || { contract: 'CDI', work_mode: 'Hybride', working_time: 'Temps plein', status: 'draft', featured: 0, contact_id: state.user.id };
  goTo(id ? `admin/ads/${id}` : 'admin/ads/new');
  const field = (name, label, input, cls = '') => `<label class="field ${cls}"><span>${label}</span>${input}</label>`;
  const body = openDrawer({
    title: ad ? 'Modifier l’offre' : 'Nouvelle offre', wide: true,
    subtitle: ad ? `${adBadge(ad.status)} <span>${ad.applications_count}</span> <span>candidature(s)</span> · <span>${number(ad.views)}</span> <span>vues</span>` : '',
    onClose: () => goTo('admin/ads'),
    content: `<form id="ad-form" class="drawer-form" novalidate>
      <fieldset class="form-section"><legend>L’essentiel</legend><div class="form-grid">
        ${field('title', 'Intitulé du poste', `<input name="title" required maxlength="160" value="${esc(v.title)}" placeholder="Ex. : Développeur·se back-end Python">`, 'wide')}
        ${field('summary', 'Accroche', `<textarea name="summary" rows="2" required maxlength="500" placeholder="Une ou deux phrases affichées dans la liste des offres.">${esc(v.summary)}</textarea>`, 'wide')}
        ${field('category_id', 'Domaine', `<select name="category_id" required>${options(meta.categories, v.category_id, 'Choisir…')}</select>`)}
        ${isAdmin() ? field('company_id', 'Entreprise', `<select name="company_id" required>${options(meta.companies, v.company_id, 'Choisir…')}</select>`) : ''}
        ${isAdmin() ? field('contact_id', 'Contact recruteur', `<select name="contact_id" required>${options(staff.map(p => ({ id: p.id, name: p.company_name ? `${p.name} · ${p.company_name}` : `${p.name} · HireLoop` })), v.contact_id, 'Choisir…')}</select>`) : ''}
      </div></fieldset>
      <fieldset class="form-section"><legend>Conditions</legend><div class="form-grid">
        ${field('location', 'Ville', `<input name="location" required maxlength="120" value="${esc(v.location)}" list="cities"><datalist id="cities">${meta.locations.map(l => `<option value="${esc(l)}">`).join('')}</datalist>`)}
        ${field('contract', 'Contrat', `<select name="contract" required>${options(meta.contracts, v.contract, null)}</select>`)}
        ${field('work_mode', 'Mode de travail', `<select name="work_mode" required>${options(meta.work_modes, v.work_mode, null)}</select>`)}
        ${field('working_time', 'Temps de travail', `<select name="working_time">${options(['Temps plein', 'Temps partiel'], v.working_time, null)}</select>`)}
        ${field('salary_min', 'Salaire minimum (brut annuel, €)', `<input type="number" name="salary_min" required min="0" step="500" value="${esc(v.salary_min)}" inputmode="numeric">`)}
        ${field('salary_max', 'Salaire maximum (brut annuel, €)', `<input type="number" name="salary_max" required min="0" step="500" value="${esc(v.salary_max)}" inputmode="numeric">`)}
      </div></fieldset>
      <fieldset class="form-section"><legend>Description</legend><div class="form-grid">
        ${field('description', 'Le poste', `<textarea name="description" rows="8" required maxlength="12000" placeholder="Missions, équipe, outils, organisation. Laissez une ligne vide entre deux paragraphes.">${esc(v.description)}</textarea>`, 'wide')}
        ${field('requirements', 'Profil recherché', `<textarea name="requirements" rows="5" required maxlength="12000" placeholder="Une exigence par ligne.">${esc(v.requirements)}</textarea><span class="hint">Une ligne par exigence : elles s’affichent sous forme de liste.</span>`, 'wide')}
      </div></fieldset>
      <fieldset class="form-section"><legend>Publication</legend><div class="form-grid">
        <div class="field wide"><span>Statut</span><div class="radio-cards">${Object.entries(AD_STATUS).map(([value, label]) => `<label class="radio-card"><input type="radio" name="status" value="${value}" ${v.status === value ? 'checked' : ''}><span><strong>${label}</strong><small>${{ draft: 'Visible uniquement par votre équipe.', published: 'Visible par tous, ouverte aux candidatures.', closed: 'Visible, mais plus de nouvelles candidatures.' }[value]}</small></span></label>`).join('')}</div></div>
        ${isAdmin() ? `<label class="check wide"><input type="checkbox" name="featured" ${v.featured ? 'checked' : ''}><span>Mettre en avant sur la page d’accueil</span></label>` : ''}
      </div></fieldset>
      <p class="form-error" role="alert" hidden></p>
      <div class="drawer-footer"><button type="button" class="btn ghost" data-close>Annuler</button><button class="btn" type="submit">${ad ? 'Enregistrer' : 'Créer l’offre'}</button></div>
    </form>`,
  });
  const form = $('#ad-form', body);
  form.onsubmit = e => {
    e.preventDefault();
    submitForm(form, async data => {
      const missing = [...form.querySelectorAll('[required]')].find(input => !input.value.trim());
      if (missing) { missing.focus(); throw new Error('Remplissez tous les champs obligatoires.'); }
      if (Number(data.salary_max) < Number(data.salary_min)) throw new Error('Le salaire maximum doit être supérieur au minimum.');
      if (isAdmin()) data.featured = form.featured.checked ? 1 : 0;
      if (!isAdmin()) { delete data.company_id; delete data.contact_id; }
      await api(id ? '/ads/' + id : '/ads', id ? 'PATCH' : 'POST', data);
      state.meta = null;
      closeDrawer();
      toast(id ? 'Offre enregistrée.' : data.status === 'published' ? 'Offre publiée.' : 'Brouillon créé.', { type: 'success' });
      reload();
    });
  };
}

// ---------------------------------------------------------------- applications
async function applicationsSection(box, id, params) {
  const f = filters.applications;
  if (params.has('status')) f.status = params.get('status');
  if (params.has('ad_id')) f.ad_id = params.get('ad_id');
  if (params.has('status') || params.has('ad_id')) { f.page = 1; goTo('admin/applications'); }
  const ads = (await api('/admin/ads?limit=100')).items;
  const exportUrl = () => '/api/admin/applications/export?' + query({ status: f.status, ad_id: f.ad_id });
  box.innerHTML = `${head('Candidatures', 'Changez le statut d’une candidature pour tenir le candidat informé : il voit chaque étape dans son espace.',
      `<a class="btn secondary" id="export" href="${exportUrl()}" download>${icon('download')}<span>Exporter (CSV)</span></a>`)}
    <div class="toolbar"><div id="app-tabs"></div><div class="toolbar-right">
      <select id="app-ad" aria-label="Offre">${options(ads.map(a => ({ id: a.id, name: isAdmin() ? `${a.title} · ${a.company_name}` : a.title })), f.ad_id, 'Toutes les offres')}</select>
      ${searchBox(f.q, 'Nom ou e-mail')}</div></div>
    <div id="app-table"></div>`;
  const reload = async () => {
    $('#export', box).href = exportUrl();
    const data = await api('/admin/applications?' + query({ ...f, limit: 12 }));
    $('#app-tabs', box).innerHTML = tabs([['', 'Toutes'], ...APPLICATION_STATUSES.map(s => [s, s])], f.status, data.facets);
    $('#app-table', box).innerHTML = data.items.length ? `<div class="table-wrap card"><table class="data-table">
      <thead><tr><th>Candidat</th><th>Offre</th><th>Reçue</th><th>Statut</th><th><span class="sr-only">Actions</span></th></tr></thead>
      <tbody>${data.items.map(a => `<tr class="${a.status === 'Reçue' ? 'is-new' : ''}">
        ${cell(`<div class="cell-main">${avatar(a.applicant_name, 'sm')}<div><button type="button" class="row-title" data-open="${a.id}" translate="no">${esc(a.applicant_name)}</button><small translate="no">${esc(a.applicant_email)}</small></div></div>`)}
        ${cell(`<span translate="no">${esc(a.ad_title)}</span>${isAdmin() ? `<small class="block" translate="no">${esc(a.company_name)}</small>` : ''}`)}
        ${cell(`<span title="${esc(date(a.created_at))}">${relative(a.created_at)}</span>`, 'nowrap')}
        ${cell(`<select class="status-select status-${STATUS[a.status]}" data-status-for="${a.id}" aria-label="Statut de la candidature">${options(APPLICATION_STATUSES, a.status, null)}</select>`)}
        ${cell(`<div class="row-actions">${a.notes ? `<span class="icon-hint" title="Une note privée est enregistrée">${icon('edit')}</span>` : ''}<button type="button" class="btn small secondary" data-open="${a.id}">Ouvrir</button></div>`, 'cell-actions')}
      </tr>`).join('')}</tbody></table></div>${pagination(data.total, data.page, data.limit)}`
      : emptyState({ iconName: 'inbox', title: f.status || f.q || f.ad_id ? 'Aucune candidature ne correspond.' : 'Aucune candidature pour le moment.', text: f.status || f.q || f.ad_id ? 'Essayez un autre filtre.' : 'Les candidatures envoyées depuis vos offres arriveront ici.' });
    bindListControls(box, 'applications', reload);
    for (const b of $$('[data-open]', box)) b.onclick = () => openApplication(Number(b.dataset.open), reload);
    for (const select of $$('[data-status-for]', box)) select.onchange = async () => {
      try {
        await api('/applications/' + select.dataset.statusFor, 'PATCH', { status: select.value });
        select.className = `status-select status-${STATUS[select.value]}`;
        toast(`Statut mis à jour : ${select.value}`, { type: 'success' });
        refreshBadge();
        if (f.status) reload();
      } catch (e) { toast(e.message, { type: 'error' }); reload(); }
    };
  };
  const adSelect = $('#app-ad', box);
  adSelect.onchange = () => { f.ad_id = adSelect.value; f.page = 1; reload(); };
  await reload();
  if (id) openApplication(Number(id), reload);
}

async function openApplication(id, reload) {
  let a;
  try { a = await api('/admin/applications/' + id); } catch (e) { toast(e.message, { type: 'error' }); return; }
  goTo('admin/applications/' + id);
  const c = a.candidate || {};
  const body = openDrawer({
    title: a.applicant_name, wide: true,
    subtitle: `<span>Candidature à</span> <a href="#job/${a.ad_id}" translate="no">${esc(a.ad_title)}</a> · <span>${date(a.created_at)}</span>`,
    onClose: () => goTo('admin/applications'),
    content: `<div class="applicant-card">
        ${avatar(a.applicant_name, 'lg')}
        <div><strong translate="no">${esc(a.applicant_name)}</strong>${c.headline ? `<span translate="no">${esc(c.headline)}</span>` : ''}${c.location ? `<small>${icon('pin')}<span translate="no">${esc(c.location)}</span></small>` : ''}</div>
      </div>
      <ul class="contact-list">
        <li><a href="mailto:${esc(a.applicant_email)}">${icon('mail')}<span translate="no">${esc(a.applicant_email)}</span></a></li>
        ${a.applicant_phone ? `<li><a href="tel:${esc(a.applicant_phone.replace(/\s/g, ''))}">${icon('phone')}<span translate="no">${esc(a.applicant_phone)}</span></a></li>` : ''}
        ${c.website ? `<li><a href="${esc(c.website)}" target="_blank" rel="noopener noreferrer">${icon('globe')}<span translate="no">${esc(c.website.replace(/^https?:\/\//, ''))}</span></a></li>` : ''}
      </ul>
      <section class="drawer-section"><h3>Statut</h3>
        <div class="status-picker" role="group" aria-label="Statut">${APPLICATION_STATUSES.map(s => `<button type="button" class="status-${STATUS[s]} ${s === a.status ? 'active' : ''}" aria-pressed="${s === a.status}" data-set-status="${esc(s)}">${esc(s)}</button>`).join('')}</div>
        <p class="hint">Le candidat voit ce statut dans son espace.</p></section>
      <section class="drawer-section"><h3>Message du candidat</h3><blockquote translate="no">${esc(a.message)}</blockquote></section>
      ${c.bio ? `<section class="drawer-section"><h3>À propos</h3><p translate="no">${esc(c.bio)}</p></section>` : ''}
      <section class="drawer-section"><h3>Notes privées</h3>
        <form id="notes-form"><textarea name="notes" rows="4" maxlength="12000" placeholder="Visible uniquement par votre équipe, jamais par le candidat.">${esc(a.notes)}</textarea>
        <p class="form-error" role="alert" hidden></p><div class="actions"><button class="btn small secondary" type="submit">Enregistrer la note</button><span class="hint" id="notes-saved" hidden>Enregistrée</span></div></form></section>
      <section class="drawer-section"><h3>Historique</h3>
        <ol class="timeline">${a.events.slice().reverse().map(e => `<li><span class="timeline-dot status-${STATUS[e.status]}"></span><span>${esc(e.status)}</span>${e.actor_name ? `<small translate="no">${esc(e.actor_name)}</small>` : ''}<time title="${esc(date(e.created_at))}">${relative(e.created_at)}</time></li>`).join('')}</ol></section>`,
  });
  for (const b of $$('[data-set-status]', body)) b.onclick = async () => {
    if (b.classList.contains('active')) return;
    try {
      await api('/applications/' + id, 'PATCH', { status: b.dataset.setStatus });
      toast(`Statut mis à jour : ${b.dataset.setStatus}`, { type: 'success' });
      refreshBadge();
      reload();
      openApplication(id, reload);
    } catch (e) { toast(e.message, { type: 'error' }); }
  };
  const notes = $('#notes-form', body);
  notes.onsubmit = e => {
    e.preventDefault();
    submitForm(notes, async data => {
      await api('/applications/' + id, 'PATCH', { notes: data.notes });
      $('#notes-saved', body).hidden = false;
      setTimeout(() => { const s = $('#notes-saved'); if (s) s.hidden = true; }, 2500);
      reload();
    });
  };
}

// ---------------------------------------------------------------- companies
const companyFields = c => `<div class="form-grid">
    <label class="field"><span>Nom</span><input name="name" required maxlength="160" value="${esc(c.name)}"></label>
    <label class="field"><span>Secteur</span><input name="industry" required maxlength="120" value="${esc(c.industry)}" placeholder="Ex. : Logiciel SaaS"></label>
    <label class="field"><span>Ville</span><input name="location" required maxlength="120" value="${esc(c.location)}"></label>
    <label class="field"><span>Site web</span><input type="url" name="website" maxlength="300" value="${esc(c.website)}" placeholder="https://"></label>
    <label class="field"><span>Couleur du logo</span><span class="color-input"><input type="color" name="color" value="${esc(c.color || '#355d50')}"><code>${esc(c.color || '#355d50')}</code></span></label>
    <label class="field wide"><span>Présentation</span><textarea name="description" rows="6" required maxlength="12000" placeholder="Activité, taille de l’équipe, ce qui vous distingue.">${esc(c.description)}</textarea></label>
  </div>`;

function bindColor(form) {
  const input = form.color, code = $('.color-input code', form);
  input.addEventListener('input', () => { code.textContent = input.value; });
}

async function companiesSection(box) {
  const f = filters.companies;
  box.innerHTML = `${head('Entreprises', 'Les entreprises qui publient des offres. Rattachez-leur des recruteurs depuis l’onglet Utilisateurs.',
      `<button type="button" class="btn" id="new-company">${icon('plus')}<span>Nouvelle entreprise</span></button>`)}
    <div class="toolbar"><div></div><div class="toolbar-right">${searchBox(f.q, 'Rechercher une entreprise')}</div></div><div id="company-table"></div>`;
  const reload = async () => {
    const data = await api('/admin/companies?' + query({ ...f, limit: 12 }));
    $('#company-table', box).innerHTML = data.items.length ? `<div class="table-wrap card"><table class="data-table">
      <thead><tr><th>Entreprise</th><th>Ville</th><th class="num">Offres ouvertes</th><th class="num">Recruteurs</th><th><span class="sr-only">Actions</span></th></tr></thead>
      <tbody>${data.items.map(c => `<tr>
        ${cell(`<div class="cell-main">${logo(c.name, c.color, 'sm')}<div><button type="button" class="row-title" data-edit="${c.id}" translate="no">${esc(c.name)}</button><small>${esc(c.industry)}</small></div></div>`)}
        ${cell(esc(c.location))}
        ${cell(`${c.open_ads}<small class="muted"> / ${c.ads_count}</small>`, 'num', 'Offres ouvertes')}
        ${cell(String(c.members), 'num', 'Recruteurs')}
        ${cell(`<div class="row-actions"><a class="icon-btn" href="#company/${c.id}" title="Page publique" aria-label="Page publique">${icon('eye')}</a>
          <button type="button" class="icon-btn" data-edit="${c.id}" title="Modifier" aria-label="Modifier">${icon('edit')}</button>
          <button type="button" class="icon-btn danger" data-delete="${c.id}" data-name="${esc(c.name)}" ${c.ads_count || c.members ? 'disabled title="Supprimez d’abord ses offres et ses recruteurs"' : 'title="Supprimer" aria-label="Supprimer"'}>${icon('trash')}</button></div>`, 'cell-actions')}
      </tr>`).join('')}</tbody></table></div>${pagination(data.total, data.page, data.limit)}` : emptyState({ iconName: 'building', title: 'Aucune entreprise ne correspond.' });
    bindListControls(box, 'companies', reload);
    for (const b of $$('[data-edit]', box)) b.onclick = () => editCompany(data.items.find(c => c.id === Number(b.dataset.edit)), reload);
    for (const b of $$('[data-delete]:not([disabled])', box)) b.onclick = async () => {
      if (!await confirmDialog({ title: 'Supprimer cette entreprise ?', body: `« ${b.dataset.name} » sera supprimée définitivement.`, confirm: 'Supprimer', danger: true })) return;
      try { await api('/companies/' + b.dataset.delete, 'DELETE'); state.meta = null; toast('Entreprise supprimée.'); reload(); }
      catch (e) { toast(e.message, { type: 'error' }); }
    };
  };
  $('#new-company', box).onclick = () => editCompany(null, reload);
  await reload();
}

function editCompany(c, reload) {
  const body = openDrawer({
    title: c ? 'Modifier l’entreprise' : 'Nouvelle entreprise',
    content: `<form id="company-form" class="drawer-form" novalidate>${companyFields(c || {})}<p class="form-error" role="alert" hidden></p>
      <div class="drawer-footer"><button type="button" class="btn ghost" data-close>Annuler</button><button class="btn" type="submit">${c ? 'Enregistrer' : 'Créer l’entreprise'}</button></div></form>`,
  });
  const form = $('#company-form', body);
  bindColor(form);
  form.onsubmit = e => {
    e.preventDefault();
    submitForm(form, async data => {
      await api(c ? '/companies/' + c.id : '/companies', c ? 'PATCH' : 'POST', data);
      state.meta = null;
      closeDrawer();
      toast(c ? 'Entreprise enregistrée.' : 'Entreprise créée.', { type: 'success' });
      reload();
    });
  };
}

// Company admins edit their own company profile with a live preview.
async function companyProfile(box) {
  const c = await api('/admin/companies/' + state.user.company_id);
  box.innerHTML = `${head('Profil de l’entreprise', 'Ces informations apparaissent sur chacune de vos offres et sur votre page entreprise.',
      `<a class="btn secondary" href="#company/${c.id}">${icon('eye')}<span>Voir la page publique</span></a>`)}
    <div class="profile-layout">
      <form id="company-form" class="card form-card" novalidate>${companyFields(c)}<p class="form-error" role="alert" hidden></p>
        <div class="form-footer"><button class="btn" type="submit">Enregistrer</button></div></form>
      <aside class="preview"><p class="preview-label">Aperçu</p><div class="card company-mini" id="preview"></div></aside>
    </div>`;
  const form = $('#company-form', box);
  bindColor(form);
  const preview = () => {
    const d = Object.fromEntries(new FormData(form));
    $('#preview', box).innerHTML = `<div class="company-mini-head">${logo(d.name || '?', d.color)}<div><strong translate="no">${esc(d.name || 'Nom de l’entreprise')}</strong><small><span>${esc(d.industry)}</span> · <span translate="no">${esc(d.location)}</span></small></div></div><p translate="no">${esc(d.description)}</p>`;
  };
  form.addEventListener('input', preview);
  preview();
  form.onsubmit = e => {
    e.preventDefault();
    submitForm(form, async data => {
      company = await api('/companies/' + c.id, 'PATCH', data);
      state.meta = null;
      toast('Profil de l’entreprise enregistré.', { type: 'success' });
      delete main.dataset.consoleUser; // redraw the sidebar with the new name and colour
      renderAdmin('company');
    });
  };
}

// ---------------------------------------------------------------- categories
async function categoriesSection(box) {
  const data = await api('/admin/categories?limit=100');
  box.innerHTML = `${head('Catégories', 'Les domaines proposés dans les filtres de recherche.')}
    <div class="card narrow">
      <form id="category-form" class="inline-form"><label class="field"><span class="sr-only">Nouvelle catégorie</span><input name="name" required maxlength="160" placeholder="Nouvelle catégorie"></label><button class="btn" type="submit">${icon('plus')}<span>Ajouter</span></button><p class="form-error" role="alert" hidden></p></form>
      <ul class="category-list">${data.items.map(k => `<li data-id="${k.id}">
        <span class="category-name">${esc(k.name)}</span><span class="muted"><span>${k.ads_count}</span> <span>${k.ads_count > 1 ? 'offres' : 'offre'}</span></span>
        <div class="row-actions"><button type="button" class="icon-btn" data-rename="${k.id}" title="Renommer" aria-label="Renommer">${icon('edit')}</button>
        <button type="button" class="icon-btn danger" data-delete="${k.id}" ${k.ads_count ? 'disabled title="Utilisée par des offres"' : 'title="Supprimer" aria-label="Supprimer"'}>${icon('trash')}</button></div></li>`).join('')}</ul>
    </div>`;
  const form = $('#category-form', box);
  form.onsubmit = e => {
    e.preventDefault();
    submitForm(form, async values => {
      await api('/categories', 'POST', values);
      state.meta = null;
      toast('Catégorie ajoutée.', { type: 'success' });
      categoriesSection(box);
    });
  };
  for (const b of $$('[data-rename]', box)) b.onclick = async () => {
    const item = data.items.find(k => k.id === Number(b.dataset.rename));
    const result = await confirmDialog({ title: 'Renommer la catégorie', confirm: 'Renommer', fields: `<label class="field"><span>Nom</span><input name="name" required maxlength="160" value="${esc(item.name)}"></label>` });
    if (!result || !result.name.trim() || result.name.trim() === item.name) return;
    try { await api('/categories/' + item.id, 'PATCH', { name: result.name }); state.meta = null; toast('Catégorie renommée.'); categoriesSection(box); }
    catch (e) { toast(e.message, { type: 'error' }); }
  };
  for (const b of $$('[data-delete]:not([disabled])', box)) b.onclick = async () => {
    if (!await confirmDialog({ title: 'Supprimer cette catégorie ?', confirm: 'Supprimer', danger: true })) return;
    try { await api('/categories/' + b.dataset.delete, 'DELETE'); state.meta = null; toast('Catégorie supprimée.'); categoriesSection(box); }
    catch (e) { toast(e.message, { type: 'error' }); }
  };
}

// ---------------------------------------------------------------- people
async function peopleSection(box) {
  const f = filters.people;
  box.innerHTML = `${head('Utilisateurs', 'Candidats, recruteurs et administrateurs. Pour créer un compte recruteur, choisissez le rôle Recruteur et son entreprise.',
      `<button type="button" class="btn" id="new-person">${icon('plus')}<span>Nouvel utilisateur</span></button>`)}
    <div class="toolbar"><div id="people-tabs"></div><div class="toolbar-right">${searchBox(f.q, 'Nom ou e-mail')}</div></div><div id="people-table"></div>`;
  const reload = async () => {
    const data = await api('/admin/people?' + query({ ...f, limit: 12 }));
    $('#people-tabs', box).innerHTML = tabs([['', 'Tous'], ['candidate', 'Candidats'], ['company_admin', 'Recruteurs'], ['admin', 'Administrateurs']], f.role);
    $('#people-table', box).innerHTML = data.items.length ? `<div class="table-wrap card"><table class="data-table">
      <thead><tr><th>Personne</th><th>Rôle</th><th class="num">Candidatures</th><th>Dernière connexion</th><th><span class="sr-only">Actions</span></th></tr></thead>
      <tbody>${data.items.map(p => `<tr>
        ${cell(`<div class="cell-main">${avatar(p.name, 'sm')}<div><button type="button" class="row-title" data-edit="${p.id}" translate="no">${esc(p.name)}</button><small translate="no">${esc(p.email)}</small></div></div>`)}
        ${cell(`<span class="badge role-${p.role}">${ROLE[p.role]}</span>${p.company_name ? `<small class="block" translate="no">${esc(p.company_name)}</small>` : ''}`)}
        ${cell(String(p.applications_count), 'num', 'Candidatures')}
        ${cell(p.last_login_at ? `<span title="${esc(date(p.last_login_at))}">${relative(p.last_login_at)}</span>` : '<span class="muted">Jamais</span>', 'nowrap')}
        ${cell(`<div class="row-actions"><button type="button" class="icon-btn" data-edit="${p.id}" title="Modifier" aria-label="Modifier">${icon('edit')}</button>
          ${p.id === state.user.id ? '' : `<button type="button" class="icon-btn danger" data-delete="${p.id}" data-name="${esc(p.name)}" title="Supprimer" aria-label="Supprimer">${icon('trash')}</button>`}</div>`, 'cell-actions')}
      </tr>`).join('')}</tbody></table></div>${pagination(data.total, data.page, data.limit)}` : emptyState({ iconName: 'users', title: 'Aucun utilisateur ne correspond.' });
    bindListControls(box, 'people', reload);
    for (const b of $$('[data-edit]', box)) b.onclick = () => editPerson(data.items.find(p => p.id === Number(b.dataset.edit)), reload);
    for (const b of $$('[data-delete]', box)) b.onclick = async () => {
      if (!await confirmDialog({ title: 'Supprimer ce compte ?', body: `Le compte de ${b.dataset.name} et ses candidatures seront supprimés définitivement.`, confirm: 'Supprimer', danger: true })) return;
      try { await api('/people/' + b.dataset.delete, 'DELETE'); toast('Compte supprimé.'); reload(); }
      catch (e) { toast(e.message, { type: 'error' }); }
    };
  };
  $('#new-person', box).onclick = () => editPerson(null, reload);
  await reload();
}

async function editPerson(p, reload) {
  const meta = await getMeta();
  const v = p || { role: 'candidate' };
  const body = openDrawer({
    title: p ? 'Modifier le compte' : 'Nouvel utilisateur',
    subtitle: p ? `<span>Inscrit le</span> ${date(p.created_at)}` : '',
    content: `<form id="person-form" class="drawer-form" novalidate><div class="form-grid">
        <label class="field"><span>Nom complet</span><input name="name" required maxlength="160" value="${esc(v.name)}"></label>
        <label class="field"><span>Adresse e-mail</span><input type="email" name="email" required maxlength="254" value="${esc(v.email)}"></label>
        <label class="field"><span>Téléphone</span><input type="tel" name="phone" maxlength="40" value="${esc(v.phone)}"></label>
        <label class="field"><span>Titre</span><input name="headline" maxlength="160" value="${esc(v.headline)}"></label>
        <label class="field"><span>Rôle</span><select name="role">${options(Object.entries(ROLE).map(([id, name]) => ({ id, name })), v.role, null)}</select></label>
        <label class="field" id="company-field"><span>Entreprise</span><select name="company_id">${options(meta.companies, v.company_id, 'Choisir…')}</select></label>
        <label class="field wide"><span>${p ? 'Nouveau mot de passe' : 'Mot de passe'} <em>facultatif</em></span><input type="password" name="password" minlength="10" maxlength="200" autocomplete="new-password">
          <span class="hint">${p ? 'Laisser vide pour ne pas le changer. Le changer déconnecte la personne.' : 'Sans mot de passe, le compte ne peut pas se connecter.'}</span></label>
      </div><p class="form-error" role="alert" hidden></p>
      <div class="drawer-footer"><button type="button" class="btn ghost" data-close>Annuler</button><button class="btn" type="submit">${p ? 'Enregistrer' : 'Créer le compte'}</button></div></form>`,
  });
  const form = $('#person-form', body);
  const sync = () => {
    const recruiter = form.role.value === 'company_admin';
    $('#company-field', body).hidden = !recruiter;
    form.company_id.required = recruiter;
  };
  form.role.onchange = sync;
  sync();
  form.onsubmit = e => {
    e.preventDefault();
    submitForm(form, async data => {
      if (!data.password) delete data.password;
      if (data.role !== 'company_admin') data.company_id = '';
      else if (!data.company_id) throw new Error('Choisissez une entreprise pour cet administrateur.');
      await api(p ? '/people/' + p.id : '/people', p ? 'PATCH' : 'POST', data);
      if (p && p.id === state.user.id) await refreshSession();
      closeDrawer();
      toast(p ? 'Compte enregistré.' : 'Compte créé.', { type: 'success' });
      reload();
    });
  };
}
