(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else { root.DInspector = api; api.start(); }
})(typeof globalThis === 'undefined' ? this : globalThis, function() {
  'use strict';
  const GOALS = ['bulk', 'cut', 'budget'];
  const PROFILES = ['all', 'vegan', 'vegetarian', 'no_pork', 'no_beef', 'no_pork_beef'];
  const percent = value => (value * 100).toFixed(1) + '%';

  function displayPlate(p) {
    const t = p.total;
    return {id: p.candidate_id, items: p.items, price: t.price_eur, kcal: t.kcal,
      protein: t.protein_g, fat_g: t.fat_g, carbs_g: t.carbs_g, weight_g: t.weight_g,
      dish_count: p.items.length, fat_energy_pct: t.kcal ? 9 * t.fat_g / t.kcal * 100 : 0,
      meat_dish_weight_g: p.items.filter(i => (i.meat_types || []).some(x => !['unknown', 'fish'].includes(x))).reduce((s, i) => s + i.weight_g, 0),
      unknown_diet_weight_g: p.items.filter(i => (i.meat_types || []).includes('unknown')).reduce((s, i) => s + i.weight_g, 0),
      has_estimated_prices: p.has_estimated_prices};
  }

  function decisionText(row) {
    return row.decision === 'selected' ? 'Selected' :
      `Skipped · ${percent(row.similarity.total)} similar to pick at rank #${row.closest_selected_rank}`;
  }

  function validateDay(data) {
    if (!data || !/^\d{4}-\d{2}-\d{2}$/.test(data.date) || !data.variants || !data.settings) throw Error('Invalid D ranking data.');
    for (const v of Object.values(data.variants)) {
      if (!Array.isArray(v.plates) || !Array.isArray(v.walk) || v.plates.length > 5 || v.pool_count > 100 || v.walk.length > v.pool_count) throw Error('Invalid D selections.');
      const accepted = v.walk.filter(r => r.decision === 'selected').map(r => r.preference_rank);
      if (accepted.length !== v.plates.length || v.walk.some((r, i) => r.preference_rank !== i + 1 || !['selected', 'skipped'].includes(r.decision)) ||
          v.plates.some((p, i) => p.preference_rank !== accepted[i])) throw Error('Invalid D ranking walk.');
    }
    return data;
  }

  function start() {
    const $ = id => document.getElementById(id), query = new URLSearchParams(location.search);
    const element = (tag, cls, text) => {
      const el = document.createElement(tag);
      if (cls) el.className = cls;
      if (text !== undefined) el.textContent = text;
      return el;
    };
    let index, data, requestId = 0;
    $('goal').value = GOALS.includes(query.get('goal')) ? query.get('goal') : 'bulk';
    $('profile').value = PROFILES.includes(query.get('profile')) ? query.get('profile') : 'all';

    function render() {
      if (!data) return;
      const v = data.variants[$('goal').value + '_' + $('profile').value];
      if (!v) throw Error('This context has not been generated.');
      const cards = v.plates.map(p => {
        const card = BulkPlateCard.render(displayPlate(p), p.candidate_id, () => {});
        card.removeAttribute('role'); card.removeAttribute('tabindex'); card.removeAttribute('aria-label');
        card.dataset.picked = 'true';
        card.querySelector('h2').textContent = `Preference #${p.preference_rank}`;
        for (const [group, label] of [['core', 'Core'], ['accompaniment', 'Accompaniments']]) {
          const names = p.diversity.components.filter(i => i.group === group).map(i => i.name);
          card.append(element('p', 'component-note', `${label}: ${names.join(' + ') || 'None'}`));
        }
        card.append(element('p', 'selection-note', p.reason));
        card.append(element('p', 'candidate-score', `Preference score ${p.score.total.toFixed(3)}`));
        return card;
      });
      $('candidates').replaceChildren(...(cards.length ? cards : [element('p', 'empty', v.message || 'No eligible combinations.')]));
      $('candidates').setAttribute('aria-busy', 'false');
      $('selected-count').textContent = String(v.plates.length);
      $('status').textContent = v.state === 'ready' ? `${v.plates.length} distinct picks from ${v.pool_count} eligible ranked combinations. ${v.message || ''}`.trim() : v.message;
      $('walk-count').textContent = `${v.scanned_count} combinations examined in rank order; ${v.walk.filter(r => r.decision === 'skipped').length} lookalikes skipped.`;
      $('walk').replaceChildren(...v.walk.map(row => {
        const tr = element('tr'), title = element('td', '', row.title), decision = element('td', '', decisionText(row));
        title.append(element('small', '', `Preference score ${row.score.toFixed(3)}`));
        if (row.similarity) decision.append(element('small', '', `Core ${percent(row.similarity.core)} · accompaniments ${percent(row.similarity.accompaniment)}`));
        tr.append(element('td', '', String(row.preference_rank)), title, decision);
        return tr;
      }));
      $('walk-details').hidden = !v.walk.length;
      const params = new URLSearchParams({date: data.date, goal: $('goal').value, profile: $('profile').value});
      history.replaceState(null, '', '?' + params);
      const menu = new URL('../../menu.html', document.baseURI);
      menu.search = new URLSearchParams({...Object.fromEntries(params), campus: 'arcisstr', method: 'd'});
      $('menu-link').href = menu.href; $('menu-link').hidden = false;
    }

    async function load() {
      const id = ++requestId; data = null;
      $('candidates').setAttribute('aria-busy', 'true'); $('status').textContent = 'Loading D’s selections…';
      try {
        const day = index.days.find(d => d.date === $('date').value);
        if (!day || !/^\d{4}-\d{2}-\d{2}\.json$/.test(day.file)) throw Error('No ranking is available for this date.');
        const response = await fetch(new URL('./data/' + day.file, document.baseURI));
        if (!response.ok) throw Error(`HTTP ${response.status}`);
        const value = validateDay(await response.json());
        if (id !== requestId) return;
        data = value; render();
      } catch (error) {
        if (id !== requestId) return;
        $('candidates').setAttribute('aria-busy', 'false');
        $('candidates').replaceChildren(element('p', 'empty', error.message + ' Try another date or reload.'));
        $('status').textContent = 'D selections unavailable.'; $('selected-count').textContent = '—';
        $('walk').replaceChildren(); $('walk-count').textContent = ''; $('walk-details').hidden = true; $('menu-link').hidden = true;
      }
    }
    $('date').onchange = load;
    $('goal').onchange = $('profile').onchange = () => { try { render(); } catch (error) { $('status').textContent = error.message; } };
    fetch(new URL('./data/index.json', document.baseURI), {cache: 'no-cache'}).then(r => {
      if (!r.ok) throw Error(`HTTP ${r.status}`);
      return r.json();
    }).then(value => {
      if (value.schema_version !== 1 || !value.days?.length) throw Error('No generated D ranking data.');
      index = value;
      const today = new Date().toLocaleDateString('en-CA', {timeZone: 'Europe/Berlin'});
      for (const row of value.days) $('date').append(new Option(new Date(row.date + 'T12:00:00Z').toLocaleDateString('en-GB', {weekday: 'short', day: 'numeric', month: 'short', timeZone: 'Europe/Berlin'}), row.date));
      $('date').value = value.days.some(d => d.date === query.get('date')) ? query.get('date') : value.days.some(d => d.date === today) ? today : value.days[0].date;
      $('date').disabled = false; return load();
    }).catch(error => {
      $('status').textContent = error.message; $('candidates').setAttribute('aria-busy', 'false');
      $('candidates').replaceChildren(element('p', 'empty', error.message)); $('menu-link').hidden = true;
    });
  }
  return {GOALS, PROFILES, displayPlate, decisionText, validateDay, start};
});
