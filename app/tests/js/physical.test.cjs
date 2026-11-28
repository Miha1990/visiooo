const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function setup({supported=false,secure=true,localOnly=false,storageBlocked=false,saved={},withWriter=true}={}){
  const el=(dataset={})=>({dataset,hidden:true,disabled:false,checked:false,textContent:'',handlers:{},setAttribute(key,value){this[key]=value;},addEventListener(key,fn){this.handlers[key]=fn;},focus(){this.focused=true;}});
  const methods=[el({bindMethod:'qr'}),el({bindMethod:'nfc'})];
  const sections=Object.fromEntries(['nfc-methods','guide-qr','guide-nfc','physical-qr','physical-nfc'].map(key=>[`[data-${key}]`,[el()]]));
  const capability=el(),guide={dataset:{localOnly:String(localOnly)},querySelector:()=>capability,querySelectorAll:()=>methods};
  const ids={'nfc-write':el({url:'https://visiooo.ru/p/example',localOnly:String(localOnly)}),'nfc-status':el(),'nfc-write-consent':el(),'nfc-cancel':el()};
  const writes=[];
  const window={isSecureContext:secure,addEventListener(){}};
  if(supported)window.NDEFReader=class{async write(...args){writes.push(args);}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/physical.js'),'utf8'),{window,document:{querySelector:()=>guide,querySelectorAll:selector=>sections[selector]||[],getElementById:id=>!withWriter&&id==='nfc-write'?null:ids[id]},sessionStorage:{getItem:key=>{if(storageBlocked)throw Error('Blocked');return saved[key];},setItem:(key,value)=>{if(storageBlocked)throw Error('Blocked');saved[key]=value;}},AbortController,setTimeout,clearTimeout});
  return {methods,ids,writes,saved,capability,visible:key=>!sections[`[data-${key}]`][0].hidden};
}

test('unsupported browsers automatically show QR without asking for a phone type',()=>{
 const ui=setup();
 assert.equal(ui.visible('guide-qr'),true);assert.equal(ui.visible('physical-qr'),true);
 assert.equal(ui.visible('nfc-methods'),false);assert.equal(ui.visible('physical-nfc'),false);
 assert.equal(ui.methods[1].disabled,true);assert.equal(ui.ids['nfc-write'].disabled,true);
 ui.methods[1].handlers.click();assert.equal(ui.visible('physical-nfc'),false);
});

test('supported browsers automatically offer NFC and allow choosing QR',()=>{
 const ui=setup({supported:true});
 assert.equal(ui.visible('physical-nfc'),true);assert.equal(ui.visible('nfc-methods'),true);
 assert.equal(ui.ids['nfc-write'].disabled,false);assert.equal(ui.writes.length,0);
 ui.methods[0].handlers.click();assert.equal(ui.visible('physical-qr'),true);assert.equal(ui.visible('physical-nfc'),false);
 assert.equal(ui.saved['physical-method'],'qr');
});

test('insecure pages and local-only links fall back to QR even with the API present',()=>{
 for(const options of [{secure:false},{localOnly:true}]){
  const ui=setup({supported:true,...options});
  assert.equal(ui.visible('physical-qr'),true);assert.equal(ui.visible('physical-nfc'),false);assert.equal(ui.ids['nfc-write'].disabled,true);
 }
});

test('stale NFC preferences cannot enable unsupported features',()=>{
 const ui=setup({saved:{'physical-phone':'android','physical-method':'nfc'}});
 assert.equal(ui.visible('physical-qr'),true);assert.equal(ui.visible('physical-nfc'),false);
 const preferred=setup({supported:true,saved:{'physical-method':'qr'}});
 assert.equal(preferred.visible('physical-qr'),true);
});

test('blocked browser storage still initializes a usable interface on create and edit pages',()=>{
 for(const withWriter of [false,true]){
  assert.equal(setup({storageBlocked:true,withWriter}).visible('guide-qr'),true);
  assert.equal(setup({supported:true,storageBlocked:true,withWriter}).visible('guide-nfc'),true);
 }
});

test('NFC writing still requires consent and an explicit button press',async()=>{
 const ui=setup({supported:true});assert.equal(ui.writes.length,0);
 await ui.ids['nfc-write'].handlers.click();assert.equal(ui.writes.length,0);assert.equal(ui.ids['nfc-write-consent'].focused,true);
 ui.ids['nfc-write-consent'].checked=true;await ui.ids['nfc-write'].handlers.click();assert.equal(ui.writes.length,1);
 assert.equal(ui.writes[0][0].records[0].data,'https://visiooo.ru/p/example');
 ui.methods[0].handlers.click();await ui.ids['nfc-write'].handlers.click();assert.equal(ui.writes.length,1);
});
