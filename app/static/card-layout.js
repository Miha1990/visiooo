/* Responsive sizes, bounded to the card width; editor handles never reach public markup. */
(() => {
  const states=new WeakMap(),daisies=new WeakMap(),widths=[25,33,50,66,75,100],counts=[1,1.5,2,2.5,3,4];
  const labels={cover:'Обложка',logo:'Логотип',avatar:'Фото',identity:'Имя и информация',bio:'О себе',save:'Сохранение контакта',business:'График и статус',contacts:'Контакты',socials:'Соцсети',carousel:'Карусель',video:'Видео',document:'Файл',map:'Карта',daisy:'Ромашка'};
  const node=(tag,attrs={},text)=>{const e=document.createElement(tag);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e;};
  const nearest=(values,n)=>values.reduce((a,b)=>Math.abs(a-n)<=Math.abs(b-n)?a:b);
  const clamp=(n,min,max)=>Math.round(Math.max(min,Math.min(max,n)));
  function read(card){const scripts=card.querySelectorAll('[data-card-layout] script');try{return {layout:JSON.parse(scripts[0]?.textContent||'{}')||{},daisy:JSON.parse(scripts[1]?.textContent||'{}')||{}};}catch{return {layout:{},daisy:{}};}}
  function identify(card){
    card.querySelectorAll('[data-design-block]').forEach(el=>el.dataset.layoutBlock=el.dataset.designBlock);
    const selectors={cover:'.contact-cover',avatar:'.contact-avatar',logo:'.card-logo',bio:'[data-preview="bio"]',save:'.contact-save-group',business:'.work-summary',contacts:'.contact-actions',socials:'.social-section',carousel:'[data-content-block="carousel"]',video:'[data-content-block="video"]',document:'[data-content-block="document"]',map:'[data-content-block="map"]'};
    for(const [key,selector]of Object.entries(selectors)){if(card.querySelector(`[data-layout-block="${key}"]`))continue;const el=card.querySelector(selector);if(el)el.dataset.layoutBlock=key;}
    return [...card.querySelectorAll('[data-layout-block],[data-layout-button]')];
  }
  const keyFor=el=>el.hasAttribute('data-layout-button')?'button:'+el.dataset.layoutButton:el.dataset.layoutBlock;
  function dimensions(state,key,create=false){const [group,index]=key.split(':');const map=group==='button'?(create?state.layout.buttons??={}:state.layout.buttons):(create?state.layout.blocks??={}:state.layout.blocks);return create?map[index??key]??={}:map?.[index??key]||{};}
  function size(el,config,button){
    el.classList.toggle('has-custom-size',Object.keys(config).length>0);
    const span={25:3,33:4,50:6,66:8,75:9,100:12}[config.width]||12;
    el.style.setProperty('--size-span',String(span));if(config.height)el.style.setProperty('--size-height',config.height+'px');else el.style.removeProperty('--size-height');
    el.style.setProperty('--size-radius',(config.shape==='circle'?999:config.radius??(button?14:0))+'px');
    el.dataset.sizeShape=config.shape||'auto';
    el.dataset.sizeWidth=String(config.width|| (button?(Number(el.dataset.layoutButton)<2?50:33):100));
    if(button)el.style.setProperty('--button-span',String(config.width?span:Number(el.dataset.layoutButton)<2?6:4));
  }
  function setupDaisy(el){
    const old=daisies.get(el);if(old){old.position();return;}
    const toggle=el.querySelector('[data-daisy-toggle]');
    const links=()=>[...el.querySelectorAll('.daisy-petal')];
    const position=()=>{const radius=Math.max(60,Math.min(112,el.clientWidth/2-34));links().forEach((a,i)=>{const angle=-Math.PI/2+i*Math.PI*2/Math.max(1,links().length);a.style.setProperty('--petal-x',Math.cos(angle)*radius+'px');a.style.setProperty('--petal-y',Math.sin(angle)*radius+'px');a.style.setProperty('--petal-index',i);});};
    const set=open=>{el.dataset.open=String(open);toggle.setAttribute('aria-expanded',String(open));links().forEach(a=>{a.tabIndex=open?0:-1;a.setAttribute('aria-hidden',String(!open));});};
    toggle.addEventListener('click',()=>set(el.dataset.open!=='true'));
    el.addEventListener('keydown',event=>{if(event.key==='Escape'){set(false);toggle.focus();}});
    document.addEventListener('click',event=>{if(!el.contains(event.target))set(false);});
    const observer=typeof ResizeObserver==='function'?new ResizeObserver(position):null;observer?.observe(el);
    daisies.set(el,{position,set});set(false);position();
  }
  function renderDaisy(card,data){
    const el=card.querySelector('[data-daisy]');if(!el)return;
    const signature=JSON.stringify(data);if(el.dataset.signature===signature){setupDaisy(el);return;}
    el.dataset.signature=signature;const list=el.querySelector('.daisy-petals'),local=list.querySelector('[data-local-file]');if(local)card.dataset.localFileUrl=local.getAttribute('href');list.replaceChildren();
    el.querySelector('[data-daisy-toggle]').textContent=data.label||'Контакты';
    const base=new URL('icons/',document.querySelector('script[src*="card-layout.js"]')?.src||location.href);
    for(const item of data.items||[]){const href=window.CardButtons?.href(item,card.dataset.localFileUrl||'');if(!href)continue;
      const a=node('a',{class:'daisy-petal',href,'aria-label':item.label,tabindex:'-1','aria-hidden':'true'});
      if(!href.startsWith('tel:')&&!href.startsWith('mailto:')){a.target='_blank';a.rel='noopener noreferrer';}if(item.kind==='file')a.download='';
      a.append(node('img',{src:new URL(window.CardButtons.icon(item.kind)+'.svg',base).href,width:24,height:24,alt:''}),node('span',{},item.label));list.append(a);
    }
    el.hidden=!list.childElementCount;setupDaisy(el);daisies.get(el)?.set(false);
  }
  function apply(card){
    let state=states.get(card);if(!state){state=read(card);states.set(card,state);}
    const active=Boolean(Object.keys(state.layout.blocks||{}).length||Object.keys(state.layout.buttons||{}).length||state.layout.carousel);
    card.classList.toggle('layout-custom',active);
    if(active&&card.dataset.canvasEnabled==='true'){card.dataset.previousCanvas='true';card.dataset.canvasEnabled='false';}
    else if(!active&&card.dataset.previousCanvas==='true'){card.dataset.canvasEnabled='true';delete card.dataset.previousCanvas;}
    for(const el of identify(card))size(el,dimensions(state,keyFor(el)),el.hasAttribute('data-layout-button'));
    const carousel=card.querySelector('[data-card-carousel]'),settings=state.layout.carousel;
    if(carousel){carousel.dataset.customSize=String(Boolean(settings));carousel.dataset.photoAspect=settings?.aspect||'custom';if(settings){carousel.dataset.visible=String(settings.visible||1);carousel.style.setProperty('--custom-slide-height',(settings.height||220)+'px');carousel.style.setProperty('--custom-slide-fit',settings.fit||'cover');}window.CardWidgets?.refresh(card);}
    renderDaisy(card,state.daisy);
    state.handles?.();
  }
  window.CardLayout={refresh:apply,removeButton(form,index){const card=document.querySelector('.phone-preview .contact-card'),state=states.get(card);if(!state?.layout.buttons)return;const next={};for(const [key,value]of Object.entries(state.layout.buttons)){const i=Number(key);if(i!==index)next[i>index?i-1:i]=value;}state.layout.buttons=next;const input=form.elements.namedItem('layout_data');if(input)input.value=JSON.stringify(state.layout);},setDaisy(card,data){const state=states.get(card)||read(card);state.daisy=data;states.set(card,state);renderDaisy(card,data);}};
  document.querySelectorAll('.contact-card:has([data-card-layout])').forEach(apply);
  const form=document.getElementById('editor-form'),card=document.querySelector('.phone-preview .contact-card'),editor=document.querySelector('.editor');
  if(!form||!card||!form.elements.namedItem('layout_data'))return;
  const state=states.get(card)||read(card);states.set(card,state);let selected=null,editing=false;
  const input=form.elements.namedItem('layout_data'),panel=node('details',{class:'size-panel',hidden:'','aria-label':'Размеры блоков'}),summary=node('summary',{},'Параметры блока — выберите блок или тяните за угол'),description=node('p',{class:'size-selection','aria-live':'polite'},'Нажмите на блок или потяните за его угол.');
  const createSelect=(label,values)=>{const wrapper=node('label',{},label),select=node('select');for(const [value,text]of values)select.append(node('option',{value},text));wrapper.append(select);panel.append(wrapper);return select;};
  panel.append(summary,description);
  const width=createSelect('Ширина',widths.map(value=>[value,value+'%'])),heightLabel=node('label',{},'Высота, пикс. (0 — по содержимому)'),height=node('input',{type:'number',min:0,max:720,step:1,value:0});heightLabel.append(height);panel.append(heightLabel);
  const shape=createSelect('Форма',[['auto','По размерам'],['square','Квадрат'],['circle','Круг']]),radiusLabel=node('label',{},'Скругление углов'),radius=node('input',{type:'range',min:0,max:180,value:14});radiusLabel.append(radius);panel.append(radiusLabel);
  const visible=createSelect('Фотографий в строке',counts.map(value=>[value,String(value)])),fit=createSelect('Фото',[['cover','Заполнить кадр'],['contain','Показать целиком']]);
  const photoShape=createSelect('Формат фото',[['custom','Свой размер'],['landscape','Горизонтальное 16:9'],['square','Квадрат'],['portrait','Вертикальное 3:4']]);
  const action=(text,fn)=>{const b=node('button',{type:'button'},text);b.addEventListener('click',fn);panel.append(b);return b;};
  const persist=()=>{input.value=JSON.stringify(state.layout);input.dispatchEvent(new Event('input',{bubbles:true}));apply(card);};
  function select(el){selected=el;card.querySelectorAll('.size-selected').forEach(e=>e.classList.remove('size-selected'));el.classList.add('size-selected');const key=keyFor(el),config=dimensions(state,key);description.textContent=key.startsWith('button:')?'Кнопка «'+el.querySelector('span:not(.size-handle)')?.textContent+'»':labels[key]||key;summary.textContent='Параметры: '+description.textContent;
    width.value=String(config.width|| (key.startsWith('button:')?(Number(el.dataset.layoutButton)<2?50:33):100));height.value=String(config.height||0);shape.value=config.shape||'auto';radius.value=String(config.radius??14);
    const isCarousel=key==='carousel';for(const control of [visible,fit,photoShape])control.parentElement.hidden=!isCarousel;visible.value=String(state.layout.carousel?.visible||2.5);fit.value=state.layout.carousel?.fit||'cover';photoShape.value=state.layout.carousel?.aspect||'custom';
  }
  function update(event){if(!selected)return;const config=dimensions(state,keyFor(selected),true);config.width=Number(width.value);config.height=clamp(Number(height.value)||0,0,720);config.shape=shape.value;config.radius=Number(radius.value);if(keyFor(selected)==='carousel'){state.layout.carousel={visible:Number(visible.value),height:clamp(config.height||220,80,640),fit:fit.value,aspect:event?.target===height?'custom':state.layout.carousel?.aspect||'custom'};}persist();select(selected);}
  for(const control of [width,height,shape,radius,visible,fit])control.addEventListener('change',update);
  photoShape.addEventListener('change',()=>{if(!selected)return;const aspect=photoShape.value;state.layout.carousel={visible:Number(visible.value),height:state.layout.carousel?.height||220,fit:fit.value,aspect};if(aspect!=='custom')dimensions(state,keyFor(selected),true).height=0;persist();select(selected);});
  action('Применить размер ко всем контактным кнопкам',()=>{if(!selected?.hasAttribute('data-layout-button')){description.textContent='Сначала выберите контактную кнопку в визитке.';return;}const config={...dimensions(state,keyFor(selected))};state.layout.buttons={};card.querySelectorAll('[data-layout-button]').forEach(el=>state.layout.buttons[el.dataset.layoutButton]={...config});persist();});
  for(const count of [1,2,3,4])action(count+' '+(count===1?'кнопка':'кнопки')+' в ряд',()=>{state.layout.buttons={};card.querySelectorAll('[data-layout-button]').forEach(el=>state.layout.buttons[el.dataset.layoutButton]={width:({1:100,2:50,3:33,4:25})[count],height:count===1?56:0,shape:count===1?'auto':'square',radius:14});persist();});
  action('Сбросить размеры выбранного блока',()=>{if(!selected)return;const key=keyFor(selected);if(key.startsWith('button:'))delete (state.layout.buttons||{})[key.split(':')[1]];else delete (state.layout.blocks||{})[key];if(key==='carousel')delete state.layout.carousel;persist();select(selected);});
  action('Сбросить все размеры',()=>{state.layout={};persist();});
  const toggle=node('button',{type:'button',class:'builder-preview-back','aria-pressed':'false'},'Настроить размеры блоков');
  editor.querySelector('.preview-column')?.prepend(toggle,panel);
  const setEditing=value=>{editing=value;card.classList.toggle('size-editing',value);panel.hidden=!value;toggle.setAttribute('aria-pressed',String(value));toggle.textContent=value?'Готово, посмотреть визитку':'Настроить размеры блоков';if(value)state.handles();else{card.querySelectorAll('.size-handle').forEach(e=>e.remove());card.querySelectorAll('[data-saved-href]').forEach(a=>{a.setAttribute('href',a.dataset.savedHref);delete a.dataset.savedHref;});card.querySelectorAll('.size-selected').forEach(e=>e.classList.remove('size-selected'));}};
  toggle.addEventListener('click',()=>setEditing(!editing));
  function handle(el,photo=false){
    if(el.querySelector(':scope>.size-handle'))return;
    const corner=node('span',{class:photo?'size-handle size-photo-handle':'size-handle',role:'button',tabindex:'0','aria-label':photo?'Изменить размер фотографии карусели':'Изменить размер блока'});el.append(corner);
    corner.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Enter',' '].includes(event.key))return;event.preventDefault();select(photo?el.closest('[data-layout-block="carousel"]'):el);if(['Enter',' '].includes(event.key))return;const horizontal=event.key==='ArrowLeft'||event.key==='ArrowRight';if(photo){const config=state.layout.carousel??={visible:2.5,height:220,fit:'cover'};if(horizontal)config.visible=counts[clamp(counts.indexOf(config.visible)+(event.key==='ArrowLeft'?1:-1),0,counts.length-1)];else{config.height=clamp((config.height||el.clientHeight)+(event.key==='ArrowUp'?-8:8),80,640);config.aspect='custom';}}else{const config=dimensions(state,keyFor(selected),true);if(horizontal){const i=widths.indexOf(config.width||100);config.width=widths[clamp(i+(event.key==='ArrowLeft'?-1:1),0,5)];}else{config.height=clamp((config.height||selected.clientHeight)+(event.key==='ArrowUp'?-8:8),44,720);config.shape='auto';}}persist();select(selected);});
    corner.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();event.stopPropagation();const target=photo?el.closest('[data-layout-block="carousel"]'):el;select(target);const rect=el.getBoundingClientRect(),parent=el.parentElement.getBoundingClientRect(),startX=event.clientX,startY=event.clientY,before=JSON.parse(JSON.stringify(state.layout));corner.setPointerCapture?.(event.pointerId);
      const move=e=>{const config=dimensions(state,keyFor(target),true),w=rect.width+(photo?startX-e.clientX:e.clientX-startX),h=rect.height+e.clientY-startY;if(photo){state.layout.carousel={visible:nearest(counts,(parent.width+10)/(Math.max(44,w)+10)),height:clamp(h,80,640),fit:state.layout.carousel?.fit||'cover'};}else{config.width=nearest(widths,w/Math.max(1,parent.width)*100);config.height=clamp(h,44,720);config.shape='auto';if(keyFor(target)==='carousel')state.layout.carousel={visible:state.layout.carousel?.visible||2.5,height:clamp(h,80,640),fit:state.layout.carousel?.fit||'cover'};}apply(card);};
      const finish=e=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',cancel);persist();select(target);};
      const cancel=()=>{state.layout=before;apply(card);window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',cancel);};
      window.addEventListener('pointermove',move);window.addEventListener('pointerup',finish,{once:true});window.addEventListener('pointercancel',cancel,{once:true});
    });
  }
  state.handles=()=>{if(!editing)return;for(const el of identify(card)){if(el.hidden||el.closest('[hidden]'))continue;if(el.matches('a[href]')){el.dataset.savedHref=el.getAttribute('href');el.removeAttribute('href');}handle(el);}const first=card.querySelector('[data-card-carousel] .carousel-slide');if(first)handle(first,true);};
  card.addEventListener('click',event=>{if(!editing)return;const el=event.target.closest('[data-layout-button],[data-layout-block]');if(el){if(!event.target.closest('[data-daisy-toggle]')){event.preventDefault();event.stopPropagation();}select(el);}},{capture:true});
  form.addEventListener('input',event=>{if(event.target.name==='daisy_data'){try{state.daisy=JSON.parse(event.target.value||'{}');}catch{}}apply(card);});
})();
