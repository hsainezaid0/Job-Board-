const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync('public/i18n.js', 'utf8');

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
  assert.equal(setup().run('translate("Les offres")'), 'Les offres');
  assert.equal(setup('en').run('translate("Les offres")'), 'Jobs');
  assert.equal(setup('invalid').root.lang, 'fr');
  assert.equal(setup(null, true).root.lang, 'fr');
});

test('dynamic messages, titles, dates and validation', () => {
  const { run } = setup('en');
  assert.equal(run('translate("1 opportunité pour écrire la suite")'), '1 opportunity for your next chapter');
  assert.equal(run('translate("12 opportunités pour écrire la suite")'), '12 opportunities for your next chapter');
  assert.equal(run('translate("Mes candidatures · HireLoop")'), 'My applications · HireLoop');
  assert.equal(run('translate("+ Ajouter une offre")'), '+ Add a job');
  assert.equal(run('translate("Champ obligatoire : email.")'), 'Required field: email.');
  assert.equal(run('translate(localizedDate("2026-02-05"))'), '5 Feb 2026');
  assert.equal(run('translate("Studio North")'), 'Studio North');
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
  context.node = { nodeType: 3, nodeValue: 'Les offres', parentElement: { closest: () => true } };
  run('localize(node)');
  assert.equal(context.node.nodeValue, 'Les offres');
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
