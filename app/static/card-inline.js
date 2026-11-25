/* Edit the real card, with editor-only placeholders and pointer/keyboard ordering. */
(() => {
  const editor=document.querySelector('.card-builder-active'),form=document.getElementById('editor-form'),api=window.CardBuilder,layout=window.CardLayout;
  if(!editor||!form||!api||!layout)return;
  const preview=editor.querySelector('.phone-preview'),card=preview?.querySelector('.contact-card');if(!card)return;
  const labels={cover:'Обложка',avatar:'Фото',identity:'Информация о себе',bio:'О себе',save:'Сохранение контакта',business:'График и статус',contacts:'Контакты',socials:'Соцсети',carousel:'Карусель',video:'Видео',document:'Файл',map:'Адрес',daisy:'Ромашка'};
  const node=(tag,attrs={},text)=>{const el=document.createElement(tag);for(const [k,v]of Object.entries(attrs))el.setAttribute(k,v);if(text!==undefined)el.textContent=text;return el;};
  const host=node('section',{class:'inline-card-host','aria-label':'Редактирование блоков визитки'}),actions=node('div',{class:'inline-media-actions'}),hint=node('p',{class:'inline-edit-hint'},'Нажмите на блок, чтобы выбрать. Удерживайте и перетаскивайте, чтобы переместить. Тяните за края или уголки, чтобы изменить размер.'),status=node('p',{class:'inline-order-status',role:'status','aria-live':'polite'});
  for(const [slot,title]of [['logo','Лого'],['header','Обложка'],['avatar','Фото']]){const button=node('button',{type:'button'},'+ '+title);button.addEventListener('click',()=>editor.querySelector(`[data-image-slot="${slot}"] input[type=file],.builder-image-${slot} input[type=file]`)?.click());actions.append(button);}
  const panel=editor.querySelector('.size-panel'),oldToggle=editor.querySelector('[data-size-mode]');
  host.append(actions,hint);if(panel)host.append(panel);host.append(preview,status);form.prepend(host);editor.classList.add('inline-builder');if(oldToggle)oldToggle.hidden=true;
  const empty=new Map();let syncing=false,pendingContact=null;
  const input=name=>form.elements.namedItem(name),value=name=>input(name)?.value.trim()||'';
  function hasContent(key){if(key==='carousel')return Boolean(card.querySelector('.carousel-slide'));if(key==='video')return Boolean(window.CardEmbeds?.video(window.WebLinks.normalize(value('video_url')),window.WebLinks.normalize(value('video_player'))));if(key==='map')return Boolean(value('map_address'));if(key==='daisy'){try{return (JSON.parse(input('daisy_data').value||'{}').items||[]).length>0;}catch{return false;}}return true;}
  function persist(){const source=input('layout_data');source.value=JSON.stringify(layout.get(card));source.dispatchEvent(new Event('input',{bubbles:true}));}
  function insert(key){const config=layout.get(card);const known=['cover','avatar','identity','bio','business','save','contacts','socials','carousel','video','document','map','daisy'];config.order=config.order||known.filter(item=>card.querySelector(`[data-layout-block="${item}"]:not([hidden])`));if(!config.order.includes(key))config.order.push(key);layout.set(card,config);persist();sync();}
  function restore(key){const entry=empty.get(key);if(!entry)return;entry.demo.remove();entry.children.forEach(([child,hidden])=>child.hidden=hidden);delete entry.block.dataset.editorExample;empty.delete(key);}
  function placeholders(editing){
    const requested=layout.get(card).order||[];
    for(const key of ['carousel','video','map','daisy']){
      const filled=hasContent(key),block=card.querySelector(`[data-layout-block="${key}"]`);if(!block)continue;
      if(!editing||filled||!requested.includes(key)){restore(key);if(!filled)block.hidden=true;continue;}
      if(!empty.has(key)){
        const children=[...block.children].filter(child=>!child.matches('.size-handle,.block-move-grip,.inline-edit-block')).map(child=>[child,child.hidden]);children.forEach(([child])=>child.hidden=true);
        const demo=node('div',{class:'inline-empty-block'}),example=window.CardBlockExamples.create(key);if(example)demo.append(example);demo.append(node('p',{},'Пример: '+labels[key]+'. Добавьте свои данные.'));block.append(demo);empty.set(key,{block,demo,children});block.dataset.editorExample='true';
      }
      block.hidden=false;
    }
    contactSlots(editing);
  }
  function contactSlots(editing=editor.dataset.view!=='preview'){
    const grid=card.querySelector('.contact-actions');if(!grid)return;const wrapper=grid.closest('[data-design-block="contacts"]')||grid;
    grid.querySelectorAll('[data-empty-contact]').forEach(el=>el.remove());let count=0;try{count=JSON.parse(input('button_items').value||'[]').length;}catch{}
    if(!editing){if(!count){grid.hidden=true;wrapper.hidden=true;}return;}
    if(count>=30)return;
    const buttons=[...grid.querySelectorAll(':scope>[data-layout-button]')],last=buttons.at(-1),config=last?layout.get(card).buttons?.[last.dataset.layoutButton]||{}:{};
    const computed=last?getComputedStyle(last):null,span=(computed?.gridColumnStart+' '+computed?.gridColumnEnd).match(/span\s+(\d+)/)?.[1]|| (card.classList.contains('layout-custom')?6:3);
    for(let i=0;i<(buttons.length?1:2);i++){
      const button=node('button',{type:'button','data-empty-contact':'','data-inline-edit':'contacts',class:'inline-add-contact','aria-label':'Добавить контакт или соцсеть',title:'Добавить контакт или соцсеть'},'+');
      button.style.setProperty('--add-span',span);button.style.setProperty('--add-radius',computed?.borderRadius||'20px');
      const height=last?.getBoundingClientRect().height;if(height)button.style.setProperty('--add-height',height+'px');
      button.addEventListener('click',()=>{const width=config.width||Number(last?.dataset.sizeWidth)||50,shape=config.shape||(last?.classList.contains('has-custom-size')?'auto':'square');pendingContact={count,config:{...config,width,shape,...(shape==='auto'?{height:config.height||Math.round(height)||0}:{})}};api.choose();});grid.append(button);
    }
    grid.hidden=false;wrapper.hidden=false;
  }
  // Keep the new contact the same size as the empty tile the user tapped.
  form.addEventListener('input',event=>{if(event.target.name!=='button_items'||!pendingContact)return;let items;try{items=JSON.parse(event.target.value);}catch{return;}if(items.length>pendingContact.count){const config=layout.get(card);config.buttons??={};for(let i=pendingContact.count;i<items.length;i++)config.buttons[i]={...pendingContact.config};input('layout_data').value=JSON.stringify(config);layout.set(card,config);}pendingContact=null;},true);
  // A resize can change a tile without changing form fields until the gesture ends.
  card.addEventListener('card:layout-applied',()=>contactSlots());
  editor.addEventListener('close',()=>{setTimeout(()=>{if(!editor.querySelector('dialog[open]'))pendingContact=null;},0);},true);
  function edit(key,index){if(index!==undefined)api.choose('all',Number(index));else if(['identity','bio'].includes(key))api.profile();else if(['cover','avatar','logo'].includes(key))editor.querySelector(`.builder-image-${key==='cover'?'header':key} input[type=file]`)?.click();else if(key==='daisy')api.daisy();else if(['carousel','video','map','document'].includes(key))api.openMedia(key);else if(key==='business')api.features();else api.choose();}
  function keyFor(el){return el.hasAttribute('data-layout-button')?'button:'+el.dataset.layoutButton:el.dataset.layoutBlock;}
  function peers(el){return el.hasAttribute('data-layout-button')?[...el.parentElement.querySelectorAll(':scope>[data-layout-button]')]:[...card.querySelectorAll(':scope>[data-layout-block="cover"],:scope>[data-layout-block="avatar"],.contact-body>[data-layout-block]')];}
  function reorder(el,target,after){const isButton=el.hasAttribute('data-layout-button');if(!target||isButton!==target.hasAttribute('data-layout-button'))return;const list=peers(el);if(!list.includes(target)||el===target)return;const keys=list.map(keyFor),key=keyFor(el);keys.splice(keys.indexOf(key),1);keys.splice(keys.indexOf(keyFor(target))+(after?1:0),0,key);const config=layout.get(card);if(isButton)config.buttonOrder=keys.map(key=>Number(key.split(':')[1]));else config.order=keys;layout.set(card,config);persist();status.textContent='Порядок блоков изменён. Сохраните визитку.';}
  // Touch listeners let a normal swipe scroll, but keep the held gesture in the editor.
  let gesture=null,suppressClickUntil=0;
  const clearDrop=()=>card.querySelectorAll('.block-drop-target').forEach(el=>el.classList.remove('block-drop-target'));
  function endGesture(commit=false){
    const g=gesture;if(!g)return;gesture=null;clearTimeout(g.timer);cancelAnimationFrame(g.frame);clearDrop();g.el.classList.remove('block-moving');g.el.style.removeProperty('translate');card.classList.remove('block-dragging');
    if(g.active){suppressClickUntil=Date.now()+500;if(commit&&g.target)reorder(g.el,g.target,g.after);const current=g.key.startsWith('button:')?card.querySelector(`[data-layout-button="${g.key.slice(7)}"]`):card.querySelector(`[data-layout-block="${g.key}"]`);layout.select(card,current);status.textContent=commit&&g.target?'Блок перемещён. Сохраните визитку.':'Блок выбран. Тяните за края, чтобы изменить размер.';}
  }
  function locate(g){clearDrop();const list=peers(g.el);g.target=document.elementsFromPoint(g.x,g.y).map(el=>el.closest('[data-layout-button],[data-layout-block]')).find(el=>el&&el!==g.el&&list.includes(el))||null;if(g.target){const r=g.target.getBoundingClientRect();g.after=g.el.hasAttribute('data-layout-button')?g.x>r.x+r.width/2:g.y>r.y+r.height/2;g.target.classList.add('block-drop-target');g.target.dataset.dropSide=g.after?'after':'before';}}
  function dragFrame(){const g=gesture;if(!g?.active)return;const speed=g.y<90?-10:g.y>innerHeight-90?10:0;if(speed)window.scrollBy({top:speed,behavior:'instant'});const bounds=card.getBoundingClientRect(),dx=Math.max(bounds.left-g.rect.left,Math.min(bounds.right-g.rect.right,g.x-g.startX));g.el.style.translate=`${dx}px ${g.y-g.startY+window.scrollY-g.scrollY}px`;locate(g);g.frame=requestAnimationFrame(dragFrame);}
  function beginGesture(event,x,y,id,touch){
    if(editor.dataset.view==='preview'||event.target.closest('.size-handle,.inline-edit-block,.block-move-grip,input,textarea,select,[data-empty-contact]'))return;
    const el=event.target.closest('[data-layout-button],[data-layout-block]');if(!el||!peers(el).includes(el))return;endGesture();
    const g=gesture={el,key:keyFor(el),startX:x,startY:y,x,y,id,touch,active:false,target:null};
    g.timer=setTimeout(()=>{if(gesture!==g||!el.isConnected)return;g.active=true;g.rect=el.getBoundingClientRect();g.scrollY=window.scrollY;layout.select(card,el);el.classList.add('block-moving');card.classList.add('block-dragging');navigator.vibrate?.(15);status.textContent='Перетаскивайте блок на нужное место.';g.frame=requestAnimationFrame(dragFrame);},450);
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
  card.addEventListener('contextmenu',event=>{if(editor.dataset.view!=='preview'&&event.target.closest('[data-layout-block],[data-layout-button]'))event.preventDefault();});
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
    card.querySelectorAll('[data-inline-edit].inline-edit-block,.block-move-grip').forEach(node=>node.remove());if(!editing)return;
    for(const el of card.querySelectorAll('[data-layout-block],[data-layout-button]')){
      if(el.hidden||el.closest('[hidden]'))continue;const key=keyFor(el);if(key==='logo')continue;
      if(!el.querySelector(':scope>.inline-edit-block')){const button=node('button',{type:'button',class:'inline-edit-block','data-inline-edit':key,'aria-label':'Изменить '+(labels[key]||'контакт')},'Изменить');button.addEventListener('click',event=>{event.stopPropagation();edit(el.dataset.layoutBlock,el.dataset.layoutButton);});el.append(button);}
      if(peers(el).includes(el))grip(el);
    }
  }
  function sync(){if(syncing)return;syncing=true;try{const editing=editor.dataset.view!=='preview';if(!editing)endGesture();layout.refresh(card);placeholders(editing);layout.setEditing(card,editing);controls(editing);actions.hidden=!editing;hint.hidden=!editing;if(panel&&!editing)panel.hidden=true;}finally{syncing=false;}}
  form.addEventListener('card:insert-block',event=>insert(event.detail.key));form.addEventListener('card:editor-view',sync);form.addEventListener('input',sync);form.addEventListener('change',sync);
  const observer=new MutationObserver(()=>{if(!syncing)sync();});observer.observe(editor,{attributes:true,attributeFilter:['data-view']});
  sync();
})();
