/* Owner preview follows publication visibility, including unsaved form values. */
(() => {
  const form=document.getElementById('editor-form'),card=document.querySelector('.phone-preview .contact-card');if(!form||!card)return;
  const field=name=>form.elements.namedItem(name),value=name=>field(name)?.value.trim()||'';
  function visibility(key,hasContent){
    const block=card.querySelector(`[data-design-block="${key}"],[data-content-block="${key}"]`);
    if(block)block.hidden=block.dataset.templateHidden==='true'||!hasContent;
  }
  function embed(node,url){
    if(!node)return;
    if(node.dataset.embedUrl!==url){node.querySelector('iframe')?.remove();node.dataset.embedUrl=url;}
    const empty=node.querySelector('[data-embed-empty]');if(empty)empty.hidden=Boolean(url);
  }
  function update(){
    if(window.CardFeatures&&field('work_status')){
      const business={status:value('work_status'),timezone:value('work_timezone')||'Europe/Moscow',hours:[]};
      for(let day=0;day<7;day++){const open=value(`work_${day}_open`),close=value(`work_${day}_close`);if(open&&close&&open!==close)business.hours.push({day,open,close});}
      window.CardFeatures.renderBusiness(card,business);
      card.dataset.motion=field('motion')?.checked?'true':'false';
      const primary=card.querySelector('[data-primary-action]'),kind=value('action_kind');
      const href=kind?window.CardButtons.href({kind:kind==='phone'?'phone':'link',value:value('action_target')}):'';
      if(primary){primary.hidden=!href;const link=primary.querySelector('a');link.href=href||'#';link.textContent=value('action_label')||({phone:'Позвонить',booking:'Записаться',message:'Написать'})[kind]||'';if(kind==='phone')link.removeAttribute('target');else link.target='_blank';}
    }
    for(const key of ['phone','email']){
      const example=document.querySelector(`[data-button-example="${key}"]`);
      if(example)example.textContent=value(key+'_label')||card.dataset[key+'Label']||(key==='phone'?'Позвонить':'Написать');
    }
    for(const key of ['title','company','bio']){const node=card.querySelector(`[data-preview="${key}"]`);if(node)node.hidden=!node.textContent.trim();}
    visibility('bio',Boolean(value('bio')));
    visibility('contacts',Boolean(card.querySelector('.contact-actions')?.childElementCount));
    visibility('socials',card.dataset.buttonLayout!=='tiles'&&Boolean(card.querySelector('.social-links')?.childElementCount));
    visibility('carousel',Boolean(card.querySelector('.carousel-slide')));
    if(field('video_url')){
      const videos=window.CardVideos?.fromForm(form),url=window.WebLinks.normalize(value('video_url')),player=window.CardEmbeds.video(url,window.WebLinks.normalize(value('video_player')));
      visibility('video',videos?Boolean(videos.length):Boolean(player));
      const section=card.querySelector('[data-video-block]');
      if(section&&videos)window.CardVideos.render(section,videos);
      else if(section){section.querySelector('[data-video-title]').textContent=value('video_title')||'Видео';embed(section.querySelector('[data-external-embed]'),player);const link=section.querySelector('[data-video-link]');link.hidden=!player;link.href=player?url:'#';}
    }
    if(field('map_address')){
      const address=value('map_address'),location={address};
      if(value('map_latitude')&&value('map_longitude')){location.latitude=Number(value('map_latitude'));location.longitude=Number(value('map_longitude'));}
      visibility('map',Boolean(address));
      const section=card.querySelector('[data-map-block]');
      if(section){section.querySelector('[data-map-address]').textContent=address;embed(section.querySelector('[data-external-embed]'),window.CardEmbeds.map(location));}
    }
    const pdf=card.querySelector('[data-document-link]');
    visibility('document',card.dataset.buttonLayout!=='tiles'&&Boolean(pdf?.getAttribute('href')));
    if(pdf&&field('pdf_label'))pdf.textContent=value('pdf_label')||'Скачать прайс-лист (PDF)';
    window.CardWidgets?.refresh(card);
  }
  form.addEventListener('input',update);form.addEventListener('change',update);update();
})();
