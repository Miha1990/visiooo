const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const drag=require('../../static/card-editor-drag.js');
const rect=(top,height=100,left=0,width=300)=>({top,bottom:top+height,left,right:left+width,width,height});

test('a bottom block can be dropped before the first block and into gaps',()=>{
 const entries=[{element:'first',rect:rect(150)},{element:'second',rect:rect(300)}];
 assert.deepEqual(drag.destination(entries,150,80),{element:'first',after:false});
 assert.deepEqual(drag.destination(entries,150,270),{element:'first',after:true});
 assert.deepEqual(drag.destination(entries,150,600),{element:'second',after:true});
 assert.equal(drag.destination([],0,0),null);
});

test('contacts can move across rows and edge scrolling continues while held still',()=>{
 const entries=[{element:'left',rect:rect(100,80,0,80)},{element:'right',rect:rect(100,80,90,80)}];
 assert.deepEqual(drag.destination(entries,130,90,true),{element:'right',after:false});
 assert.deepEqual(drag.destination(entries,160,150,true),{element:'right',after:true});
 assert.ok(drag.scrollSpeed(75,70,700)<0);
 assert.ok(drag.scrollSpeed(690,70,700)>0);
 assert.equal(drag.scrollSpeed(350,70,700),0);
});

test('the add-contact tile fills the remaining space in a row',()=>{
 assert.equal(drag.contactGap([6,3]),3);
 assert.equal(drag.contactGap([6,6,4]),8);
 assert.equal(drag.contactGap([6,6]),6);
 assert.equal(drag.contactGap([1,1,1],4),1);
});

function fixture(){
 class Element{
  constructor(attrs={}){this.attrs={};this.dataset={};this.children=[];this.events={};this.style={setProperty(){},removeProperty(){}};this.hidden=false;this.isConnected=true;this.rect=rect(0);const classes=new Set();this.classList={add:v=>classes.add(v),remove:v=>classes.delete(v),contains:v=>classes.has(v),toggle(v,on){if(on)classes.add(v);else classes.delete(v);}};for(const [key,value]of Object.entries(attrs))this.setAttribute(key,value);}
  setAttribute(key,value){this.attrs[key]=value;if(key.startsWith('data-'))this.dataset[key.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=value;if(key==='class')value.split(' ').forEach(v=>this.classList.add(v));}
  hasAttribute(key){return key in this.attrs;}
  append(...children){for(const child of children){child.parentElement=this;this.children.push(child);}}
  prepend(...children){this.append(...children);}
  addEventListener(key,fn){(this.events[key]??=[]).push(fn);}
  fire(key,event={}){for(const fn of this.events[key]||[])fn(event);}
  dispatchEvent(event){this.fire(event.type,event);}
  remove(){if(this.parentElement)this.parentElement.children=this.parentElement.children.filter(el=>el!==this);}
  getBoundingClientRect(){return this.rect;}
  closest(selector){if(selector==='[hidden]')return this.hidden?this:this.parentElement?.closest(selector)||null;if(selector.includes('data-layout-block')&&this.dataset.layoutBlock)return this;if(selector.includes('block-move-grip')&&this.classList.contains('block-move-grip'))return this;return this.parentElement?.closest(selector)||null;}
  querySelector(selector){if(selector===':scope>.block-move-grip')return this.children.find(el=>el.classList.contains('block-move-grip'))||null;if(selector===':scope>.inline-edit-block')return this.children.find(el=>el.classList.contains('inline-edit-block'))||null;return null;}
  querySelectorAll(selector){return selector==='button'?this.children.filter(el=>el.tagName==='button'):[];}
 }
 const body=new Element(),editor=new Element(),form=new Element(),card=new Element(),preview=new Element();card.parentElement=body;card.rect=rect(0,1800);
 editor.dataset.view='edit';
 const blocks=['identity','bio','video'].map((key,i)=>{const el=new Element({'data-layout-block':key});el.rect=rect(150+i*300,200);card.append(el);return el;});
 const fields={layout_data:{value:'{}',dispatchEvent(){}},map_address:{value:''},daisy_data:{value:'{}'},button_items:{value:'[]'}};
 form.elements={namedItem:key=>fields[key]};
 const originalQuery=card.querySelector.bind(card);
 card.querySelector=selector=>{if(selector.startsWith('[data-layout-block='))return blocks.find(el=>el.dataset.layoutBlock===selector.match(/"(\w+)"/)[1])||null;return originalQuery(selector);};
 card.querySelectorAll=selector=>selector.includes('[data-layout-block')?blocks:selector.includes('.inline-remove-block')?blocks.flatMap(el=>el.children.filter(c=>c.classList.contains('inline-edit-block')||c.classList.contains('inline-remove-block')||c.classList.contains('block-move-grip'))):[];
 editor.querySelector=selector=>selector==='.phone-preview'?preview:null;preview.querySelector=()=>card;
 const config={};let frame,timer,scroll=0;
 const window={CardEditorDrag:drag,CardBuilder:{isRemoved:()=>false},CardVideos:{fromForm:()=>[{url:'video'}]},CardLayout:{get:()=>config,refresh(){},setEditing(){},select(){},set(c,next){Object.assign(config,next);}},scrollY:200,scrollBy({top}){scroll+=top;this.scrollY+=top;},events:{},addEventListener(key,fn){(this.events[key]??=[]).push(fn);}};
 const document={body,getElementById:()=>form,querySelector:()=>editor,createElement(tag){const el=new Element();el.tagName=tag;return el;}};
 const event=target=>({target,button:0,pointerId:1,pointerType:'mouse',clientX:150,clientY:800,cancelable:true,preventDefault(){},stopPropagation(){}});
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/card-inline.js'),'utf8'),{window,document,innerHeight:900,navigator:{},getComputedStyle:()=>({overflowY:'visible'}),MutationObserver:class{observe(){}},Event:class{constructor(type){this.type=type;}},setTimeout:fn=>(timer=fn,1),clearTimeout(){},requestAnimationFrame:fn=>(frame=fn,1),cancelAnimationFrame(){}});
 return {editor,card,blocks,fields,config,event,window,hold:()=>timer(),runFrame:()=>frame(),get scroll(){return scroll;},fire(key,event){for(const fn of window.events[key]||[])fn(event);}};
}

test('simple mode drags a newly added bottom block to the top and persists its order',()=>{
 const f=fixture();assert.equal(f.editor.dataset.editMode,'simple');
 const down=f.event(f.blocks[2]);f.card.fire('pointerdown',down);
 f.fire('pointermove',{...down,clientY:80});
 f.runFrame();assert.ok(f.scroll<0);
 // Keeping the pointer still continues scrolling on the next animation frame.
 const before=f.scroll;f.runFrame();assert.ok(f.scroll<before);
 f.fire('pointerup',{...down,clientY:80});
 assert.deepEqual(Array.from(f.config.order),['video','identity','bio']);
 assert.deepEqual(JSON.parse(f.fields.layout_data.value).order,['video','identity','bio']);
});

test('the visible move handle starts dragging immediately in simple mode',()=>{
 const f=fixture(),handle=f.blocks[2].querySelector(':scope>.block-move-grip');
 assert.ok(handle);
 const down=f.event(handle);handle.fire('pointerdown',down);
 f.fire('pointermove',{...down,clientY:90});
 f.fire('pointerup',{...down,clientY:90});
 assert.deepEqual(Array.from(f.config.order),['video','identity','bio']);
});

test('clicking the move handle without dragging leaves the order unchanged',()=>{
 const f=fixture(),handle=f.blocks[2].querySelector(':scope>.block-move-grip'),down=f.event(handle);
 handle.fire('pointerdown',down);f.runFrame();f.fire('pointerup',down);
 assert.equal(f.config.order,undefined);assert.equal(f.scroll,0);
});

test('holding a block on touch moves it while a regular swipe keeps scrolling',()=>{
 const f=fixture(),touch={identifier:2,clientX:150,clientY:800};
 const event={...f.event(f.blocks[2]),touches:[touch]};
 f.card.fire('touchstart',event);f.hold();
 f.fire('touchmove',{...event,touches:[{...touch,clientY:90}]});
 f.fire('touchend',{...event,changedTouches:[touch]});
 assert.deepEqual(Array.from(f.config.order),['video','identity','bio']);
 const g=fixture(),swipe={...g.event(g.blocks[2]),touches:[touch]};
 g.card.fire('touchstart',swipe);
 g.fire('touchmove',{...swipe,touches:[{...touch,clientY:750}]});
 g.fire('touchend',{...swipe,changedTouches:[touch]});
 assert.equal(g.config.order,undefined);
});
