/* Decorative local examples: no embeds, requests to map/video services or saved demo data. */
(() => {
  const base=new URL('./',document.currentScript.src);
  function create(key){
    const box=document.createElement('div');box.className='block-example example-'+key;box.setAttribute('aria-hidden','true');
    if(key==='carousel'){
      const strip=document.createElement('div');strip.className='example-photo-strip';
      for(const file of ['designer-cover.webp','property-cover.webp','photographer-cover.webp','designer-cover.webp']){const image=document.createElement('img');image.src=new URL('examples/'+file,base).href;image.alt='';image.loading='lazy';strip.append(image);}box.append(strip);
    }else if(key==='video'){
      const play=document.createElement('span');play.className='example-play';play.textContent='▶';const label=document.createElement('span');label.textContent='Карусель видео · ссылки на видеосервисы';box.append(play,label);
    }else if(key==='map'){
      box.innerHTML='<svg viewBox="0 0 360 140" focusable="false"><rect width="360" height="140" fill="#edf2e9"/><path d="M0 25L360 110M35 0L115 140M260 0L220 140M0 105L360 45" stroke="#fff" stroke-width="17"/><path d="M0 25L360 110M35 0L115 140M260 0L220 140M0 105L360 45" stroke="#d9e1d3" stroke-width="2"/><path d="M180 30c-18 0-30 13-30 30 0 22 30 47 30 47s30-25 30-47c0-17-12-30-30-30z" fill="#2457db"/><circle cx="180" cy="59" r="10" fill="white"/></svg>';
    }else if(key==='daisy'){
      const center=document.createElement('span');center.className='example-daisy-center';center.textContent='Контакты';box.append(center);
      for(const [index,icon]of ['phone','telegram','vk','email'].entries()){const petal=document.createElement('span');petal.className='example-petal';petal.style.setProperty('--demo-index',index);const image=document.createElement('img');image.src=new URL('icons/'+icon+'.svg',base).href;image.alt='';petal.append(image);box.append(petal);}
    }else{return null;}
    return box;
  }
  window.CardBlockExamples={create};
})();
