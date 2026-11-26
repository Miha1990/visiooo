const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
function setup({width=390,height=844,visualHeight=844,top=0,scale=1,typing=false,api=true}={}){
 const values={},classes=new Set(),events={},frames=[];
 const root={style:{setProperty:(k,v)=>values[k]=v,removeProperty:k=>delete values[k]},classList:{remove:k=>classes.delete(k),toggle:(k,on)=>on?classes.add(k):classes.delete(k)}};
 const document={documentElement:root,activeElement:{matches:()=>typing},addEventListener:(k,f)=>events[k]=f};
 const viewport={height:visualHeight,offsetTop:top,scale,addEventListener:(k,f)=>events['visual-'+k]=f};
 const window={innerWidth:width,innerHeight:height,visualViewport:api?viewport:undefined,addEventListener:(k,f)=>events['window-'+k]=f};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/mobile-viewport.js'),'utf8'),{document,window,requestAnimationFrame:f=>{frames.push(f);return frames.length;}});
 return {values,classes,events,frames,window,viewport,document};
}
test('records actual visible viewport and marks keyboard only while typing',()=>{
 const ui=setup({visualHeight:440,top:70,typing:true});assert.equal(ui.values['--mobile-viewport-height'],'440px');assert.equal(ui.values['--mobile-viewport-top'],'70px');assert(ui.classes.has('keyboard-open'));
 ui.document.activeElement.matches=()=>false;ui.events.focusout();ui.frames.pop()();assert(!ui.classes.has('keyboard-open'));
});
test('pinch zoom and browser controls do not count as an open keyboard',()=>{
 assert(!setup({visualHeight:720,typing:true}).classes.has('keyboard-open'));
 assert(!setup({visualHeight:400,scale:2,typing:true}).classes.has('keyboard-open'));
 assert(!setup({visualHeight:400}).classes.has('keyboard-open'));
});
test('resizing to desktop clears mobile geometry and handles missing viewport API',()=>{
 const ui=setup({typing:true,visualHeight:440});ui.window.innerWidth=1280;ui.events['window-resize']();ui.events['window-resize']();assert.equal(ui.frames.length,1);ui.frames.pop()();assert.deepEqual(ui.values,{});assert(!ui.classes.has('keyboard-open'));
 const fallback=setup({api:false});assert.equal(fallback.values['--mobile-viewport-height'],'844px');assert(!fallback.classes.has('keyboard-open'));
});
