document.querySelectorAll('[data-avatar-toggle]').forEach(button => {
  const photo = button.querySelector('.avatar-photo-face');
  const qr = button.querySelector('.avatar-qr-face');
  const image = button.querySelector('[data-avatar-qr]');
  const show = visible => {
    photo.hidden = visible;
    qr.hidden = !visible;
    photo.setAttribute('aria-hidden', String(visible));
    qr.setAttribute('aria-hidden', String(!visible));
    button.dataset.qrVisible = String(visible);
    button.setAttribute('aria-pressed', String(visible));
    button.setAttribute('aria-label', visible ? 'Показать фото' : 'Показать QR-код визитки');
  };
  show(false);
  image.addEventListener('error', () => {
    show(false);
    image.removeAttribute('src');
    const hint = button.nextElementSibling;
    if (hint && !('ownerPortrait' in button.dataset)) hint.textContent = 'QR недоступен. Проверьте публикацию визитки.';
  });
  button.addEventListener('click', () => {
    const visible = button.getAttribute('aria-pressed') !== 'true';
    if (visible && !image.getAttribute('src')) image.src = image.dataset.avatarQr;
    show(visible);
  });
});

/* Public-card features are progressively enhanced; native actions work without JavaScript. */
(() => {
  if(typeof window==='undefined')return;
  const days=['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье'];
  const minute=value=>{const [h,m]=value.split(':').map(Number);return h*60+m;};
  function workStatus(business,now=new Date()){
    if(business.status)return business.status;
    if(!business.hours?.length)return '';
    const parts=new Intl.DateTimeFormat('en-GB',{timeZone:business.timezone||'Europe/Moscow',weekday:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(now);
    const get=type=>parts.find(part=>part.type===type).value;
    const today=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].indexOf(get('weekday')),time=Number(get('hour'))*60+Number(get('minute'));
    for(const offset of [-1,0]){
      const hours=business.hours.find(item=>item.day===(today+offset+7)%7);if(!hours)continue;
      const start=minute(hours.open)+offset*1440;let end=minute(hours.close)+offset*1440;if(end<=start)end+=1440;
      if(start<=time&&time<end)return 'Открыто до '+hours.close;
    }
    return 'Сейчас закрыто';
  }
  function renderBusiness(card,business){
    const section=card.querySelector('[data-work-summary]');if(!section)return;
    const status=section.querySelector('[data-work-status]'),hours=section.querySelector('[data-work-hours]');
    status.textContent=workStatus(business);status.hidden=!status.textContent;
    section.hidden=!status.textContent&&!business.hours?.length;hours.hidden=!business.hours?.length;
    const list=section.querySelector('[data-work-days]');list.replaceChildren();
    const zones={'Europe/Kaliningrad':'Калининград','Europe/Moscow':'Москва','Europe/Samara':'Самара','Asia/Yekaterinburg':'Екатеринбург','Asia/Omsk':'Омск','Asia/Krasnoyarsk':'Красноярск','Asia/Irkutsk':'Иркутск','Asia/Yakutsk':'Якутск','Asia/Vladivostok':'Владивосток','Asia/Magadan':'Магадан','Asia/Kamchatka':'Камчатка'};
    section.querySelector('[data-work-zone]').textContent='Часовой пояс: '+(zones[business.timezone]||'Москва');
    if(business.hours?.length)days.forEach((name,day)=>{
      const item=business.hours.find(item=>item.day===day),row=document.createElement('div'),label=document.createElement('dt'),value=document.createElement('dd');
      label.textContent=name;value.textContent=item?item.open+'–'+item.close+(item.close<item.open?' (следующий день)':''):'Выходной';row.append(label,value);list.append(row);
    });
  }
  window.CardFeatures={workStatus,renderBusiness};
  document.querySelectorAll('.contact-card').forEach(card=>{
    const businessNode=card.querySelector('[data-work-summary] script');
    let business={};try{business=JSON.parse(businessNode?.textContent||'{}')||{};}catch{}
    const update=()=>renderBusiness(card,business);update();
    const publicPage=Boolean(card.closest('.public-page'));
    if(publicPage&&business.hours?.length)setInterval(()=>{if(!document.hidden)update();},60000);
    card.dataset.motion=card.querySelector('[data-card-motion]')?.dataset.cardMotion||'false';
    if(!publicPage||card.dataset.motion!=='true')return;
    const preference=window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if(preference?.matches||typeof IntersectionObserver==='undefined')return;
    const observer=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting){entry.target.classList.remove('card-reveal-pending');observer.unobserve(entry.target);}},{threshold:0.05});
    card.querySelectorAll('.contact-body>*,[data-design-block]').forEach(block=>{
      if(block.hidden||block.matches('[data-design-block="cover"],[data-design-block="avatar"]'))return;
      block.classList.add('card-reveal-pending');observer.observe(block);
    });
    const reveal=()=>{observer.disconnect();card.querySelectorAll('.card-reveal-pending').forEach(block=>block.classList.remove('card-reveal-pending'));};
    preference?.addEventListener?.('change',event=>{if(event.matches)reveal();});
    card.addEventListener('focusin',reveal,{once:true});
  });
})();
