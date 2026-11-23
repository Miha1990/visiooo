const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../../static/client-editor.js'),'utf8');
function setup(reply){
 const group={tagName:'DETAILS',open:false,parentElement:null};
 const name={value:'Анна',type:'text',parentElement:group,setCustomValidity(v){this.validityMessage=v;},focus(){this.focused=true;}};
 const version={value:'1'},uploadVersion={value:'1'},events={},windowEvents={};let calls=0,submissions=0,notice=null;
 const form={action:'/edit',elements:{namedItem:key=>({name,draft_version:version})[key]},addEventListener:(key,fn)=>events[key]=fn,
  querySelector:()=>notice,prepend:node=>notice=node,checkValidity:()=>true,inert:false};
 const button={disabled:false};
 const upload={addEventListener:(key,fn)=>upload[key]=fn,requestSubmit(submitter){submissions++;upload.submit({submitter,preventDefault(){throw Error('Approved native submission must proceed');}});}};
 const editor={querySelectorAll:selector=>selector.startsWith('input')?[version,uploadVersion]:[upload]};form.closest=()=>editor;
 class FormData{constructor(){this.entries=[['name',name.value],['draft_version',version.value]];}[Symbol.iterator](){return this.entries[Symbol.iterator]();}}
 const document={getElementById:()=>form,createElement:()=>({dataset:{},setAttribute(){},scrollIntoView(){}})};
 const window={addEventListener:(key,fn)=>windowEvents[key]=fn};
 vm.runInNewContext(source,{document,window,FormData,WeakSet,location:{href:'/edit'},fetch:async()=>{calls++;return reply();}});
 const submit=()=>{let prevented=false;const promise=upload.submit({submitter:button,preventDefault(){prevented=true;}});return {promise,get prevented(){return prevented;}};};
 return {form,name,version,uploadVersion,button,group,submit,windowEvents,get calls(){return calls;},get submissions(){return submissions;},get notice(){return notice;}};
}
test('upload waits for text save and submits with the returned draft version',async()=>{
 let resolve;const f=setup(()=>new Promise(r=>resolve=r));f.name.value='Новый клиент';
 const action=f.submit();assert.equal(action.prevented,true);assert.equal(f.submissions,0);assert.equal(f.form.inert,true);
 resolve({ok:true,json:async()=>({version:2})});await action.promise;
 assert.equal(f.calls,1);assert.equal(f.submissions,1);assert.equal(f.version.value,2);assert.equal(f.uploadVersion.value,2);assert.equal(f.form.inert,false);
});
test('validation failure keeps entered data and file upload pending',async()=>{
 const f=setup(()=>({ok:false,json:async()=>({errors:{name:[{message:'Исправьте имя'}]}})}));f.name.value='Новый клиент';
 await f.submit().promise;
 assert.equal(f.submissions,0);assert.equal(f.name.value,'Новый клиент');assert.equal(f.name.validityMessage,'Исправьте имя');assert.equal(f.group.open,true);assert.equal(f.name.focused,true);
 assert.equal(f.button.disabled,false);assert.equal(f.version.value,'1');
});
test('unchanged content uploads directly, while unsaved navigation is guarded',async()=>{
 const f=setup(()=>{throw Error('No save needed');});await f.submit().promise;assert.equal(f.calls,0);
 const g=setup(()=>{});g.name.value='Изменено';let blocked=false;g.windowEvents.beforeunload({preventDefault(){blocked=true;}});assert.equal(blocked,true);
});
