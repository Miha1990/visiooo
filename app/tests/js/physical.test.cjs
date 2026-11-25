const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function setup({supported=false,saved={}}={}){
  const el=(dataset={})=>({dataset,hidden:true,disabled:false,checked:false,textContent:'',handlers:{},setAttribute(key,value){this[key]=value;},addEventListener(key,fn){this.handlers[key]=fn;},focus(){this.focused=true;}});
  const phones=[el({phone:'iphone'}),el({phone:'android'})],methods=[el({bindMethod:'qr'}),el({bindMethod:'nfc'})];
  const sections=Object.fromEntries(['android-methods','guide-qr','guide-nfc','physical-qr','physical-nfc'].map(key=>[`[data-${key}]`,[el()]]));
  const guide={querySelectorAll:selector=>selector==='[data-phone]'?phones:methods};
  const ids={'nfc-write':el({url:'https://visiooo.ru/p/example',localOnly:'false'}),'nfc-status':el(),'nfc-write-consent':el(),'nfc-cancel':el()};
  const writes=[];
  const window={isSecureContext:true,addEventListener(){}};
  if(supported)window.NDEFReader=class{async write(...args){writes.push(args);}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/physical.js'),'utf8'),{window,document:{querySelector:()=>guide,querySelectorAll:selector=>sections[selector]||[],getElementById:id=>ids[id]},sessionStorage:{getItem:key=>saved[key],setItem:(key,value)=>saved[key]=value},AbortController,setTimeout,clearTimeout});
  return {phones,methods,ids,writes,saved,visible:key=>!sections[`[data-${key}]`][0].hidden};
}
test('iPhone shows QR only, Android offers both methods',()=>{
  const ui=setup();ui.phones[0].handlers.click();
  assert.equal(ui.visible('guide-qr'),true);assert.equal(ui.visible('physical-qr'),true);
  assert.equal(ui.visible('android-methods'),false);assert.equal(ui.visible('physical-nfc'),false);
  ui.phones[1].handlers.click();assert.equal(ui.visible('android-methods'),true);
  ui.methods[1].handlers.click();assert.equal(ui.visible('physical-nfc'),true);assert.equal(ui.visible('physical-qr'),false);
  assert.match(ui.ids['nfc-status'].textContent,/Chrome/);assert.equal(ui.ids['nfc-write'].disabled,true);
  ui.phones[0].handlers.click();assert.equal(ui.visible('physical-nfc'),false);assert.equal(ui.saved['physical-method'],'qr');
});
test('restores device preference and writes NFC only with consent on Android',async()=>{
  const ui=setup({supported:true,saved:{'physical-phone':'android','physical-method':'nfc'}});
  assert.equal(ui.visible('physical-nfc'),true);
  await ui.ids['nfc-write'].handlers.click();assert.equal(ui.writes.length,0);assert.equal(ui.ids['nfc-write-consent'].focused,true);
  ui.ids['nfc-write-consent'].checked=true;
  await ui.ids['nfc-write'].handlers.click();assert.equal(ui.writes.length,1);
  assert.equal(ui.writes[0][0].records[0].data,'https://visiooo.ru/p/example');
  ui.phones[0].handlers.click();await ui.ids['nfc-write'].handlers.click();assert.equal(ui.writes.length,1);
});
