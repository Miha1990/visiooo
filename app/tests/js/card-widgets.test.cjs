const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
function node(){return {dataset:{},style:{values:{},setProperty(key,value){this.values[key]=value;}},events:{},attrs:{},hidden:false,tabIndex:0,
 addEventListener(name,fn){this.events[name]=fn;},removeEventListener(name,fn){if(this.events[name]===fn)delete this.events[name];},
 setAttribute(key,value){this.attrs[key]=value;},removeAttribute(key){delete this.attrs[key];},focus(){this.focused=true;},contains(target){return target===this;},
 classList:{values:new Set(),toggle(key,value){if(value)this.values.add(key);else this.values.delete(key);}}};}
function setup({autoplay=true,reduced=false,radial=false,peek=false}={}){
 const card=node();card.clientWidth=360;card.dataset={socialMode:radial?'radial':'both',canvasHeight:'1200'};
 const gallery=node(),track=node(),prev=node(),next=node(),pause=node(),status=node(),empty=node(),controls=node();
 gallery.dataset={visible:'2',peek:String(peek),autoplay:String(autoplay),interval:'5'};track.scrollLeft=0;
 const slides=Array.from({length:5},()=>({getBoundingClientRect:()=>({width:90})}));
 track.querySelectorAll=()=>slides;track.scrollTo=({left})=>{track.scrollLeft=left;track.events.scroll?.();};
 gallery.querySelector=selector=>({'.carousel-track':track,'[data-carousel-status]':status,'[data-carousel-prev]':prev,'[data-carousel-next]':next,'[data-carousel-pause]':pause,'.carousel-empty':empty,'.carousel-controls':controls})[selector];
 const sun=node(),toggle=node(),links=Array.from({length:4},()=>node());sun.clientWidth=280;sun.querySelector=()=>toggle;sun.querySelectorAll=()=>links;
 card.querySelectorAll=selector=>selector==='[data-card-carousel]'?[gallery]:selector==='[data-contact-sun]'?[sun]:[];
 const document=node();document.hidden=false;document.querySelectorAll=()=>[card];
 const timers=new Map();let id=0;
 const window={matchMedia:()=>({matches:reduced})};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/card-widgets.js'),'utf8'),{document,window,setInterval(fn,ms){timers.set(++id,{fn,ms});return id;},clearInterval(key){timers.delete(key);}});
 return {card,gallery,track,prev,next,pause,status,document,timers,sun,toggle,links,window};
}

test('external embeds load immediately, preserve an existing player and reject other hosts or hidden blocks',()=>{
 const card=node(),box=node(),frames=[];let hidden=false;
 box.dataset={embedUrl:'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ',embedTitle:'Видео'};
 box.querySelector=selector=>selector==='iframe'?frames[0]||null:null;box.closest=()=>hidden?{}:null;box.append=frame=>frames.push(frame);
 card.clientWidth=360;card.querySelectorAll=selector=>selector==='[data-external-embed]'?[box]:[];
 const document={querySelectorAll:()=>[card],createElement:tag=>({tag,getAttribute(name){return this[name];},remove(){frames.splice(frames.indexOf(this),1);}})};
 const window={};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/card-widgets.js'),'utf8'),{document,window});
 assert.equal(frames.length,1);const first=frames[0];
 assert.equal(first.src,box.dataset.embedUrl);assert.equal(first.allowFullscreen,true);
 window.CardWidgets.refresh();assert.equal(frames[0],first);
 hidden=true;window.CardWidgets.refresh();assert.equal(frames.length,0);
 hidden=false;box.dataset.embedUrl='https://evil.test/embed/anything';window.CardWidgets.refresh();assert.equal(frames.length,0);
 box.dataset.embedUrl='https://yandex.ru/map-widget/v1/?text=test';window.CardWidgets.refresh();assert.equal(frames.length,1);
});
test('fractional carousel preserves the next-photo cue and wraps from its partial final position',()=>{
 const {gallery,track,next}=setup({peek:true});
 assert.equal(gallery.style.values['--slides-visible'],'2.5');
 track.clientWidth=300;track.scrollWidth=545;track.scrollLeft=245;
 next.onclick();assert.equal(track.scrollLeft,0);
});

test('carousel advances manually, wraps and pauses its automatic timer',()=>{
 const {next,prev,track,pause,timers,status}=setup();
 assert.equal(timers.size,1);assert.equal([...timers.values()][0].ms,5000);
 next.onclick();assert.equal(track.scrollLeft,100);assert.equal(status.textContent,'2 / 5');
 prev.onclick();assert.equal(track.scrollLeft,0);prev.onclick();assert.equal(track.scrollLeft,300);
 pause.onclick();assert.equal(timers.size,0);pause.onclick();assert.equal(timers.size,1);
});

test('narrow gallery fits one readable slide and can reach its final photo',()=>{
 const {gallery,window,prev,track}=setup();gallery.clientWidth=280;window.CardWidgets.refresh();
 assert.equal(gallery.style.values['--slides-visible'],'1');prev.onclick();assert.equal(track.scrollLeft,400);
});
test('autoplay stops while hidden or focused and does not start with reduced motion',()=>{
 const {gallery,document,timers}=setup();gallery.events.focusin();assert.equal(timers.size,0);
 gallery.events.focusout({relatedTarget:null});assert.equal(timers.size,1);
 document.hidden=true;document.events.visibilitychange();assert.equal(timers.size,0);
 assert.equal(setup({reduced:true}).timers.size,0);
 assert.equal(setup({autoplay:false}).timers.size,0);
});
test('sun contacts open by button, support keyboard access and close with Escape',()=>{
 const {sun,toggle,links}=setup({radial:true});
 assert.equal(toggle.hidden,false);assert.equal(toggle.attrs['aria-expanded'],'false');
 assert.ok(links.every(link=>link.tabIndex===-1));
 toggle.onclick();assert.equal(sun.dataset.expanded,'true');assert.ok(links.every(link=>link.tabIndex===0));
 assert.notEqual(links[0].style.values['--sun-y'],links[1].style.values['--sun-y']);
 sun.events.keydown({key:'Escape'});assert.equal(toggle.attrs['aria-expanded'],'false');assert.equal(toggle.focused,true);
});
test('refresh replaces old timers and listeners instead of duplicating them',()=>{
 const {window,document,timers,toggle}=setup();assert.equal(toggle.hidden,true);
 window.CardWidgets.refresh(document);window.CardWidgets.refresh(document);assert.equal(timers.size,1);
});
