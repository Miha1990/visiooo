const {test}=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');const path=require('node:path');
const CardEmbeds=require('../../static/card-embeds.js');
const WebLinks=require('../../static/web-links.js');
function setup(){
 const fields=Object.fromEntries(['phone_label','email_label','bio','video_url','video_player','video_title','map_address','map_latitude','map_longitude','pdf_label'].map(key=>[key,{value:''}]));
 const examples={phone:{textContent:''},email:{textContent:''}};
 const wrappers=Object.fromEntries(['bio','contacts','socials','carousel','video','document','map'].map(key=>[key,{dataset:{templateHidden:'false'},hidden:false}]));
 const texts={title:{textContent:''},company:{textContent:''},bio:{textContent:''}},actions={childElementCount:0},socials={childElementCount:0};
 const button={disabled:false},small={hidden:false};let removed=0;
 const embed=()=>({dataset:{embedUrl:''},frame:null,querySelector(selector){return selector==='iframe'?this.frame:button;},querySelectorAll:()=>[button,small]});
 const videoEmbed=embed(),mapEmbed=embed(),title={textContent:''},address={textContent:''},link={hidden:false,href:''};
 const video={querySelector:key=>({'[data-video-title]':title,'[data-external-embed]':videoEmbed,'[data-video-link]':link})[key]};
 const map={querySelector:key=>({'[data-map-address]':address,'[data-external-embed]':mapEmbed})[key]};
 const pdf={href:'',getAttribute(){return this.href;},textContent:''};
 let hasSlides=false;
 const card={dataset:{},querySelector(selector){
  if(selector.startsWith('[data-design-block='))return wrappers[selector.match(/"(\w+)"/)[1]];
  if(selector.startsWith('[data-preview='))return texts[selector.match(/"(\w+)"/)[1]];
  return {'.contact-actions':actions,'.social-links':socials,'.carousel-slide':hasSlides?{}:null,'[data-video-block]':video,'[data-map-block]':map,'[data-document-link]':pdf}[selector];
 }};
 const events={},form={elements:{namedItem:key=>fields[key]},addEventListener:(key,fn)=>events[key]=fn};
 const document={getElementById:()=>form,querySelector:selector=>selector.startsWith('[data-button-example=')?examples[selector.match(/"(\w+)"/)[1]]:card};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/client-preview.js'),'utf8'),{document,window:{CardEmbeds,WebLinks,CardWidgets:{refresh(){}}}});
 return {fields,examples,wrappers,texts,actions,socials,pdf,videoEmbed,mapEmbed,title,address,update:()=>events.input(),setSlides(value){hasSlides=value;}};
}
test('button examples show the supplied label and keep markup as plain text',()=>{
 const f=setup();f.fields.phone_label.value='89289091817';f.fields.email_label.value='<b>Write</b>';f.update();
 assert.equal(f.examples.phone.textContent,'89289091817');assert.equal(f.examples.email.textContent,'<b>Write</b>');
 f.fields.phone_label.value='Call';f.update();assert.equal(f.examples.phone.textContent,'Call');
});
test('empty blocks stay hidden, filling and clearing video and address updates visibility',()=>{
 const f=setup();for(const node of Object.values(f.wrappers))assert.equal(node.hidden,true);
 f.fields.video_url.value='https://youtu.be/dQw4w9WgXcQ';f.fields.video_title.value='Моя работа';f.fields.map_address.value='Ростов-на-Дону';f.update();
 assert.equal(f.wrappers.video.hidden,false);assert.equal(f.title.textContent,'Моя работа');assert.match(f.videoEmbed.dataset.embedUrl,/youtube-nocookie/);assert.equal(f.wrappers.map.hidden,false);
 f.fields.video_url.value='';f.fields.map_address.value='';f.update();assert.equal(f.wrappers.video.hidden,true);assert.equal(f.wrappers.map.hidden,true);
});
test('template-hidden blocks cannot be revealed by input and empty PDF is omitted',()=>{
 const f=setup();f.wrappers.video.dataset.templateHidden='true';f.fields.video_url.value='https://youtu.be/dQw4w9WgXcQ';f.update();assert.equal(f.wrappers.video.hidden,true);
 assert.equal(f.wrappers.document.hidden,true);f.pdf.href='/private/document';f.fields.pdf_label.value='Мой прайс';f.update();assert.equal(f.wrappers.document.hidden,false);assert.equal(f.pdf.textContent,'Мой прайс');
 f.setSlides(true);f.actions.childElementCount=1;f.update();assert.equal(f.wrappers.carousel.hidden,false);assert.equal(f.wrappers.contacts.hidden,false);
});
