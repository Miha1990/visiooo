/* Owner-only photo ordering. The existing editor saves text before each media request. */
(() => {
  const grid=document.querySelector('[data-gallery-editor]');if(!grid)return;
  const section=grid.closest('[data-builder-media]'),editor=grid.closest('.editor'),orderForm=section.querySelector('[data-gallery-reorder]'),status=section.querySelector('[data-gallery-status]');
  const photos=()=>[...grid.querySelectorAll(':scope>[data-gallery-id]')],ids=()=>photos().map(el=>el.dataset.galleryId);
  let busy=false,gesture=null,before=null,suppressUntil=0;
  function restore(){if(before)for(const id of before){const photo=photos().find(el=>el.dataset.galleryId===id);if(photo)grid.append(photo);}before=null;}
  function failed(message){restore();status.textContent=message||'Изменения не сохранены. Попробуйте ещё раз.';}
  function saveOrder(){orderForm.elements.order.value=JSON.stringify(ids());status.textContent='Сохраняем порядок…';orderForm.requestSubmit();}
  function preview(order){
    const card=editor.querySelector('.phone-preview .contact-card'),track=card?.querySelector('.carousel-track');if(!track)return;
    const slides=[...track.querySelectorAll('[data-slide-id]')];for(const slide of slides)if(!order.includes(slide.dataset.slideId))slide.remove();
    for(const id of order){const slide=slides.find(el=>el.dataset.slideId===id);if(slide?.isConnected)track.append(slide);}
    const block=track.closest('[data-layout-block="carousel"]')||track.closest('[data-card-carousel]');if(block)block.hidden=!order.length;
    window.CardLayout?.refresh(card);document.getElementById('editor-form')?.dispatchEvent(new Event('input',{bubbles:true}));
  }
  section.querySelectorAll('[data-gallery-remove]').forEach(button=>button.addEventListener('click',event=>{if(busy||!window.confirm('Удалить?'))event.preventDefault();}));
  section.querySelectorAll('form[data-ajax-media]').forEach(form=>{
    form.addEventListener('card:submit-failed',()=>failed());
    form.addEventListener('submit',async event=>{
      if(event.defaultPrevented)return;event.preventDefault();if(busy)return;busy=true;section.inert=true;status.textContent='Сохраняем…';
      try{
        const response=await fetch(form.action,{method:'POST',body:new FormData(form),headers:{Accept:'application/json'}}),result=await response.json();
        if(!response.ok||!result.version||!Array.isArray(result.gallery))throw Error(result.error||'Не удалось сохранить фотографии.');
        editor.querySelectorAll('input[name="draft_version"]').forEach(input=>input.value=result.version);
        for(const photo of photos())if(!result.gallery.includes(photo.dataset.galleryId))photo.remove();
        for(const id of result.gallery){const photo=photos().find(el=>el.dataset.galleryId===id);if(photo)grid.append(photo);}
        before=null;preview(result.gallery);status.textContent='Сохранено. Опубликуйте визитку, чтобы обновить фотографии для посетителей.';
      }catch(error){failed(error.message||'Не удалось сохранить фотографии.');}
      finally{busy=false;section.inert=false;}
    });
  });
  function clearTarget(){grid.querySelectorAll('.gallery-drop-target').forEach(el=>el.classList.remove('gallery-drop-target'));}
  function finish(commit=false){const g=gesture;if(!g)return;if(commit&&g.active){g.target=document.elementsFromPoint(g.x,g.y).map(el=>el.closest('[data-gallery-id]')).find(el=>el&&el!==g.photo&&grid.contains(el))||null;if(g.target){const r=g.target.getBoundingClientRect();g.after=g.x>r.x+r.width/2;}}gesture=null;clearTimeout(g.timer);cancelAnimationFrame(g.frame);g.photo.classList.remove('gallery-moving');g.ghost?.remove();clearTarget();if(!g.active)return;suppressUntil=Date.now()+500;if(commit&&g.target){before=ids();grid.insertBefore(g.photo,g.after?g.target.nextSibling:g.target);if(JSON.stringify(before)!==JSON.stringify(ids()))saveOrder();else before=null;}}
  function frame(){const g=gesture;if(!g?.active)return;g.ghost.style.left=Math.max(0,Math.min(innerWidth-g.rect.width,g.x-g.offsetX))+'px';g.ghost.style.top=(g.y-g.offsetY)+'px';clearTarget();g.target=document.elementsFromPoint(g.x,g.y).map(el=>el.closest('[data-gallery-id]')).find(el=>el&&el!==g.photo&&grid.contains(el))||null;if(g.target){const r=g.target.getBoundingClientRect();g.after=g.x>r.x+r.width/2;g.target.classList.add('gallery-drop-target');}const dialog=section.closest('dialog'),r=dialog?.getBoundingClientRect();if(dialog&&r){if(g.y<r.top+60)dialog.scrollTop-=10;else if(g.y>r.bottom-60)dialog.scrollTop+=10;}g.frame=requestAnimationFrame(frame);}
  function begin(event,x,y,id,touch){if(busy||event.target.closest('button,form'))return;const photo=event.target.closest('[data-gallery-id]');if(!photo)return;finish();const g=gesture={photo,x,y,startX:x,startY:y,id,touch,active:false};g.timer=setTimeout(()=>{if(gesture!==g)return;g.active=true;g.rect=photo.getBoundingClientRect();g.offsetX=x-g.rect.x;g.offsetY=y-g.rect.y;g.ghost=photo.querySelector('img').cloneNode();g.ghost.className='gallery-drag-ghost';g.ghost.style.width=g.rect.width+'px';g.ghost.style.height=g.rect.height+'px';g.ghost.alt='';g.ghost.setAttribute('aria-hidden','true');section.append(g.ghost);photo.classList.add('gallery-moving');navigator.vibrate?.(15);g.frame=requestAnimationFrame(frame);},touch?400:180);}
  function move(event,x,y){const g=gesture;if(!g)return;g.x=x;g.y=y;if(!g.active){if(Math.hypot(x-g.startX,y-g.startY)>8)finish();return;}if(event.cancelable)event.preventDefault();}
  grid.addEventListener('touchstart',event=>{if(event.touches.length!==1){finish();return;}const t=event.touches[0];begin(event,t.clientX,t.clientY,t.identifier,true);},{passive:true});
  window.addEventListener('touchmove',event=>{if(!gesture?.touch)return;if(event.touches.length!==1){finish();return;}const t=[...event.touches].find(t=>t.identifier===gesture.id);if(t)move(event,t.clientX,t.clientY);},{passive:false});
  window.addEventListener('touchend',event=>{if(gesture?.touch&&[...event.changedTouches].some(t=>t.identifier===gesture.id))finish(true);});window.addEventListener('touchcancel',()=>finish());
  grid.addEventListener('pointerdown',event=>{if(event.pointerType!=='touch'&&event.button===0)begin(event,event.clientX,event.clientY,event.pointerId,false);});window.addEventListener('pointermove',event=>{if(gesture&&!gesture.touch&&gesture.id===event.pointerId)move(event,event.clientX,event.clientY);});window.addEventListener('pointerup',event=>{if(gesture&&!gesture.touch&&gesture.id===event.pointerId)finish(true);});window.addEventListener('pointercancel',event=>{if(gesture&&!gesture.touch&&gesture.id===event.pointerId)finish();});
  grid.addEventListener('click',event=>{if(Date.now()<suppressUntil){event.preventDefault();event.stopImmediatePropagation();}},true);
  grid.addEventListener('contextmenu',event=>{if(event.target.closest('[data-gallery-id]'))event.preventDefault();});
  grid.addEventListener('keydown',event=>{const photo=event.target.closest('[data-gallery-id]');if(event.target.closest('button')||!photo||busy||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();const list=photos(),columns=getComputedStyle(grid).gridTemplateColumns.split(' ').length,delta=({ArrowLeft:-1,ArrowRight:1,ArrowUp:-columns,ArrowDown:columns})[event.key],target=list[list.indexOf(photo)+delta];if(target){before=ids();grid.insertBefore(photo,delta>0?target.nextSibling:target);photo.focus();saveOrder();}});
  window.addEventListener('blur',()=>finish());window.addEventListener('pagehide',()=>finish());window.addEventListener('keydown',event=>{if(event.key==='Escape')finish();});section.closest('dialog')?.addEventListener('close',()=>finish());
})();
