const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function studio() {
  const settings = {gap:16,radius:20,avatarSize:96,coverHeight:130,iconSize:24,nameSize:30,
    accent:'#2457DB',background:'#ffffff',text:'#17272d',font:'ui',align:'left',weight:700,
    buttonColumns:1,avatarShape:'circle',buttonShape:'rounded',buttonStyle:'filled',iconPosition:'left',socialMode:'both',
    caption:'Привет',icon_phone:''};
  const fields=Object.fromEntries(Object.entries(settings).map(([key,value])=>[key,{value}]));
  fields.block_order={value:''};
  const keys=['cover','avatar','identity','bio','save','contacts','socials'];
  const list={children:keys.map(key=>({dataset:{block:key}})),events:{},
    addEventListener(name,fn){this.events[name]=fn;},
    insertBefore(node,ref){this.children.splice(this.children.indexOf(node),1);this.children.splice(this.children.indexOf(ref),0,node);}};
  for(const item of list.children){
    Object.defineProperty(item,'previousElementSibling',{get(){return list.children[list.children.indexOf(item)-1];}});
    Object.defineProperty(item,'nextElementSibling',{get(){return list.children[list.children.indexOf(item)+1];}});
  }
  const blocks=Object.fromEntries(keys.map(key=>[key,{key,hidden:false,dataset:{},style:{values:{},setProperty(key,value){this.values[key]=value;}}}]));
  const body={order:[],querySelector(selector){return blocks[selector.match(/"(.*?)"/)[1]];},
    append(node){this.order=this.order.filter(key=>key!==node.key);this.order.push(node.key);}};
  const label={dataset:{designLabel:'caption'},textContent:''};
  const icon={dataset:{designIcon:'phone'},src:''};
  const card={dataset:{},style:{values:{},setProperty(key,value){this.values[key]=value;}},
    querySelector:()=>body,querySelectorAll(selector){return selector==='[data-design-label]'?[label]:[icon];}};
  const hidden=[];
  const form={events:{},elements:{namedItem:name=>fields[name]},querySelector:()=>list,querySelectorAll:()=>hidden,
    addEventListener(name,fn){this.events[name]=fn;}};
  const document={currentScript:{src:'https://visiooo.ru/static/studio.hash.js'},querySelector(selector){return selector==='#template-form'?form:card;},querySelectorAll:()=>[]};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/studio.js'),'utf8'),{document,URL});
  return {form,fields,list,body,blocks,hidden,card,label,icon};
}

test('moving blocks changes the preview and order submitted to the server',()=>{
  const {list,body,fields}=studio();
  const item=list.children[1];
  const button={dataset:{move:'up'},closest:()=>item};
  list.events.click({target:{closest:()=>button}});
  assert.equal(list.children[0].dataset.block,'avatar');
  assert.equal(body.order[0],'avatar');
  assert.equal(fields.block_order.value,'avatar,cover,identity,bio,save,contacts,socials');
});

test('editing controls updates labels, SVG choice, hidden blocks and bounded sizing',()=>{
  const {fields,form,hidden,blocks,card,label,icon}=studio();
  hidden.push({value:'bio'});fields.caption.value='Новая надпись';fields.icon_phone.value='test-id';fields.avatarSize.value='9999';
  fields.buttonColumns.value='2';fields.buttonShape.value='pill';form.events.input();
  assert.equal(label.textContent,'Новая надпись');assert.equal(blocks.bio.hidden,true);
  assert.equal(icon.src,'/template-icons/test-id.svg');
  assert.equal(card.style.values['--design-avatar'],'144px');
  assert.equal(card.style.values['--design-button-radius'],'999px');
  assert.equal(card.style.values['--design-columns'],'2');
});

test('block alignment and icons change independently without changing other blocks',()=>{
  const {fields,form,blocks}=studio();
  fields.block_identity_align={value:'center'};fields.block_contacts_align={value:'left'};
  fields.block_contacts_iconPosition={value:'none'};fields.block_socials_iconPosition={value:'right'};
  fields.block_socials_iconSize={value:'32'};form.events.change();
  assert.equal(blocks.identity.dataset.blockAlign,'center');
  assert.equal(blocks.contacts.dataset.blockAlign,'left');
  assert.equal(blocks.contacts.dataset.blockIcons,'none');
  assert.equal(blocks.socials.dataset.blockIcons,'right');
  assert.equal(blocks.socials.style.values['--design-icon'],'32px');
  assert.equal(blocks.save.dataset.blockIcons,'left');
});
