/* Shared visual editor: bounded data is saved; DOM/HTML is never accepted as a template. */
(() => {
  const form=document.querySelector('[data-visual-editor]');if(!form)return;
  const data=JSON.parse(document.getElementById('visual-editor-data').textContent);
  let design=data.design,content=data.content,selected='identity',preview=false,dirty=false,busy=false;
  const card=form.querySelector('.designed-card'),body=card.querySelector('.design-body');
  const artboard=form.querySelector('[data-artboard]'),selection=form.querySelector('[data-selection]');
  const inspector=form.querySelector('[data-inspector]'),status=form.querySelector('[data-editor-status]');
  const clone=value=>JSON.parse(JSON.stringify(value));
  const clamp=(v,min,max)=>Math.min(max,Math.max(min,Number(v)||0));
  const rounded=v=>Math.round(v*100)/100;
  const snapshot=()=>JSON.stringify({design,content});
  const galleryLimit=data.carouselLimit||10;
  const history=[];
  const checkpoint=()=>{const value=snapshot();if(history.at(-1)!==value){history.push(value);if(history.length>30)history.shift();}};
  const state=key=>(design.blockStyles??={})[key]??={align:'inherit',iconPosition:'inherit'};
  const block=key=>body.querySelector(`[data-design-block="${key}"]`);
  const scale=()=>card.clientWidth/360;
  const fonts={ui:"'Segoe UI',system-ui,sans-serif",serif:'Georgia,serif',rounded:"'Trebuchet MS',Arial,sans-serif"};
  const iconBase=new URL('icons/',document.currentScript.src).href;
  const roles={save:'Сохранение',phone:'Телефон',email:'Почта',link:'Ссылки',instagram:'Инстаграм',threads:'Тредс',telegram:'Телеграм',vk:'ВКонтакте',ok:'Одноклассники',max:'Макс',avito:'Авито',website:'Сайт'};
  const urls=new Map();card.querySelectorAll('[data-image-slot]').forEach(img=>{if(img.getAttribute('src'))urls.set(img.dataset.imageSlot,img.src);});
  card.querySelectorAll('[data-slide-id]').forEach(slide=>urls.set(slide.dataset.slideId,slide.querySelector('img').src));
  function message(text,error=false){status.textContent=text;status.classList.toggle('error',error);}
  function iconUrl(role){const id=design.icons[role];return id?`/template-icons/${id}.svg`:`${iconBase}${role}.svg`;}
  const safeUrl=value=>{try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)&&!url.username&&!url.password?url.href:'#';}catch{return '#';}};
  function element(tag,attrs={},text=''){
    const node=document.createElement(tag);for(const [key,value]of Object.entries(attrs)){if(key==='class')node.className=value;else node.setAttribute(key,String(value));}node.textContent=text;return node;
  }
  function button(label,fn,parent=inspector){const node=element('button',{type:'button'},label);node.addEventListener('click',fn);parent.append(node);return node;}
  function control(label,value,fn,{type='text',options=null,min,max,step=1,parent=inspector}={}){
    const wrapper=element('label',{},label),input=element(options?'select':type==='textarea'?'textarea':'input');
    if(options)for(const [key,text]of options)input.append(element('option',{value:key},text));
    else if(type!=='textarea')input.type=type;
    if(type==='checkbox')input.checked=Boolean(value);else input.value=value??'';
    if(min!==undefined)input.min=min;if(max!==undefined)input.max=max;input.step=step;
    input.addEventListener('focus',checkpoint,{once:true});
    input.addEventListener(type==='checkbox'||options?'change':'input',()=>{fn(type==='checkbox'?input.checked:type==='number'?Number(input.value):input.value);dirty=true;apply();});
    wrapper.append(input);parent.append(wrapper);return input;
  }
  function small(text,parent=inspector){parent.append(element('small',{},text));}
  function action(role,label,href,detail='',external=false){
    const anchor=element('a',{href,'aria-label':label});
    if(external){anchor.target='_blank';anchor.rel='noopener noreferrer';}
    anchor.append(element('img',{src:iconUrl(role),alt:'',class:'design-contact-icon','data-design-icon':role,width:24,height:24}),element('span',{},label));
    if(detail)anchor.append(element('span',{class:'contact-detail'},detail));return anchor;
  }
  function renderContacts(){
    const actions=card.querySelector('.contact-actions');actions.replaceChildren();
    if(content.phone)actions.append(action('phone',design.phoneLabel,`tel:${content.phone}`,content.phone));
    if(content.email)actions.append(action('email',design.emailLabel,`mailto:${content.email}`,content.email));
    for(const link of content.links)actions.append(action('link',link.label,safeUrl(link.url),'',true));
    const links=card.querySelector('.social-links');links.replaceChildren();
    for(const [role,label]of Object.entries(roles)){
      const url=role==='website'?content.website:content.socials?.[role];if(!url)continue;
      const anchor=element('a',{href:safeUrl(url),class:`social-link social-${role}`,target:'_blank',rel:'noopener noreferrer','aria-label':label});
      const icon=element('span',{class:'social-icon'});icon.append(element('img',{src:iconUrl(role),alt:'','data-design-icon':role,width:24,height:24}));
      anchor.append(icon,element('span',{},label));links.append(anchor);
    }
    card.querySelector('.social-section').hidden=!links.childElementCount;
  }
  function photos(){return !data.template&&Array.isArray(content.galleryAssetIds)?content.galleryAssetIds:design.carousel.photos;}
  function renderGallery(){
    const carousel=card.querySelector('[data-card-carousel]');if(!carousel)return;
    const settings=design.carousel;
    carousel.dataset.visible=settings.visible;carousel.dataset.autoplay=String(settings.autoplay);carousel.dataset.interval=settings.interval;
    carousel.style.setProperty('--slides-visible',settings.visible);carousel.style.setProperty('--slide-height',`${settings.height}px`);
    const track=carousel.querySelector('.carousel-track');track.replaceChildren();
    photos().forEach((id,i)=>{const figure=element('figure',{class:'carousel-slide','data-slide-id':id});figure.append(element('img',{src:urls.get(id)||`/template-photos/${id}.webp`,alt:`Фотография ${i+1} из ${photos().length}`,loading:'lazy'}));track.append(figure);});
  }
  function setEmbed(node,url){
    if(!node)return;
    if(node.dataset.embedUrl!==url){node.querySelector('iframe')?.remove();node.dataset.embedUrl=url;node.querySelectorAll('button,small').forEach(item=>item.hidden=false);}
    node.querySelector('[data-load-embed]').disabled=!url;
  }
  function renderMedia(){
    const video=content.video||{},location=content.map||{},doc=content.document||{};
    const videoNode=card.querySelector('[data-video-block]');
    if(videoNode){
      videoNode.querySelector('[data-video-title]').textContent=video.title||'Видео';
      const link=videoNode.querySelector('[data-video-link]');link.href=safeUrl(video.url);link.hidden=!video.url;
      setEmbed(videoNode.querySelector('[data-external-embed]'),window.CardEmbeds.video(video.url||'',video.embedUrl||''));
    }
    const mapNode=card.querySelector('[data-map-block]');
    if(mapNode){mapNode.querySelector('[data-map-address]').textContent=location.address||'Укажите адрес';setEmbed(mapNode.querySelector('[data-external-embed]'),window.CardEmbeds.map(location));}
    const docNode=card.querySelector('[data-document-block]');
    if(docNode){const link=docNode.querySelector('[data-document-link]');if(data.samplePdfUrl)link.href=data.samplePdfUrl;if(doc.assetId&&urls.has(doc.assetId))link.href=urls.get(doc.assetId);link.hidden=!doc.assetId&&!data.samplePdfUrl;link.textContent=doc.label||'Скачать прайс-лист (PDF)';docNode.querySelector('[data-document-empty]').hidden=Boolean(doc.assetId||data.samplePdfUrl);}
  }
  const existingPDF=card.querySelector('[data-document-link][href]');if(existingPDF&&content.document?.assetId)urls.set(content.document.assetId,existingPDF.href);
  function overlay(){
    const node=block(selected);selection.hidden=preview||!node||node.hidden;if(selection.hidden)return;
    const rect=node.getBoundingClientRect(),stage=artboard.getBoundingClientRect();
    Object.assign(selection.style,{left:`${rect.left-stage.left}px`,top:`${rect.top-stage.top}px`,width:`${rect.width}px`,height:`${Math.max(20,rect.height)}px`});
    form.querySelector('[data-drag-handle]').textContent=data.blocks[selected];
  }
  function apply(widgets=true){
    content.design=design;content.accent=design.accent;
    renderMedia();
    const set=(key,value)=>card.style.setProperty(`--${key}`,value);
    for(const [key,value]of Object.entries({'accent':design.accent,'design-bg':design.background,'design-text':design.text,'design-font':fonts[design.font],'design-align':design.align,'design-gap':`${design.gap}px`,'design-radius':`${design.radius}px`,'design-avatar':`${design.avatarSize}px`,'design-avatar-radius':`${({circle:999,rounded:16,square:0})[design.avatarShape]}px`,'design-cover':`${design.coverHeight}px`,'design-icon':`${design.iconSize}px`,'design-name':`${design.nameSize}px`,'design-weight':design.weight,'design-columns':design.buttonColumns}))set(key,value);
    const defaultRadius=design.buttonCorners?.map(v=>`${v}px`).join(' ')||`${({rect:0,rounded:12,pill:999})[design.buttonShape]}px`;
    set('design-button-radius',defaultRadius);
    card.dataset.canvasEnabled=String(Boolean(design.canvas?.enabled));card.dataset.canvasHeight=design.canvas?.height||1000;
    set('canvas-height',design.canvas?.height||1000);set('canvas-scale',scale());
    card.dataset.buttonStyle=design.buttonStyle;card.dataset.iconPosition=design.iconPosition;card.dataset.socialMode=design.socialMode;
    for(const key of design.blocks){
      const node=block(key);if(!node)continue;body.append(node);node.hidden=design.hidden.includes(key);
      const settings=state(key),frame=design.canvas?.enabled?design.frames?.[key]:null;
      node.dataset.blockAlign=settings.align||'inherit';node.dataset.blockIcons=settings.iconPosition&&settings.iconPosition!=='inherit'?settings.iconPosition:design.iconPosition;node.dataset.blockButton=settings.buttonShape||'inherit';
      node.style.setProperty('--design-icon',`${settings.iconSize||design.iconSize}px`);
      node.style.setProperty('--design-button-radius',settings.buttonCorners?.map(v=>`${v}px`).join(' ')||({rect:'0px',rounded:'12px',pill:'999px'})[settings.buttonShape]||defaultRadius);
      for(const property of ['left','top','width','height','z-index'])node.style.removeProperty(property);
      node.style.removeProperty('--frame-radius');
      if(frame){Object.assign(node.style,{left:`${frame.x}%`,top:`calc(${frame.y}px * var(--canvas-scale,1))`,width:frame.unit==='%'?`${frame.width}%`:`calc(${frame.width}px * var(--canvas-scale,1))`,height:frame.height?`calc(${frame.height}px * var(--canvas-scale,1))`:'auto',zIndex:frame.z});node.style.setProperty('--frame-radius',frame.corners.map(v=>`${v}px`).join(' '));}
      const img=node.querySelector('[data-block-icon]');img.hidden=!settings.icon;if(settings.icon)img.src=`/template-icons/${settings.icon}.svg`;else img.removeAttribute('src');
    }
    card.querySelectorAll('[data-design-label]').forEach(node=>{if(!node.isContentEditable)node.textContent=design[node.dataset.designLabel];});
    for(const key of ['name','title','company','bio']){const node=card.querySelector(`[data-preview="${key}"]`);if(node&&!node.isContentEditable)node.textContent=content[key]||'';}
    card.querySelectorAll('[data-design-icon]').forEach(img=>img.src=iconUrl(img.dataset.designIcon));
    form.querySelector('[data-layout-mode]').value=design.canvas?.enabled?'free':'flow';
    form.querySelector('[data-canvas-height]').value=design.canvas?.height||Math.round(body.getBoundingClientRect().height/scale());
    form.querySelectorAll('[data-global]').forEach(input=>{if(document.activeElement!==input)input.value=design[input.dataset.global];});
    if(widgets)window.CardWidgets?.refresh(card);
    requestAnimationFrame(()=>{
      if(design.canvas?.enabled){
        const required=Math.max(240,...design.blocks.filter(key=>!design.hidden.includes(key)).map(key=>design.frames[key].y+block(key).getBoundingClientRect().height/scale()+24));
        if(required>design.canvas.height){design.canvas.height=Math.min(4000,Math.ceil(required/10)*10);set('canvas-height',design.canvas.height);card.dataset.canvasHeight=design.canvas.height;}
      }
      overlay();
    });
  }
  function layers(){
    const list=form.querySelector('[data-layer-list]');list.replaceChildren();
    for(const key of design.blocks)button(`${design.hidden.includes(key)?'Скрыт: ':''}${data.blocks[key]}`,()=>select(key),list).setAttribute('aria-pressed',String(selected===key));
    form.querySelectorAll('[data-add-block]').forEach(button=>button.hidden=!design.hidden.includes(button.dataset.addBlock));
  }
  function enableCanvas(){
    if(design.canvas?.enabled)return;
    const scene=body.getBoundingClientRect(),ratio=scale();let height=240;design.frames??={};
    for(const key of design.blocks){
      let node=block(key);if(key==='avatar')node=node.querySelector('.contact-avatar');if(key==='cover')node=node.querySelector('.contact-cover');
      const rect=node.getBoundingClientRect(),hidden=design.hidden.includes(key);
      const x=hidden?6:clamp((rect.left-scene.left)/scene.width*100,0,95);
      design.frames[key]={x:rounded(x),y:hidden?height:rounded(Math.max(0,(rect.top-scene.top)/ratio)),width:hidden?88:rounded(Math.min(100-x,rect.width/scene.width*100)),unit:'%',height:key==='cover'||key==='avatar'?Math.max(20,rounded(rect.height/ratio)):0,z:key==='avatar'?3:1,corners:key==='avatar'?[200,200,200,200]:[0,0,0,0]};
      if(!hidden)height=Math.max(height,(rect.bottom-scene.top)/ratio+40);
    }
    design.canvas={enabled:true,height:Math.min(4000,Math.ceil(height/10)*10)};
  }
  function geometry(){
    const frame=design.frames?.[selected];if(!frame)return;
    const pair=element('div',{class:'control-pair'});inspector.append(pair);
    control('X, %',frame.x,value=>{frame.x=clamp(value,0,frame.unit==='%'?100-frame.width:100);},{type:'number',min:0,max:100,step:.5,parent:pair});
    control('Y, пкс',frame.y,value=>frame.y=clamp(value,0,4000),{type:'number',min:0,max:4000,parent:pair});
    control('Ширина',frame.width,value=>frame.width=clamp(value,8,frame.unit==='%'?100-frame.x:720),{type:'number',min:8,max:frame.unit==='%'?100:720});
    control('Единицы ширины',frame.unit,value=>{frame.width=value==='%'?rounded(frame.width/360*100):rounded(frame.width/100*360);frame.unit=value;if(value==='%')frame.x=Math.min(92,frame.x);frame.width=clamp(frame.width,8,value==='%'?100-frame.x:720);requestAnimationFrame(inspectorContent);},{options:[['%','Адаптивно, % холста'],['px','Пиксели макета']]});
    control('Высота, пкс (0 — по содержимому)',frame.height,value=>frame.height=clamp(value,0,2000),{type:'number',min:0,max:2000});
    control('Слой',frame.z,value=>frame.z=clamp(value,0,30),{type:'number',min:0,max:30});
    corners('Углы блока',frame.corners,values=>frame.corners=values);
  }
  function corners(title,values,fn){
    const fieldset=element('fieldset');fieldset.append(element('legend',{},title));inspector.append(fieldset);
    let current=[...(values||[12,12,12,12])],linked=current.every(v=>v===current[0]);
    control('Все углы вместе',linked,value=>linked=value,{type:'checkbox',parent:fieldset});
    const inputs=[];['Слева сверху','Справа сверху','Справа снизу','Слева снизу'].forEach((label,i)=>{
      inputs.push(control(label,current[i],value=>{value=clamp(value,0,200);if(linked){current=current.map(()=>value);inputs.forEach(input=>input.value=value);}else current[i]=value;fn([...current]);},{type:'number',min:0,max:200,parent:fieldset}));
    });
  }
  function choosePhoto(kind){if(busy){message('Дождитесь завершения текущей загрузки.');return;}pendingPhoto=kind;const input=form.querySelector('[data-photo-file]');input.multiple=kind==='gallery';input.click();}
  function inspectorContent(){
    inspector.replaceChildren();form.querySelector('[data-selected-title]').textContent=data.blocks[selected];
    const settings=state(selected);
    const actions=element('div',{class:'control-actions'});inspector.append(actions);
    if(!['identity','save'].includes(selected))button(design.hidden.includes(selected)?'Показать':'Скрыть',()=>{checkpoint();design.hidden=design.hidden.includes(selected)?design.hidden.filter(k=>k!==selected):[...design.hidden,selected];dirty=true;apply();layers();inspectorContent();},actions);
    for(const [label,delta]of [['Выше',-1],['Ниже',1]])button(label,()=>{checkpoint();const i=design.blocks.indexOf(selected),target=i+delta;if(target>=0&&target<design.blocks.length)[design.blocks[i],design.blocks[target]]=[design.blocks[target],design.blocks[i]];if(design.canvas?.enabled)design.frames[selected].z=clamp(design.frames[selected].z-delta,0,30);dirty=true;apply();layers();inspectorContent();},actions);
    if(!design.canvas?.enabled)button('Свободно перемещать',()=>{checkpoint();enableCanvas();dirty=true;apply();inspectorContent();});else geometry();
    control('Выравнивание',settings.align||'inherit',value=>settings.align=value,{options:[['inherit','Общее'],['left','Слева'],['center','По центру'],['right','Справа']]});
    control('Значки',settings.iconPosition||'inherit',value=>settings.iconPosition=value,{options:[['inherit','Общее положение'],['left','Слева'],['right','Справа'],['top','Сверху'],['none','Не показывать']]});
    control('Размер значков',settings.iconSize||design.iconSize,value=>settings.iconSize=clamp(value,16,36),{type:'number',min:16,max:36});
    if(['save','contacts','socials'].includes(selected)){
      const shapeControl=control('Форма кнопок',settings.buttonShape||'inherit',value=>{settings.buttonShape=value;delete settings.buttonCorners;},{options:[['inherit','Из шаблона'],['rect','Прямоугольные'],['rounded','Скруглённые'],['pill','Овальные'],['circle','Кружки со значками']]});
      control('Колонки кнопок',design.buttonColumns,value=>design.buttonColumns=Number(value),{options:[['1','Одна'],['2','Две']]});
      control('Заливка кнопок',design.buttonStyle,value=>design.buttonStyle=value,{options:[['filled','Заливка'],['outline','Контур']]});
      corners('Углы кнопок',settings.buttonCorners||design.buttonCorners||[12,12,12,12],values=>{settings.buttonCorners=values;settings.buttonShape='inherit';shapeControl.value='inherit';});
      button('Применить углы ко всем кнопкам',()=>{checkpoint();const values=settings.buttonCorners||[12,12,12,12];design.buttonCorners=[...values];for(const key of ['save','contacts','socials']){state(key).buttonCorners=[...values];state(key).buttonShape='inherit';}dirty=true;apply();});
    }
    if(selected==='cover'){control('Надпись',design.caption,value=>design.caption=value);control('Высота шапки в потоке',design.coverHeight,value=>design.coverHeight=clamp(value,60,240),{type:'number',min:60,max:240});button('Загрузить фото шапки',()=>choosePhoto('header'));}
    if(selected==='avatar'){control('Форма фото',design.avatarShape,value=>{design.avatarShape=value;if(design.canvas?.enabled)design.frames.avatar.corners=value==='circle'?[200,200,200,200]:value==='rounded'?[16,16,16,16]:[0,0,0,0];},{options:[['circle','Круг'],['rounded','Скруглённый квадрат'],['square','Квадрат']]});button('Загрузить фото',()=>choosePhoto('avatar'));}
    if(selected==='identity'){
      control('Размер ФИО',design.nameSize,value=>design.nameSize=clamp(value,22,40),{type:'number',min:22,max:40});
      control('Насыщенность',design.weight,value=>design.weight=Number(value),{options:[['400','Обычная'],['600','Полужирная'],['700','Жирная']]});
      for(const [key,label]of [['name','ФИО'],['title','Должность'],['company','Компания']])control(data.template?`Образец: ${label}`:label,content[key],value=>content[key]=value);
    }
    if(selected==='bio')control(data.template?'Образец текста':'О себе',content.bio||'',value=>content.bio=value,{type:'textarea'});
    if(selected==='save')control('Подпись кнопки',design.saveLabel,value=>design.saveLabel=value);
    if(selected==='socials'){
      control('Отображение',design.socialMode,value=>design.socialMode=value,{options:[['both','Значки и названия'],['icons','Круглые значки'],['radial','Солнце: контакты по кругу']]});
      control('Заголовок',design.socialLabel,value=>design.socialLabel=value);
      if(!data.template)for(const [role,label]of Object.entries(roles).filter(([key])=>!['save','phone','email','link'].includes(key)))control(`Ссылка: ${label}`,role==='website'?content.website||'':content.socials?.[role]||'',value=>{if(role==='website')content.website=value;else{content.socials??={};if(value)content.socials[role]=value;else delete content.socials[role];}renderContacts();},{type:'url'});
    }
    if(selected==='contacts'){
      control('Подпись звонка',design.phoneLabel,value=>design.phoneLabel=value);control('Подпись письма',design.emailLabel,value=>design.emailLabel=value);
      if(!data.template){
        for(const [key,label]of [['phone','Телефон'],['email','Электронная почта']])control(label,content[key]||'',value=>{content[key]=value;renderContacts();});
        content.links.forEach((link,i)=>{control(`Кнопка ${i+1}: название`,link.label,value=>{link.label=value;renderContacts();});control('Адрес ссылки',link.url,value=>{link.url=value;renderContacts();},{type:'url'});button('Убрать эту ссылку',()=>{checkpoint();content.links.splice(i,1);dirty=true;renderContacts();apply();inspectorContent();});});
        if(content.links.length<10)button('Добавить кнопку со ссылкой',()=>{checkpoint();content.links.push({label:'Новая кнопка',url:'https://example.ru'});dirty=true;renderContacts();apply();inspectorContent();});
      }
    }
    if(['video','document','map'].includes(selected)&&data.template)small('В шаблоне настраивается расположение и оформление. Видео, PDF и адрес клиент добавляет в своей визитке.');
    if(selected==='video'&&!data.template){
      content.video??={};
      control('Название видео',content.video.title||'',value=>content.video.title=value);
      control('Ссылка на видео',content.video.url||'',value=>content.video.url=value,{type:'url'});
      control('Ссылка плеера ВК (при необходимости)',content.video.embedUrl||'',value=>content.video.embedUrl=value,{type:'url'});
      small('Рутуб, ВК Видео или Ютуб. Для ВК при ошибке плеера откройте «Поделиться → Экспортировать» и скопируйте адрес src из кода, включая hash. Размещение на других сайтах должно быть разрешено автором.');
      button('Убрать видео',()=>{checkpoint();delete content.video;dirty=true;apply();inspectorContent();});
    }
    if(selected==='document'&&!data.template){
      content.document??={};
      control('Текст кнопки скачивания',content.document.label||'',value=>content.document.label=value);
      button(content.document.assetId?'Заменить PDF':'Загрузить PDF',()=>{if(!busy)form.querySelector('[data-pdf-file]').click();});
      small('Один PDF до 10 МБ. Посетитель сможет скачать файл. Загружайте документы, которые разрешено публиковать.');
      if(content.document.assetId)button('Убрать файл',()=>{checkpoint();delete content.document.assetId;dirty=true;apply();inspectorContent();});
    }
    if(selected==='map'&&!data.template){
      content.map??={};
      control('Полный адрес',content.map.address||'',value=>{content.map.address=value;delete content.map.latitude;delete content.map.longitude;});
      small('Введите город, улицу и дом. Проверьте найденную точку в предпросмотре. При неоднозначном адресе уточните обе координаты с Яндекс Карт.');
      for(const [key,label,min,max]of [['latitude','Широта',-90,90],['longitude','Долгота',-180,180]]){
        const input=control(label,content.map[key]??'',value=>content.map[key]=clamp(value,min,max),{type:'number',min,max,step:.000001});
        input.addEventListener('input',()=>{if(input.value===''){delete content.map[key];apply();}});
      }
      button('Использовать поиск по адресу',()=>{checkpoint();delete content.map.latitude;delete content.map.longitude;dirty=true;apply();inspectorContent();});
    }
    if(selected==='carousel'){
      control('Фотографий одновременно',design.carousel.visible,value=>{design.carousel.visible=clamp(value,1,10);renderGallery();},{type:'number',min:1,max:10});
      control('Высота фотографии',design.carousel.height,value=>{design.carousel.height=clamp(value,80,600);renderGallery();},{type:'number',min:80,max:600});
      control('Автоматическое пролистывание',design.carousel.autoplay,value=>{design.carousel.autoplay=value;renderGallery();},{type:'checkbox'});
      control('Интервал, секунд',design.carousel.interval,value=>{design.carousel.interval=clamp(value,2,120);renderGallery();},{type:'number',min:2,max:120});
      button(`Добавить фотографии (${photos().length}/${galleryLimit})`,()=>choosePhoto('gallery'));small('Можно листать вручную и свайпом. Автопоказ приостанавливается при наведении, фокусе и скрытии страницы. Собственные фото заменяют фото шаблона.');
      const list=element('div',{class:'photo-list'});inspector.append(list);
      photos().forEach((id,i)=>{const row=element('div',{class:'photo-row'});row.append(element('img',{src:urls.get(id)||`/template-photos/${id}.webp`,alt:`Фото ${i+1}`}));
        for(const [label,delta]of [['Раньше',-1],['Позже',1]])button(label,()=>{checkpoint();const items=photos();if(i+delta>=0&&i+delta<items.length)[items[i],items[i+delta]]=[items[i+delta],items[i]];dirty=true;renderGallery();apply();inspectorContent();},row);
        button('Убрать',()=>{checkpoint();photos().splice(i,1);dirty=true;renderGallery();apply();inspectorContent();},row);list.append(row);});
    }
    const iconRoles=[...new Set([...block(selected).querySelectorAll('[data-design-icon]')].map(img=>img.dataset.designIcon))];
    let iconTarget='block';
    control('Настраивать значок',iconTarget,value=>{iconTarget=value;selectIcon.value=value==='block'?settings.icon||'':design.icons[value]||'';},{options:[['block','Значок всего блока'],...iconRoles.map(key=>[key,roles[key]||key])]});
    const selectIcon=control('Значок из библиотеки',settings.icon||'',value=>{if(iconTarget==='block'){if(value)settings.icon=value;else delete settings.icon;}else{if(value)design.icons[iconTarget]=value;else delete design.icons[iconTarget];}},{options:[['','Стандартный / без дополнительного'],...data.icons.map(icon=>[icon.id,icon.name])]});
    button('Загрузить SVG прямо в блок',()=>{pendingIcon={key:selected,role:iconTarget};form.querySelector('[data-icon-file]').click();});
    small('SVG: до 64 КБ, контуры и фигуры. Фото: JPEG, PNG, WebP до 5 МБ.');
    if(data.template){control('Клиент может менять цвет',design.allowAccent,value=>design.allowAccent=value,{type:'checkbox'});control('Клиент может менять шрифт',design.allowFont,value=>design.allowFont=value,{type:'checkbox'});}
  }
  function select(key){selected=key;layers();inspectorContent();overlay();}
  card.addEventListener('click',event=>{if(preview)return;const node=event.target.closest('[data-design-block]');if(node){event.preventDefault();event.stopPropagation();select(node.dataset.designBlock);}},true);
  card.addEventListener('dblclick',event=>{
    if(preview)return;const node=event.target.closest('[data-preview],[data-design-label]');if(!node||node.dataset.preview==='initial')return;
    event.preventDefault();checkpoint();node.contentEditable='true';node.focus();
    node.onpaste=e=>{e.preventDefault();const text=e.clipboardData.getData('text/plain');document.execCommand('insertText',false,text);};
    node.onkeydown=e=>{if(e.key==='Escape'||(e.key==='Enter'&&node.dataset.preview!=='bio')){e.preventDefault();node.blur();}};
    node.onblur=()=>{const text=node.textContent.trim();if(node.dataset.designLabel)design[node.dataset.designLabel]=text;else content[node.dataset.preview]=text;node.contentEditable='false';dirty=true;apply();inspectorContent();};
  });
  let drag=null;
  selection.addEventListener('pointerdown',event=>{
    const handle=event.target.closest('[data-resize],[data-drag-handle]');if(!handle||preview)return;
    event.preventDefault();checkpoint();enableCanvas();apply(false);
    const rect=block(selected).getBoundingClientRect();
    drag={x:event.clientX,y:event.clientY,frame:clone(design.frames[selected]),height:rect.height/scale(),handle:handle.dataset.resize||'move'};
    handle.setPointerCapture(event.pointerId);
  });
  selection.addEventListener('pointermove',event=>{
    if(!drag)return;event.preventDefault();const dx=(event.clientX-drag.x)/scale(),dy=(event.clientY-drag.y)/scale(),snap=form.querySelector('[data-snap]').checked?4:1;
    const frame=window.CardGeometry.transform(drag.frame,{dx,dy,snap,handle:drag.handle,height:drag.height});design.frames[selected]=frame;
    design.canvas.height=Math.max(design.canvas.height,Math.min(4000,Math.ceil((frame.y+(frame.height||drag.height)+30)/10)*10));dirty=true;apply(false);
  });
  const finish=()=>{if(drag){drag=null;apply();inspectorContent();}};selection.addEventListener('pointerup',finish);selection.addEventListener('pointercancel',finish);
  form.querySelector('[data-layout-mode]').addEventListener('change',event=>{checkpoint();if(event.target.value==='free')enableCanvas();else if(design.canvas)design.canvas.enabled=false;dirty=true;apply();inspectorContent();});
  form.querySelector('[data-canvas-height]').addEventListener('change',event=>{checkpoint();enableCanvas();design.canvas.height=clamp(event.target.value,240,4000);dirty=true;apply();});
  form.querySelector('[data-screen]').addEventListener('change',event=>{artboard.style.width=`${event.target.value}px`;requestAnimationFrame(()=>apply());});
  form.querySelector('[data-preview-mode]').addEventListener('click',event=>{preview=!preview;form.classList.toggle('is-preview',preview);event.currentTarget.setAttribute('aria-pressed',String(preview));event.currentTarget.textContent=preview?'Вернуться к оформлению':'Предпросмотр';window.CardWidgets?.refresh(card);overlay();});
  form.querySelectorAll('[data-global]').forEach(input=>{input.value=design[input.dataset.global];if(!data.template&&design.sourceId&&((input.dataset.global==='font'&&!design.allowFont)||(input.dataset.global==='accent'&&!design.allowAccent)))input.disabled=true;input.addEventListener('focus',checkpoint);input.addEventListener('input',()=>{design[input.dataset.global]=input.value;dirty=true;apply();});});
  form.querySelectorAll('[data-add-block]').forEach(button=>button.addEventListener('click',()=>{const key=button.dataset.addBlock;checkpoint();design.hidden=design.hidden.filter(item=>item!==key);if(design.canvas?.enabled){const frame=design.frames[key];frame.y=Math.min(3500,design.canvas.height);frame.height=0;design.canvas.height=Math.min(4000,frame.y+450);}dirty=true;apply();select(key);}));
  function undo(){if(!history.length)return;const previous=JSON.parse(history.pop());design=previous.design;content=previous.content;dirty=true;renderContacts();renderGallery();apply();select(selected);}
  form.querySelector('[data-undo]').addEventListener('click',undo);
  document.addEventListener('keydown',event=>{
    if(event.target.closest('input,textarea,select,[contenteditable=true]'))return;
    if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'){event.preventDefault();undo();return;}
    if(!preview&&design.canvas?.enabled&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();checkpoint();const frame=design.frames[selected],amount=event.shiftKey?10:1;if(event.key==='ArrowLeft')frame.x=clamp(frame.x-amount/3.6,0,100);if(event.key==='ArrowRight')frame.x=clamp(frame.x+amount/3.6,0,frame.unit==='%'?100-frame.width:100);if(event.key==='ArrowUp')frame.y=clamp(frame.y-amount,0,4000);if(event.key==='ArrowDown')frame.y=clamp(frame.y+amount,0,4000);dirty=true;apply();inspectorContent();}
  });
  function serialize(){
    content.design=design;content.accent=design.accent;
    for(const key of ['phone','email','website'])if(!content[key])delete content[key];
    if(data.template){
      form.elements.namedItem('visual_design').value=JSON.stringify(design);
      form.querySelectorAll('[data-meta]').forEach(input=>form.elements.namedItem(input.dataset.meta).value=input.value);
    }else form.elements.namedItem('content').value=JSON.stringify(content);
  }
  form.addEventListener('submit',async event=>{
    if(busy){event.preventDefault();return;}serialize();
    event.preventDefault();busy=true;
    try{
      if(data.template){
        const sent=snapshot(),payload=new FormData(form);payload.set('operation',event.submitter?.value||'save');
        const response=await fetch(form.action||location.href,{method:'POST',body:payload,headers:{Accept:'application/json'}}),result=await response.json();
        if(!response.ok)throw new Error(result.error||'Не удалось сохранить шаблон.');
        form.elements.namedItem('version').value=result.version;
        document.querySelectorAll('[data-template-version]').forEach(input=>input.value=result.version);
        dirty=snapshot()!==sent;
        if(!dirty){design=result.design;content.design=design;}
        for(const icon of result.icons||[])if(!data.icons.some(item=>item.id===icon.id))data.icons.push(icon);
        apply();inspectorContent();message(result.published?'Шаблон опубликован в каталоге. Визитки клиентов сохраняют прежнюю версию до нового выбора шаблона.':'Черновик шаблона сохранён.');
      }else{await saveBeforeUpload();message('Черновик сохранён. Опубликуйте визитку в основном редакторе, чтобы обновить её для посетителей.');}
    }catch(error){dirty=true;message(error.message,true);}finally{busy=false;}
  });
  async function saveBeforeUpload(){
    if(data.template)return;
    serialize();const sent=snapshot();const response=await fetch(form.action||location.href,{method:'POST',body:new FormData(form),headers:{Accept:'application/json'}});
    const result=await response.json().catch(()=>null);if(!response.ok||!result?.version)throw new Error(result?.error||'Не удалось сохранить черновик. Проверьте настройки и обновите страницу при конфликте версий.');
    form.elements.namedItem('draft_version').value=result.version;dirty=snapshot()!==sent;
  }
  let pendingPhoto='header',pendingIcon=null;
  form.querySelector('[data-background-upload]').addEventListener('click',()=>choosePhoto('background'));
  async function upload(file,kind){
    const payload=new FormData();payload.set('image',file);payload.set('kind',kind);payload.set('csrfmiddlewaretoken',form.elements.namedItem('csrfmiddlewaretoken').value);
    if(!data.template)payload.set('draft_version',form.elements.namedItem('draft_version').value);
    const response=await fetch(data.uploadUrl,{method:'POST',body:payload});const result=await response.json().catch(()=>({error:'Сервер не принял файл. Проверьте размер и повторите загрузку.'}));
    if(!response.ok)throw new Error(result.error||'Не удалось загрузить файл.');
    if(result.version)form.elements.namedItem('draft_version').value=result.version;
    return result;
  }
  form.querySelector('[data-photo-file]').addEventListener('change',async event=>{
    const files=[...event.target.files];event.target.value='';if(!files.length||busy)return;
    const kind=pendingPhoto;
    const count=data.template?photos().length:(content.galleryAssetIds||[]).length;
    if(kind==='gallery'&&count+files.length>galleryLimit){message(`В карусели может быть до ${galleryLimit} фотографий.`,true);return;}
    busy=true;message('Загружаю фотографии…');
    try{
      await saveBeforeUpload();
      for(const file of files){
        const result=await upload(file,kind);urls.set(result.id,result.url);
        dirty=true;
        if(kind==='gallery'){
          if(data.template)design.carousel.photos.push(result.id);else{content.galleryAssetIds??=[];content.galleryAssetIds.push(result.id);}
        }else{
          if(data.template){design.images??={};design.images[kind]=result.id;}else content[{avatar:'avatarAssetId',header:'headerAssetId',background:'backgroundAssetId'}[kind]]=result.id;
          urls.set(kind,result.url);const img=card.querySelector(`[data-image-slot="${kind}"]`);img.src=result.url;img.hidden=false;if(kind==='avatar')card.querySelector('[data-preview=initial]')?.setAttribute('hidden','');
        }
      }
      history.length=0;dirty=true;renderGallery();apply();inspectorContent();message('Фото загружены. Сохраните оформление; публичная визитка обновится после публикации.');
    }catch(error){message(error.message,true);}finally{busy=false;renderGallery();apply();inspectorContent();}
  });
  form.querySelector('[data-pdf-file]').addEventListener('change',async event=>{
    const file=event.target.files[0];event.target.value='';if(!file||busy)return;
    if(file.size>10*1024*1024){message('PDF должен быть не больше 10 МБ.',true);return;}
    busy=true;message('Загружаю PDF…');
    try{await saveBeforeUpload();const result=await upload(file,'pdf');urls.set(result.id,result.url);content.document??={};content.document.assetId=result.id;history.length=0;dirty=true;apply();inspectorContent();message('PDF добавлен в черновик. Опубликуйте визитку, чтобы файл стал доступен посетителям.');}catch(error){message(error.message,true);}finally{busy=false;}
  });
  form.querySelector('[data-icon-file]').addEventListener('change',async event=>{
    const file=event.target.files[0];event.target.value='';if(!file||!pendingIcon||busy)return;const target={...pendingIcon};busy=true;message('Загружаю значок…');
    try{const result=await upload(file,'icon');data.icons.push(result);checkpoint();if(target.role==='block')state(target.key).icon=result.id;else design.icons[target.role]=result.id;dirty=true;apply();inspectorContent();message('Значок добавлен прямо в блок. Сохраните оформление.');}catch(error){message(error.message,true);}finally{busy=false;}
  });
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
  window.addEventListener('resize',overlay);card.querySelectorAll('img').forEach(img=>img.addEventListener('load',overlay));
  renderContacts();renderGallery();apply();select(selected);
})();
