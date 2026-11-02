const {test} = require('node:test');
const assert = require('node:assert/strict');
const {existsSync,readdirSync,readFileSync} = require('node:fs');
const {join} = require('node:path');
const icons = require('../dish-icons.js');

test('dish identity wins over a sauce, garnish, protein, or translated side', () => {
  const cases = [
    ['Seelachsfilet (1Stück)', 'Pollock fillet (1 piece)', 'fish'],
    ['Zanderfilet mit Chilli und Koriander', 'Pike-perch with chili and coriander', 'fish'],
    ['Tom Kha Gai (Scharfe Suppe mit Hühnerfleisch)', 'Tom Kha Gai (spicy chicken soup)', 'soup'],
    ['Maultaschensuppe', 'Swabian dumpling soup', 'soup'],
    ['Cremige Kürbissuppe', 'Creamy pumpkin soup', 'soup'],
    ['Pasta mit Sojabolognese', 'Pasta with soy Bolognese', 'pasta'],
    ['Pasta in Rahmsauce', 'Creamy pasta', 'pasta'],
    ['Gnocchi Alfredo mit Gemüse', 'Gnocchi Alfredo with vegetables', 'pasta'],
    ['Vegane Maultaschen mit Zwiebelmarmelade', 'Vegan German filled pasta pockets with onion jam', 'pasta'],
    ['Dim Sum: Asian Dumplings mit Asiagemüse', 'Dim Sum: Asian dumplings with Asian vegetables', 'dumplings'],
    ['Asia-Reisbällchen auf Teriyakigemüse', 'Asian rice balls on teriyaki vegetables', 'dumplings'],
    ['Semmelknödel', 'Bread dumplings', 'dumplings'],
    ['Fleischpflanzerl mit Kümmelsauce', 'Bavarian meat patty with caraway gravy', 'meatballs'],
    ['Cevapcici mit Ajvar', 'Cevapcici with ajvar', 'meatballs'],
    ['Putensteak mit Chimichuri', 'Turkey steak with chimichurri', 'chicken'],
    ['Entenkeule mit Bratensauce', 'Duck leg with gravy', 'chicken'],
    ['Truthahnschnitzel mit Paprikasauce', 'Turkey schnitzel with bell pepper sauce', 'schnitzel'],
    ['Boeuf Stroganoff mit Schnitzelgurken', 'Beef Stroganoff with gherkins', 'stew'],
    ['Veganer Gulaschtopf mit Kartoffeln', 'Vegan goulash stew with potatoes', 'stew'],
    ['Gegrillte Zucchini mit Tomaten-Paprika-Ragout', 'Grilled zucchini with tomato and pepper ragout', 'vegetables'],
    ['Broccolicurry mit Paprika', 'Broccoli curry with peppers', 'broccoli'],
    ['Blumenkohlauflauf mit Currydip', 'Cauliflower casserole with curry dip', 'vegetables'],
    ['Kartoffelsalat', 'Potato salad', 'salad'],
    ['Reis', 'Rice', 'rice'],
    ['Bulgur mit roten Linsen', 'Bulgur with red lentils', 'rice'],
    ['Käsekrainer', 'Cheese Krainer sausage', 'sausage'],
    ['Pommes', 'French fries', 'fries'],
    ['Topfenstrudel mit Vanillesauce', 'Curd strudel with vanilla sauce', 'cake'],
    ['Faschingskrapfen', 'Carnival doughnut', 'cake'],
    ['Schokoladen-Seidentofu-Creme', 'Chocolate silken tofu cream', 'dessert'],
    ['Vanillecreme', 'Vanilla cream', 'dessert'],
    ['PINSA Caprese mit Tomaten', 'Pizza with tomato and mozzarella', 'tray'],
    ['PINSA Flammkuchenstyle mit Sauerrahm und Speck', 'Pinsa in tarte flambee style with bacon', 'tray'],
    ['Tomate-Mozzarella-Strudel mit Tomatenragout', 'Tomato and mozzarella strudel with tomato ragout', 'tray'],
    ['Yufkateigschnecke mit Spinatfüllung', 'Yufka pastry spiral with spinach filling', 'tray'],
  ];
  for (const [name,name_en,key] of cases) assert.equal(icons.classify({name,name_en}),key,name);
});

test('unknown dishes have a stable category fallback without changing diet data', () => {
  for (const [item,key] of [[null,'tray'],[{},'tray'],[{name:'New lunch'},'tray'],[{name:'New lunch',diet:'vegan'},'vegetables'],[{station:'Fisch'},'fish'],[{station:'Pasta'},'pasta'],[{station:'Dessert (Glas)'},'dessert']]) {
    const before = JSON.stringify(item);
    assert.equal(icons.classify(item),key);
    assert.equal(JSON.stringify(item),before);
  }
});

test('every current menu item and extra resolves to an existing new icon', () => {
  const items=[];
  for (const file of readdirSync(join(__dirname,'../data/menus')).filter(f=>f.endsWith('.json'))) {
    items.push(...JSON.parse(readFileSync(join(__dirname,'../data/menus',file),'utf8')).dishes);
  }
  for (const file of readdirSync(join(__dirname,'../data/days')).filter(f=>f.endsWith('.json'))) {
    const day=JSON.parse(readFileSync(join(__dirname,'../data/days',file),'utf8'));
    for (const variant of Object.values(day.variants)) for (const plate of variant.plates) items.push(...plate.items);
    items.push(...day.extras.all,...day.extras.vegan);
  }
  assert(items.length>50);
  for(const item of items) {
    const key=icons.classify(item);
    assert(icons.keys.includes(key),item.name);
    assert(existsSync(join(__dirname,'../icons/ui',key+'.webp')),item.name);
  }
});
