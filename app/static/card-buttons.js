(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./web-links.js'));
  else root.CardButtons = factory(root.WebLinks, document.currentScript?.src);
})(typeof window !== 'undefined' ? window : globalThis, function(links, scriptUrl) {
  const kinds=new Set(['phone','other_phone','email','file','link','vk','instagram','telegram','dzen','youtube','ok','whatsapp','viber','max','other_social','threads','avito','website']);
  const icon=kind=>({other_phone:'phone',other_social:'website'})[kind]||kind;
  const inputs={
    telegram:{prefix:'https://t.me/',pattern:/^[A-Za-z0-9_]{1,32}$/,hosts:['t.me','telegram.me']},
    instagram:{prefix:'https://www.instagram.com/',pattern:/^[A-Za-z0-9_.]{1,30}$/,hosts:['instagram.com']},
    vk:{prefix:'https://vk.com/',pattern:/^[A-Za-z0-9_.-]{1,64}$/,hosts:['vk.com','vk.ru']},
    threads:{prefix:'https://www.threads.net/@',pattern:/^[A-Za-z0-9_.]{1,30}$/,hosts:['threads.net','threads.com']},
    youtube:{prefix:'https://www.youtube.com/@',pattern:/^[\p{L}\p{N}_.-]{3,30}$/u,hosts:['youtube.com','youtu.be']},
    dzen:{prefix:'https://dzen.ru/',pattern:/^[A-Za-z0-9_-]{1,100}$/,hosts:['dzen.ru','zen.yandex.ru']},ok:{prefix:'https://ok.ru/',pattern:/^[A-Za-z0-9_.-]{1,64}$/,hosts:['ok.ru']},max:{hosts:['max.ru']},avito:{hosts:['avito.ru']},viber:{hosts:['invite.viber.com','vb.me']}
  };
  function phone(value){let p=value.replace(/[\s()\-]/g,'');if(/^[78][0-9]{10}$/.test(p))p='+7'+p.slice(1);return /^\+[1-9][0-9]{7,14}$/.test(p)&&(!p.startsWith('+7')||p.length===12)?p:'';}
  function normalize(kind,value){
    value=String(value||'').trim();
    if(kind==='phone'||kind==='other_phone')return phone(value);
    if(kind==='whatsapp'){
      let number=value;
      if(/^(?:https?:\/\/)?(?:wa\.me|(?:api|web)\.whatsapp\.com)\//i.test(value)){
        const safe=links.normalize(value);if(!safe)return '';const u=new URL(safe);number=u.hostname==='wa.me'?u.pathname.replace(/^\/|\/$/g,''):u.searchParams.get('phone')||'';if(/^\d+$/.test(number))number='+'+number;
      }
      const p=phone(number);return p?'https://wa.me/'+p.slice(1):'';
    }
    const rules=inputs[kind],username=value.replace(/^@/,'');
    if(rules?.prefix&&rules.pattern.test(username)&&username.replace(/\./g,''))return rules.prefix+username;
    const safe=links.normalize(value);if(!safe)return '';const u=new URL(safe);
    if(kind==='telegram'&&u.hostname.endsWith('.t.me')&&u.pathname==='/'){const username=u.hostname.slice(0,-5);if(rules.pattern.test(username))return rules.prefix+username;}
    if(rules&&(!rules.hosts.some(host=>u.hostname===host||u.hostname.endsWith('.'+host))||!u.pathname.replace(/\//g,'')))return '';
    return safe;
  }
  function href(item, fileUrl='') {
    if(!kinds.has(item.kind))return '';
    const value=String(item.value||'').trim();
    if(item.kind==='phone'||item.kind==='other_phone'){
      const p=phone(value),ext=item.extension||'';
      if(ext&&!/^[0-9]{1,8}$/.test(ext))return '';
      return p?'tel:'+p+(ext?';ext='+ext:''):'';
    }
    if(item.kind==='email')return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)?'mailto:'+value:'';
    if(item.kind==='file'&&!value)return fileUrl;
    return normalize(item.kind,value);
  }
  function render(card, items) {
    const target=card.querySelector('.contact-actions');if(!target)return;
    const local=card.querySelector('[data-document-link][href], [data-local-file]');
    if(local?.getAttribute('href'))card.dataset.localFileUrl=local.getAttribute('href');
    const base=new URL('icons/',scriptUrl||location.href).href;
    target.replaceChildren();target.classList.add('builder-contact-buttons');card.dataset.buttonLayout='tiles';
    for(const item of items){
      const url=href(item,card.dataset.localFileUrl||'');if(!url)continue;
      const a=document.createElement('a'),img=document.createElement('img'),label=document.createElement('span');
      a.className='builder-contact-button';a.href=url;img.src=base+icon(item.kind)+'.svg';img.width=28;img.height=28;img.alt='';label.textContent=item.label;
      if(!url.startsWith('tel:')&&!url.startsWith('mailto:')){a.target='_blank';a.rel='noopener noreferrer';}
      if(item.kind==='file')a.download='';a.append(img,label);target.append(a);
    }
    target.hidden=!target.childElementCount;
    const wrapper=target.closest('[data-design-block="contacts"]');if(wrapper)wrapper.hidden=wrapper.dataset.templateHidden==='true'||!target.childElementCount;
    const social=card.querySelector('.social-section');if(social)social.hidden=true;
  }
  return {href,icon,render,normalize,inputs};
});
