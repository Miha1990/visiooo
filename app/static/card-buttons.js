(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./web-links.js'));
  else root.CardButtons = factory(root.WebLinks, document.currentScript?.src);
})(typeof window !== 'undefined' ? window : globalThis, function(links, scriptUrl) {
  const kinds=new Set(['phone','other_phone','email','file','link','vk','instagram','telegram','dzen','youtube','ok','whatsapp','viber','max','other_social','threads','avito','website']);
  const icon=kind=>({other_phone:'phone',other_social:'website'})[kind]||kind;
  function href(item, fileUrl='') {
    if(!kinds.has(item.kind))return '';
    const value=String(item.value||'').trim();
    if(item.kind==='phone'||item.kind==='other_phone'){
      let phone=value.replace(/[\s()\-]/g,'');if(/^[78][0-9]{10}$/.test(phone))phone='+7'+phone.slice(1);
      return /^\+[1-9][0-9]{7,14}$/.test(phone)?'tel:'+phone:'';
    }
    if(item.kind==='email')return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)?'mailto:'+value:'';
    if(item.kind==='file'&&!value)return fileUrl;
    return links.normalize(value);
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
  return {href,icon,render};
});
