// Sign-in, registration and the candidate space (applications, saved jobs, profile, security).
import {
  $, $$, main, state, api, esc, icon, logo, avatar, date, relative, statusBadge, emptyState,
  submitForm, toast, confirmDialog, setTitle, isCandidate, isStaff, refreshSession, ROLE, STATUS,
} from './core.js';
import { jobRow, bindSaveButtons } from './jobs.js';

const DEMO = [
  ['Candidat', 'camille@hireloop.test', 'Camille2026!'],
  ['Recruteur', 'company@test.com', 'Company123!'],
  ['Administrateur', 'admin@hireloop.test', 'Admin2026!'],
];

const passwordField = (name, label, autocomplete, extra = '') => `<label class="field"><span>${label}</span>
  <span class="password"><input type="password" name="${name}" autocomplete="${autocomplete}" maxlength="200" ${extra}>
  <button type="button" class="icon-btn" data-reveal aria-label="Afficher le mot de passe" title="Afficher le mot de passe">${icon('eye')}</button></span></label>`;

function bindReveal(root) {
  for (const button of $$('[data-reveal]', root)) {
    button.onclick = () => {
      const input = button.previousElementSibling;
      const shown = input.type === 'text';
      input.type = shown ? 'password' : 'text';
      const label = shown ? 'Afficher le mot de passe' : 'Masquer le mot de passe';
      button.setAttribute('aria-label', label);
      button.setAttribute('title', label);
    };
  }
}

// ---------------------------------------------------------------- sign in / register
export function renderAuth(register, onSignedIn) {
  setTitle(register ? 'Créer un compte' : 'Connexion');
  main.innerHTML = `<div class="container auth">
    <section class="auth-card card">
      <h1>${register ? 'Créer un compte candidat' : 'Connexion'}</h1>
      <p class="muted">${register ? 'Un compte suffit pour postuler à toutes les offres et suivre vos candidatures.' : 'Accédez à vos candidatures ou à votre espace recruteur.'}</p>
      <form id="auth-form" novalidate>
        ${register ? '<label class="field"><span>Nom complet</span><input name="name" autocomplete="name" required maxlength="160"></label>' : ''}
        <label class="field"><span>Adresse e-mail</span><input type="email" name="email" required autocomplete="email" maxlength="254"></label>
        ${register ? '<label class="field"><span>Téléphone <em>facultatif</em></span><input type="tel" name="phone" autocomplete="tel" maxlength="40"></label>' : ''}
        ${passwordField('password', 'Mot de passe', register ? 'new-password' : 'current-password', `required ${register ? 'minlength="10"' : ''}`)}
        ${register ? '<p class="hint" id="password-hint">10 caractères minimum.</p>' : ''}
        <p class="form-error" role="alert" hidden></p>
        <button class="btn full" type="submit">${register ? 'Créer mon compte' : 'Se connecter'}</button>
      </form>
      <p class="auth-switch">${register ? 'Vous avez déjà un compte ? <a href="#login">Se connecter</a>' : 'Pas encore de compte ? <a href="#register">Créer un compte</a>'}</p>
      ${register ? '<p class="hint">Vous recrutez ? Les comptes recruteurs sont créés par l’administrateur de la plateforme.</p>' : `
      <div class="demo">
        <p><strong>Comptes de démonstration</strong></p>
        <ul>${DEMO.map(([role, email, password]) => `<li><span><strong>${role}</strong><small translate="no">${email}</small></span><button type="button" class="btn small secondary" data-email="${email}" data-password="${password}">Utiliser</button></li>`).join('')}</ul>
      </div>`}
    </section>
    <aside class="auth-side">
      <h2>Avec un compte, vous pouvez :</h2>
      <ul class="checklist">
        <li>${icon('check')}<span>postuler en un clic, sans ressaisir vos coordonnées ;</span></li>
        <li>${icon('check')}<span>suivre l’avancement de chaque candidature ;</span></li>
        <li>${icon('check')}<span>sauvegarder des offres pour y revenir plus tard.</span></li>
      </ul>
    </aside>
  </div>`;
  const form = $('#auth-form');
  bindReveal(form);
  for (const button of $$('[data-email]')) {
    button.onclick = () => {
      form.email.value = button.dataset.email;
      form.password.value = button.dataset.password;
      form.requestSubmit();
    };
  }
  if (register) {
    form.password.addEventListener('input', () => {
      const n = form.password.value.length;
      const hint = $('#password-hint');
      hint.textContent = n >= 10 ? 'Longueur suffisante.' : '10 caractères minimum.';
      hint.classList.toggle('ok', n >= 10);
    });
  }
  form.onsubmit = e => {
    e.preventDefault();
    submitForm(form, async data => {
      if (!data.email || !data.password || (register && !data.name)) throw new Error('Remplissez les champs obligatoires.');
      await api('/auth/' + (register ? 'register' : 'login'), 'POST', data);
      await refreshSession();
      onSignedIn();
      if (isStaff()) location.hash = 'admin';
      else location.hash = state.afterAuth || 'jobs';
      toast(register ? 'Votre compte est créé. Bienvenue !' : `Bonjour ${state.user.name.split(' ')[0]} !`, { type: 'success' });
    });
  };
  form.querySelector('input').focus();
}

// ---------------------------------------------------------------- candidate space
const TABS = [
  ['applications', 'Candidatures', 'inbox'],
  ['saved', 'Offres sauvegardées', 'bookmark'],
  ['account', 'Profil', 'user'],
  ['security', 'Sécurité', 'lock'],
];

function completion(user) {
  const fields = ['name', 'email', 'phone', 'headline', 'location', 'bio'];
  return Math.round(fields.filter(f => (user[f] || '').trim()).length / fields.length * 100);
}

export async function renderSpace(tab, onChange) {
  if (!state.user) { state.afterAuth = tab === 'account' ? 'account' : tab; location.hash = 'login'; return; }
  if (!isCandidate() && (tab === 'applications' || tab === 'saved')) tab = 'account';
  const user = state.user;
  const tabs = TABS.filter(([key]) => isCandidate() || key === 'account' || key === 'security');
  setTitle(Object.fromEntries(tabs.map(([k, l]) => [k, l]))[tab]);
  const score = completion(user);
  main.innerHTML = `<div class="container page space">
    <header class="space-head">
      ${avatar(user.name, 'lg')}
      <div><h1 translate="no">${esc(user.name)}</h1><p>${user.headline ? `<span translate="no">${esc(user.headline)}</span>` : `<span class="muted">${ROLE[user.role]}</span>`}</p></div>
      ${isCandidate() ? `<div class="completion" title="Un profil complet aide les recruteurs à vous répondre."><span><span>Profil complété à</span> <strong>${score} %</strong></span><span class="meter"><span style="width:${score}%"></span></span></div>` : `<a class="btn secondary" href="#admin">${icon('grid')}<span>Espace recruteur</span></a>`}
    </header>
    <nav class="tabs" aria-label="Mon espace">${tabs.map(([key, label, iconName]) => `<a href="#${key}" class="${key === tab ? 'active' : ''}" ${key === tab ? 'aria-current="page"' : ''}>${icon(iconName)}<span>${label}</span>${key === 'applications' && state.updates ? `<span class="pill">${state.updates}</span>` : ''}${key === 'saved' && state.saved.size ? `<span class="count">${state.saved.size}</span>` : ''}</a>`).join('')}</nav>
    <section id="space-content"></section>
  </div>`;
  const box = $('#space-content');
  if (tab === 'applications') await renderApplications(box, onChange);
  else if (tab === 'saved') await renderSaved(box);
  else if (tab === 'security') renderSecurity(box, onChange);
  else renderProfile(box, onChange);
}

const STEPS = ['Reçue', 'En cours', 'Entretien'];
// Steps are marked done only if the application really went through them.
function stepper(status, events) {
  const final = status === 'Acceptée' || status === 'Refusée';
  const reached = new Set(events.map(e => e.status));
  const current = final ? 3 : STEPS.indexOf(status);
  const labels = [...STEPS, final ? status : 'Réponse'];
  return `<ol class="stepper ${status === 'Refusée' ? 'is-rejected' : ''} ${status === 'Acceptée' ? 'is-accepted' : ''}">${labels.map((label, i) => {
    const state = i === current ? 'current' : i < current && reached.has(label) ? 'done' : i < current ? 'skipped' : '';
    return `<li class="${state}"><span class="step-dot"></span><span>${esc(label)}</span></li>`;
  }).join('')}</ol>`;
}

async function renderApplications(box, onChange) {
  const { items } = await api('/my-applications');
  if (!items.length) {
    box.innerHTML = emptyState({ iconName: 'inbox', title: 'Vous n’avez pas encore postulé.', text: 'Quand vous enverrez une candidature, vous suivrez ici chaque étape.', action: '<a class="btn" href="#jobs">Parcourir les offres</a>' });
    return;
  }
  const active = items.filter(a => !['Acceptée', 'Refusée'].includes(a.status)).length;
  box.innerHTML = `<div class="segmented" role="group" aria-label="Filtrer les candidatures">
      <button type="button" data-filter="all" class="active"><span>Toutes</span> <span class="count">${items.length}</span></button>
      <button type="button" data-filter="active"><span>En cours</span> <span class="count">${active}</span></button>
      <button type="button" data-filter="done"><span>Terminées</span> <span class="count">${items.length - active}</span></button></div>
    <div class="app-list">${items.map(applicationCard).join('')}</div>`;
  for (const button of $$('[data-filter]', box)) {
    button.onclick = () => {
      for (const b of $$('[data-filter]', box)) b.classList.toggle('active', b === button);
      for (const card of $$('.app-card', box)) {
        const done = card.dataset.final === '1';
        card.hidden = button.dataset.filter === 'active' ? done : button.dataset.filter === 'done' ? !done : false;
      }
    };
  }
  for (const button of $$('[data-withdraw]', box)) {
    button.onclick = async () => {
      const ok = await confirmDialog({ title: 'Retirer cette candidature ?', body: 'Le recruteur ne la verra plus. Vous pourrez postuler à nouveau plus tard.', confirm: 'Retirer', danger: true });
      if (!ok) return;
      try {
        await api('/my-applications/' + button.dataset.withdraw, 'DELETE');
        toast('Candidature retirée.');
        renderApplications(box, onChange);
      } catch (e) { toast(e.message, { type: 'error' }); }
    };
  }
  // The "updated" pills stay visible for this visit, then the badge in the header is cleared.
  if (state.updates) {
    api('/my-applications/seen', 'POST', {}).then(() => { state.updates = 0; onChange(); }).catch(() => {});
  }
}

function applicationCard(a) {
  const final = a.status === 'Acceptée' || a.status === 'Refusée';
  return `<article class="app-card card" data-final="${final ? 1 : 0}">
    <header>
      ${logo(a.company_name, a.company_color)}
      <div class="app-title"><h3><a href="#job/${a.ad_id}" translate="no">${esc(a.title)}</a></h3>
        <p><span translate="no">${esc(a.company_name)}</span> · ${esc(a.location)} · <span>Envoyée le</span> ${date(a.created_at)}</p></div>
      <div class="app-status">${a.updated ? '<span class="pill">Nouveau</span>' : ''}${statusBadge(a.status)}</div>
    </header>
    ${stepper(a.status, a.events)}
    ${a.ad_status === 'closed' && !final ? '<p class="hint">L’offre est désormais fermée, mais votre candidature reste visible par le recruteur.</p>' : ''}
    <details><summary>Historique et message</summary>
      <ol class="timeline">${a.events.slice().reverse().map(e => `<li><span class="timeline-dot status-${STATUS[e.status]}"></span><span>${esc(e.status)}</span><time>${date(e.created_at)}</time></li>`).join('')}</ol>
      <blockquote translate="no">${esc(a.message)}</blockquote>
    </details>
    <footer>${final ? '' : `<button type="button" class="link danger" data-withdraw="${a.id}">Retirer ma candidature</button>`}<a class="link" href="#job/${a.ad_id}">Voir l’offre</a></footer>
  </article>`;
}

async function renderSaved(box) {
  const { items } = await api('/saved');
  const draw = list => {
    box.innerHTML = list.length
      ? `<ul class="job-list">${list.map(j => jobRow(j)).join('')}</ul>`
      : emptyState({ iconName: 'bookmark', title: 'Aucune offre sauvegardée.', text: 'Utilisez l’icône signet sur une offre pour la retrouver ici.', action: '<a class="btn" href="#jobs">Parcourir les offres</a>' });
    bindSaveButtons(box);
  };
  draw(items);
  const onChange = e => {
    if (!box.isConnected) { document.removeEventListener('saved-change', onChange); return; }
    const index = items.findIndex(j => j.id === e.detail.id);
    if (!e.detail.saved && index >= 0) { items.splice(index, 1); draw(items); }
  };
  document.addEventListener('saved-change', onChange);
}

function renderProfile(box, onChange) {
  const user = state.user;
  box.innerHTML = `<form id="profile-form" class="card form-card" novalidate>
    <div class="form-section"><div class="form-section-head"><h2>Coordonnées</h2><p>Transmises au recruteur avec chaque candidature.</p></div>
      <div class="form-grid">
        <label class="field"><span>Nom complet</span><input name="name" required maxlength="160" value="${esc(user.name)}" autocomplete="name"></label>
        <label class="field"><span>Adresse e-mail</span><input type="email" name="email" required maxlength="254" value="${esc(user.email)}" autocomplete="email"></label>
        <label class="field"><span>Téléphone</span><input type="tel" name="phone" maxlength="40" value="${esc(user.phone)}" autocomplete="tel"></label>
        <label class="field"><span>Ville</span><input name="location" maxlength="120" value="${esc(user.location)}" autocomplete="address-level2"></label>
        <div class="field wide" id="email-password" hidden>${passwordField('current_password', 'Mot de passe actuel (requis pour changer d’e-mail)', 'current-password')}</div>
      </div></div>
    <div class="form-section"><div class="form-section-head"><h2>Présentation</h2><p>Ce que le recruteur voit en premier.</p></div>
      <div class="form-grid">
        <label class="field wide"><span>Titre</span><input name="headline" maxlength="160" value="${esc(user.headline)}" placeholder="Ex. : Développeuse front-end, 3 ans d’expérience"></label>
        <label class="field wide"><span>Portfolio ou profil en ligne</span><input type="url" name="website" maxlength="300" value="${esc(user.website)}" placeholder="https://"></label>
        <label class="field wide"><span>À propos</span><textarea name="bio" rows="5" maxlength="2000" placeholder="Votre parcours en quelques phrases.">${esc(user.bio)}</textarea></label>
      </div></div>
    <p class="form-error" role="alert" hidden></p>
    <div class="form-footer"><button class="btn" type="submit">Enregistrer</button></div>
  </form>`;
  const form = $('#profile-form');
  bindReveal(form);
  form.email.addEventListener('input', () => { $('#email-password').hidden = form.email.value.trim().toLowerCase() === user.email.toLowerCase(); });
  form.onsubmit = e => {
    e.preventDefault();
    submitForm(form, async data => {
      if (!data.current_password) delete data.current_password;
      const result = await api('/account', 'PATCH', data);
      state.user = result.user;
      onChange();
      toast('Profil enregistré.', { type: 'success' });
      renderSpace('account', onChange);
    });
  };
}

function renderSecurity(box, onChange) {
  const user = state.user;
  box.innerHTML = `<form id="password-form" class="card form-card" novalidate>
      <div class="form-section"><div class="form-section-head"><h2>Mot de passe</h2><p>Changer de mot de passe déconnecte vos autres appareils.</p></div>
        <div class="form-grid">
          ${passwordField('current_password', 'Mot de passe actuel', 'current-password', 'required')}
          <span></span>
          ${passwordField('password', 'Nouveau mot de passe', 'new-password', 'required minlength="10"')}
          ${passwordField('confirm', 'Confirmer le nouveau mot de passe', 'new-password', 'required minlength="10"')}
        </div></div>
      <p class="form-error" role="alert" hidden></p>
      <div class="form-footer"><button class="btn" type="submit">Changer le mot de passe</button></div>
    </form>
    <section class="card danger-zone">
      <div><h2>Supprimer mon compte</h2><p>Votre profil, vos candidatures et vos offres sauvegardées seront effacés définitivement.</p></div>
      <button type="button" class="btn danger" id="delete-account">Supprimer mon compte</button>
    </section>
    <p class="hint"><span>Dernière connexion :</span> ${user.last_login_at ? `<span>${date(user.last_login_at)}</span> (<span>${relative(user.last_login_at)}</span>)` : '—'} · <span>Compte créé le</span> <span>${date(user.created_at)}</span></p>`;
  const form = $('#password-form');
  bindReveal(form);
  form.onsubmit = e => {
    e.preventDefault();
    submitForm(form, async data => {
      if (data.password.length < 10) throw new Error('Le mot de passe doit contenir au moins 10 caractères.');
      if (data.password !== data.confirm) throw new Error('Les deux mots de passe ne correspondent pas.');
      await api('/account', 'PATCH', { current_password: data.current_password, password: data.password });
      form.reset();
      toast('Mot de passe modifié.', { type: 'success' });
    });
  };
  $('#delete-account').onclick = async () => {
    const result = await confirmDialog({
      title: 'Supprimer votre compte ?', body: 'Cette action est définitive. Saisissez votre mot de passe pour confirmer.',
      confirm: 'Supprimer définitivement', danger: true,
      fields: `<label class="field"><span>Mot de passe</span><input type="password" name="current_password" required autocomplete="current-password"></label>`,
    });
    if (!result) return;
    try {
      await api('/account', 'DELETE', { current_password: result.current_password });
      state.user = null; state.saved = new Set(); state.updates = 0;
      onChange();
      location.hash = 'jobs';
      toast('Votre compte a été supprimé.');
    } catch (e) { toast(e.message, { type: 'error' }); }
  };
}
