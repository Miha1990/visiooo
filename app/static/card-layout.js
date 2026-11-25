/* Responsive sizes, bounded to the card width; editor handles never reach public markup. */
(() => {
  const scriptUrl=document.currentScript?.src;
  const states=new WeakMap(),daisies=new WeakMap(),widths=[25,33,50,66,75,100],counts=[1,1.5,2,2.5,3,4];
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
  function orderBlocks(card,state){
    const order=state.layout.order,body=card.querySelector('.contact-body');
    if(order?.length&&body){
      const cover=card.querySelector(':scope>.contact-cover');if(cover)body.prepend(cover);
      const avatar=card.querySelector(':scope>.contact-avatar');if(avatar){const wrap=node('div',{'data-layout-block':'avatar',class:'layout-avatar-wrap'});delete avatar.dataset.layoutBlock;avatar.before(wrap);wrap.append(avatar);body.prepend(wrap);}
      const business=card.querySelector('[data-layout-block="business"]');if(business&&business.parentElement!==body)body.append(business);
      const children=[...body.children],original=new Map(children.map((el,i)=>[el,i])),rank=el=>{const i=order.indexOf(el.dataset.layoutBlock);return i<0?order.length+original.get(el):i;};
      children.sort((a,b)=>rank(a)-rank(b)).forEach((el,index)=>{if(body.children[index]!==el)body.insertBefore(el,body.children[index]||null);});
    }
    const buttons=state.layout.buttonOrder,grid=card.querySelector('.builder-contact-buttons');
    if(buttons?.length&&grid){const children=[...grid.children],original=new Map(children.map((el,i)=>[el,i])),rank=el=>{const i=buttons.indexOf(Number(el.dataset.layoutButton));return i<0?buttons.length+original.get(el):i;};children.sort((a,b)=>rank(a)-rank(b)).forEach((el,index)=>{if(grid.children[index]!==el)grid.insertBefore(el,grid.children[index]||null);});}
  }
  function dimensions(state,key,create=false){const [group,index]=key.split(':');const map=group==='button'?(create?state.layout.buttons??={}:state.layout.buttons):(create?state.layout.blocks??={}:state.layout.blocks);return create?map[index??key]??={}:map?.[index??key]||{};}
  function positionAvatar(card,state){
    const avatar=card.querySelector('.contact-body>[data-layout-block="avatar"]');if(!avatar)return;
    const previous=avatar.previousElementSibling,cover=previous?.dataset.layoutBlock==='cover'&&!previous.hidden?previous:null;
    const composed=['forma','estate'].includes(card.dataset.presetStyle)&&card.dataset.customGeometry!=='true';
    const photo=avatar.querySelector('.contact-avatar:not(.avatar-photo)')||avatar,amount=cover&&!avatar.hidden&&!composed&&card.classList.contains('layout-custom')?state.layout.avatarOverlap??50:0;
    avatar.classList.toggle('avatar-on-cover',amount>0);avatar.style.setProperty('--avatar-overlap',Math.round(photo.getBoundingClientRect().height*amount/100)+'px');
    if(amount>0){const p=photo.getBoundingClientRect(),r=cover.getBoundingClientRect(),previousX=parseFloat(avatar.style.getPropertyValue('--avatar-offset-x'))||0,base=p.left-previousX;avatar.style.setProperty('--avatar-offset-x',Math.round(r.left+Math.max(0,r.width-p.width)*(state.layout.avatarX??50)/100-base)+'px');}else avatar.style.setProperty('--avatar-offset-x','0px');
    if(typeof ResizeObserver==='function'&&!state.avatarObserver){state.avatarObserver=new ResizeObserver(()=>positionAvatar(card,state));state.avatarObserver.observe(photo);state.avatarObserver.observe(avatar);if(cover)state.avatarObserver.observe(cover);}
  }
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
    const toggle=el.querySelector('[data-daisy-toggle]');
    let caption=toggle.querySelector('.daisy-center-label');
    if(!caption){toggle.replaceChildren();const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.setAttribute('class','daisy-center-icon');const path=document.createElementNS('http://www.w3.org/2000/svg','path');path.setAttribute('d','M8 4h11a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2ZM3 8h4M3 13h4M3 18h4M10 18c0-4 7-4 7 0M15.5 10a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z');svg.append(path);caption=node('span',{class:'daisy-center-label'});toggle.append(svg,caption);}
    caption.textContent=data.label||'Контакты';
    const base=new URL('icons/',scriptUrl||location.href);
    for(const item of data.items||[]){const href=window.CardButtons?.href(item,card.dataset.localFileUrl||'');if(!href)continue;
      const a=node('a',{class:'daisy-petal',href,'aria-label':item.label,tabindex:'-1','aria-hidden':'true'});
      if(!href.startsWith('tel:')&&!href.startsWith('mailto:')){a.target='_blank';a.rel='noopener noreferrer';}if(item.kind==='file')a.download='';
      a.append(node('img',{src:new URL(window.CardButtons.icon(item.kind)+'.svg',base).href,width:24,height:24,alt:''}),node('span',{},item.label));list.append(a);
    }
    el.hidden=!list.childElementCount;setupDaisy(el);daisies.get(el)?.set(false);
  }
  function apply(card){
    let state=states.get(card);if(!state){state=read(card);states.set(card,state);}
    const active=Boolean(Object.keys(state.layout.blocks||{}).length||Object.keys(state.layout.buttons||{}).length||state.layout.carousel||state.layout.order?.length||state.layout.buttonOrder?.length);
    card.classList.toggle('layout-custom',active);
    card.dataset.customGeometry=String(Boolean(state.layout.order?.length||Object.keys(state.layout.blocks||{}).length));
    if(active&&card.dataset.canvasEnabled==='true'){card.dataset.previousCanvas='true';card.dataset.canvasEnabled='false';}
    else if(!active&&card.dataset.previousCanvas==='true'){card.dataset.canvasEnabled='true';delete card.dataset.previousCanvas;}
    identify(card);
    orderBlocks(card,state);
    for(const el of identify(card))size(el,dimensions(state,keyFor(el)),el.hasAttribute('data-layout-button'));
    positionAvatar(card,state);
    const carousel=card.querySelector('[data-card-carousel]'),settings=state.layout.carousel;
    if(carousel){carousel.dataset.customSize=String(Boolean(settings));carousel.dataset.photoAspect=settings?.aspect||'custom';if(settings){carousel.dataset.visible=String(settings.visible||1);carousel.style.setProperty('--custom-slide-height',(settings.height||220)+'px');carousel.style.setProperty('--custom-slide-fit',settings.fit||'cover');}window.CardWidgets?.refresh(card);}
    renderDaisy(card,state.daisy);
    state.handles?.();
    card.dispatchEvent(new Event('card:layout-applied'));
  }
  window.CardLayout={refresh:apply,removeButton(form,index){const card=document.querySelector('.phone-preview .contact-card'),state=states.get(card);if(!state)return;const next={};for(const [key,value]of Object.entries(state.layout.buttons||{})){const i=Number(key);if(i!==index)next[i>index?i-1:i]=value;}state.layout.buttons=next;if(state.layout.buttonOrder)state.layout.buttonOrder=state.layout.buttonOrder.filter(i=>i!==index).map(i=>i>index?i-1:i);const input=form.elements.namedItem('layout_data');if(input)input.value=JSON.stringify(state.layout);},setDaisy(card,data){const state=states.get(card)||read(card);state.daisy=data;states.set(card,state);renderDaisy(card,data);}};
  window.CardLayout.get=card=>states.get(card)?.layout||{};
  window.CardLayout.set=(card,layout)=>{const state=states.get(card)||read(card);state.layout=layout;states.set(card,state);apply(card);};
  window.CardLayout.setEditing=(card,value)=>states.get(card)?.setEditing?.(value);
  document.querySelectorAll('.contact-card:has([data-card-layout])').forEach(apply);
  const form=document.getElementById('editor-form'),card=document.querySelector('.phone-preview .contact-card'),editor=document.querySelector('.editor');
  if(!form||!card||!form.elements.namedItem('layout_data'))return;
  const state=states.get(card)||read(card);states.set(card,state);let selected=null,editing=false;
  const input=form.elements.namedItem('layout_data'),tools=node('div',{class:'shape-tools',role:'group','aria-label':'Форма выбранной кнопки',hidden:''});
  const persist=()=>{input.value=JSON.stringify(state.layout);input.dispatchEvent(new Event('input',{bubbles:true}));apply(card);};
  function select(el){selected=el;card.querySelectorAll('.size-selected').forEach(e=>e.classList.remove('size-selected'));el.classList.add('size-selected');tools.hidden=!editing||!el.hasAttribute('data-layout-button');const config=dimensions(state,keyFor(el));tools.querySelectorAll('[data-shape]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.shape===(config.shape||'square'))));
  }
  for(const [shape,label]of [['auto','Прямоугольная кнопка'],['square','Квадратная кнопка'],['circle','Круглая кнопка']]){const button=node('button',{type:'button','data-shape':shape,'aria-label':label,title:label,'aria-pressed':'false'});button.append(node('span',{class:'shape-example shape-example-'+shape,'aria-hidden':'true'}));button.addEventListener('click',()=>{if(!selected||!editing)return;const config=dimensions(state,keyFor(selected),true);config.shape=shape;config.height=shape==='auto'?56:0;if(shape==='auto')config.width=100;persist();select(selected);});tools.append(button);}
  const editButton=node('button',{type:'button','aria-label':'Изменить контакт',title:'Изменить контакт',class:'shape-edit'},'✎');editButton.addEventListener('click',()=>{if(selected&&editing)card.dispatchEvent(new CustomEvent('card:edit-block',{detail:{key:selected.dataset.layoutBlock,index:selected.dataset.layoutButton}}));});tools.append(editButton);
  const copy=node('button',{type:'button','aria-label':'Применить форму и размер ко всем кнопкам',title:'Применить ко всем кнопкам',class:'shape-copy'});copy.append(node('span',{'aria-hidden':'true'},'▦'));copy.addEventListener('click',()=>{if(!selected?.hasAttribute('data-layout-button')||!editing)return;const config={...dimensions(state,keyFor(selected))};state.layout.buttons={};card.querySelectorAll('[data-layout-button]').forEach(el=>state.layout.buttons[el.dataset.layoutButton]={...config});persist();});tools.append(copy);
  editor.querySelector('.preview-column')?.prepend(tools);
  const setEditing=value=>{editing=value;card.classList.toggle('size-editing',value);if(value)state.handles();else{state.cancelResize?.();selected=null;tools.hidden=true;card.querySelectorAll('.size-handle').forEach(e=>e.remove());card.querySelectorAll('[data-saved-href]').forEach(a=>{a.setAttribute('href',a.dataset.savedHref);delete a.dataset.savedHref;});card.querySelectorAll('.size-selected').forEach(e=>e.classList.remove('size-selected'));}};
  state.setEditing=setEditing;
  window.CardLayout.select=(target,el)=>{if(target===card&&editing&&el?.isConnected)select(el);};
  function handle(el,photo=false,direction='se'){
    if(el.querySelector(`:scope>.size-handle[data-resize="${direction}"]`))return;
    const corner=node('span',{class:photo?'size-handle size-photo-handle':'size-handle', 'data-resize':direction,role:'button',tabindex:'0','aria-label':photo?'Изменить размер фотографии карусели':'Изменить размер блока: '+({n:'верх',s:'низ',e:'справа',w:'слева',ne:'верхний правый угол',nw:'верхний левый угол',se:'нижний правый угол',sw:'нижний левый угол'}[direction])});el.append(corner);
    corner.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Enter',' '].includes(event.key))return;event.preventDefault();select(photo?el.closest('[data-layout-block="carousel"]'):el);if(['Enter',' '].includes(event.key))return;const horizontal=event.key==='ArrowLeft'||event.key==='ArrowRight';if(photo){const config=state.layout.carousel??={visible:2.5,height:220,fit:'cover'};if(horizontal)config.visible=counts[clamp(counts.indexOf(config.visible)+(event.key==='ArrowLeft'?1:-1),0,counts.length-1)];else{config.height=clamp((config.height||el.clientHeight)+(event.key==='ArrowUp'?-8:8),80,640);config.aspect='custom';}}else{const config=dimensions(state,keyFor(selected),true);if(horizontal){const i=widths.indexOf(config.width||100);config.width=widths[clamp(i+(event.key==='ArrowLeft'?-1:1),0,5)];}else{config.height=clamp((config.height||selected.clientHeight)+(event.key==='ArrowUp'?-8:8),44,720);config.shape='auto';}}persist();select(selected);});
    corner.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();event.stopPropagation();const target=photo?el.closest('[data-layout-block="carousel"]'):el;select(target);const rect=el.getBoundingClientRect(),parent=el.parentElement.getBoundingClientRect(),startX=event.clientX,startY=event.clientY,before=JSON.parse(JSON.stringify(state.layout));corner.setPointerCapture?.(event.pointerId);
      const move=e=>{if(e.pointerId!==event.pointerId)return;const config=dimensions(state,keyFor(target),true),w=rect.width+(photo||direction.includes('w')?startX-e.clientX:e.clientX-startX),h=rect.height+(direction.includes('n')?startY-e.clientY:e.clientY-startY);if(photo){state.layout.carousel={visible:nearest(counts,(parent.width+10)/(Math.max(44,w)+10)),height:clamp(h,80,640),fit:state.layout.carousel?.fit||'cover',aspect:'custom'};}else{if(/[ew]/.test(direction))config.width=nearest(widths,w/Math.max(1,parent.width)*100);if(/[ns]/.test(direction)){config.height=clamp(h,44,720);config.shape='auto';if(keyFor(target)==='carousel')state.layout.carousel={visible:state.layout.carousel?.visible||2.5,height:clamp(h,80,640),fit:state.layout.carousel?.fit||'cover',aspect:'custom'};}}apply(card);};
      const finish=e=>{if(e.pointerId!==event.pointerId)return;clean();persist();select(target);};
      const clean=()=>{state.cancelResize=null;window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',cancel);};
      const cancel=()=>{clean();state.layout=before;apply(card);};state.cancelResize=cancel;
      window.addEventListener('pointermove',move);window.addEventListener('pointerup',finish);window.addEventListener('pointercancel',cancel,{once:true});
    });
  }
  function radiusHandle(el){
    if(el.querySelector(':scope>.size-radius-handle'))return;const point=node('span',{class:'size-handle size-radius-handle',role:'button',tabindex:'0','data-resize':'radius','aria-label':'Скруглить углы блока',title:'Потяните, чтобы скруглить углы'});el.append(point);
    const change=value=>{const config=dimensions(state,keyFor(el),true);config.radius=clamp(value,0,180);if(config.shape==='circle')config.shape='square';apply(card);};
    point.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();select(el);change((dimensions(state,keyFor(el)).radius??14)+(['ArrowLeft','ArrowDown'].includes(event.key)?-4:4));persist();});
    point.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();event.stopPropagation();select(el);const before=JSON.parse(JSON.stringify(state.layout)),start=event.clientX,radius=dimensions(state,keyFor(el)).radius??14;point.setPointerCapture?.(event.pointerId);
      const move=e=>{if(e.pointerId===event.pointerId)change(radius+e.clientX-start);};
      const clean=()=>{state.cancelResize=null;window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',cancel);};
      const finish=e=>{if(e.pointerId!==event.pointerId)return;clean();persist();select(el);};const cancel=()=>{clean();state.layout=before;apply(card);};state.cancelResize=cancel;window.addEventListener('pointermove',move);window.addEventListener('pointerup',finish);window.addEventListener('pointercancel',cancel,{once:true});
    });
  }
  state.handles=()=>{if(!editing)return;for(const el of identify(card)){if(el.hidden||el.closest('[hidden]'))continue;if(el.matches('a[href]')){el.dataset.savedHref=el.getAttribute('href');el.removeAttribute('href');}for(const direction of ['se','nw','ne','sw','n','s','e','w'])handle(el,false,direction);radiusHandle(el);}const first=card.querySelector('[data-card-carousel] .carousel-slide');if(first)handle(first,true);};
  card.addEventListener('click',event=>{if(!editing||event.target.closest('[data-inline-edit],.block-move-grip'))return;const el=event.target.closest('[data-layout-button],[data-layout-block]');if(el){if(!event.target.closest('[data-daisy-toggle]')){event.preventDefault();event.stopPropagation();}select(el);}},{capture:true});
  form.addEventListener('input',event=>{if(event.target.name==='daisy_data'){try{state.daisy=JSON.parse(event.target.value||'{}');}catch{}}apply(card);});
})();
