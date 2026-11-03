'use strict';

((root) => {
  const keys = Object.freeze(['dumplings','broccoli','cake','coins','dumbbell','fish','fries','chicken','leaf','tape','meatballs','pasta','rice','empty','error','salad','sausage','schnitzel','soup','dessert','stew','tray','vegetables']);
  const known = new Set(keys);
  const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ß/g, 'ss').toLowerCase();

  function classify(item = {}) {
    item = item || {};
    // A sauce or side mentioned after "with" must not override the dish itself.
    const identity = [item.name, item.name_en].map(value => normalize(value).split(/\s+(?:mit|with|auf|on|in|served)\s+/)[0]).join(' ');
    const station = normalize(item.station);

    // Preparation/format first: chicken soup is soup, dumpling soup is soup.
    if (/suppe|soup|bruhe|broth|consomme|tom kha/.test(identity)) return 'soup';
    if (/pizza|pinsa|flammkuchen|krautwickerl|cabbage roll/.test(identity)) return 'tray';
    if (/strudel|pastry|yufka/.test(identity) && !/apfel|apple|topfen|curd|quark|birne|pear|kirsche|cherry|vanille|vanilla|chocolate|schoko|sweet/.test(identity) && !/dessert|sussspeise/.test(station)) return 'tray';
    if (/kuchen|cake|torte|strudel|krapfen|doughnut|donut|pastry|yufka|waffle|pancake|pfannkuchen|kaiserschmarrn/.test(identity)) return 'cake';
    if (/pudding|creme|mousse|quark|joghurt|yogurt|yoghurt|dessert|ice cream/.test(identity) || /(?:vanilla|chocolate|bavarian|cappuccino|mascarpone|macchiato)\s+cream/.test(identity) || /dessert|sussspeise/.test(station)) return 'dessert';
    if (/eintopf|stew|gulasch|goulash|ragout|stroganoff|chili|chilli/.test(identity)) return 'stew';
    if (/salat|salad/.test(identity)) return 'salad';
    if (/pommes|fries|frites|wedges|rosti/.test(identity)) return 'fries';
    if (/schnitzel|cordon\s*bleu/.test(identity)) return 'schnitzel';
    if (/fish|fisch|lachs|zander|pollock|perch|salmon|trout|tuna|kabeljau|forelle|dorade|\bcod\b/.test(identity)) return 'fish';
    if (/wurst|krainer|sausage|hot\s*dog/.test(identity)) return 'sausage';
    if (/meatball|meat patt|fleischpflanzerl|frikadell|hackball|cevap|koft|kofte|koefte|bulett|\bpatty\b|burger/.test(identity)) return 'meatballs';
    if (/knodel|knoedel|kloss|kloess|dumpling|dim sum|falafel|reisballchen|rice balls/.test(identity)) return 'dumplings';
    if (/pasta|nudel|spaghetti|tortellin|raviol|cannellon|gnocchi|spatzle|spaetzle|knopf|knoepf|maultasch|lasagn/.test(identity)) return 'pasta';
    if (/huhn|hahnchen|huehn|chicken|pute|turkey|enten|duck|poultry|geflugel|gefluegel/.test(identity)) return 'chicken';
    if (/\breis\b|rice|reispfanne|bulgur|couscous|hirse|millet|zartweizen|ebly|quinoa|grain|barley/.test(identity)) return 'rice';
    if (/broccoli|brokkoli|brocoli/.test(identity)) return 'broccoli';
    if (/gemuse|vegetable|tofu|pilz|mushroom|spinat|spinach|potato|kartoffel|zucchini|shakshuka|paprika|pepper|curry|chunks|stripes|kohl|cabbage/.test(identity)) return 'vegetables';

    // Generic illustrations are deliberate for categories without a supplied icon.
    if (/suppe|soup/.test(station)) return 'soup';
    if (/fisch|fish/.test(station) || item.diet === 'fish') return 'fish';
    if (/pasta/.test(station)) return 'pasta';
    if (/wok|vegetar|vegan|studitopf/.test(station) || item.diet === 'vegan' || item.is_vegan === true) return 'vegetables';
    return 'tray';
  }

  function apply(target, key, options = {}) {
    key = known.has(key) ? key : 'tray';
    const previous = target.dataset.icon;
    if (previous) target.classList.remove('art-' + previous);
    target.classList.add('artwork', 'art-' + key);
    target.dataset.icon = key;
    let img = target.querySelector('img');
    if (!img) { img = document.createElement('img'); target.append(img); }
    const src = './icons/ui/' + key + '.webp';
    if (img.getAttribute('src') !== src) img.src = src;
    img.width = img.height = key === 'tray' ? 1254 : 640;
    img.alt = options.alt || '';
    img.decoding = 'async';
    return target;
  }

  function create(key, options) { return apply(document.createElement('span'), key, options); }

  function compose(target, items = [], options = {}) {
    const main = items.find(item => item.role === 'main') || items[0];
    let primary = target.querySelector('.artwork:not(.dish-companion)');
    if (!primary) { primary = create('tray'); target.append(primary); }
    apply(primary, main ? classify(main) : options.fallback);
    target.querySelectorAll('.dish-companion').forEach(art => art.remove());
    const companions = items.filter(item => item !== main).slice(0, 2);
    target.dataset.companions = String(companions.length);
    for (const item of companions) {
      const art = create(classify(item));
      art.classList.add('dish-companion');
      art.setAttribute('aria-hidden', 'true');
      target.append(art);
    }
    return target;
  }

  const api = Object.freeze({ keys, classify, apply, create, compose });
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.DishIcons = api;
})(typeof globalThis === 'undefined' ? this : globalThis);
