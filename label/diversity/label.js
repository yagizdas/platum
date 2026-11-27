(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else { root.DiversityLabeler = api; api.start(); }
})(typeof globalThis === 'undefined' ? this : globalThis, function() {
  'use strict';
  const EXPERIMENT = 'plate-diversity-v1', VERSION = 1;
  const REASONS = ['main', 'taste', 'price', 'portion_nutrition', 'other'];
  const GOALS = ['all', 'bulk', 'cut', 'budget'];
  const storageKey = data => `plato-diversity-v1:${data.dataset_id}`;
  const blank = () => ({records: [], deferred: [], resume: null, review: null, goal: 'all'});

  function indexData(data) {
    if (data?.schema_version !== VERSION || data.experiment !== EXPERIMENT || data.feature_version !== 1 || !data.dataset_id || !data.pairs?.length || !Array.isArray(data.plates)) throw Error('Invalid diversity dataset.');
    const plates = new Map(data.plates.map(p => [p.id, p]));
    if (plates.size !== data.plates.length) throw Error('Duplicate plate snapshots.');
    const index = new Map();
    for (const pair of data.pairs) {
      const a = plates.get(pair.a), b = plates.get(pair.b);
      if (index.has(pair.id) || !a || !b || pair.a === pair.b || !GOALS.slice(1).includes(pair.goal) || !pair.features) throw Error('Invalid comparison.');
      index.set(pair.id, {pair, a, b});
    }
    return index;
  }

  function makeRecord(data, index, id, decision, flags = {}, reasons = [], note = '', now = new Date()) {
    const value = index.get(id);
    if (!value || !['worth_both', 'redundant', 'unsuitable'].includes(decision) || !Array.isArray(reasons) || reasons.some(r => !REASONS.includes(r)) || typeof note !== 'string' || note.length > 500) throw Error('Invalid label.');
    const badA = flags.a === true, badB = flags.b === true;
    if ((decision === 'unsuitable') !== (badA || badB)) throw Error('Save suitability flags separately from a redundancy judgment.');
    return {schema_version: VERSION, experiment: EXPERIMENT, dataset_id: data.dataset_id,
      feature_version: data.feature_version, annotation_source: 'human_direct', is_human_judgment: true,
      timestamp: now.toISOString(), pair_id: id, date: value.pair.date, goal: value.pair.goal, campus: data.campus,
      strategy: value.pair.strategy, decision, worth_offering_both: decision === 'unsuitable' ? null : decision === 'worth_both',
      unsuitable_a: badA, unsuitable_b: badB, reasons: [...new Set(reasons)], note,
      features: structuredClone(value.pair.features), plate_a: structuredClone(value.a), plate_b: structuredClone(value.b)};
  }

  function restoreRecords(data, index, rows) {
    if (!Array.isArray(rows)) throw Error('This backup has no labels.');
    const restored = new Map();
    for (const row of rows) {
      const pair = index.get(row.pair_id);
      if (row.dataset_id !== data.dataset_id || row.experiment !== EXPERIMENT || row.is_human_judgment !== true || row.annotation_source !== 'human_direct' || !pair || row.plate_a?.id !== pair.a.id || row.plate_b?.id !== pair.b.id || !Number.isFinite(Date.parse(row.timestamp))) throw Error('Labels do not match this human diversity dataset.');
      const record = makeRecord(data, index, row.pair_id, row.decision, {a: row.unsuitable_a, b: row.unsuitable_b}, row.reasons, row.note, new Date(row.timestamp));
      const old = restored.get(row.pair_id);
      if (!old || record.timestamp > old.timestamp) restored.set(row.pair_id, record);
    }
    return [...restored.values()];
  }

  function compact(state) {
    return {...state, records: state.records.map(r => ({...r, features: undefined, plate_a: {id: r.plate_a.id}, plate_b: {id: r.plate_b.id}}))};
  }
  function readState(storage, data, index) {
    const raw = storage.getItem(storageKey(data));
    if (!raw) return blank();
    const value = JSON.parse(raw);
    return {records: restoreRecords(data, index, value.records),
      deferred: Array.isArray(value.deferred) ? [...new Set(value.deferred.filter(id => index.has(id)))] : [],
      resume: index.has(value.resume) ? value.resume : null, review: index.has(value.review) && value.records.some(r => r.pair_id === value.review) ? value.review : null, goal: GOALS.includes(value.goal) ? value.goal : 'all'};
  }
  function pending(data, state) {
    const done = new Set(state.records.map(r => r.pair_id));
    return data.pairs.filter(p => (state.goal === 'all' || p.goal === state.goal) && !done.has(p.id));
  }
  function nextPair(data, state) {
    if (state.review) return data.pairs.find(p => p.id === state.review) || null;
    const remaining = pending(data, state), deferred = new Set(state.deferred);
    return remaining.find(p => p.id === state.resume) || remaining.find(p => !deferred.has(p.id)) || state.deferred.map(id => remaining.find(p => p.id === id)).find(Boolean) || remaining[0] || null;
  }
  function applyChoice(state, record) {
    return {...state, records: [...state.records.filter(r => r.pair_id !== record.pair_id), record], deferred: state.deferred.filter(id => id !== record.pair_id), resume: null, review: null};
  }
  function undo(state) {
    if (!state.records.length) return state;
    const last = state.records.at(-1);
    return {...state, records: state.records.slice(0, -1), resume: last.pair_id, review: null,
      goal: state.goal === 'all' ? 'all' : last.goal, deferred: state.deferred.filter(id => id !== last.pair_id)};
  }
  function defer(state, id) {
    return {...state, deferred: state.review ? state.deferred : [...state.deferred.filter(key => key !== id), id], resume: null, review: null};
  }
  function backup(data, state) {
    return {schema_version: VERSION, experiment: EXPERIMENT, feature_version: data.feature_version,
      dataset_id: data.dataset_id, exported_at: new Date().toISOString(), records: state.records};
  }
  function mergeBackup(data, index, state, value) {
    if (value?.schema_version !== VERSION || value.experiment !== EXPERIMENT || value.dataset_id !== data.dataset_id || value.feature_version !== data.feature_version) throw Error('Choose a backup from this diversity dataset.');
    const imported = restoreRecords(data, index, value.records), rows = new Map(state.records.map(r => [r.pair_id, r]));
    for (const r of imported) if (!rows.has(r.pair_id) || r.timestamp > rows.get(r.pair_id).timestamp) rows.set(r.pair_id, r);
    return {...state, records: [...rows.values()].sort((a, b) => a.timestamp.localeCompare(b.timestamp) || a.pair_id.localeCompare(b.pair_id)), resume: null, review: null};
  }

  function start() {
    const $ = id => document.getElementById(id), element = (tag, cls, text) => {
      const node = document.createElement(tag); if (cls) node.className = cls;
      if (text !== undefined) node.textContent = text; return node;
    };
    let data, index, state = blank(), pair = null, busy = false;
    const notice = text => { $('notice').textContent = text; $('notice').hidden = !text; };
    function persist(next) {
      try { localStorage.setItem(storageKey(data), JSON.stringify(compact(next))); state = next; notice(''); return true; }
      catch { notice('Your choice could not be saved. This pair has not advanced. Export your existing labels and free browser storage, then try again.'); return false; }
    }
    const flags = () => ({a: $('bad-a')?.checked === true, b: $('bad-b')?.checked === true});
    function syncFlags() {
      const flagged = Object.values(flags()).some(Boolean);
      $('worth-both').disabled = $('redundant').disabled = !pair || flagged;
      $('save-unsuitable').hidden = !pair || !flagged;
    }
    function drawPlate(plate, side) {
      const card = BulkPlateCard.render(plate, side, () => {});
      for (const attr of ['role', 'tabindex', 'aria-label']) card.removeAttribute(attr);
      const label = element('label', 'suitability'), input = element('input');
      input.type = 'checkbox'; input.id = 'bad-' + side;
      input.onchange = syncFlags; label.append(input, document.createTextNode(`Plate ${side.toUpperCase()} does not suit ${pair.goal === 'bulk' ? 'Bulk' : pair.goal === 'cut' ? 'Cut' : 'Budget'}`));
      card.append(label); return card;
    }
    function draw() {
      pair = nextPair(data, state); $('goal').value = state.goal; $('goal').disabled = false;
      const reviewed = state.records.filter(r => state.goal === 'all' || r.goal === state.goal);
      $('review').replaceChildren(new Option('Continue labeling', ''), ...reviewed.map(r => new Option(`${r.goal.toUpperCase()} · ${r.date} · ${r.decision.replaceAll('_', ' ')}`, r.pair_id)));
      $('review').disabled = !reviewed.length; $('review').value = state.review || '';
      $('pass').textContent = state.review ? 'Back to queue' : 'Unsure / skip';
      const total = data.pairs.filter(p => state.goal === 'all' || p.goal === state.goal).length;
      const done = total - pending(data, state).length;
      $('count').textContent = String(state.records.length);
      $('remaining').textContent = `${done} of ${total} pairs labeled in this view · ${state.records.length} of ${data.pairs.length} overall. ${state.records.filter(r => r.worth_offering_both !== null).length} usefulness labels; ${state.records.filter(r => r.worth_offering_both === null).length} suitability-only.`;
      $('undo').disabled = !state.records.length; $('export').disabled = !state.records.length; $('pass').disabled = !pair;
      $('pair').setAttribute('aria-busy', 'false');
      document.querySelectorAll('[name="reason"]').forEach(el => { el.checked = false; });
      $('note').value = ''; $('reason-panel').open = false; $('reason-panel').hidden = !pair;
      syncFlags();
      if (!pair) {
        const box = element('div', 'empty');
        box.append(element('h2', '', 'This session is complete.'), element('p', '', state.goal === 'all' ? 'All pairs are labeled. Export your labels to keep a training-ready backup.' : 'You have labeled every pair for this goal. Switch to All goals to continue, or export your labels.'));
        $('pair').replaceChildren(box); $('scope').textContent = 'Arcisstraße · Useful alternatives'; return;
      }
      const value = index.get(pair.id);
      $('pair').replaceChildren(drawPlate(value.a, 'a'), drawPlate(value.b, 'b'));
      const previous = state.review && state.records.find(r => r.pair_id === state.review);
      if (previous) {
        $('bad-a').checked = previous.unsuitable_a; $('bad-b').checked = previous.unsuitable_b;
        document.querySelectorAll('[name="reason"]').forEach(el => { el.checked = previous.reasons.includes(el.value); });
        $('note').value = previous.note; $('status').textContent = `Saved label: ${previous.decision.replaceAll('_', ' ')}. Choose again to change it.`;
      }
      syncFlags();
      const goal = {bulk: 'Bulk — a substantial, protein-rich lunch', cut: 'Cut — a lighter, protein-focused lunch', budget: 'Budget — a useful student lunch for the money'}[pair.goal];
      const date = new Date(pair.date + 'T12:00:00Z').toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Europe/Berlin'});
      $('scope').textContent = `${goal} · Arcisstraße · ${date}`;
    }
    function save(decision) {
      if (!pair || busy) return;
      busy = true;
      try {
        const reasons = [...document.querySelectorAll('[name="reason"]:checked')].map(el => el.value);
        const record = makeRecord(data, index, pair.id, decision, flags(), reasons, $('note').value);
        if (persist(applyChoice(state, record))) {
          draw(); $('status').textContent = decision === 'unsuitable' ? 'Saved suitability flags; no similarity label assigned.' : decision === 'worth_both' ? 'Saved: worth offering both.' : 'Saved: mostly redundant.';
          window.scrollTo({top: 0, behavior: 'instant'});
        }
      } catch (error) { notice(error.message); }
      finally { busy = false; }
    }
    $('worth-both').onclick = () => save('worth_both'); $('redundant').onclick = () => save('redundant');
    $('save-unsuitable').onclick = () => save('unsuitable');
    $('undo').onclick = () => { if (persist(undo(state))) { draw(); $('status').textContent = 'Last label removed. Here is that pair again.'; window.scrollTo({top: 0, behavior: 'instant'}); } };
    $('pass').onclick = () => { if (pair && persist(defer(state, pair.id))) { draw(); $('status').textContent = 'Skipped without a label. This pair will return after the others.'; window.scrollTo({top: 0, behavior: 'instant'}); } };
    $('goal').onchange = () => { if (!data) return; if (persist({...state, goal: $('goal').value, resume: null, review: null})) draw(); else $('goal').value = state.goal; };
    $('review').onchange = () => { if (persist({...state, review: $('review').value || null, resume: null})) draw(); };
    $('export').onclick = () => {
      const url = URL.createObjectURL(new Blob([JSON.stringify(backup(data, state), null, 2)], {type: 'application/json'})), link = document.createElement('a');
      link.href = url; link.download = `plato-diversity-${data.dataset_id}-labels.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      $('status').textContent = 'Labels exported with full plate snapshots and pair features.';
    };
    $('import').onclick = () => $('import-file').click();
    $('import-file').onchange = async event => {
      const file = event.target.files[0]; if (!file) return;
      try { if (file.size > 20 * 1024 * 1024) throw Error('This backup is too large.');
        const next = mergeBackup(data, index, state, JSON.parse(await file.text()));
        if (persist(next)) { draw(); $('status').textContent = 'Backup restored; duplicate labels merged by latest timestamp.'; }
      } catch (error) { notice(error.message); } finally { event.target.value = ''; }
    };
    document.addEventListener('keydown', event => {
      if (!data || event.repeat || event.altKey || event.ctrlKey || event.metaKey || event.target.matches('input,textarea,select,summary')) return;
      if (event.key === 'ArrowLeft' && !$('worth-both').disabled) { event.preventDefault(); save('worth_both'); }
      else if (event.key === 'ArrowRight' && !$('redundant').disabled) { event.preventDefault(); save('redundant'); }
      else if (event.key === 'ArrowDown' && !$('pass').disabled) { event.preventDefault(); $('pass').click(); }
      else if (event.key.toLowerCase() === 'u' && !$('undo').disabled) { event.preventDefault(); $('undo').click(); }
    });
    window.addEventListener('storage', event => {
      if (!data || event.key !== storageKey(data)) return;
      try { state = readState(localStorage, data, index); draw(); $('status').textContent = 'Progress updated from your other tab.'; }
      catch { pair = null; syncFlags(); $('goal').disabled = $('review').disabled = true; $('pass').disabled = true; $('undo').disabled = true; notice('Saved labels could not be read. Restore a backup to continue.'); }
    });
    fetch(new URL('./data.json', document.baseURI), {cache: 'no-cache'}).then(r => {
      if (!r.ok) throw Error(`Could not load comparisons (HTTP ${r.status}).`); return r.json();
    }).then(value => {
      index = indexData(value); data = value; $('import').disabled = false;
      try { state = readState(localStorage, data, index); }
      catch { $('pair').setAttribute('aria-busy', 'false'); notice('Saved labels could not be read. Labeling is paused to protect them. Restore a backup to continue.'); return; }
      draw();
    }).catch(error => { $('pair').setAttribute('aria-busy', 'false'); $('pair').replaceChildren(element('p', 'empty', error.message + ' Reload to try again.')); });
  }
  return {VERSION, EXPERIMENT, GOALS, REASONS, storageKey, blank, indexData, makeRecord, restoreRecords, compact, readState, pending, nextPair, applyChoice, undo, defer, backup, mergeBackup, start};
});
