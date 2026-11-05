'use strict';

// OUTILS : sélectionner des éléments et préparer les textes.
function $(selector, root = document) {
  // Chercher un élément dans la page, ou dans un élément précis.
  return root.querySelector(selector);
}
const main = $('#main'); // $('#main') = document.querySelector('#main');

$('.skip').addEventListener('click', function (event) {
  event.preventDefault();
  main.focus();
  main.scrollIntoView();
});

// state = mémoriser l’état actuel de l’interface
//Cet objet rassemble les informations dont l’interface a besoin.
const state = {
  user: null,
  meta: null,
  stats: null,
  filters: {
    q: '', // filters.q = text a rechercher 
    location: '', // filters.location = ville a choisie
    category_id: '',
    contract: '',
    work_mode: '', // 	Présentiel, hybride ou télétravail.
    sort: 'relevant', // relevant, recent, salary , Ordre de tri.
    page: 1, // Page de résultats à afficher.
  },
  adminResource: 'ads', // Ressource à afficher dans l’administration.
  adminPage: 1, //Page de résultats à afficher dans l’administration.
};

function esc(value) { //esc() transforme les caractères spéciaux pour que le navigateur affiche un texte sans l’interpréter comme du HTML.

  // Empêcher un texte utilisateur d'être interprété comme du HTML.
  if (value === null || value === undefined) {// Si la valeur est nulle ou indéfinie, on la remplace par une chaîne vide.
    value = '';
  }
  let text = String(value); //Convertir la valeur en texte

  text = text.replace(/&/g, '&amp;'); // /.../ délimite une expression régulière.
  // & est le caractère recherché.

  text = text.replace(/</g, '&lt;'); // g signifie global : remplacer toutes les occurrences.
  text = text.replace(/>/g, '&gt;');
  text = text.replace(/"/g, '&quot;');
  text = text.replace(/'/g, '&#39;');
  return text;
}
// & = &amp; , < =	&lt; , > =	&gt; , " =	&quot; , ' =	&#39;



function isAdmin() {
  if (!state.user) { // si aucun user n'est connecté, la fonction retourne false
    return false;
  }
  return state.user.role === 'admin' || state.user.role === 'company_admin';
}

function companyAdmin() {
  if (!state.user) { // si aucun user n'est connecté, la fonction retourne false
    return false;
  }
  return state.user.role === 'company_admin';
}

const roleNames = { //  associer les rôles aux noms affichés dans l’interface.
  candidate: 'Candidat',
  admin: 'Administrateur du projet',
  company_admin: 'Administrateur d’entreprise',
};

function money(n) { // money() et date() : présenter les valeurs et les dates dans le format français.
  return new Intl.NumberFormat('fr-FR').format(n);
}
function date(v) { // date() : présenter les valeurs et les dates dans le format français.
  return localizedDate(v);
}

function options(rows, selected = '', empty = 'Sélectionner') { //construire une liste déroulante
  // rows = choix disponibles, sous forme de tableau d’objets {id, name}.
  // selected = valeur de l’option sélectionnée.
  // empty = texte de l’option vide.

  let html = '<option value="">' + esc(empty) + '</option>';
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i]; // rows[i] : récupérer l’élément actuel

    let value = row; // id ou valeur de l’option
    let label = row; // name ou texte affiché de l’option

    //Ces lignes utilisent l’identifiant et le nom lorsqu’ils existent :
    if (row.id !== null && row.id !== undefined) {
      value = row.id;
    }
    if (row.name !== null && row.name !== undefined) {
      label = row.name;
    }

    let selectedAttribute = '';
    if (String(value) === String(selected)) {
      selectedAttribute = 'selected';
    }
    html += // ajoute chaque option au texte déjà construit.
      '<option value="' + esc(value) + '" ' + selectedAttribute + '>' + esc(label) + '</option>';
  }
  return html;
}

function icon(name) { // icon() : renvoyer le code SVG d’une icône.
  return {
    search:
      '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.6" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg>',
    pin: '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.6" aria-hidden="true"><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2.5"/></svg>',
  }[name];

  // Le résultat est du HTML à insérer dans la page.
}


// GESTION DES NOTIFICATIONS
let toastTimer; // timer pour masquer la notification après 5 secondes
let routeSequence = 0; // compteur pour suivre la séquence des routes et éviter les conflits lors de l'affichage des offres
let listSequence = 0; // compte les chargements de résultats.


// COMMUNICATION AVEC LE SERVEUR : async / await attend la réponse sans bloquer la page.

async function api(path, method = 'GET', body) {
  // Envoyer une requête au serveur et récupérer sa réponse JSON.
  const settings = {
    method: method,
    credentials: 'same-origin', // permet notamment d’envoyer le cookie de session au même site.
    headers: {},
  };

  if (body) {
    settings.headers['Content-Type'] = 'application/json';
    settings.body = JSON.stringify(body); //JSON.stringify() transforme un objet JavaScript en texte JSON.
  }

  const response = await fetch('/api' + path, settings); // fetch() envoie la requête et attend la réponse du serveur.
  const data = await response.json(); // await response.json() lit la réponse et la transforme en objet JavaScript.

  // await attend le résultat dans cette fonction. , - response.json() lit la réponse JSON.

  if (!response.ok) {
    let message = data.error;
    if (!message) {
      message = 'Une erreur est survenue.';
    }
    const error = new Error(message);
    error.status = response.status;
    throw error; //si la reponce indique une erreur, déclenche une erreur qui sera récupérée par un catch.
  }
  return data;
}

// MESSAGES : afficher une notification pendant cinq secondes.
function toast(message) {
  clearTimeout(toastTimer);
  $('#toast').textContent = message; // $('#toast') = document.querySelector('#toast') , textContent = message à afficher
  $('#toast').hidden = false;
  toastTimer = setTimeout(function () {
    return ($('#toast').hidden = true);
  }, 5000);
}

function errorBox(error) { // construit un bloc HTML avec le message d’erreur et un bouton « Réessayer ».
  return `<div class="empty"><div class="empty-icon">↻</div><h3>Impossible de charger ce contenu</h3><p>${esc(error.message)}</p><button class="btn secondary" data-retry>Réessayer</button></div>`;
}

// NAVIGATION : adapter les liens au compte connecté.

function updateNav() { // modifier le menu nav 
  if (state.user) {
    $('#auth-nav').innerHTML =
      `<span class="user-name">Bonjour, ${esc(state.user.name.split(' ')[0])}</span>${isAdmin() ? '<a class="btn small" href="#admin">Administration ↗</a>' : '<a class="btn secondary small" href="#account">Mon compte</a>'}<button class="link-button" id="logout">Déconnexion</button>`;
  } else {
    $('#auth-nav').innerHTML =
      '<a href="#login">Se connecter</a><a class="btn" href="#register">Créer un compte <span>↗</span></a>';
  }
  for (const el of document.querySelectorAll('.signed-only')) {
    el.hidden = !state.user;
  }
  const logoutButton = $('#logout');
  if (logoutButton) {
    logoutButton.addEventListener('click', async function () {
      try {
        await api('/auth/logout', 'POST', {});
        state.user = null;
        updateNav();
        location.hash = 'jobs';
        await route();
        toast('Vous êtes déconnecté.');
      } catch (e) {
        toast(e.message);
      }
    });
  }
}

function logo(job) { // choisit une couleur valide et la première lettre de l’entreprise.
  let color;
  if (/^#[0-9a-f]{6}$/i.test(job.company_color || job.color)) { // /^#[0-9a-f]{6}$/ = expression régulière qui vérifie si la couleur est au format hexadécimal (ex : #ff0000)
    color = job.company_color || job.color;
  } else {
    color = '#355d50';
  }
  return `<span class="company-logo" style="--logo:${color}" aria-hidden="true">${esc((job.company_name || job.name || '?')[0])}</span>`;
}
// OFFRES : construire le HTML d’une carte / offre .
function jobCard(job) {
  return `<article class="job-card">${job.featured ? '<span class="featured">✦ À découvrir</span>' : ''}<div class="job-top">${logo(job)}<div class="company-info">${esc(job.company_name)}<small>${esc(job.industry)}</small></div></div><h3><a href="#job/${job.id}">${esc(job.title)}</a></h3><p class="summary">${esc(job.summary)}</p><div class="tags"><span class="tag contract">${esc(job.contract)}</span><span class="tag">⌖ ${esc(job.location)}</span><span class="tag">${esc(job.work_mode)}</span></div><p class="salary">${money(job.salary_min)} – ${money(job.salary_max)} € <span>/ an brut</span></p><div class="card-bottom"><a class="details-btn" href="#job/${job.id}">En savoir plus <span>↗</span></a><a class="btn secondary" href="#job/${job.id}/apply">Postuler <span>→</span></a></div></article>`;
}
// PAGINATION : afficher les premières, dernières et pages voisines.

function pagination(total, page, limit, attr = 'page') { // créer les boutons de pages
  const pages = Math.ceil(total / limit); // Math.ceil() arrondit à l’entier supérieur
  if (pages <= 1) {
    return '';
  }
  let nums = [];
  for (let n = 1; n <= pages; n++) {
    if (n === 1 || n === pages || Math.abs(n - page) <= 1) {
      nums.push(n);
    }
  }

  let previous = 0;
  function createPageButtons(rows) { //ajoute les … entre les numéros éloignés.
    let html = '';
    for (let i = 0; i < rows.length; i++) {
      const n = rows[i];
      let gap;
      if (previous && n - previous > 1) {
        gap = '<span>…</span>';
      } else {
        gap = '';
      }
      previous = n;
      html +=
        gap +
        `<button data-${attr}="${n}" class="${page === n ? 'active' : ''}" ${page === n ? 'aria-current="page"' : ''}>${n}</button>`;
    }
    return html;
  }
  return `<nav class="pagination" aria-label="Pagination"><button data-${attr}="${page - 1}" ${page === 1 ? 'disabled' : ''} aria-label="Page précédente">←</button>${createPageButtons(nums)}<button data-${attr}="${page + 1}" ${page === pages ? 'disabled' : ''} aria-label="Page suivante">→</button></nav>`;
}
// PAGE DES OFFRES : affichage et événements des filtres.
async function renderJobs() { //préparer l’écran de recherche
  if (!state.meta) {
    const results = await Promise.all([api('/meta'), api('/stats')]);
    state.meta = results[0];
    state.stats = results[1];
  }
  // createContractFilters() et createWorkModeFilters() utilisent des boucles pour construire les boutons radio.

  function createContractFilters(rows) {
    let html = '';
    for (let i = 0; i < rows.length; i++) {
      const v = rows[i];
      html += `<label class="check"><input type="radio" name="contract" value="${v}" ${state.filters.contract === v ? 'checked' : ''}>${v}</label>`;
    }
    return html;
  }
  function createWorkModeFilters(rows) {
    let html = '';
    for (let i = 0; i < rows.length; i++) {
      const v = rows[i];
      html += `<label class="check"><input type="radio" name="work_mode" value="${v}" ${state.filters.work_mode === v ? 'checked' : ''}>${v}</label>`;
    }
    return html;
  }
  main.innerHTML = `<section class="hero"><div class="hero-copy"><span class="eyebrow">Votre avenir mérite le bon départ</span><h1>Le prochain chapitre<br>commence <span class="serif">ici.</span></h1><p>Un nouveau défi, une équipe qui vous ressemble.<br>Trouvez l’opportunité qui vous donne envie d’avancer.</p><div class="hero-bottom"><div class="avatars" aria-hidden="true"><span class="avatar">CM</span><span class="avatar">AB</span><span class="avatar">JD</span><span class="avatar">SL</span></div><p><strong>Des talents. Des équipes. Des rencontres.</strong><br>Le travail commence par une belle connexion.</p></div></div><div class="hero-art" aria-hidden="true"><div class="orbit"></div><div class="orbit o2"></div><div class="orbit o3"></div><div class="art-center"><svg viewBox="0 0 100 100" fill="none"><path d="M21 72V25h20v20c8-11 30-11 30 9v18H51V55c0-8-10-7-10 0v17Z" fill="#244c3e"/><path d="M61 20h22v22M82 21 58 45" stroke="#244c3e" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/></svg></div><div class="float-card"><div class="float-icon">✧</div><div><strong>Le bon talent, la bonne équipe.</strong><span>Tout commence par une rencontre</span></div></div><div class="float-card second"><div class="float-icon">✓</div><div><strong>Votre prochain départ</strong><span>${state.stats.ads} opportunités à explorer</span></div></div><span class="spark">✳</span><span class="spark s2">✦</span></div></section>
  <section class="search-wrap" aria-label="Rechercher une offre"><form id="search" class="search-form"><label class="search-field">${icon('search')}<input name="q" aria-label="Métier, mot-clé ou entreprise" placeholder="Un métier, un mot-clé, une entreprise…" value="${esc(state.filters.q)}"></label><label class="search-field">${icon('pin')}<select name="location" aria-label="Ville">${options(state.meta.locations, state.filters.location, 'Où souhaitez-vous travailler ?')}</select></label><button class="btn" type="submit">Trouver mon prochain job <span>↗</span></button></form></section>
  <div class="trust"><p>Des équipes à découvrir.<br>Des projets qui ont du sens.</p><span class="trust-logo">◈ Studio North</span><span class="trust-logo">✳ bloom</span><span class="trust-logo">◉ orbit</span><span class="trust-logo">MAISON ATLAS</span><span class="trust-logo">▥ Linear Labs</span></div>
  <section class="board" id="board"><aside class="filters" aria-label="Filtres des offres"><div class="filter-head"><h2>Affiner la recherche</h2><button class="reset" id="reset">Tout effacer</button></div><div class="filters-inner"><fieldset class="filter-group"><legend>Type de contrat</legend>${createContractFilters(['CDI', 'CDD', 'Stage', 'Alternance', 'Freelance'])}</fieldset><fieldset class="filter-group"><legend>Votre domaine</legend><select class="filter-select" id="category" aria-label="Domaine">${options(state.meta.categories, state.filters.category_id, 'Tous les domaines')}</select></fieldset><fieldset class="filter-group"><legend>Mode de travail</legend>${createWorkModeFilters(['Sur site', 'Hybride', 'Télétravail'])}</fieldset><div class="filter-group"><p class="note">Une envie précise ? Combinez les filtres pour trouver votre prochaine équipe.</p></div></div></aside><div class="results"><div class="results-header"><div><h2>À vous de jouer<span class="serif">.</span></h2><p id="result-count" aria-live="polite">Recherche des opportunités…</p></div><label class="sort">Trier par <select id="sort">${options(
    [
      {
        id: 'relevant',
        name: 'Pertinence',
      },
      {
        id: 'recent',
        name: 'Plus récentes',
      },
      {
        id: 'salary',
        name: 'Salaire décroissant',
      },
    ],
    state.filters.sort,
    'Choisir',
  )}</select></label></div><div id="jobs-list" class="jobs-grid"><div class="loading">Chargement des offres…</div></div><div id="pagination"></div><div class="callout"><div><h3>Votre prochaine équipe vous attend.</h3><p>Un profil, de nouvelles perspectives. Faites le premier pas.</p></div><a class="btn lime" href="${state.user ? '#account' : '#register'}">${state.user ? 'Mon profil' : 'Créer mon compte'} ↗</a></div></div></section>`;
  $('#search').onsubmit = function (e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    state.filters.q = form.get('q');
    state.filters.location = form.get('location');
    state.filters.page = 1;
    loadJobs();
  };
  for (const input of document.querySelectorAll('.filters input')) {
    input.onchange = function () {
      state.filters[input.name] = input.value;
      state.filters.page = 1;
      loadJobs();
    };
  }
  $('#category').onchange = function (e) {
    state.filters.category_id = e.target.value;
    state.filters.page = 1;
    loadJobs();
  };
  $('#sort').onchange = function (e) {
    state.filters.sort = e.target.value;
    state.filters.page = 1;
    loadJobs();
  };
  $('#reset').onclick = function () {
    state.filters = {
      q: '',
      location: '',
      category_id: '',
      contract: '',
      work_mode: '',
      sort: 'relevant',
      page: 1,
    };
    renderJobs();
  };
  await loadJobs();
}
// RECHERCHE : récupérer les offres qui correspondent aux filtres.
async function loadJobs() {
  // Seule la recherche la plus récente doit actualiser la liste.
  listSequence++;
  const sequence = listSequence;
  try {
    const data = await api(
      '/ads?' +
      new URLSearchParams({
        q: state.filters.q,
        location: state.filters.location,
        category_id: state.filters.category_id,
        contract: state.filters.contract,
        work_mode: state.filters.work_mode,
        sort: state.filters.sort,
        page: state.filters.page,
        limit: 6,
      }),
    );
    if (sequence !== listSequence || !$('#jobs-list')) {
      return;
    }
    $('#result-count').textContent =
      `${data.total} opportunité${data.total > 1 ? 's' : ''} pour écrire la suite`;
    function createOfferCards(rows) {
      let html = '';
      for (let i = 0; i < rows.length; i++) {
        html += jobCard(rows[i]);
      }
      return html;
    }
    if (data.items.length) {
      $('#jobs-list').innerHTML = createOfferCards(data.items);
    } else {
      $('#jobs-list').innerHTML =
        '<div class="empty"><div class="empty-icon">⌕</div><h3>La bonne rencontre se prépare.</h3><p>Aucune offre ne correspond à ces critères. Essayez un autre mot-clé ou effacez les filtres.</p><button class="btn secondary" id="empty-reset">Effacer les filtres</button></div>';
    }
    const resetButton = $('#empty-reset');
    if (resetButton) {
      resetButton.addEventListener('click', function () {
        return $('#reset').click();
      });
    }
    $('#pagination').innerHTML = pagination(data.total, data.page, data.limit);
    for (const b of document.querySelectorAll('[data-page]')) {
      b.onclick = function () {
        state.filters.page = Number(b.dataset.page);
        loadJobs();
        $('#board').scrollIntoView({
          behavior: 'smooth',
        });
      };
    }
  } catch (e) {
    if ($('#jobs-list')) {
      $('#jobs-list').innerHTML = errorBox(e);
      $('[data-retry]').onclick = loadJobs;
    }
  }
}
// DÉTAIL D’UNE OFFRE.
async function renderJob(id, apply) {
  const job = await api('/ads/' + id);
  function createOfferFacts(rows) {
    let html = '';
    for (let i = 0; i < rows.length; i++) {
      const entry = rows[i];
      const k = entry[0];
      const v = entry[1];
      html += `<div class="fact"><span>${esc(k)}</span><strong>${esc(v)}</strong></div>`;
    }
    return html;
  }
  main.innerHTML = `<div class="page"><a href="#jobs" class="back">← Toutes les opportunités</a><div class="detail-layout"><article class="panel detail-body"><div class="job-top">${logo(job)}<div class="company-info">${esc(job.company_name)}<small>${esc(job.industry)}</small></div></div><h1 class="detail-title">${esc(job.title)}</h1><div class="tags"><span class="tag contract">${esc(job.contract)}</span><span class="tag">${esc(job.location)}</span><span class="tag">${esc(job.work_mode)}</span><span class="tag">${esc(job.category_name)}</span></div><p class="note">Publiée le ${date(job.created_at)}</p><h2>Le prochain chapitre, ensemble.</h2><p class="prose">${esc(job.description)}</p><h2>Et si c’était vous ?</h2><p class="prose">${esc(job.requirements)}</p><div id="apply-section" class="apply-box" ${apply ? '' : 'hidden'}></div></article><aside class="panel detail-side"><h2 style="font-size:21px">L’essentiel de l’offre</h2><div class="facts">${createOfferFacts(
    [
      ['Contrat', job.contract],
      ['Localisation', job.location],
      ['Organisation', job.work_mode],
      ['Rythme', job.working_time],
      ['Salaire annuel brut', money(job.salary_min) + ' – ' + money(job.salary_max) + ' €'],
    ],
  )}</div><button class="btn full" id="show-apply">C’est parti, je postule ↗</button><p class="note">Votre candidature arrive directement dans l’espace du recruteur.</p><h3>À propos de ${esc(job.company_name)}</h3><p class="prose company-text">${esc(job.company_description)}</p><a class="details-btn" href="#company/${job.company_id}">Découvrir leurs offres ↗</a></aside></div></div>`;
  $('#show-apply').onclick = function () {
    return showApply(job, true);
  };
  if (apply) {
    showApply(job, true);
  }
}
// CANDIDATURE : ouvrir le formulaire et envoyer les informations.
function showApply(job, scroll) {
  const target = $('#apply-section');
  target.hidden = false;
  if (state.user) {
    target.innerHTML = `<h2>On fait connaissance ?</h2><p class="note">Vous postulez avec le profil de <strong>${esc(state.user.name)}</strong> (${esc(state.user.email)}). <a href="#account">Modifier mon profil</a></p><form id="apply-form"><div class="form-grid"><label class="field wide">Votre message au recruteur *<textarea name="message" required minlength="20" maxlength="12000" placeholder="Pourquoi cette opportunité vous donne-t-elle envie de nous rejoindre ?"></textarea></label></div><p class="note">Les informations de votre profil et votre message seront enregistrés et consultables par l’administrateur pour traiter votre candidature.</p><p class="form-error" role="alert" hidden></p><div class="form-actions"><button class="btn" type="submit">Envoyer ma candidature ↗</button><button class="link-button muted" type="button" id="cancel-apply">Annuler</button></div></form>`;
  } else {
    // Revenir à cette offre après la connexion ou l'inscription.
    state.afterAuth = `job/${job.id}/apply`;
    target.innerHTML = `<h2>On fait connaissance ?</h2><p class="note">Connectez-vous ou créez un compte pour postuler. Votre candidature utilisera les informations de votre profil.</p><div class="form-actions"><a class="btn" href="#login">Se connecter</a><a class="btn secondary" href="#register">Créer un compte</a><button class="link-button muted" type="button" id="cancel-apply">Annuler</button></div>`;
  }
  $('#cancel-apply').onclick = function () {
    target.hidden = true;
    $('#show-apply').focus();
  };
  const applyForm = $('#apply-form');
  if (applyForm) applyForm.onsubmit = async function (e) {
    e.preventDefault();
    await submit(e.currentTarget, async function (data) {
      const result = await api(`/ads/${job.id}/applications`, 'POST', data);
      target.innerHTML = `<div class="success-box" role="status"><h3>Le premier pas est fait ✓</h3><p>${esc(result.message)}</p>${state.user ? '<p><a href="#applications" style="text-decoration:underline">Suivre mes candidatures →</a></p>' : ''}</div>`;
      target.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    });
  };
  if (scroll) {
    target.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    });
    const firstField = $('textarea, .btn', target);
    if (firstField) {
      firstField.focus({
        preventScroll: true,
      });
    }
  }
}
// FORMULAIRES : traitement commun des envois et des erreurs.
async function submit(form, action) { // récupérer les champs et gérer l’envoi
  // Éviter les doubles clics et afficher les erreurs dans le formulaire.
  const button = $('[type="submit"]', form);
  const error = $('.form-error', form);
  button.disabled = true;
  error.hidden = true;
  try {
    const formData = new FormData(form);
    const data = {};
    for (const entry of formData.entries()) {
      data[entry[0]] = entry[1];
    }
    await action(data);
  } catch (e) {
    error.textContent = e.message;
    error.hidden = false;
  } finally {
    if (button.isConnected) {
      button.disabled = false;
    }
  }
}
// CONNEXION ET INSCRIPTION : le paramètre register choisit le formulaire.
function renderAuth(register = false) {
  main.innerHTML = `<section class="auth-layout"><div class="auth-aside"><span class="eyebrow">Un nouveau départ</span><h1>Les belles carrières commencent par <span class="serif">une rencontre.</span></h1><p>Des opportunités choisies, des équipes engagées et la place pour écrire votre propre histoire.</p><span class="art-mini" aria-hidden="true">↗</span></div><div class="auth-form"><h2>${register ? 'Faisons connaissance.' : 'Heureux de vous retrouver.'}</h2><p class="note">${register ? 'Votre prochaine opportunité n’est peut-être qu’à un clic.' : 'Connectez-vous pour retrouver votre espace.'}</p><form id="auth-form">${register ? '<label class="field">Nom complet *<input name="name" autocomplete="name" required maxlength="120"></label>' : ''}<label class="field">Adresse e-mail *<input type="email" name="email" required autocomplete="email" maxlength="250"></label>${register ? '<label class="field">Téléphone<input type="tel" name="phone" autocomplete="tel" maxlength="40"></label>' : ''}<label class="field">Mot de passe *<input type="password" name="password" required minlength="${register ? 10 : 1}" maxlength="200" autocomplete="${register ? 'new-password' : 'current-password'}"></label>${register ? '<p class="note">Au moins 10 caractères pour protéger votre compte.</p>' : ''}<p class="form-error" role="alert" hidden></p><button class="btn full" type="submit">${register ? 'Créer mon compte' : 'Me connecter'} ↗</button></form><p class="auth-switch">${register ? 'Déjà un compte ? <a href="#login">Se connecter</a>' : 'Pas encore de compte ? <a href="#register">Rejoindre HireLoop</a>'}</p>${register ? '' : '<div class="demo-box"><strong>Explorer la démonstration</strong>Candidat : camille@hireloop.test · Camille2026!<br>Admin : admin@hireloop.test · Admin2026!</div>'}</div></section>`;
  $('#auth-form').onsubmit = async function (e) {
    e.preventDefault();
    await submit(e.currentTarget, async function (data) {
      const result = await api('/auth/' + (register ? 'register' : 'login'), 'POST', data);
      state.user = result.user;
      updateNav();
      if (isAdmin()) {
        location.hash = 'admin';
      } else {
        location.hash = state.afterAuth || 'jobs';
      }
      toast(register ? 'Bienvenue sur HireLoop. Votre compte est prêt !' : 'Vous êtes connecté.');
    });
  };
}
// PROFIL : consulter et modifier les informations du compte.
async function renderAccount() {
  if (!state.user) {
    location.hash = 'login';
    return;
  }
  const user = state.user;
  main.innerHTML = `<section class="page"><div class="page-head"><div><span class="eyebrow">Votre espace personnel</span><h1>Un profil qui vous ressemble.</h1><p>Vos informations sont utilisées pour vos prochaines candidatures.</p></div></div><div class="panel profile-panel"><form id="profile-form"><div class="form-grid"><label class="field">Nom complet *<input name="name" required value="${esc(user.name)}" maxlength="120" autocomplete="name"></label><label class="field">Adresse e-mail *<input type="email" name="email" required value="${esc(user.email)}" maxlength="250" autocomplete="email"></label><label class="field wide">Téléphone<input type="tel" name="phone" value="${esc(user.phone)}" maxlength="40" autocomplete="tel"></label><label class="field">Mot de passe actuel<input type="password" name="current_password" autocomplete="current-password"><span class="note">Requis pour modifier votre e-mail ou mot de passe.</span></label><label class="field">Nouveau mot de passe<input type="password" name="password" minlength="10" autocomplete="new-password"><span class="note">Facultatif, au moins 10 caractères.</span></label></div><p class="form-error" role="alert" hidden></p><div class="form-actions"><button class="btn" type="submit">Enregistrer mon profil ↗</button><a href="#applications" class="details-btn">Mes candidatures →</a></div></form></div></section>`;
  $('#profile-form').onsubmit = async function (e) {
    e.preventDefault();
    await submit(e.currentTarget, async function (data) {
      if (!data.password) {
        delete data.password;
      }
      const result = await api('/account', 'PATCH', data);
      state.user = result.user;
      updateNav();
      toast('Votre profil a été mis à jour.');
      renderAccount();
    });
  };
}
// SUIVI DES CANDIDATURES.
async function renderApplications() { //Afficher les candidatures et leur statut.
  if (!state.user) {
    location.hash = 'login';
    return;
  }
  const data = await api('/my-applications');
  function createApplicationCards(rows) {
    let html = '';
    for (let i = 0; i < rows.length; i++) {
      const a = rows[i];
      html += `<article class="application-card"><div><h3><a href="#job/${a.ad_id}">${esc(a.title)} ↗</a></h3><p>${esc(a.company_name)} · Candidature du ${date(a.created_at)}</p><details><summary>Relire mon message</summary><p class="prose">${esc(a.message)}</p></details></div><span class="status ${esc(a.status.toLowerCase())}">${esc(a.status)}</span></article>`;
    }
    return html;
  }
  main.innerHTML = `<section class="page"><div class="page-head"><div><span class="eyebrow">Chaque pas compte</span><h1>Vos prochaines rencontres.</h1><p>Retrouvez vos candidatures et leur avancement.</p></div><a class="btn secondary" href="#jobs">Voir les offres ↗</a></div>${data.items.length ? createApplicationCards(data.items) : '<div class="empty"><div class="empty-icon">↗</div><h3>Votre histoire commence ici.</h3><p>Vous n’avez pas encore postulé. Découvrez les équipes qui recrutent.</p><a class="btn" href="#jobs">Explorer les opportunités</a></div>'}</section>`;
}
// ENTREPRISES : liste générale ou offres d’une entreprise.
async function renderCompanies(companyId) { //Afficher les entreprises.
  const meta = await api('/meta');
  if (companyId) {
    const data = await api(`/companies/${companyId}/ads`);
    const company = meta.companies.find(function (c) {
      return c.id === Number(companyId);
    });
    function createCompanyOfferCards(rows) {
      let html = '';
      for (let i = 0; i < rows.length; i++) {
        html += jobCard(rows[i]);
      }
      return html;
    }
    main.innerHTML = `<section class="page"><a class="back" href="#companies">← Les entreprises</a><div class="page-head"><div><h1>${esc((company && company.name) || 'Entreprise')}</h1><p>${data.items.length} offre(s) à découvrir dans cette équipe.</p></div></div><div class="jobs-grid">${data.items.length ? createCompanyOfferCards(data.items) : '<div class="empty"><h3>Aucune offre pour le moment.</h3><p>Cette équipe ne recrute pas actuellement.</p></div>'}</div></section>`;
    return;
  }
  // Les informations publiques des entreprises sont issues des offres et du catalogue API.
  const jobs = await api('/ads?limit=100');
  function createCompanyCards(rows) {
    let html = '';
    for (let i = 0; i < rows.length; i++) {
      const c = rows[i];
      const j = jobs.items.find(function (j) {
        return j.company_id === c.id;
      });
      html += `<article class="panel company-card">${logo(j || c)}<h2>${esc(c.name)}</h2><p>${esc((j && j.industry) || 'Entreprise partenaire')}${j ? ' · ' + esc(j.location) : ''}</p><p>${esc((j && j.company_description) || 'Découvrez les prochaines opportunités proposées par cette entreprise.')}</p><a class="btn secondary small" href="#company/${c.id}">Voir les offres ↗</a></article>`;
    }
    return html;
  }
  main.innerHTML = `<section class="page"><div class="page-head"><div><span class="eyebrow">Derrière chaque offre, une équipe</span><h1>Le bon endroit pour grandir.</h1><p>Découvrez les entreprises présentes sur HireLoop.</p></div></div><div class="company-grid">${createCompanyCards(meta.companies)}</div></section>`;
}
// Configuration des colonnes et des champs pour chaque table.
const adminSchemas = {
  ads: {
    label: 'Offres',
    single: 'une offre',
    columns: [
      ['id', 'ID'],
      ['title', 'Titre'],
      ['company_id', 'Entreprise'],
      ['contract', 'Contrat'],
      ['location', 'Ville'],
    ],
    fields: [
      ['title', 'Titre'],
      ['company_id', 'Entreprise', 'companies'],
      ['category_id', 'Catégorie', 'categories'],
      ['contact_id', 'Contact recruteur', 'people'],
      ['summary', 'Résumé', 'textarea'],
      ['description', 'Description complète', 'textarea'],
      ['requirements', 'Profil recherché', 'textarea'],
      ['location', 'Ville'],
      ['contract', 'Contrat', ['CDI', 'CDD', 'Stage', 'Alternance', 'Freelance']],
      ['work_mode', 'Organisation', ['Hybride', 'Sur site', 'Télétravail']],
      ['salary_min', 'Salaire minimum annuel brut', 'number'],
      ['salary_max', 'Salaire maximum annuel brut', 'number'],
      ['working_time', 'Temps de travail'],
      [
        'featured',
        'Mise en avant',
        [
          {
            id: 0,
            name: 'Non',
          },
          {
            id: 1,
            name: 'Oui',
          },
        ],
      ],
    ],
  },
  companies: {
    label: 'Entreprises',
    single: 'une entreprise',
    columns: [
      ['id', 'ID'],
      ['name', 'Nom'],
      ['industry', 'Secteur'],
      ['location', 'Ville'],
    ],
    fields: [
      ['name', 'Nom'],
      ['industry', 'Secteur'],
      ['location', 'Ville'],
      ['website', 'Site internet', 'url'],
      ['color', 'Couleur', 'color'],
      ['description', 'Présentation', 'textarea'],
    ],
  },
  categories: {
    label: 'Catégories',
    single: 'une catégorie',
    columns: [
      ['id', 'ID'],
      ['name', 'Nom'],
    ],
    fields: [['name', 'Nom']],
  },
  people: {
    label: 'Personnes',
    single: 'une personne',
    columns: [
      ['id', 'ID'],
      ['name', 'Nom'],
      ['email', 'E-mail'],
      ['role', 'Rôle'],
      ['company_id', 'Entreprise'],
    ],
    fields: [
      ['name', 'Nom'],
      ['email', 'E-mail', 'email'],
      ['phone', 'Téléphone', 'tel'],
      [
        'role',
        'Rôle',
        [
          {
            id: 'candidate',
            name: roleNames.candidate,
          },
          {
            id: 'admin',
            name: roleNames.admin,
          },
          {
            id: 'company_admin',
            name: roleNames.company_admin,
          },
        ],
      ],
      ['company_id', 'Entreprise administrée', 'companies'],
      ['password', 'Mot de passe (facultatif)', 'password'],
    ],
  },
  applications: {
    label: 'Candidatures',
    single: 'une candidature',
    columns: [
      ['id', 'ID'],
      ['ad_id', 'Offre'],
      ['person_id', 'Compte candidat'],
      ['applicant_name', 'Nom complet'],
      ['applicant_email', 'E-mail de contact'],
      ['applicant_phone', 'Téléphone'],
      ['message', 'Message'],
      ['status', 'Statut'],
      ['created_at', 'Date'],
    ],
    fields: [
      ['ad_id', 'Offre', 'ads'],
      ['person_id', 'Personne', 'people'],
      ['message', 'Message', 'textarea'],
      ['status', 'Statut', ['Reçue', 'En cours', 'Entretien', 'Acceptée', 'Refusée']],
    ],
  },
};
const requiredFields = {
  ads: [
    'title',
    'company_id',
    'category_id',
    'contact_id',
    'summary',
    'description',
    'requirements',
    'location',
    'contract',
    'work_mode',
    'salary_min',
    'salary_max',
  ],
  companies: ['name', 'industry', 'location', 'description'],
  categories: ['name'],
  people: ['name', 'email'],
  applications: ['ad_id', 'person_id', 'message'],
};
let adminRefs = {};
// ADMINISTRATION : charger les références utilisées dans les listes déroulantes.
async function allRecords(resource) {
  // L'API renvoie au maximum 100 lignes : lire toutes les pages.
  let page = 1;
  const items = [];
  let total = 0;
  do {
    const result = await api('/admin/' + resource + '?page=' + page + '&limit=100');
    total = result.total;
    for (let i = 0; i < result.items.length; i++) {
      items.push(result.items[i]);
    }
    page++;
  } while (items.length < total);
  return {
    items: items,
  };
}
// ADMINISTRATION : vérifier le rôle et afficher les onglets autorisés.
async function renderAdmin() {
  if (!state.user) {
    location.hash = 'login';
    return;
  }
  if (!isAdmin()) {
    main.innerHTML =
      '<div class="page error-page"><h1>Un espace réservé.</h1><p>Seuls les administrateurs peuvent accéder à cette page.</p><a class="btn" href="#jobs">Revenir aux offres</a></div>';
    return;
  }
  if (companyAdmin() && !['ads', 'companies', 'applications'].includes(state.adminResource)) {
    state.adminResource = 'ads';
  }
  const stats = await api('/admin/stats');
  function createAdminStats(rows) {
    let html = '';
    for (let i = 0; i < rows.length; i++) {
      const entry3 = rows[i];
      const k = entry3[0];
      const label = entry3[1];
      html += `<div class="stat"><strong>${stats[k]}</strong><span>${label}</span></div>`;
    }
    return html;
  }
  const visibleTabs = [];
  for (const key in adminSchemas) {
    if (!companyAdmin() || key === 'ads' || key === 'companies' || key === 'applications') {
      visibleTabs.push([key, adminSchemas[key]]);
    }
  }
  function createAdminTabs(rows) {
    let html = '';
    for (let i = 0; i < rows.length; i++) {
      const entry5 = rows[i];
      const key = entry5[0];
      const s = entry5[1];
      html += `<button data-resource="${key}" class="${key === state.adminResource ? 'active' : ''}">${s.label}</button>`;
    }
    return html;
  }
  main.innerHTML = `<section class="page"><div class="page-head"><div><span class="eyebrow">${companyAdmin() ? 'Administration de mon entreprise' : 'Administration du projet'}</span><h1>Les rencontres, côté coulisses.</h1><p>${companyAdmin() ? 'Gérez votre entreprise, ses offres et les candidatures reçues.' : 'Gérez toutes les entreprises et attribuez les rôles depuis l’onglet Personnes.'}</p></div><a class="btn secondary" href="#account">Mon profil</a></div><div class="admin-stats">${createAdminStats(
    [
      ['ads', 'Offres publiées'],
      ['companies', 'Entreprises'],
      ['people', 'Personnes'],
      ['applications', 'Candidatures'],
    ],
  )}</div><nav class="admin-tabs" aria-label="Tables de la base de données">${createAdminTabs(visibleTabs)}</nav><div id="admin-content"></div></section>`;
  for (const b of document.querySelectorAll('[data-resource]')) {
    b.onclick = function () {
      state.adminResource = b.dataset.resource;
      state.adminPage = 1;
      renderAdmin();
    };
  }
  await loadAdmin();
}
// TABLEAU ADMINISTRATEUR : lignes, boutons et pagination.
async function loadAdmin() {
  const resource = state.adminResource;
  const schema = adminSchemas[resource];
  const results = await Promise.all([
    api('/admin/' + resource + '?page=' + state.adminPage + '&limit=8'),
    allRecords('companies'),
    allRecords('categories'),
    allRecords('people'),
    allRecords('ads'),
  ]);
  const data = results[0];
  const companies = results[1];
  const categories = results[2];
  const people = results[3];
  const ads = results[4];
  const adChoices = [];
  for (const ad of ads.items) {
    adChoices.push({
      id: ad.id,
      name: ad.title,
    });
  }
  adminRefs = {
    companies: companies.items,
    categories: categories.items,
    people: people.items,
    ads: adChoices,
  };
  function createTableHeadings(rows) {
    let html = '';
    for (let i = 0; i < rows.length; i++) {
      const entry6 = rows[i];
      const label = entry6[1];
      html += `<th scope="col">${label}</th>`;
    }
    return html;
  }
  function createTableRows(rows) {
    let html = '';
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      function createTableCells(rows) {
        let html = '';
        for (let i = 0; i < rows.length; i++) {
          const entry7 = rows[i];
          const key = entry7[0];
          let value = row[key];
          const ref = {
            company_id: 'companies',
            category_id: 'categories',
            contact_id: 'people',
            person_id: 'people',
            ad_id: 'ads',
          }[key];
          if (ref) {
            let record;
            if (adminRefs[ref]) {
              record = adminRefs[ref].find(function (r) {
                return r.id === value;
              });
            }
            if (record) {
              if (key === 'person_id') {
                value = `${record.name} · ${record.email}${record.phone ? ' · ' + record.phone : ''}`;
              } else {
                value = record.name;
              }
            } else {
              value = '#' + value;
            }
          }
          if (key === 'role') {
            value = roleNames[value] || value;
          }
          if (key === 'created_at') {
            value = date(value);
          }
          html += `<td><div class="cell" title="${esc(value)}">${key === 'status' ? `<span class="status">${esc(value)}</span>` : esc(value)}</div></td>`;
        }
        return html;
      }
      html += `<tr>${createTableCells(schema.columns)}<td><div class="row-actions"><button class="btn secondary small" data-edit="${row.id}">Modifier</button>${!companyAdmin() || resource === 'ads' ? `<button class="btn danger small" data-delete="${row.id}">Supprimer</button>` : ''}</div></td></tr>`;
    }
    return html;
  }
  $('#admin-content').innerHTML =
    `<div class="results-header"><div><h2>${schema.label}</h2><p>${data.total} enregistrement(s)</p></div>${!companyAdmin() || resource === 'ads' ? `<button class="btn small" id="create-record">+ Ajouter ${schema.single}</button>` : ''}</div><div id="admin-editor"></div><div id="delete-area"></div><div class="table-wrap"><table><thead><tr>${createTableHeadings(schema.columns)}<th scope="col">Actions</th></tr></thead><tbody>${createTableRows(data.items) || `<tr><td colspan="${schema.columns.length + 1}">Aucun enregistrement. Ajoutez le premier.</td></tr>`}</tbody></table></div>${pagination(data.total, data.page, data.limit, 'admin-page')}<p class="note admin-note">Les suppressions d’offres et de personnes effacent leurs candidatures associées. Une entreprise, une catégorie ou un contact lié à une offre ne peut pas être supprimé.</p>`;
  const createButton = $('#create-record');
  if (createButton) {
    createButton.addEventListener('click', function () {
      return editRecord(resource);
    });
  }
  for (const b of document.querySelectorAll('[data-edit]')) {
    b.onclick = function () {
      return editRecord(
        resource,
        data.items.find(function (r) {
          return r.id === Number(b.dataset.edit);
        }),
      );
    };
  }
  for (const b of document.querySelectorAll('[data-delete]')) {
    b.onclick = function () {
      return confirmDelete(resource, Number(b.dataset.delete));
    };
  }
  for (const b of document.querySelectorAll('[data-admin-page]')) {
    b.onclick = function () {
      state.adminPage = Number(b.dataset.adminPage);
      loadAdmin();
    };
  }
}
// ÉDITEUR : créer ou modifier un enregistrement.
function editRecord(resource, row = {}) { //construire le formulaire d’ajout ou de modification
  const schema = adminSchemas[resource];
  const editing = !!row.id;
  const visibleFields = [];
  for (const field of schema.fields) {
    const key = field[0];
    if (companyAdmin()) {
      if (resource === 'applications' && key !== 'status') {
        continue;
      }
      if (resource === 'ads' && (key === 'company_id' || key === 'contact_id')) {
        continue;
      }
    }
    visibleFields.push(field);
  }
  function createEditorFields(rows) { // construire les champs du formulaire
    let html = '';
    for (let i = 0; i < rows.length; i++) {
      const entry9 = rows[i];
      const key = entry9[0];
      const label = entry9[1];
      let type = entry9[2];
      if (type === undefined) {
        type = 'text';
      }
      const defaultValues = {
        color: '#355d50',
        working_time: 'Temps plein',
        featured: 0,
        role: 'candidate',
        status: 'Reçue',
      };
      let value = row[key];
      if (value === null || value === undefined) {
        value = defaultValues[key];
      }
      if (value === null || value === undefined) {
        value = '';
      }
      const required = requiredFields[resource].includes(key);
      let choices;
      if (Array.isArray(type)) {
        choices = type;
      } else {
        choices = adminRefs[type];
      }
      let fieldHtml;
      if (choices) {
        fieldHtml = `<select name="${key}" ${required ? 'required' : ''}>${options(choices, value, 'Choisir')}</select>`;
      } else {
        if (type === 'textarea') {
          fieldHtml = `<textarea name="${key}" ${required ? 'required' : ''} maxlength="12000">${esc(value)}</textarea>`;
        } else {
          fieldHtml = `<input name="${key}" type="${type}" value="${esc(value)}" ${required ? 'required' : ''} ${type === 'number' ? 'min="0" step="1"' : ''} ${type === 'password' ? 'minlength="10" autocomplete="new-password"' : ''}>`;
        }
      }
      html += `<label class="field ${type === 'textarea' ? 'wide' : ''}">${esc(label)}${required ? ' *' : ''}${fieldHtml}</label>`;
    }
    return html;
  }
  $('#admin-editor').innerHTML =
    `<section class="panel admin-editor"><h3>${editing ? 'Modifier' : 'Ajouter'} ${schema.single}${editing ? ' #' + row.id : ''}</h3><form id="admin-form">${companyAdmin() && resource === 'applications' ? `<p class="prose">${esc(row.message)}</p>` : ''}<div class="form-grid">${createEditorFields(visibleFields)}</div><p class="form-error" role="alert" hidden></p><div class="form-actions"><button class="btn" type="submit">${editing ? 'Enregistrer les modifications' : 'Créer l’enregistrement'} ↗</button><button class="btn secondary" type="button" id="cancel-edit">Annuler</button></div></form></section>`;
  if (resource === 'people') {
    const role = $('[name="role"]', $('#admin-form'));
    const company = $('[name="company_id"]', $('#admin-form'));
    const help = document.createElement('small');
    help.id = 'company-role-help';
    help.className = 'note';
    help.textContent =
      'Choisir une entreprise attribue le rôle Administrateur d’entreprise. Pour conserver un administrateur du projet, créez ou modifiez un autre compte.';
    company.setAttribute('aria-describedby', help.id);
    company.parentElement.append(help);
    const syncCompany = function () {
      company.required = role.value === 'company_admin';
      if (!company.required) {
        company.value = '';
      }
    };
    company.addEventListener('change', function () {
      if (company.value) {
        role.value = 'company_admin';
      }
      syncCompany();
    });
    role.addEventListener('change', syncCompany);
    syncCompany();
  }
  $('#cancel-edit').onclick = function () {
    return ($('#admin-editor').innerHTML = '');
  };
  $('#admin-form').onsubmit = async function (e) {
    e.preventDefault();
    await submit(e.currentTarget, async function (data) {
      if (!data.password) {
        delete data.password;
      }
      if (resource === 'ads' && companyAdmin()) {
        data.company_id = state.user.company_id;
        data.contact_id = state.user.id;
      }
      await api('/' + resource + (editing ? '/' + row.id : ''), editing ? 'PATCH' : 'POST', data);
      toast(editing ? 'Modifications enregistrées.' : 'Enregistrement créé.');
      state.meta = null;
      const result = await api('/auth/me');
      state.user = result.user;
      updateNav();
      await renderAdmin();
    });
  };
  $('#admin-editor').scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  });
  const firstEditorField = $('input,select', $('#admin-editor'));
  if (firstEditorField) {
    firstEditorField.focus({
      preventScroll: true,
    });
  }
}
// SUPPRESSION : attendre le clic de confirmation.
function confirmDelete(resource, id) {
  $('#delete-area').innerHTML =
    `<div class="delete-confirm" role="alert"><p>Supprimer l’enregistrement #${id} de « ${adminSchemas[resource].label} » ? ${['ads', 'people'].includes(resource) ? 'Ses candidatures associées seront aussi supprimées.' : ''} Cette action est définitive.</p><div class="row-actions"><button class="btn danger small" id="confirm-delete">Confirmer la suppression</button><button class="btn secondary small" id="cancel-delete">Annuler</button></div><p class="form-error" hidden></p></div>`;
  $('#cancel-delete').onclick = function () {
    return ($('#delete-area').innerHTML = '');
  };
  $('#confirm-delete').onclick = async function (e) {
    e.target.disabled = true;
    try {
      await api(`/${resource}/${id}`, 'DELETE');
      state.meta = null;
      toast('Enregistrement supprimé.');
      state.adminPage = 1;
      await renderAdmin();
    } catch (error) {
      const field = $('.form-error', $('#delete-area'));
      field.textContent = error.message;
      field.hidden = false;
      e.target.disabled = false;
    }
  };
  $('#delete-area').scrollIntoView({
    behavior: 'smooth',
    block: 'center',
  });
}
// ROUTAGE : choisir la page à partir du texte après # dans l’URL.
async function route() { // choisir l’écran à afficher
  routeSequence++;
  const sequence = routeSequence;
  const parts = (location.hash.slice(1) || 'jobs').split('/');
  const page = parts[0];
  if (page !== 'login' && page !== 'register') {
    state.afterAuth = null;
  }
  for (const a of document.querySelectorAll('[data-nav]')) {
    a.classList.toggle(
      'active',
      a.dataset.nav === page ||
      (a.dataset.nav === 'jobs' && page === 'job') ||
      (a.dataset.nav === 'companies' && page === 'company'),
    );
  }
  main.innerHTML = '<div class="loading">Un instant, votre prochaine rencontre se prépare…</div>';
  window.scrollTo(0, 0);
  document.title =
    ({
      jobs: 'Les offres',
      job: 'Détail de l’offre',
      companies: 'Les entreprises',
      company: 'Entreprise',
      login: 'Connexion',
      register: 'Créer un compte',
      account: 'Mon profil',
      applications: 'Mes candidatures',
      admin: 'Administration',
    }[page] || 'Bienvenue') + ' · HireLoop';
  try {
    if (page === 'jobs') {
      await renderJobs();
    } else if (page === 'job' && /^\d+$/.test(parts[1])) {
      await renderJob(parts[1], parts[2] === 'apply');
    } else if (page === 'login') {
      renderAuth(false);
    } else if (page === 'register') {
      renderAuth(true);
    } else if (page === 'account') {
      await renderAccount();
    } else if (page === 'applications') {
      await renderApplications();
    } else if (page === 'companies') {
      await renderCompanies();
    } else if (page === 'company' && /^\d+$/.test(parts[1])) {
      await renderCompanies(parts[1]);
    } else if (page === 'admin') {
      await renderAdmin();
    } else {
      main.innerHTML =
        '<div class="page error-page"><h1>Cette page a pris un autre chemin.</h1><a class="btn" href="#jobs">Revenir aux offres</a></div>';
    }
  } catch (e) {
    if (sequence !== routeSequence) {
      return;
    }
    main.innerHTML = `<div class="page">${errorBox(e)}</div>`;
    $('[data-retry]').onclick = route;
  }
}
window.addEventListener('hashchange', route);
// DÉMARRAGE : retrouver la session, mettre à jour le menu et ouvrir la page.
async function startApp() {
  try {
    state.user = (await api('/auth/me')).user;
    updateNav();
    await route();
  } catch (e) {
    main.innerHTML = errorBox(e);
    $('[data-retry]').onclick = function () {
      return location.reload();
    };
  }
}
startApp();
