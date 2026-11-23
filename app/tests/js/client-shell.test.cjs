const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../../static/client-shell.js'),'utf8');
function setup(navigator={}, modal=true, portrait=null){
 const qr={open:false,addEventListener(){},showModal(){this.open=true;}};
 if(!modal)delete qr.showModal;
 const shareDialog={open:false,addEventListener(){},showModal(){this.open=true;}};
 const button={disabled:false,dataset:{url:'https://example.test/c/own',title:'My card'},addEventListener:(name,fn)=>button[name]=fn};
 const link={addEventListener:(name,fn)=>link[name]=fn};
 const input={focus(){this.focused=true;},select(){this.selected=true;}};
 const status={textContent:''};
 const document={querySelector:selector=>({'[data-owner-portrait]':portrait,'[data-qr-dialog]':qr,'[data-share-dialog]':shareDialog,'#client-share-url':input,'[data-client-share-status]':status})[selector],
  querySelectorAll:selector=>({'[data-open-qr]':[link],'.client-dialog':[qr,shareDialog],'[data-client-share]':[button]})[selector]||[]};
 vm.runInNewContext(source,{document,navigator});
 return {qr,button,link,shareDialog,input,status};
}
test('QR opens in a dialog while unsupported browsers keep the direct image link',()=>{
 const f=setup();let prevented=false;f.link.click({preventDefault(){prevented=true;}});
 assert.equal(prevented,true);assert.equal(f.qr.open,true);
 const legacy=setup({},false);legacy.link.click({preventDefault(){throw Error('Do not intercept fallback link');}});
});

test('owner QR action flips the portrait without opening a modal or dark backdrop',()=>{
 let clicks=0,scrolls=0;const portrait={click(){clicks++;},scrollIntoView(){scrolls++;}};
 const f=setup({},true,portrait);
 f.link.click({preventDefault(){}});f.link.click({preventDefault(){}});
 assert.equal(clicks,2);assert.equal(scrolls,2);assert.equal(f.qr.open,false);
});
test('canceling native share does not copy the link or open a fallback',async()=>{
 const f=setup({share:async()=>{throw {name:'AbortError'};},clipboard:{writeText(){throw Error('Unexpected copy');}}});
 await f.button.click();assert.equal(f.button.disabled,false);assert.equal(f.shareDialog.open,false);
});
test('clipboard failures expose a selected link for manual copying',async()=>{
 const f=setup({clipboard:{writeText:async()=>{throw Error('Denied');}}});
 await f.button.click();assert.equal(f.shareDialog.open,true);assert.equal(f.input.selected,true);assert.equal(f.button.disabled,false);
});
test('share sends the selected card URL and prevents duplicate requests',async()=>{
 let resolve,calls=0;const f=setup({share:data=>{calls++;assert.equal(data.url,'https://example.test/c/own');return new Promise(r=>resolve=r);}});
 const first=f.button.click();await f.button.click();assert.equal(calls,1);resolve();await first;assert.equal(f.button.disabled,false);
});
