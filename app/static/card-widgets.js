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
    const slides=()=>[...track.querySelectorAll('.carousel-slide')];
    const step=()=>slides()[0]?.getBoundingClientRect().width+10 || 1;
    const index=()=>Math.round(track.scrollLeft/step());
    const maximum=()=>Math.max(0,slides().length-Number(el.dataset.visible || 1));
    const move=delta=>{
      let target=index()+delta;if(target>maximum())target=0;if(target<0)target=maximum();
      track.scrollTo({left:target*step(),behavior:reduced()?'auto':'smooth'});
    };
    const update=()=>{status.textContent=`${Math.min(index()+1,slides().length)} / ${slides().length}`;};
    const schedule=()=>{
      clearInterval(timer);timer=null;
      if(el.dataset.autoplay==='true' && slides().length>Number(el.dataset.visible || 1) && !paused && !hover && !document.hidden && !reduced()) timer=setInterval(()=>move(1),Math.max(2,Math.min(120,Number(el.dataset.interval)||5))*1000);
    };
    prev.onclick=()=>move(-1);next.onclick=()=>move(1);
    pause.hidden=el.dataset.autoplay!=='true';
    pause.onclick=()=>{paused=!paused;pause.textContent=paused?'Продолжить':'Пауза';schedule();};
    const enter=()=>{hover=true;schedule();},leave=()=>{hover=false;schedule();};
    const focusout=event=>{if(!el.contains(event.relatedTarget))leave();};
    track.addEventListener('scroll',update);el.addEventListener('mouseenter',enter);el.addEventListener('mouseleave',leave);
    el.addEventListener('focusin',enter);el.addEventListener('focusout',focusout);document.addEventListener('visibilitychange',schedule);
    el.style.setProperty('--slides-visible',el.dataset.visible || '1');
    el.querySelector('.carousel-empty').hidden=slides().length>0;el.querySelector('.carousel-controls').hidden=!slides().length;
    update();schedule();
    initialized.set(el,{destroy(){clearInterval(timer);track.removeEventListener('scroll',update);el.removeEventListener('mouseenter',enter);el.removeEventListener('mouseleave',leave);el.removeEventListener('focusin',enter);el.removeEventListener('focusout',focusout);document.removeEventListener('visibilitychange',schedule);}});
  }
  function sun(el, enabled) {
    const previous=initialized.get(el);previous?.destroy();
    const toggle=el.querySelector('[data-sun-toggle]'),links=[...el.querySelectorAll('.social-link')];
    el.classList.toggle('is-radial',enabled);toggle.hidden=!enabled;el.dataset.expanded='false';toggle.setAttribute('aria-expanded','false');
    if(!enabled){links.forEach(link=>link.removeAttribute('tabindex'));initialized.delete(el);return;}
    const position=()=>{
      const radius=Math.max(35,Math.min(el.clientWidth/2-28,105));
      links.forEach((link,i)=>{
        const angle=-Math.PI/2+i*2*Math.PI/Math.max(1,links.length);
        link.style.setProperty('--sun-x',`${Math.cos(angle)*radius}px`);link.style.setProperty('--sun-y',`${Math.sin(angle)*radius}px`);link.style.setProperty('--sun-index',String(i));
      });
    };
    const set=open=>{el.dataset.expanded=String(open);toggle.setAttribute('aria-expanded',String(open));links.forEach(link=>link.tabIndex=open?0:-1);};
    set(false);position();
    toggle.onclick=()=>set(el.dataset.expanded!=='true');
    const key=event=>{if(event.key==='Escape'){set(false);toggle.focus();}};
    const outside=event=>{if(!el.contains(event.target))set(false);};
    el.addEventListener('keydown',key);document.addEventListener('click',outside);
    const observer=typeof ResizeObserver==='function'?new ResizeObserver(position):null;observer?.observe(el);
    initialized.set(el,{destroy(){observer?.disconnect();el.removeEventListener('keydown',key);document.removeEventListener('click',outside);}});
  }
  function refresh(root=document) {
    const cards=root.matches?.('.designed-card')?[root]:[...root.querySelectorAll('.designed-card')];
    cards.forEach(card=>{card.querySelectorAll('[data-load-embed]').forEach(button=>{button.onclick=()=>{const box=button.closest('[data-external-embed]'),url=box.dataset.embedUrl;if(!/^https:\/\/(www\.youtube-nocookie\.com\/embed\/|rutube\.ru\/play\/embed\/|vk\.com\/video_ext\.php\?|yandex\.ru\/map-widget\/v1\/)/.test(url)||box.querySelector('iframe'))return;const iframe=document.createElement('iframe');iframe.src=url;iframe.title=box.dataset.embedTitle||'Встроенный сервис';iframe.allow='fullscreen; picture-in-picture; encrypted-media';iframe.allowFullscreen=true;iframe.referrerPolicy='strict-origin-when-cross-origin';box.querySelectorAll('button,small').forEach(node=>node.hidden=true);box.append(iframe);};});canvas(card);card.querySelectorAll('[data-card-carousel]').forEach(carousel);card.querySelectorAll('[data-contact-sun]').forEach(el=>sun(el,card.dataset.socialMode==='radial'));});
  }
  window.CardWidgets={refresh};refresh();
})();
