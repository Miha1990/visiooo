const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
class Element {
  constructor(tag='div',attrs={}){this.tag=tag;this.attrs={...attrs};this.children=[];this.dataset={};this.handlers={};this.clientWidth=320;this.style={setProperty(){}};}
  setAttribute(k,v){this.attrs[k]=String(v);}
  getAttribute(k){return this.attrs[k];}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=[...children];}
  get childElementCount(){return this.children.length;}
  addEventListener(type,fn){this.handlers[type]=fn;}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
  querySelectorAll(selector){const match=el=>selector.startsWith('.')?(el.attrs.class||'').split(' ').includes(selector.slice(1)):selector.startsWith('[')?Object.hasOwn(el.attrs,selector.slice(1,-1)):el.tag===selector;return this.children.flatMap(el=>[...(match(el)?[el]:[]),...el.querySelectorAll(selector)]);}
}
function fixture(){
  const card=new Element(),daisy=new Element('section',{'data-daisy':''}),toggle=new Element('button',{'data-daisy-toggle':''}),petals=new Element('div',{class:'daisy-petals'});daisy.append(toggle,petals);card.append(daisy);
  const document={currentScript:{src:'https://visiooo.ru/static/card-layout.abc123.js'},createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),querySelectorAll:()=>[],querySelector:()=>null,getElementById:()=>null,addEventListener(){}};
  const window={CardButtons:require('../../static/card-buttons.js')};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/card-layout.js'),'utf8'),{window,document,URL,location:{href:'https://visiooo.ru/c/mike'},Event});
  return {card,daisy,toggle,petals,layout:window.CardLayout};
}
test('daisy logos resolve from the fingerprinted static script, not the public card URL',()=>{
  const {card,petals,layout}=fixture();layout.setDaisy(card,{label:'Написать',items:[{kind:'telegram',label:'Telegram',value:'https://t.me/mike'},{kind:'vk',label:'VK',value:'https://vk.com/mike'}]});
  assert.deepEqual(petals.children.map(el=>el.querySelector('img').attrs.src),['https://visiooo.ru/static/icons/telegram.svg','https://visiooo.ru/static/icons/vk.svg']);
  assert.equal(petals.children[0].attrs.href,'https://t.me/mike');
});
test('center keeps its contact icon when the caption changes and opens the social buttons',()=>{
  const {card,daisy,toggle,petals,layout}=fixture(),items=[{kind:'email',label:'Почта',value:'test@example.test'}];
  layout.setDaisy(card,{label:'Контакты',items});layout.setDaisy(card,{label:'Связаться',items});
  assert.equal(toggle.querySelectorAll('.daisy-center-icon').length,1);assert.equal(toggle.querySelector('.daisy-center-label').textContent,'Связаться');
  toggle.handlers.click();assert.equal(daisy.dataset.open,'true');assert.equal(toggle.attrs['aria-expanded'],'true');assert.equal(petals.children[0].tabIndex,0);
  toggle.handlers.click();assert.equal(daisy.dataset.open,'false');assert.equal(petals.children[0].tabIndex,-1);
});
