const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
function setup({seconds=0,withEmail=false,password=false,valid=true}={}){
 let now=100000,tick;const pageEvents={},docEvents={};
 const el=()=>({dataset:{},attrs:{},events:{},children:[],textContent:'',setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,f){this.events[k]=f;},append(...children){this.children.push(...children);},before(wrapper){this.wrapper=wrapper;}});
 const button=el();button.textContent='Отправить код повторно';
 const email=el();email.value='anna@example.test';
 const form=el();form.dataset.retrySeconds=String(seconds);form.dataset.retryEmail=withEmail?email.value:'';form.elements={namedItem:()=>withEmail?email:null};form.querySelector=()=>button;form.checkValidity=()=>valid;form.reportValidity=()=>form.reported=true;
 const input=el();input.type='password';input.id='id_password';
 const document={querySelectorAll:selector=>selector==='input[type="password"]'?(password?[input]:[]):[form],createElement:el,addEventListener:(k,f)=>docEvents[k]=f};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/auth-controls.js'),'utf8'),{document,window:{addEventListener:(k,f)=>pageEvents[k]=f},Date:{now:()=>now},setInterval:f=>tick=f});
 const submit=()=>{const event={defaultPrevented:false,preventDefault(){this.defaultPrevented=true;}};form.events.submit(event);return event;};
 return {form,button,input,email,submit,pageEvents,advance(ms){now+=ms;tick();}};
}
test('cooldown uses elapsed time, survives tab suspension and enables at 60 seconds',()=>{
 const f=setup({seconds:60});assert(f.button.disabled);assert.match(f.button.textContent,/1:00/);
 f.advance(1000);assert.match(f.button.textContent,/0:59/);assert(f.submit().defaultPrevented);
 f.advance(59000);assert.equal(f.button.disabled,false);assert.equal(f.button.textContent,'Отправить код повторно');
});
test('first valid submit blocks double clicks immediately and stays blocked while request is in flight',()=>{
 const f=setup();assert.equal(f.submit().defaultPrevented,false);assert(f.button.disabled);assert.match(f.button.textContent,/1:00/);
 assert(f.submit().defaultPrevented);f.advance(61000);assert(f.button.disabled);assert.equal(f.button.textContent,'Отправляем код…');
 f.pageEvents.pageshow({persisted:true});assert.equal(f.button.disabled,false);
});
test('invalid form does not start a timer and changing email scopes the old cooldown',()=>{
 const invalid=setup({valid:false});assert(invalid.submit().defaultPrevented);assert.equal(invalid.button.disabled,false);assert(invalid.form.reported);
 const f=setup({seconds:45,withEmail:true});assert(f.button.disabled);f.email.value='different@example.test';f.email.events.input();assert.equal(f.button.disabled,false);f.email.value='ANNA@example.test';f.email.events.input();assert(f.button.disabled);
});
test('password visibility is a non-submit accessible toggle and hides when leaving or returning',()=>{
 const f=setup({password:true}),toggle=f.input.wrapper.children[1];assert.equal(toggle.type,'button');assert.equal(toggle.attrs['aria-controls'],'id_password');
 toggle.events.click();assert.equal(f.input.type,'text');assert.equal(toggle.attrs['aria-pressed'],'true');assert.equal(toggle.textContent,'Скрыть');
 f.pageEvents.pagehide();assert.equal(f.input.type,'password');toggle.events.click();f.pageEvents.pageshow({persisted:true});assert.equal(f.input.type,'password');
});
