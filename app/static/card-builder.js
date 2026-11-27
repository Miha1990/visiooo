/* Progressive customer UI. Existing forms keep server validation and upload/version handling. */
(() => {
  const editor=document.querySelector('.editor'),form=document.getElementById('editor-form'),config=document.getElementById('builder-options');
  if(!editor||!form||!config||typeof HTMLDialogElement==='undefined')return;
  const options=JSON.parse(config.textContent),types=new Map(options.map(item=>[item.kind,item]));
  const source=form.elements.namedItem('button_items');if(!source)return;
  if(editor.querySelector('.contact-card')?.dataset.buttonLayout!=='tiles')form.dataset.pendingBuilder='true';
  let items;try{items=JSON.parse(source.value||'[]');}catch{return;}
  const daisySource=form.elements.namedItem('daisy_data');let daisy;try{daisy=JSON.parse(daisySource?.value||'{}');}catch{daisy={};}daisy={label:daisy.label||'Контакты',items:daisy.items||[]};let editingDaisy=false;
  const activeItems=()=>editingDaisy?daisy.items:items;
  const node=(tag,attrs={},text)=>{const el=document.createElement(tag);for(const [key,value]of Object.entries(attrs))el.setAttribute(key,value);if(text!==undefined)el.textContent=text;return el;};
  const button=(text,fn,cls='')=>{const el=node('button',{type:'button',class:cls},text);if(fn)el.addEventListener('click',fn);return el;};
  const field=name=>form.elements.namedItem(name);
  const iconBase=new URL('icons/',document.querySelector('script[src*="card-builder."]').src).href;
  const image=kind=>node('img',{src:iconBase+(types.get(kind)?.icon||'link')+'.svg',width:28,height:28,alt:''});
  const built=node('div',{class:'builder-editor'}),cover=node('div',{class:'builder-cover'}),identity=button('',()=>profile.showModal(),'builder-identity'),tiles=node('div',{class:'builder-tiles'}),rows=node('div',{class:'builder-rows'});
  identity.setAttribute('aria-label','Изменить имя, должность, компанию и информацию о себе');
  const socials=node('section',{class:'builder-socials'}),socialGrid=node('div',{class:'builder-social-grid'});
  socials.append(node('h2',{},'Соцсети и мессенджеры'),socialGrid);
  const oldChildren=[...form.children],sourceBox=node('div',{class:'builder-source',hidden:''});
  for(const child of oldChildren)sourceBox.append(child);form.append(sourceBox);form.noValidate=true;
  const mode=node('input',{type:'hidden',name:'builder_mode',value:'tiles'});form.append(mode);form.action=location.pathname;
  const errors=[...sourceBox.querySelectorAll('.errorlist')].map(el=>el.textContent.trim()).filter(Boolean);
  editor.prepend(built);built.append(cover,form);form.prepend(identity,tiles,rows,socials);
  const dialog=(title,parent=editor)=>{
    const el=node('dialog',{class:'builder-dialog','aria-label':title}),head=node('div',{class:'builder-dialog-head'});
    head.append(node('h2',{},title),button('Закрыть',()=>el.close(),'builder-close'));el.append(head);parent.append(el);
    el.addEventListener('click',event=>{const rect=el.getBoundingClientRect();if(event.target===el&&(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom))el.close();});
    return el;
  };
  const profile=dialog('Информация о себе',form);
  for(const key of ['name','title','company','bio']){const input=field(key);if(input)profile.append(input.closest('div'));}
  profile.append(button('Готово',()=>{if(field('name').reportValidity())profile.close();},'button'));
  profile.addEventListener('keydown',event=>{if(event.key==='Enter'&&event.target.tagName==='INPUT'){event.preventDefault();if(field('name').reportValidity())profile.close();}});
  const settings=dialog('Оформление и настройки');
  const styling=editor.querySelector('#styling-fields');if(styling)settings.append(styling);
  const templateLink=editor.querySelector('a[href$="/templates"]');if(templateLink)settings.append(templateLink);
  const saveTemplate=editor.querySelector('form[action*="/templates/from-card/"]');if(saveTemplate)settings.append(saveTemplate);
  const publish=dialog('Публикация визитки');const publishPanel=editor.querySelector('#publish-card');if(publishPanel)publish.append(publishPanel);
  const danger=editor.querySelector('.danger-zone');if(danger)settings.append(danger);
  const featureFields=sourceBox.querySelector('[data-card-feature-fields]'),features=dialog('График работы',form),featureSettings=dialog('Главная кнопка и анимация',form);
  if(featureFields){
    for(const name of ['action_kind','action_label','action_target','motion']){const input=field(name);if(input)featureSettings.append(input.closest('div'));}
    featureFields.querySelectorAll('h3').forEach(heading=>{if(!heading.textContent.startsWith('График'))heading.remove();});
    featureSettings.append(button('Готово',()=>{const invalid=featureSettings.querySelector(':invalid');if(invalid)invalid.reportValidity();else featureSettings.close();},'button'));
    featureFields.open=true;features.append(featureFields,button('Готово',()=>{if(features.querySelector(':invalid'))features.querySelector(':invalid').reportValidity();else features.close();},'button'));
  }
  const actionKind=field('action_kind'),actionTarget=field('action_target');
  const actionHint=()=>{const phone=actionKind.value==='phone';actionTarget.type=phone?'tel':'text';actionTarget.inputMode=phone?'tel':'url';actionTarget.placeholder=phone?'+7 (928) 909-18-17':'t.me/username или example.com/booking';};
  actionKind?.addEventListener('change',actionHint);if(actionKind&&actionTarget)actionHint();
  const sources=new Map();
  for(const key of ['video','map','document']){
    const fields=sourceBox.querySelector(`fieldset:has([name="${({video:'video_url',map:'map_address',document:'pdf_label'})[key]}"])`);
    if(fields){const d=dialog(({video:'Видео',map:'Адрес на карте',document:'Название файла'})[key],form);d.append(fields,button('Готово',()=>d.close(),'button'));sources.set(key,d);}
  }
  const media=new Map();
  editor.querySelectorAll('[data-builder-media]').forEach(section=>{const key=section.dataset.builderMedia,d=dialog(key==='carousel'?'Карусель фотографий':'Загрузить PDF');d.append(section);media.set(key,d);});
  const openMedia=key=>{const d=media.get(key)||sources.get(key);if(d)d.showModal();};
  // Place each real upload form in the visual hero, retaining CSRF and version fields.
  for(const slot of ['logo','header','avatar']){
    const panel=styling?.querySelector(`.image-panel[data-image-slot="${slot}"]`),upload=panel?.querySelector('form[enctype]');if(!upload)continue;
    const input=upload.querySelector('input[type=file]'),picture=panel.querySelector('.styling-thumbnail');
    upload.className='builder-image-upload builder-image-'+slot;upload.setAttribute('aria-label',({logo:'Логотип',header:'Обложка',avatar:'Фото профиля'})[slot]);
    const label=node('label',{for:input.id,class:'builder-image-control'});
    if(picture){const img=picture.cloneNode();img.removeAttribute('class');label.append(img);if(slot==='header')cover.style.backgroundImage=`url("${picture.src}")`;}
    else if(slot==='avatar')label.append(node('img',{class:'builder-avatar-symbol',src:iconBase+'avatar.svg',alt:''}));
    label.append(node('span',{class:'builder-image-label'},slot==='avatar'?'+':slot==='logo'?'+ Лого':'+ Обложка'));
    const hidden=node('div',{class:'builder-upload-fields'});while(upload.firstChild)hidden.append(upload.firstChild);upload.append(hidden,label);cover.append(upload);
    input.addEventListener('change',()=>{if(input.files.length)upload.requestSubmit();});
  }
  const chooser=dialog('Добавить блок'),search=node('input',{type:'search',placeholder:'Поиск по реквизитам','aria-label':'Поиск по реквизитам',class:'builder-search'}),choices=node('div');chooser.append(search,choices);
  const edit=dialog('Настройка кнопки',form),caption=node('input',{type:'text',maxlength:80,id:'builder-button-caption'}),target=node('input',{type:'text',maxlength:2048,id:'builder-button-target'}),targetLabel=node('label',{for:target.id},'URL'),error=node('p',{class:'builder-error',role:'alert'});
  const prefix=node('span',{class:'builder-target-prefix'}),targetRow=node('div',{class:'builder-target-row'}),targetHint=node('p',{class:'builder-target-hint'}),extension=node('input',{type:'text',inputmode:'numeric',maxlength:8,pattern:'[0-9]{0,8}',placeholder:'Добавочный номер',id:'builder-button-extension'}),extensionBox=node('div');
  targetRow.append(prefix,target);extensionBox.append(node('label',{for:extension.id},'Добавочный номер'),extension);
  edit.append(node('label',{for:caption.id},'Название кнопки'),caption,targetLabel,targetRow,targetHint,extensionBox,error);
  let editing=-1,kind='link';
  const isPhone=()=>['phone','other_phone','whatsapp'].includes(kind);
  function formatPhone(raw){if(raw.startsWith('+')&&!raw.startsWith('+7'))return raw;let digits=raw.replace(/\D/g,'');if(raw.startsWith('+7')||digits.length>10&&/^[78]/.test(digits))digits=digits.slice(1);digits=digits.slice(0,10);if(!digits)return '';return '+7 ('+digits.slice(0,3)+(digits.length>=3?') ':'')+digits.slice(3,6)+(digits.length>6?'-':'')+digits.slice(6,8)+(digits.length>8?'-':'')+digits.slice(8,10);}
  function inputHint(){const rules=window.CardButtons.inputs[kind],full=/^(?:https?:\/\/|www\.)/i.test(target.value)||rules?.hosts.some(host=>target.value.toLowerCase().startsWith(host+'/'));prefix.textContent=rules?.prefix&&!full?rules.prefix:'';prefix.hidden=!prefix.textContent;
    const normalized=kind==='email'?'':window.CardButtons.normalize(kind,target.value);targetHint.textContent=kind==='whatsapp'&&normalized?'Ссылка: '+normalized:rules?.prefix&&normalized?'Ссылка: '+normalized:rules?'Укажите имя пользователя или вставьте ссылку на профиль этой соцсети.':'';
  }
  target.addEventListener('input',()=>{if(isPhone()){target.value=formatPhone(target.value);}else if(window.CardButtons.inputs[kind]?.prefix){target.value=target.value.replace(/\s/g,'').replace(/^@/,'');}error.textContent='';inputHint();});
  target.addEventListener('beforeinput',event=>{const cursor=target.selectionStart;if(!isPhone()||event.inputType!=='deleteContentBackward'||cursor!==target.selectionEnd||!cursor||/[0-9]/.test(target.value[cursor-1]))return;const digits=target.value.replace(/\D/g,''),index=target.value.slice(0,cursor).replace(/\D/g,'').length-1;event.preventDefault();target.value=index<1?'':formatPhone('+'+digits.slice(0,index)+digits.slice(index+1));target.dispatchEvent(new Event('input',{bubbles:true}));});
  target.addEventListener('paste',event=>{if(!isPhone())return;const pasted=event.clipboardData?.getData('text');if(!pasted)return;event.preventDefault();let raw=pasted.trim();if(kind==='whatsapp'){const url=window.CardButtons.normalize(kind,raw);if(url)raw='+'+new URL(url).pathname.slice(1);}target.value=formatPhone(raw);inputHint();});
  extension.addEventListener('input',()=>extension.value=extension.value.replace(/[^0-9]/g,''));
  const persist=()=>{source.value=JSON.stringify(items);if(daisySource){daisySource.value=JSON.stringify(daisy.items.length?daisy:{});daisySource.dispatchEvent(new Event('input',{bubbles:true}));}source.dispatchEvent(new Event('input',{bubbles:true}));draw();};
  function commit(){
    let value=target.value.trim(),label=caption.value.trim()||types.get(kind).label;
    if(!caption.reportValidity())return false;
    if(kind!=='email'&&(kind!=='file'||value))value=window.CardButtons.normalize(kind,value);
    if(kind==='file'&&target.value.trim()&&!value){error.textContent='Укажите корректный URL файла или загрузите PDF с устройства.';target.focus();return false;}
    const item={kind,label,value};if(!extension.disabled&&extension.value)item.extension=extension.value;
    const href=window.CardButtons.href(item);
    if(kind!=='file'||value){
      if(!href){error.textContent=isPhone()?'Укажите полный номер: +7 (___) ___-__-__.':kind==='email'?'Укажите адрес электронной почты.':window.CardButtons.inputs[kind]?'Проверьте имя пользователя или ссылку на выбранную соцсеть.':'Укажите ссылку, например google.com.';target.focus();return false;}
      if(href.startsWith('tel:'))value=item.value;
      else if(href.startsWith('mailto:'))value=href.slice(7);
      else{const host=new URL(href).hostname;if(!host.includes('.')&&host!=='localhost'&&!host.includes(':')){error.textContent='Укажите полный адрес сайта, например google.com.';return false;}value=href;}
    }
    item.value=value;
    const list=activeItems(),limit=editingDaisy?8:30;
    if(editing<0){if(list.length>=limit){error.textContent='Можно добавить до '+limit+' кнопок.';return false;}list.push(item);editing=list.length-1;}
    else list[editing]=item;
    persist();return true;
  }
  const fileUpload=button('Загрузить PDF с устройства',()=>{if(commit()){edit.close();openMedia('document');}},'builder-file-upload');edit.append(fileUpload);
  edit.append(button('Готово',()=>{if(commit())edit.close();},'button'));
  edit.addEventListener('keydown',event=>{if(event.key==='Enter'&&event.target.tagName==='INPUT'){event.preventDefault();if(commit())edit.close();}});
  const remove=button('Удалить блок',()=>{if(!editingDaisy)window.CardLayout?.removeButton(form,editing);activeItems().splice(editing,1);persist();edit.close();},'builder-remove');edit.append(remove);
  function editButton(index,newKind){
    editing=index;kind=newKind||activeItems()[index]?.kind;const item=activeItems()[index],sameKind=item?.kind===kind;
    caption.value=sameKind?item.label:types.get(kind).label;target.value=sameKind?item.value:'';error.textContent='';remove.hidden=index<0;
    targetLabel.textContent=isPhone()?'Номер телефона':kind==='email'?'Электронная почта':window.CardButtons.inputs[kind]?.prefix?'Имя пользователя':kind==='file'?'URL файла (или загрузите PDF ниже)':'URL';
    target.type=isPhone()?'tel':'text';target.inputMode=isPhone()?'numeric':kind==='email'?'email':window.CardButtons.inputs[kind]?.prefix?'text':'url';target.autocapitalize='none';target.spellcheck=false;
    target.placeholder=isPhone()?'+7 (___) ___-__-__':kind==='email'?'mail@example.ru':window.CardButtons.inputs[kind]?.prefix?'username':'URL';
    extensionBox.hidden=!['phone','other_phone'].includes(kind);extension.disabled=extensionBox.hidden;extension.value=sameKind?item.extension||'':'';
    const rules=window.CardButtons.inputs[kind];if(sameKind&&isPhone()){const number=kind==='whatsapp'?window.CardButtons.normalize(kind,item.value):item.value;if(number){const raw=kind==='whatsapp'?'+'+new URL(number).pathname.slice(1):number;target.value=raw.startsWith('+7')?formatPhone(raw):raw;}}
    else if(sameKind&&rules?.prefix&&target.value.startsWith(rules.prefix)){const tail=target.value.slice(rules.prefix.length).replace(/\/$/,'');if(rules.pattern.test(tail))target.value=tail;}
    inputHint();
    fileUpload.hidden=kind!=='file'||!media.has('document');edit.showModal();
  }
  let choiceGroup='all',choiceIndex=-1;
  function choose(group='all',index=-1,inDaisy=false){editingDaisy=inDaisy;choiceGroup=group;choiceIndex=index;search.value='';filter();chooser.showModal();search.focus();}
  function filter(){
    const text=search.value.toLowerCase().trim();choices.replaceChildren();
    if(choiceIndex>=0&&!text){const current=activeItems()[choiceIndex];choices.append(button('Редактировать «'+current.label+'»',()=>{chooser.close();editButton(choiceIndex);},'builder-choice builder-current-choice'),node('p',{class:'builder-replace-hint'},'Или выберите другой тип блока. Замена сохранится после нажатия «Готово».'));}
    for(const group of ['Реквизиты','Дополнительный контент','Соцсети и мессенджеры']){
      if(choiceGroup==='social'&&group!=='Соцсети и мессенджеры')continue;
      if(choiceGroup==='primary'&&group==='Соцсети и мессенджеры')continue;
      const found=options.filter(item=>item.group===group&&(`${item.label} ${item.kind}`).toLowerCase().includes(text));if(!found.length)continue;
      const grid=node('div',{class:group==='Соцсети и мессенджеры'?'builder-choice-socials':'builder-choice-list'});choices.append(node('h3',{},group),grid);
      for(const item of found){const b=button('',()=>{chooser.close();editButton(choiceIndex,item.kind);},'builder-choice');b.append(image(item.kind),node('span',{},item.label));grid.append(b);}
    }
    const extras=[['carousel','Карусель фотографий'],['video','Видео'],['map','Адрес на карте'],['business','График работы']].filter(([key,label])=>(media.has(key)||sources.has(key)||key==='business'&&featureFields)&&label.toLowerCase().includes(text));
    if(!editingDaisy&&choiceGroup!=='social'&&choiceIndex<0){choices.append(node('h3',{},'Другие блоки'));for(const [key,label]of [...extras,['daisy','Ромашка — контакты по кругу']]){const choice=button('',()=>{chooser.close();form.dispatchEvent(new CustomEvent('card:insert-block',{detail:{key}}));if(key==='daisy')daisySettings.showModal();else if(key==='business')features.showModal();else openMedia(key);},'builder-choice builder-example-choice');choice.append(node('strong',{},label));const example=window.CardBlockExamples?.create(key);if(example)choice.append(example);choices.append(choice);}choices.append(button('Оформление и настройки',()=>{chooser.close();settings.showModal();},'builder-choice'));}
    if(!editingDaisy&&choiceGroup!=='social'&&choiceIndex<0&&featureFields)choices.append(button('Главная кнопка и анимация',()=>{chooser.close();featureSettings.showModal();},'builder-choice'));
    if(!choices.childElementCount)choices.append(node('p',{},'Ничего не найдено. Попробуйте другое название.'));
  }
  search.addEventListener('input',filter);
  const daisySettings=dialog('Ромашка — контакты по кругу',form),daisyLabel=node('input',{type:'text',maxlength:40,id:'builder-daisy-label',value:daisy.label}),daisyGrid=node('div',{class:'builder-choice-socials'});
  daisySettings.append(node('label',{for:daisyLabel.id},'Надпись в центре'),daisyLabel,node('p',{},'До 8 кнопок вокруг центра. Каждую можно настроить отдельно: телефон, почта, ссылка или соцсеть.'),daisyGrid,button('Добавить кнопку вокруг центра',()=>{daisySettings.close();choose('all',-1,true);},'builder-file-upload'),button('Готово',()=>daisySettings.close(),'button'));
  daisyLabel.addEventListener('input',()=>{daisy.label=daisyLabel.value.trim()||'Контакты';persist();});
  const daisySection=node('section',{class:'builder-palette'});daisySection.append(node('h2',{},'Ромашка'),button('Настроить контакты по кругу',()=>daisySettings.showModal(),'builder-content-row'));form.append(daisySection);
  function drawDaisy(){daisyGrid.replaceChildren();daisy.items.forEach((item,index)=>{const b=button('',()=>{daisySettings.close();choose('all',index,true);},'builder-choice');b.append(image(item.kind),node('span',{},item.label));daisyGrid.append(b);});}
  const palette=node('section',{class:'builder-palette','aria-label':'Цветовая гамма'}),accent=field('accent');
  palette.append(node('h2',{},'Цветовая гамма'));
  const swatches=node('div',{class:'builder-swatches'});
  const colors=[['#315948','Лесной'],['#2457db','Синий'],['#683db0','Фиолетовый'],['#a02c49','Ягодный'],['#985222','Терракотовый'],['#263342','Графитовый']];
  const paint=()=>{built.style.setProperty('--builder-accent',accent.value);swatches.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.classList.contains('builder-swatch-custom')?!colors.some(([color])=>color===accent.value.toLowerCase()):b.dataset.color===accent.value.toLowerCase())));};
  for(const [color,name]of colors){const b=button('',()=>{accent.value=color;accent.dispatchEvent(new Event('input',{bubbles:true}));},'builder-swatch');b.dataset.color=color;b.style.background=color;b.setAttribute('aria-label',name);swatches.append(b);}
  palette.append(swatches);if(accent){
    const wrapper=accent.closest('div');wrapper.hidden=true;palette.append(wrapper);
    const custom=button('',null,'builder-swatch builder-swatch-custom');custom.setAttribute('aria-label','Свой цвет');custom.setAttribute('aria-haspopup','dialog');swatches.append(custom);
    const picker=window.CardColorPicker?.create(custom,accent,editor);custom.addEventListener('click',()=>{if(picker)picker.open();else accent.click();});
    accent.addEventListener('input',paint);paint();
  }
  const address=field('card_address'),addressSection=node('section',{class:'builder-address'}),availability=node('p',{'aria-live':'polite',class:'builder-address-status'});
  let checkTimer,checkSerial=0;
  addressSection.append(node('h2',{},'Назначить ссылку'));
  if(address){const prefix=new URL(document.getElementById('public-url').value);prefix.pathname=prefix.pathname.slice(0,prefix.pathname.lastIndexOf('/')+1);
    address.placeholder='ivan-petrov';
    addressSection.append(node('label',{for:address.id},'Адрес визитки'),node('p',{class:'builder-address-prefix'},prefix.href),address,node('p',{},'Для нового адреса: 3–40 латинских букв, цифр или дефисов. Например, ivan-petrov.'),availability,
      node('p',{class:'builder-address-warning'},'Ссылка постоянная: изменение контактов не меняет её и QR-код. При смене адреса QR-код изменится, старая ссылка перестанет работать. Сменить адрес опубликованной визитки можно только с подтверждением.'));
    address.addEventListener('input',()=>{field('address_confirmed').value='';delete form.dataset.approvedAddress;clearTimeout(checkTimer);const serial=++checkSerial;availability.textContent='Проверяем адрес…';
      checkTimer=setTimeout(async()=>{try{const url=new URL(editor.dataset.addressCheck,location.origin);url.searchParams.set('address',address.value.trim());const response=await fetch(url,{headers:{Accept:'application/json'}});if(!response.ok)throw Error();const result=await response.json();if(serial!==checkSerial)return;availability.textContent=result.message;availability.dataset.available=String(result.available);}catch{if(serial===checkSerial)availability.textContent='Проверим адрес при сохранении.';}},350);
    });
    form.confirmAddress=()=>{const value=address.value.trim(),current=editor.dataset.currentAddress;if(!value||value===current||form.dataset.approvedAddress===value)return true;
      if(!window.confirm('Сохранить постоянную ссылку '+prefix.href+value+'?\n\nПри смене адреса QR-код изменится. Старая ссылка и QR-код с ней перестанут открывать визитку. Скачайте новый QR-код и обновите прямые ссылки в NFC-метках. Изменения адреса вступят в силу сразу после сохранения.'))return false;
      field('address_confirmed').value='true';form.dataset.approvedAddress=value;return true;
    };
    form.addEventListener('card:saved',event=>{editor.dataset.currentAddress=event.detail.address;address.value=event.detail.address;field('address_confirmed').value='';delete form.dataset.approvedAddress;const publicInput=document.getElementById('public-url');publicInput.value=event.detail.public_url;editor.querySelectorAll('img[data-avatar-qr],.share-row img').forEach(img=>{if(img.hasAttribute('src'))img.src=img.src.split('?')[0]+'?v='+event.detail.version;});});
  }
  form.append(palette,addressSection);
  function draw(){
    drawDaisy();
    identity.replaceChildren();
    for(const [key,label]of [['name','Имя'],['title','Должность'],['company','Компания'],['bio','О себе']]){
      const value=field(key)?.value.trim();identity.append(node('span',{class:'builder-identity-'+key},value&&value!=='Новая визитка'?value:label));
    }
    tiles.replaceChildren();rows.replaceChildren();socialGrid.replaceChildren();
    const primary=items.map((item,index)=>({item,index})).filter(({item})=>types.get(item.kind)?.group!=='Соцсети и мессенджеры');
    for(let i=0;i<Math.max(2,primary.length);i++){
      const entry=primary[i],item=entry?.item,b=button('',()=>choose('all',entry?.index??-1),item?'builder-filled-button':'builder-add-button');
      b.setAttribute('aria-label',item?'Изменить: '+item.label:'Добавить контакт или ссылку');
      if(item)b.append(image(item.kind),node('span',{},item.label));else b.append(node('span',{'aria-hidden':'true'},'+'));
      (i<2?tiles:rows).append(b);
    }
    items.forEach((item,index)=>{if(types.get(item.kind)?.group!=='Соцсети и мессенджеры')return;
      const tile=button('',()=>choose('all',index),'builder-social-tile'),face=node('span',{class:'builder-social-face'});
      tile.setAttribute('aria-label','Изменить: '+item.label);face.append(image(item.kind));
      tile.append(face,node('span',{class:'builder-social-name'},item.label),node('span',{class:'builder-social-value'},item.value.replace(/^https?:\/\//,'')));socialGrid.append(tile);
    });
    const addSocial=button('+',()=>choose('social'),'builder-social-add');addSocial.setAttribute('aria-label','Добавить соцсеть или мессенджер');socialGrid.append(addSocial);
    for(const [key,label]of [['carousel','Карусель фотографий'],['video','Видео'],['map','Карта']]){
      const filled=key==='carousel'?Boolean(media.get(key)?.querySelector('figure')):Boolean(field(key==='video'?'video_url':'map_address')?.value.trim());
      if(filled)rows.append(button(label,()=>openMedia(key),'builder-content-row'));
    }
  }
  form.addEventListener('input',draw);
  form.addEventListener('submit',event=>{if(!form.checkValidity()){event.preventDefault();const invalid=form.querySelector(':invalid');const d=invalid?.closest('dialog');if(d&&!d.open)d.showModal();invalid?.reportValidity();}else if(form.confirmAddress&&!form.confirmAddress())event.preventDefault();});
  const saveChoices=dialog('Сохранить визитку');saveChoices.classList.add('builder-save-choices');
  const saveDraft=node('button',{type:'submit',form:form.id,name:'save_and_close',value:'yes',class:'button'},'Сохранить черновик');
  saveChoices.append(node('p',{},'Черновик виден только вам. Публикация обновит визитку для посетителей, включая удаление фотографий.'),saveDraft,button('Опубликовать',()=>{saveChoices.close();publish.showModal();},'button'));
  saveDraft.addEventListener('click',()=>saveChoices.close());
  const topbar=node('nav',{class:'builder-topbar','aria-label':'Редактирование визитки'}),back=node('a',{href:'/app/cards','aria-label':'На главную'},'← На главную'),save=button('Сохранить и закрыть',()=>saveChoices.showModal());
  topbar.append(back,save);editor.prepend(topbar);
  const toolbar=node('div',{class:'builder-toolbar'}),addField=button('+ Добавить поле',()=>choose(),'builder-add-row'),preview=button('Предпросмотр',()=>setView(editor.dataset.view==='preview'?'edit':'preview'));
  toolbar.append(preview);editor.append(toolbar);form.append(addField);
  function setView(view){editor.dataset.view=view;preview.textContent=view==='preview'?'Редактировать':'Предпросмотр';form.dispatchEvent(new CustomEvent('card:editor-view',{detail:{view}}));}
  const returnToEdit=button('Вернуться к редактированию',()=>setView('edit'),'builder-preview-back');editor.querySelector('.preview-column')?.prepend(returnToEdit);
  for(const child of [...editor.children])if(![topbar,built,toolbar].includes(child)&&child.tagName!=='DIALOG'&&!child.classList.contains('editor-grid'))child.hidden=true;
  const oldColumn=editor.querySelector('.editor-form-column');if(oldColumn)oldColumn.hidden=true;
  editor.classList.add('card-builder-active');
  if(errors.length)built.prepend(node('p',{class:'builder-error',role:'alert'},errors.join(' ')));
  setView(editor.dataset.view||'edit');persist();
  window.CardBuilder={choose,openMedia,setView,profile:()=>profile.showModal(),daisy:()=>daisySettings.showModal(),features:()=>features.showModal()};
})();
