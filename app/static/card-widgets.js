(() => {
  const initialized = new WeakMap();
  const reduced = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  function canvas(card) {
    const update = () => {
      card.style.setProperty('--canvas-scale',String(Math.max(.1,card.clientWidth/360)));
      card.style.setProperty('--canvas-height',card.dataset.canvasHeight || '1000');
    };
    update();
    if(!initialized.has(card)){
      const observer=typeof ResizeObserver==='function'?new ResizeObserver(update):null;
      observer?.observe(card);initialized.set(card,observer);
    }
  }
  function carousel(el) {
    const previous=initialized.get(el);previous?.destroy();
    const track=el.querySelector('.carousel-track'),status=el.querySelector('[data-carousel-status]');
    const prev=el.querySelector('[data-carousel-prev]'),next=el.querySelector('[data-carousel-next]'),pause=el.querySelector('[data-carousel-pause]');
    let timer=null,paused=false,hover=false;
    const visible=()=>el.dataset.customSize==='true'?Math.max(1,Math.min(4,Number(el.dataset.visible)||1)):el.dataset.peek==='true'?2.5:Math.min(Math.max(1,Number(el.dataset.visible)||1),el.clientWidth?Math.max(1,Math.floor(el.clientWidth/170)):10);
    const slides=()=>[...track.querySelectorAll('.carousel-slide')];
    const step=()=>slides()[0]?.getBoundingClientRect().width+10 || 1;
    const index=()=>{const end=track.scrollWidth-track.clientWidth;return end>0&&track.scrollLeft>=end-1?maximum():Math.round(track.scrollLeft/step());};
    const maximum=()=>Math.max(0,Math.ceil(slides().length-visible()));
    const move=delta=>{
      let target=index()+delta;if(target>maximum())target=0;if(target<0)target=maximum();
      track.scrollTo({left:target*step(),behavior:reduced()?'auto':'smooth'});
    };
    const update=()=>{if(status)status.textContent=`${Math.min(index()+1,slides().length)} / ${slides().length}`;};
    const schedule=()=>{
      clearInterval(timer);timer=null;
      if(el.dataset.autoplay==='true' && slides().length>visible() && !paused && !hover && !document.hidden && !reduced()) timer=setInterval(()=>move(1),Math.max(2,Math.min(120,Number(el.dataset.interval)||5))*1000);
    };
    if(prev)prev.onclick=()=>move(-1);if(next)next.onclick=()=>move(1);
    pause.hidden=el.dataset.autoplay!=='true';
    pause.onclick=()=>{paused=!paused;pause.textContent=paused?'Продолжить':'Пауза';schedule();};
    const enter=()=>{hover=true;schedule();},leave=()=>{hover=false;schedule();};
    const focusout=event=>{if(!el.contains(event.relatedTarget))leave();};
    track.addEventListener('scroll',update);el.addEventListener('mouseenter',enter);el.addEventListener('mouseleave',leave);
    el.addEventListener('focusin',enter);el.addEventListener('focusout',focusout);document.addEventListener('visibilitychange',schedule);
    const resize=()=>{el.style.setProperty('--slides-visible',String(visible()));update();schedule();};
    const observer=typeof ResizeObserver==='function'?new ResizeObserver(resize):null;observer?.observe(el);
    el.querySelector('.carousel-empty').hidden=slides().length>0;el.querySelector('.carousel-controls').hidden=!slides().length||el.dataset.autoplay!=='true';
    update();schedule();
    resize();
    initialized.set(el,{destroy(){observer?.disconnect();clearInterval(timer);track.removeEventListener('scroll',update);el.removeEventListener('mouseenter',enter);el.removeEventListener('mouseleave',leave);el.removeEventListener('focusin',enter);el.removeEventListener('focusout',focusout);document.removeEventListener('visibilitychange',schedule);}});
  }
  function sun(el, enabled) {
    const previous=initialized.get(el);previous?.destroy();
    const toggle=el.querySelector('[data-sun-toggle]'),links=[...el.querySelectorAll('.social-link')];
    const wasOpen=el.dataset.expanded==='true';
    el.classList.toggle('is-radial',enabled);toggle.hidden=!enabled;toggle.setAttribute('aria-expanded','false');
    if(!enabled){links.forEach(link=>link.removeAttribute('tabindex'));initialized.delete(el);return;}
    const position=()=>{
      const radius=Math.max(35,Math.min(el.clientWidth/2-28,105));
      links.forEach((link,i)=>{
        const angle=-Math.PI/2+i*2*Math.PI/Math.max(1,links.length);
        link.style.setProperty('--sun-x',`${Math.cos(angle)*radius}px`);link.style.setProperty('--sun-y',`${Math.sin(angle)*radius}px`);link.style.setProperty('--sun-index',String(i));
      });
    };
    const set=open=>{el.dataset.expanded=String(open);toggle.setAttribute('aria-expanded',String(open));links.forEach(link=>link.tabIndex=open?0:-1);};
    set(wasOpen);position();
    toggle.onclick=()=>set(el.dataset.expanded!=='true');
    const key=event=>{if(event.key==='Escape'){set(false);toggle.focus();}};
    const outside=event=>{if(!el.contains(event.target))set(false);};
    el.addEventListener('keydown',key);document.addEventListener('click',outside);
    const observer=typeof ResizeObserver==='function'?new ResizeObserver(position):null;observer?.observe(el);
    initialized.set(el,{destroy(){observer?.disconnect();el.removeEventListener('keydown',key);document.removeEventListener('click',outside);}});
  }
  function videoCarousel(el){
    initialized.get(el)?.destroy();
    const track=el.querySelector('[data-video-track]'),slides=[...track.querySelectorAll('.video-slide')],controls=el.querySelector('.video-controls'),prev=el.querySelector('[data-video-prev]'),next=el.querySelector('[data-video-next]'),status=el.querySelector('[data-video-status]');
    let active=-1;
    const index=()=>Math.max(0,Math.min(slides.length-1,Math.round(track.scrollLeft/Math.max(1,track.clientWidth))));
    const update=()=>{const current=index();if(current!==active){active=current;slides.forEach((slide,i)=>{slide.dataset.videoActive=String(i===active);slide.querySelectorAll('[data-external-embed]').forEach(renderEmbed);});}status.textContent=`${current+1} / ${slides.length}`;prev.disabled=current===0;next.disabled=current===slides.length-1;};
    const move=delta=>track.scrollTo({left:Math.max(0,Math.min(slides.length-1,index()+delta))*track.clientWidth,behavior:reduced()?'auto':'smooth'});
    const key=event=>{if(event.target!==track||!['ArrowLeft','ArrowRight'].includes(event.key))return;event.preventDefault();move(event.key==='ArrowLeft'?-1:1);};
    prev.onclick=()=>move(-1);next.onclick=()=>move(1);controls.hidden=slides.length<2;
    track.addEventListener('scroll',update);track.addEventListener('keydown',key);
    const observer=typeof ResizeObserver==='function'?new ResizeObserver(()=>{track.scrollLeft=Math.max(0,active)*track.clientWidth;update();}):null;observer?.observe(track);
    update();initialized.set(el,{destroy(){observer?.disconnect();track.removeEventListener('scroll',update);track.removeEventListener('keydown',key);}});
  }
  function renderEmbed(box){
      const url=box.dataset.embedUrl,previous=box.querySelector('iframe');
      const allowed=/^https:\/\/(www\.youtube-nocookie\.com\/embed\/|rutube\.ru\/play\/embed\/|vk\.com\/video_ext\.php\?|player\.vimeo\.com\/video\/|ok\.ru\/videoembed\/|www\.tiktok\.com\/player\/v1\/|geo\.dailymotion\.com\/player\/|yandex\.ru\/map-widget\/v1\/)/.test(url);
      if(!allowed||box.closest('[hidden], [data-video-active="false"]')){previous?.remove();return;}
      if(previous?.getAttribute('src')===url)return;
      previous?.remove();
      const iframe=document.createElement('iframe');iframe.src=url;iframe.title=box.dataset.embedTitle||'Встроенный сервис';
      iframe.allow='fullscreen; picture-in-picture; encrypted-media';iframe.allowFullscreen=true;iframe.loading='eager';iframe.referrerPolicy='strict-origin-when-cross-origin';
      const empty=box.querySelector('[data-embed-empty]');if(empty)empty.hidden=true;box.append(iframe);
  }
  function refresh(root=document) {
    const cards=root.matches?.('.contact-card')?[root]:[...root.querySelectorAll('.contact-card')];
    cards.forEach(card=>{card.querySelectorAll('[data-external-embed]').forEach(renderEmbed);card.querySelectorAll('[data-video-block]').forEach(videoCarousel);canvas(card);card.querySelectorAll('[data-card-carousel]').forEach(carousel);card.querySelectorAll('[data-contact-sun]').forEach(el=>sun(el,card.dataset.socialMode==='radial'));});
  }
  window.CardWidgets={refresh};refresh();
})();
