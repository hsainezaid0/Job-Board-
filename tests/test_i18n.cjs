const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '..', 'public', 'i18n.js'), 'utf8');

function setup(saved = null, blocked = false) {
  const root = { nodeType: 1, matches: () => false, hasAttribute: () => false, childNodes: [] };
  const context = vm.createContext({
    Node: { TEXT_NODE: 3, ELEMENT_NODE: 1 },
    document: { documentElement: root, querySelectorAll: () => [], addEventListener() {} },
    localStorage: { getItem() { if (blocked) throw Error('Blocked'); return saved; } },
    MutationObserver: class { observe() {} },
  });
  vm.runInContext(source, context);
  return { context, root, run: code => vm.runInContext(code, context) };
}

test('French default, saved English, and unavailable storage', () => {
  assert.equal(setup().run('translate("Offres")'), 'Offres');
  assert.equal(setup('en').run('translate("Offres")'), 'Jobs');
  assert.equal(setup('invalid').root.lang, 'fr');
  assert.equal(setup(null, true).root.lang, 'fr');
});

test('templates, titles, dates and validation messages', () => {
  const { run } = setup('en');
  assert.equal(run('translate("il y a 3 jours")'), '3 days ago');
  assert.equal(run('translate("hier")'), 'yesterday');
  assert.equal(run('translate("Mes candidatures · HireLoop")'), 'My applications · HireLoop');
  assert.equal(run('translate("Statut mis à jour : Entretien")'), 'Status updated: Interview');
  assert.equal(run('translate("Champ obligatoire : email.")'), 'Required field: email.');
  assert.equal(run('translate("40 k€ brut / an")'), '40k€ gross / year');
  assert.equal(run('translate(localizedDate("2026-02-05"))'), '5 Feb 2026');
  assert.equal(run('translate("Studio North")'), 'Studio North');
  // Surrounding whitespace is preserved around translated text.
  assert.equal(run('translate(" postes ouverts dans ")'), ' open positions at ');
});

test('every catalogue line has a French and an English side', () => {
  const lines = source.split('`')[1].split('\n');
  for (const line of lines) {
    const parts = line.split('|');
    assert.equal(parts.length, 2, `Malformed line: ${line}`);
    assert.ok(parts[0].trim() && parts[1].trim(), `Empty side: ${line}`);
  }
  const keys = lines.map(l => l.split('|')[0]);
  assert.equal(new Set(keys).size, keys.length, 'Duplicate French keys');
});

test('switching is lossless and handles newly updated text', () => {
  const { context, run } = setup('en');
  context.node = { nodeType: 3, nodeValue: '  Se connecter ', parentElement: { closest: () => false } };
  run('localize(node)');
  assert.equal(context.node.nodeValue, '  Sign in ');
  run('localize(node); language = "fr"; localize(node)');
  assert.equal(context.node.nodeValue, '  Se connecter ');
  context.node.nodeValue = 'Créer un compte';
  run('language = "en"; localize(node)');
  assert.equal(context.node.nodeValue, 'Create an account');
});

test('recruiter copy and textarea drafts are excluded', () => {
  const { context, run } = setup('en');
  context.node = { nodeType: 3, nodeValue: 'Offres', parentElement: { closest: () => true } };
  run('localize(node)');
  assert.equal(context.node.nodeValue, 'Offres');
});

test('accessible attributes are translated without changing input values', () => {
  const { context, run } = setup('en');
  const attributes = { placeholder: 'Ville', 'aria-label': 'Ville', value: 'Paris' };
  context.node = {
    nodeType: 1, matches: () => false, childNodes: [],
    hasAttribute: key => key in attributes, getAttribute: key => attributes[key],
    setAttribute: (key, value) => { attributes[key] = value; },
  };
  run('localize(node)');
  assert.equal(attributes.placeholder, 'City');
  assert.equal(attributes['aria-label'], 'City');
  assert.equal(attributes.value, 'Paris');
  run('language = "fr"; localize(node)');
  assert.equal(attributes.placeholder, 'Ville');
});
