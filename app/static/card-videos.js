/* Video collections share the same data in the customer and visual editors. */
(() => {
  const node=(tag,attrs={},text)=>{const el=document.createElement(tag);for(const [key,value]of Object.entries(attrs))el.setAttribute(key,value);if(text!==undefined)el.textContent=text;return el;};
  const normalize=value=>window.WebLinks?.normalize(value?.trim()||'')||value?.trim()||'';
  const clean=item=>({url:normalize(item.url),title:item.title||'',embedUrl:normalize(item.embedUrl)});
  function fromForm(form){
    const field=name=>form.elements.namedItem(name);let extra=[];try{extra=JSON.parse(field('video_items')?.value||'[]');}catch{}
    return [{url:field('video_url')?.value||'',title:field('video_title')?.value||'',embedUrl:field('video_player')?.value||''},...(Array.isArray(extra)?extra:[])].map(clean).filter(item=>window.CardEmbeds.videoLink(item.url));
  }
  function render(section,items){
    if(!section)return;
    const track=section.querySelector('[data-video-track]');if(!track)return;
    const videos=items.map(clean).filter(item=>window.CardEmbeds.videoLink(item.url)),signature=JSON.stringify(videos);
    if(section.dataset.videoContent===signature)return;section.dataset.videoContent=signature;
    const slides=(videos.length?videos:[{url:'',title:'',embedUrl:''}]).map((item,index)=>{
      const slide=node('article',{class:'video-slide','data-video-active':String(index===0),'aria-label':`Видео ${index+1} из ${Math.max(1,videos.length)}`});
      slide.append(node('h2',{'data-video-title':''},item.title||'Видео'));
      const player=item.url?window.CardEmbeds.video(item.url,item.embedUrl):'',box=node('div',{class:'card-embed','data-external-embed':'','data-embed-url':player,'data-embed-title':'Видеоплеер'}),empty=node('p',{'data-embed-empty':''},item.url?'Откройте видео на сайте сервиса':'Добавьте ссылку на видео');empty.hidden=Boolean(player);box.append(empty);slide.append(box);
      const link=node('a',{'data-video-link':'',target:'_blank',rel:'noopener noreferrer'},'Открыть на сайте видеосервиса');link.hidden=!item.url;if(item.url)link.href=item.url;slide.append(link);return slide;
    });
    track.replaceChildren(...slides);track.scrollLeft=0;
    section.querySelector('.video-controls').hidden=videos.length<2;
  }
  window.CardVideos={fromForm,render};
  const form=document.getElementById('editor-form'),source=form?.elements.namedItem('video_items'),first=form?.elements.namedItem('video_url');if(!source||!first)return;
  const fieldset=first.closest('fieldset');if(!fieldset)return;
  let extra;try{extra=JSON.parse(source.value||'[]');if(!Array.isArray(extra))return;}catch{return;}
  const fields={url:first,title:form.elements.namedItem('video_title'),embedUrl:form.elements.namedItem('video_player')};
  const firstRow=node('section',{class:'video-editor-row'}),firstActions=node('div',{class:'video-editor-actions'}),rows=node('div'),add=node('button',{type:'button',class:'button'},'Добавить видео');
  for(const input of Object.values(fields))firstRow.append(input.closest('div'));
  fieldset.append(firstRow,rows,add);firstRow.append(firstActions);
  function persist(){source.value=JSON.stringify(extra);source.dispatchEvent(new Event('input',{bubbles:true}));}
  function all(){return [Object.fromEntries(Object.entries(fields).map(([key,input])=>[key,input.value])),...extra];}
  function assign(items){const primary=items.shift()||{};for(const [key,input]of Object.entries(fields))input.value=primary[key]||'';extra=items;draw();persist();}
  function actions(host,index){
    host.replaceChildren();
    for(const [label,delta]of [['↑',-1],['↓',1]]){const button=node('button',{type:'button','aria-label':delta<0?'Переместить видео выше':'Переместить видео ниже'},label);button.disabled=index+delta<0||index+delta>extra.length;button.onclick=()=>{const items=all();[items[index],items[index+delta]]=[items[index+delta],items[index]];assign(items);};host.append(button);}
    const remove=node('button',{type:'button'},'Удалить видео');remove.onclick=()=>{const items=all();items.splice(index,1);assign(items);};host.append(remove);
  }
  function draw(){
    actions(firstActions,0);rows.replaceChildren();
    extra.forEach((item,index)=>{
      const row=node('section',{class:'video-editor-row'});row.append(node('h3',{},`Видео ${index+2}`));
      for(const [key,label]of [['url','Ссылка на видео'],['title','Название видео'],['embedUrl','Ссылка плеера (при необходимости)']]){
        const id=`video-extra-${index}-${key}`,input=node('input',{id,type:'text',maxlength:key==='title'?100:2048});input.value=item[key]||'';
        if(key!=='title'){input.inputMode='url';input.autocapitalize='none';input.spellcheck=false;}input.required=key==='url';
        input.addEventListener('input',()=>{item[key]=input.value;persist();});row.append(node('label',{for:id},label),input);
      }
      const controls=node('div',{class:'video-editor-actions'});actions(controls,index+1);row.append(controls);rows.append(row);
    });add.disabled=extra.length>=19;
  }
  add.onclick=()=>{if(!first.value.trim()&&!extra.length){first.focus();return;}if(extra.length>=19)return;extra.push({url:'',title:'',embedUrl:''});draw();persist();rows.lastElementChild?.querySelector('input')?.focus();};
  draw();
})();
