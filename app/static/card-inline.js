/* Edit existing card blocks, with pointer/keyboard ordering and deletion. */
(() => {
  const editor=document.querySelector('.card-builder-active'),form=document.getElementById('editor-form'),api=window.CardBuilder,layout=window.CardLayout;
  if(!editor||!form||!api||!layout)return;
  const preview=editor.querySelector('.phone-preview'),card=preview?.querySelector('.contact-card');if(!card)return;
  const labels={cover:'Обложка',avatar:'Фото',identity:'Информация о себе',bio:'О себе',save:'Сохранение контакта',business:'График и статус',contacts:'Контакты',socials:'Соцсети',carousel:'Карусель',video:'Видео',document:'Файл',map:'Адрес',daisy:'Ромашка'};
  const node=(tag,attrs={},text)=>{const el=document.createElement(tag);for(const [k,v]of Object.entries(attrs))el.setAttribute(k,v);if(text!==undefined)el.textContent=text;return el;};
  const host=node('section',{class:'inline-card-host','aria-label':'Редактирование блоков визитки'}),actions=node('div',{class:'inline-media-actions'}),status=node('p',{class:'inline-order-status',role:'status','aria-live':'polite'});
  const upload=slot=>editor.querySelector(`[data-image-slot="${slot}"] input[type=file],.builder-image-${slot} input[type=file]`);
  for(const [slot,title]of [['logo','Лого'],['header','Обложка']]){if(!upload(slot)||!editor.querySelector('.builder-image-'+slot+' img'))continue;const button=node('button',{type:'button','data-inline-media':slot,'aria-label':'Изменить '+title},'Изменить '+title);button.addEventListener('click',event=>{event.stopPropagation();upload(slot)?.click();});actions.append(button);}
  const cover=card.querySelector('.contact-cover'),coverBlock=cover?.closest('[data-layout-block="cover"]')||cover,photo=card.querySelector('.contact-avatar:not(.avatar-photo)'),avatarBlock=photo?.closest('[data-layout-block="avatar"]')||photo;
  const coverWasHidden=Boolean(coverBlock?.hidden),avatarWasHidden=Boolean(avatarBlock?.hidden);
  const photoEdit=node('button',{type:'button',class:'inline-avatar-edit','data-inline-media':'avatar','aria-label':'Изменить фото',title:'Изменить фото'});
  photoEdit.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m16 3 5 5M4 15 16 3a2 2 0 0 1 3 0l2 2a2 2 0 0 1 0 3L9 20l-6 1z"/></svg>';
  photoEdit.addEventListener('click',event=>{event.stopPropagation();upload('avatar')?.click();});
  if(cover)cover.append(actions);if(photo&&upload('avatar'))card.append(photoEdit);
  function mediaControls(editing){
    actions.hidden=!editing;photoEdit.hidden=!editing;
    for(const [block,wasHidden]of [[coverBlock,coverWasHidden],[avatarBlock,avatarWasHidden]])if(block&&wasHidden&&block.dataset.templateHidden!=='true')block.hidden=true;
    if(!photo||!photoEdit.isConnected)return;
    photoEdit.hidden=!editing||Boolean(photo.closest('[hidden]'));
    const bounds=card.getBoundingClientRect(),rect=photo.getBoundingClientRect(),scale=bounds.width/Math.max(1,card.offsetWidth);
    photoEdit.style.left=((rect.right-bounds.left)/scale)+'px';photoEdit.style.top=((rect.bottom-bounds.top)/scale)+'px';
  }
  if(typeof ResizeObserver==='function'&&photo){const observer=new ResizeObserver(()=>mediaControls(editor.dataset.view!=='preview'));observer.observe(photo);observer.observe(card);}
  const tools=editor.querySelector('.shape-tools');
  const modes=node('div',{class:'inline-editor-modes',role:'group','aria-label':'Режим редактирования'});
  editor.dataset.editMode='simple';
  const advanced=()=>editor.dataset.editMode==='advanced';
  for(const [mode,label]of [['simple','Простой'],['advanced','Продвинутый']]){const button=node('button',{type:'button','data-edit-mode':mode,'aria-pressed':String(mode==='simple')},label);button.addEventListener('click',()=>{endGesture();suppressClickUntil=0;editor.dataset.editMode=mode;status.textContent='';sync();});modes.append(button);}
  host.append(modes);if(tools)host.append(tools);host.append(preview,status);form.prepend(host);editor.classList.add('inline-builder');
  let syncing=false;
  const input=name=>form.elements.namedItem(name),value=name=>input(name)?.value.trim()||'';
  function hasContent(key){if(api.isRemoved(key))return false;if(key==='carousel')return Boolean(card.querySelector('.carousel-slide'));if(key==='video')return Boolean(window.CardVideos?.fromForm(form).length);if(key==='business')return Boolean(value('work_status')||Array.from({length:7},(_,day)=>value(`work_${day}_open`)&&value(`work_${day}_close`)).some(Boolean));if(key==='map')return Boolean(value('map_address'));if(key==='daisy'){try{return (JSON.parse(input('daisy_data').value||'{}').items||[]).length>0;}catch{return false;}}return true;}
  function persist(){const source=input('layout_data');source.value=JSON.stringify(layout.get(card));source.dispatchEvent(new Event('input',{bubbles:true}));}
  function insert(key){const config=layout.get(card);const known=['cover','avatar','identity','bio','business','save','contacts','socials','carousel','video','document','map','daisy'];config.order=config.order||known.filter(item=>card.querySelector(`[data-layout-block="${item}"]:not([hidden])`));if(!config.order.includes(key))config.order.push(key);layout.set(card,config);persist();sync();}
  function placeholders(){
    for(const key of ['carousel','video','map','daisy','business','document']){
      const block=card.querySelector(`[data-layout-block="${key}"]`);
      if(block&&!hasContent(key))block.hidden=true;
    }
    const grid=card.querySelector('.contact-actions');
    grid?.querySelectorAll('[data-empty-contact]').forEach(el=>el.remove());
    if(grid&&!grid.querySelector('[data-layout-button]')){grid.hidden=true;const wrapper=grid.closest('[data-design-block="contacts"]');if(wrapper)wrapper.hidden=true;}
  }
  function edit(key,index){if(index!==undefined)api.choose('all',Number(index));else if(['identity','bio'].includes(key))api.profile();else if(['cover','avatar','logo'].includes(key))editor.querySelector(`.builder-image-${key==='cover'?'header':key} input[type=file]`)?.click();else if(key==='daisy')api.daisy();else if(['carousel','video','map','document'].includes(key))api.openMedia(key);else if(key==='business')api.features();else api.choose();}
  card.addEventListener('card:edit-block',event=>edit(event.detail.key,event.detail.index));
  function keyFor(el){return el.hasAttribute('data-layout-button')?'button:'+el.dataset.layoutButton:el.dataset.layoutBlock;}
  function peers(el){return el.hasAttribute('data-layout-button')?[...el.parentElement.querySelectorAll(':scope>[data-layout-button]')]:[...card.querySelectorAll(':scope>[data-layout-block="cover"],:scope>[data-layout-block="avatar"],.contact-body>[data-layout-block]')];}
  function reorder(el,target,after,overlap=50,avatarX=50){
    const isButton=el.hasAttribute('data-layout-button');if(!target||isButton!==target.hasAttribute('data-layout-button'))return;const list=peers(el);if(!list.includes(target)||el===target)return;
    const keys=list.map(keyFor),key=keyFor(el),onCover=key==='avatar'&&keyFor(target)==='cover';keys.splice(keys.indexOf(key),1);keys.splice(keys.indexOf(keyFor(target))+(onCover||after?1:0),0,key);
    const config=layout.get(card);if(isButton)config.buttonOrder=keys.map(key=>Number(key.split(':')[1]));else{config.order=keys;if(key==='avatar'){config.avatarOverlap=onCover?overlap:0;if(onCover)config.avatarX=avatarX;}}
    layout.set(card,config);persist();status.textContent=onCover?'Фото наложено на обложку. Сохраните визитку.':'Порядок блоков изменён. Сохраните визитку.';
  }
  // Touch listeners let a normal swipe scroll, but keep the held gesture in the editor.
  let gesture=null,suppressClickUntil=0;
  const clearDrop=()=>card.querySelectorAll('.block-drop-target').forEach(el=>el.classList.remove('block-drop-target'));
  function endGesture(commit=false){
    const g=gesture;if(!g)return;gesture=null;clearTimeout(g.timer);cancelAnimationFrame(g.frame);clearDrop();g.el.classList.remove('block-moving');g.el.style.removeProperty('translate');card.classList.remove('block-dragging');
    if(g.active){suppressClickUntil=Date.now()+500;if(commit&&g.target)reorder(g.el,g.target,g.after,g.overlap,g.avatarX);const current=g.key.startsWith('button:')?card.querySelector(`[data-layout-button="${g.key.slice(7)}"]`):card.querySelector(`[data-layout-block="${g.key}"]`);layout.select(card,current);if(!commit||!g.target)status.textContent='Блок выбран. Тяните за края, чтобы изменить размер.';}
  }
  function locate(g){clearDrop();const list=peers(g.el);g.target=document.elementsFromPoint(g.x,g.y).map(el=>el.closest('[data-layout-button],[data-layout-block]')).find(el=>el&&el!==g.el&&list.includes(el))||null;if(g.target){const r=g.target.getBoundingClientRect();g.after=g.el.hasAttribute('data-layout-button')?g.x>r.x+r.width/2:g.y>r.y+r.height/2;if(g.key==='avatar'&&keyFor(g.target)==='cover'){const photo=g.el.querySelector('.contact-avatar:not(.avatar-photo)')||g.el,p=photo.getBoundingClientRect(),h=p.height||88;g.overlap=Math.round(Math.max(10,Math.min(100,(r.bottom-g.y+h/2)/h*100)));g.avatarX=Math.round(Math.max(0,Math.min(100,(g.x-r.left-p.width/2)/Math.max(1,r.width-p.width)*100)));}g.target.classList.add('block-drop-target');g.target.dataset.dropSide=g.after?'after':'before';}}
  function dragFrame(){const g=gesture;if(!g?.active)return;const speed=g.y<90?-10:g.y>innerHeight-90?10:0;if(speed)window.scrollBy({top:speed,behavior:'instant'});const bounds=card.getBoundingClientRect(),r=g.photoRect||g.rect,dx=Math.max(bounds.left-r.left,Math.min(bounds.right-r.right,g.x-g.startX));g.el.style.translate=`${dx}px ${g.y-g.startY+window.scrollY-g.scrollY}px`;locate(g);g.frame=requestAnimationFrame(dragFrame);}
  function beginGesture(event,x,y,id,touch){
    if(!advanced()||editor.dataset.view==='preview'||event.target.closest('.size-handle,.inline-edit-block,.inline-remove-block,.block-move-grip,input,textarea,select,[data-empty-contact],[data-inline-media]'))return;
    const el=event.target.closest('[data-layout-button],[data-layout-block]');if(!el||!peers(el).includes(el))return;endGesture();
    const g=gesture={el,key:keyFor(el),startX:x,startY:y,x,y,id,touch,active:false,target:null};
    g.timer=setTimeout(()=>{if(gesture!==g||!el.isConnected)return;g.active=true;g.rect=el.getBoundingClientRect();if(g.key==='avatar')g.photoRect=(el.querySelector('.contact-avatar:not(.avatar-photo)')||el).getBoundingClientRect();g.scrollY=window.scrollY;layout.select(card,el);el.classList.add('block-moving');card.classList.add('block-dragging');navigator.vibrate?.(15);status.textContent='Перетаскивайте блок на нужное место.';g.frame=requestAnimationFrame(dragFrame);},450);
  }
  function moveGesture(event,x,y){const g=gesture;if(!g)return;g.x=x;g.y=y;if(!g.active){if(Math.hypot(x-g.startX,y-g.startY)>8)endGesture();return;}if(event.cancelable)event.preventDefault();locate(g);}
  card.addEventListener('touchstart',event=>{if(event.touches.length!==1){endGesture();return;}const t=event.touches[0];beginGesture(event,t.clientX,t.clientY,t.identifier,true);},{passive:true});
  window.addEventListener('touchmove',event=>{if(!gesture?.touch)return;if(event.touches.length!==1){endGesture();return;}const t=[...event.touches].find(t=>t.identifier===gesture.id);if(t)moveGesture(event,t.clientX,t.clientY);},{passive:false});
  window.addEventListener('touchend',event=>{if(gesture?.touch&&[...event.changedTouches].some(t=>t.identifier===gesture.id))endGesture(true);});
  window.addEventListener('touchcancel',()=>endGesture());
  card.addEventListener('pointerdown',event=>{if(event.pointerType!=='touch'&&event.button===0)beginGesture(event,event.clientX,event.clientY,event.pointerId,false);});
  window.addEventListener('pointermove',event=>{if(gesture&&!gesture.touch&&gesture.id===event.pointerId)moveGesture(event,event.clientX,event.clientY);});
  window.addEventListener('pointerup',event=>{if(gesture&&!gesture.touch&&gesture.id===event.pointerId)endGesture(true);});
  window.addEventListener('pointercancel',event=>{if(gesture&&!gesture.touch&&gesture.id===event.pointerId)endGesture();});
  window.addEventListener('blur',()=>endGesture());window.addEventListener('pagehide',()=>endGesture());
  window.addEventListener('scroll',()=>{if(gesture&&!gesture.active)endGesture();},{passive:true});
  window.addEventListener('keydown',event=>{if(event.key==='Escape')endGesture();});
  card.addEventListener('contextmenu',event=>{if(advanced()&&editor.dataset.view!=='preview'&&event.target.closest('[data-layout-block],[data-layout-button]'))event.preventDefault();});
  card.addEventListener('click',event=>{if(advanced()||editor.dataset.view==='preview'||event.target.closest('[data-inline-edit],[data-inline-media],input,textarea,select'))return;const block=event.target.closest('[data-layout-button],[data-layout-block]');if(!block)return;event.preventDefault();event.stopImmediatePropagation();edit(block.dataset.layoutBlock,block.dataset.layoutButton);},true);
  // Suppress the synthetic click after a hold, before the layout click handler sees it.
  form.addEventListener('click',event=>{if(Date.now()<suppressClickUntil&&card.contains(event.target)){event.preventDefault();event.stopImmediatePropagation();}},true);
  function grip(el){
    if(el.querySelector(':scope>.block-move-grip'))return;
    const button=node('span',{class:'block-move-grip',role:'button',tabindex:'0','aria-label':'Переместить '+(labels[keyFor(el)]||'контакт')},'⠿');el.append(button);
    button.addEventListener('keydown',event=>{if(!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.key))return;event.preventDefault();const key=keyFor(el),list=peers(el),i=list.indexOf(el),direction=['ArrowUp','ArrowLeft'].includes(event.key)?-1:1;reorder(el,list[i+direction],direction>0);const next=key.startsWith('button:')?card.querySelector(`[data-layout-button="${key.split(':')[1]}"]`):card.querySelector(`[data-layout-block="${key}"]`);next?.querySelector('.block-move-grip')?.focus();});
    button.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();event.stopPropagation();const startX=event.clientX,startY=event.clientY;let target=null,after=false,moved=false;button.setPointerCapture?.(event.pointerId);el.classList.add('block-moving');
      const move=e=>{moved=moved||Math.hypot(e.clientX-startX,e.clientY-startY)>6;if(!moved)return;card.querySelectorAll('.block-drop-target').forEach(node=>node.classList.remove('block-drop-target'));const hit=document.elementsFromPoint(e.clientX,e.clientY).map(node=>node.closest('[data-layout-button],[data-layout-block]')).find(node=>node&&node!==el&&peers(el).includes(node));target=hit||null;if(target){const rect=target.getBoundingClientRect();after=el.hasAttribute('data-layout-button')?e.clientX>rect.x+rect.width/2:e.clientY>rect.y+rect.height/2;target.classList.add('block-drop-target');}if(e.clientY<100)window.scrollBy(0,-14);else if(e.clientY>window.innerHeight-100)window.scrollBy(0,14);};
      const clean=()=>{el.classList.remove('block-moving');card.querySelectorAll('.block-drop-target').forEach(node=>node.classList.remove('block-drop-target'));window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',cancel);};
      const finish=()=>{clean();if(moved&&target)reorder(el,target,after);};const cancel=()=>clean();window.addEventListener('pointermove',move);window.addEventListener('pointerup',finish,{once:true});window.addEventListener('pointercancel',cancel,{once:true});
    });
  }
  function controls(editing){
    card.querySelectorAll('[data-inline-edit].inline-edit-block,.inline-remove-block,.block-move-grip').forEach(node=>node.remove());if(!editing)return;
    for(const el of card.querySelectorAll('[data-layout-block],[data-layout-button]')){
      if(el.hidden||el.closest('[hidden]'))continue;const key=keyFor(el);if(['logo','cover','avatar'].includes(key)){
        const slot=key==='cover'?'header':key;
        if(editor.querySelector(`[data-image-slot="${slot}"] .avatar-remove`))addRemove(el,key);
        if(key!=='logo'&&advanced()&&peers(el).includes(el))grip(el);continue;
      }
      if(!(advanced()&&(el.hasAttribute('data-layout-button')||['cover','avatar'].includes(key)))&&!el.querySelector(':scope>.inline-edit-block')){const button=node('button',{type:'button',class:'inline-edit-block','data-inline-edit':key,'aria-label':'Изменить '+(labels[key]||'контакт')},'Изменить');button.addEventListener('click',event=>{event.stopPropagation();edit(el.dataset.layoutBlock,el.dataset.layoutButton);});el.append(button);}
      if(el.hasAttribute('data-layout-button')||['bio','business','carousel','video','map','document','daisy'].includes(key)){
        addRemove(el,key);
      }
      if(advanced()&&peers(el).includes(el))grip(el);
    }
  }
  function addRemove(el,key){
    const remove=node('button',{type:'button',class:'inline-remove-block','data-inline-edit':key,'aria-label':'Удалить '+(labels[key]||'контакт'),title:'Удалить блок'},'×');
    remove.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();api.removeBlock(el.dataset.layoutBlock,el.dataset.layoutButton);status.textContent='Блок удалён. Сохраните визитку.';});el.append(remove);
  }
  function sync(){if(syncing)return;syncing=true;try{const editing=editor.dataset.view!=='preview',design=editing&&advanced();if(!design)endGesture();layout.refresh(card);mediaControls(editing);placeholders(editing);layout.setEditing(card,design);card.classList.toggle('content-editing',editing&&!design);controls(editing);modes.hidden=!editing;modes.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.editMode===editor.dataset.editMode)));}finally{syncing=false;}}
  form.addEventListener('card:insert-block',event=>insert(event.detail.key));form.addEventListener('card:editor-view',sync);form.addEventListener('input',sync);form.addEventListener('change',sync);
  const observer=new MutationObserver(()=>{if(!syncing)sync();});observer.observe(editor,{attributes:true,attributeFilter:['data-view']});
  sync();
})();
