const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const {detect,instructions}=require('../../static/install.js');
const iphone='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 ';
const android='Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 ';
test('identifies mobile browsers before generic Chrome and Safari tokens',()=>{
 for(const [ua,browser,ios]of [[iphone+'Version/18.0 Mobile Safari/604.1','safari',true],[iphone+'CriOS/130.0 Mobile Safari/604.1','chrome',true],[iphone+'FxiOS/130 Mobile Safari/604.1','firefox',true],[android+'Chrome/130 YaBrowser/24.1 Mobile Safari/537.36','yandex',false],[android+'Chrome/130 SamsungBrowser/27 Mobile Safari/537.36','samsung',false],[android+'Chrome/130 EdgA/130','edge',false],[android+'Chrome/130 OPR/85','opera',false],[android+'Firefox/130','firefox',false],[android+'Chrome/130 Mobile Safari/537.36','chrome',false],[android+'; wv) Chrome/130','embedded',false],[iphone+'Instagram Safari/604.1','embedded',true]]){
  const device=detect({userAgent:ua});assert.equal(device.browser,browser);assert.equal(device.ios,ios);assert.equal(device.mobile,true);
 }
 assert.equal(detect({userAgent:'Mozilla Macintosh Safari/605',platform:'MacIntel',maxTouchPoints:5}).ios,true);
 assert.equal(detect({userAgent:'Mozilla Windows Chrome/130'}).mobile,false);
});
test('instructions match device and do not send Chrome on iPhone through Android menu',()=>{
 const safari=instructions(detect({userAgent:iphone+'Version/18 Safari/604'}));assert.match(safari.steps.join(' '),/Поделиться/);assert.match(safari.steps.join(' '),/На экран Домой/);
 const chrome=instructions(detect({userAgent:iphone+'CriOS/130 Safari/604'}));assert.match(chrome.steps[0],/справа/);assert.doesNotMatch(chrome.steps.join(' '),/Установить и создать/);
 const embedded=instructions(detect({userAgent:android+'Telegram'}));assert.match(embedded.steps[0],/браузере/);assert.match(embedded.steps[1],/Установить приложение/);
 const firefox=instructions(detect({userAgent:iphone+'FxiOS/130 Safari/604'}));assert.match(firefox.steps[0],/Поделиться/);assert.match(firefox.steps[0],/Firefox/);
 for(const ios of [true,false])for(const browser of ['safari','chrome','firefox','yandex','edge','opera','embedded','other']){
  const info=instructions({ios,android:!ios,browser});assert.doesNotMatch([...info.steps,info.note].join(' '),/скопир|встав|следуйте инструкции/i);
  assert.match(info.steps.join(' '),/экран|Домой|Установить/);
 }
 for(const browser of ['yandex','samsung','chrome','firefox','edge','opera','other'])assert.equal(instructions({android:true,browser}).steps.length,3);
});
function setup({ua=iphone+'Version/18 Safari/604',standalone=false,saved=0,blocked=false,pathName='/app/cards'}={}){
 const el=()=>({hidden:true,open:false,disabled:false,textContent:'',events:{},addEventListener(k,f){this.events[k]=f;},replaceChildren(...items){this.items=items;},getBoundingClientRect(){return {left:0,top:0,right:400,bottom:600};}});
 const keys=['native','status','browser','steps','note'],nodes=Object.fromEntries(keys.map(k=>[`[data-install-${k}]`,el()]));
 const close=el(),dismiss=el(),launcher=el(),banner=el(),dialog=el();dialog.querySelector=k=>nodes[k];dialog.querySelectorAll=()=>[close];dialog.showModal=()=>{dialog.open=true;};dialog.close=()=>{dialog.open=false;dialog.events.close();};banner.querySelector=()=>dismiss;
 const docEvents={},winEvents={},timers=[],storage={'visiooo-install-later':String(saved)},media={matches:standalone,addEventListener:(k,f)=>docEvents[k]=f};
 const document={hidden:false,querySelector:k=>k==='[data-install-dialog]'?dialog:k==='[data-install-banner]'?banner:blocked?{}:null,querySelectorAll:()=>[launcher],createElement:el};
 const window={location:{origin:'https://visiooo.ru',pathname:pathName},matchMedia:()=>media,addEventListener:(k,f)=>winEvents[k]=f};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/install.js'),'utf8'),{document,window,navigator:{userAgent:ua},localStorage:{getItem:k=>storage[k],setItem:(k,v)=>storage[k]=v},Date,URL,setTimeout:(f,ms)=>timers.push({f,ms})});
 return {nodes,close,dismiss,launcher,banner,dialog,winEvents,timers,storage,media,docEvents};
}
test('mobile offer is delayed, dismissal lasts seven days, manual help stays available',()=>{
 const ui=setup();assert(ui.banner.hidden);assert.equal(ui.timers[0].ms,8000);ui.timers[0].f();assert.equal(ui.banner.hidden,false);
 ui.dismiss.events.click();assert(ui.banner.hidden);assert(Number(ui.storage['visiooo-install-later'])>Date.now()+6*86400000);
 ui.launcher.events.click();assert(ui.dialog.open);assert.equal(ui.nodes['[data-install-native]'].hidden,true);assert.match(ui.nodes['[data-install-steps]'].items[0].textContent,/Поделиться/);
 ui.close.events.click();assert.equal(ui.dialog.open,false);
});
test('suppresses automatic prompt on desktop, during editing, after dismissal, and in installed app',()=>{
 for(const settings of [{ua:'Windows Chrome/130'},{pathName:'/app/cards/example/edit'},{saved:Date.now()+86400000},{standalone:true},{blocked:true}]){
  const ui=setup(settings);ui.timers[0].f();assert(ui.banner.hidden);
 }
 const installed=setup({standalone:true});assert(installed.launcher.hidden);
});
test('native install is user initiated, single use, and closes after acceptance',async()=>{
 const ui=setup({ua:android+'Chrome/130'});let calls=0,prevented=false;
 ui.winEvents.beforeinstallprompt({preventDefault(){prevented=true;},async prompt(){calls++;},userChoice:Promise.resolve({outcome:'accepted'})});
 assert(prevented);assert.equal(calls,0);ui.launcher.events.click();assert.equal(ui.nodes['[data-install-native]'].hidden,false);
 await ui.nodes['[data-install-native]'].events.click();assert.equal(calls,1);assert.equal(ui.dialog.open,false);assert(ui.launcher.hidden);
 await ui.nodes['[data-install-native]'].events.click();assert.equal(calls,1);
});
test('dismissed native installation retains manual instructions and installed event removes offer',async()=>{
 const ui=setup({ua:android+'Chrome/130'});
 ui.winEvents.beforeinstallprompt({preventDefault(){},async prompt(){},userChoice:Promise.resolve({outcome:'dismissed'})});ui.launcher.events.click();
 await ui.nodes['[data-install-native]'].events.click();assert(ui.dialog.open);assert(ui.nodes['[data-install-native]'].hidden);assert.match(ui.nodes['[data-install-status]'].textContent,/позже/);
 ui.winEvents.appinstalled();assert(ui.banner.hidden);assert.equal(ui.dialog.open,false);assert(ui.launcher.hidden);
});
