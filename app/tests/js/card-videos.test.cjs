const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
function fixture(extra=[],layout={}){
 class Element{
  constructor(tag='div'){this.tag=tag;this.attrs={};this.children=[];this.events={};this.value='';}
  setAttribute(key,value){this.attrs[key]=value;this[key]=value;}
  append(...children){this.children.push(...children);}
  prepend(...children){this.children.unshift(...children);}
  replaceChildren(...children){this.children=children;}
  addEventListener(type,fn){(this.events[type]??=[]).push(fn);}
  dispatchEvent(event){event.target??=this;for(const fn of this.events[event.type]||[])fn(event);if(this.form)this.form.dispatchEvent(event);}
  fire(type){this.dispatchEvent({type});}
  focus(){}
  get lastElementChild(){return this.children.at(-1);}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
  querySelectorAll(selector){const match=el=>selector.startsWith('#')?el.id===selector.slice(1):el.tag===selector;return this.children.flatMap(el=>[...(match(el)?[el]:[]),...el.querySelectorAll(selector)]);}
 }
 const form=new Element('form'),fieldset=new Element('fieldset');
 const fields=Object.fromEntries(['video_items','video_url','video_title','video_player','layout_data'].map(name=>{const input=new Element('input'),wrapper=new Element();wrapper.append(input);input.closest=selector=>selector==='fieldset'?fieldset:wrapper;input.form=form;return [name,input];}));
 fields.video_items.value=JSON.stringify(extra);fields.video_url.value='https://vkvideo.ru/clip-243793209_456239017?sh=4';fields.layout_data.value=JSON.stringify(layout);
 form.elements={namedItem:key=>fields[key]};
 let applied;
 const window={CardEmbeds:require('../../static/card-embeds.js'),CardLayout:{set(card,value){applied=JSON.parse(JSON.stringify(value));}}};
 const document={createElement:tag=>new Element(tag),getElementById:()=>form,querySelector:()=>({})};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/card-videos.js'),'utf8'),{window,document,Event:class{constructor(type){this.type=type;}}});
 return {form,fields,fieldset,window,get applied(){return applied;}};
}

test('player width and height update saved layout without dropping other block settings',()=>{
 const f=fixture([],{blocks:{map:{width:50},video:{height:240,width:75}}});
 const height=f.fieldset.querySelector('#video-player-height'),width=f.fieldset.querySelector('#video-player-width');
 assert.equal(height.value,'240');assert.equal(width.value,'75');
 height.value='180';height.fire('input');width.value='50';width.fire('change');
 const saved=JSON.parse(f.fields.layout_data.value);
 assert.deepEqual(saved.blocks.video,{height:180,width:50});assert.deepEqual(saved.blocks.map,{width:50});assert.deepEqual(f.applied,saved);
 const reopened=fixture([],saved);assert.equal(reopened.fieldset.querySelector('#video-player-height').value,'180');assert.equal(reopened.fieldset.querySelector('#video-player-width').value,'50');
});

test('multiple videos survive editing, adding a slide and reopening the carousel',()=>{
 const extra=[{url:'https://vimeo.com/123',title:'Second',embedUrl:''}],f=fixture(extra);
 const add=f.fieldset.querySelectorAll('button').find(el=>el.textContent==='Добавить видео');
 add.onclick();const url=f.fieldset.querySelector('#video-extra-1-url');url.value='https://ok.ru/video/123';url.fire('input');
 const saved=JSON.parse(f.fields.video_items.value);assert.equal(saved.length,2);assert.equal(saved[0].title,'Second');assert.equal(saved[1].url,url.value);
 const reopened=fixture(saved);assert.equal(reopened.fieldset.querySelector('#video-extra-1-url').value,url.value);assert.equal(reopened.window.CardVideos.fromForm(reopened.form).length,3);
});

test('saved video height reaches the player styles and clears when reset',()=>{
 const style=()=>({values:{},setProperty(key,value){this.values[key]=value;},removeProperty(key){delete this.values[key];}});
 const video={dataset:{layoutBlock:'video'},classList:{toggle(){}},style:style(),hasAttribute:()=>false};
 const card={dataset:{},classList:{toggle(){},contains:()=>false},dispatchEvent(){},
  querySelector:selector=>selector==='[data-layout-block="video"]'?video:null,
  querySelectorAll:selector=>selector==='[data-layout-block],[data-layout-button]'?[video]:[]};
 const document={currentScript:null,querySelectorAll:()=>[],getElementById:()=>null,querySelector:()=>null},window={};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/card-layout.js'),'utf8'),{window,document,Event:class{}});
 window.CardLayout.set(card,{blocks:{video:{height:240,width:75}}});
 assert.equal(video.style.values['--video-player-height'],'240px');
 assert.equal(video.style.values['--size-span'],'9');
 window.CardLayout.set(card,{});assert.equal(video.style.values['--video-player-height'],undefined);
});
