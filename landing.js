'use strict';
(() => {
  const byId = id => document.getElementById(id);
  const buttons = [...document.querySelectorAll('[data-goal]')];
  const choices = { bulk: 'bulk_all', cut: 'cut_all', budget: 'budget_all', vegan: 'bulk_vegan' };
  const date = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Berlin', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  let selected = 'bulk';
  let menu;
  try {
    const saved = JSON.parse(localStorage.getItem('mensa-plate') || 'null');
    if (saved?.vegan) selected = 'vegan';
    else if (saved && Object.hasOwn(choices, saved.goal)) selected = saved.goal;
  } catch (_) {}
  function sync() {
    for (const button of buttons) button.setAttribute('aria-pressed', String(button.dataset.goal === selected));
    byId('pick-link').href = './menu.html?goal=' + (selected === 'vegan' ? 'bulk&vegan=1' : selected) + '&date=' + date;
  }
  function empty(message,icon='empty') {
    DishIcons.apply(byId('pick-illustration'),icon);
    byId('plate-name').textContent = message;
    byId('plate-price').hidden = true;
    byId('macros').hidden = true;
    byId('announcement').textContent = message;
  }
  function render() {
    sync();
    if (!menu) return;
    if (menu.date !== date) return empty('Today’s plates aren’t ready.');
    if (menu.state === 'closed') return empty('No menu today.');
    if (menu.state !== 'open') return empty('Plates are on the way.');
    const variant = menu.variants?.[choices[selected]];
    const plate = variant?.plates?.[0];
    if (variant?.state !== 'ready' || !plate) return empty('No plate fits this goal today.');
    const total = plate.total;
    if (!total || !['price_cents', 'protein_g', 'carbs_g', 'fat_g'].every(key => Number.isFinite(total[key]))) return empty('Plates are on the way.');
    const main=plate.items.find(item=>item.role==='main') || plate.items[0];
    DishIcons.apply(byId('pick-illustration'),DishIcons.classify(main));
    byId('plate-name').textContent = plate.title;
    byId('plate-name').lang = 'de';
    byId('plate-price').textContent = '€' + (total.price_cents / 100).toFixed(2);
    byId('plate-price').hidden = false;
    for (const [id, key, label] of [['protein', 'protein_g', 'protein'], ['carbs', 'carbs_g', 'carbohydrates'], ['fat', 'fat_g', 'fat']]) {
      const value = String(Math.round(total[key]));
      byId(id).textContent = value;
      byId(id).setAttribute('aria-label', value + ' grams ' + label + ', estimated');
      byId(id).title = label + ': ' + value + 'g, estimated';
    }
    byId('macros').hidden = false;
    byId('announcement').textContent = plate.title + ', ' + byId('plate-price').textContent;
  }
  for (const button of buttons) button.addEventListener('click', () => {
    selected = button.dataset.goal;
    try { localStorage.setItem('mensa-plate', JSON.stringify({ goal: selected === 'vegan' ? 'bulk' : selected, vegan: selected === 'vegan' })); } catch (_) {}
    render();
  });
  sync();
  async function load() {
    try {
      const response = await fetch('./data/days/' + date + '.json', { cache: 'no-store' });
      if (!response.ok) throw new Error('Menu unavailable');
      menu = await response.json();
    } catch (_) {
      try {
        const response = await fetch('./data/today.json', { cache: 'no-store' });
        if (!response.ok) throw new Error('Menu unavailable');
        menu = await response.json();
      } catch (_) { empty('A little trouble in the kitchen.','error'); }
    } finally {
      render();
      byId('pick-link').setAttribute('aria-busy', 'false');
    }
  }
  load();
  // Content remains visible without JavaScript or IntersectionObserver.
  if ('IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    }, { threshold: .08 });
    document.documentElement.classList.add('motion-ready');
    for (const element of document.querySelectorAll('.reveal')) observer.observe(element);
  }
})();
