(() => {
  'use strict';
  function detect(nav) {
    const ua=nav.userAgent||'',ios=/iPhone|iPad|iPod/i.test(ua)||(nav.platform==='MacIntel'&&nav.maxTouchPoints>1),android=/Android/i.test(ua);
    let browser='other';
    if(/Instagram|FBAN|FBAV|Telegram|VKClient|VKAndroidApp|; wv\)|\bwv\b/i.test(ua))browser='embedded';
    else if(/YaBrowser|YaSearchBrowser/i.test(ua))browser='yandex';
    else if(/SamsungBrowser/i.test(ua))browser='samsung';
    else if(/EdgA|EdgiOS|Edg\//i.test(ua))browser='edge';
    else if(/OPR\/|OPiOS|Opera/i.test(ua))browser='opera';
    else if(/FxiOS|Firefox/i.test(ua))browser='firefox';
    else if(/CriOS|Chrome/i.test(ua))browser='chrome';
    else if(/Safari/i.test(ua)&&/Version\//i.test(ua))browser='safari';
    return {ios,android,mobile:ios||android,browser};
  }
  function instructions(device) {
    const names={safari:'Safari',chrome:'Chrome',yandex:'Яндекс Браузер',samsung:'Samsung Internet',edge:'Microsoft Edge',opera:'Opera',firefox:'Firefox',embedded:'Браузер внутри приложения',other:'Ваш браузер'};
    const result={label:`${device.ios?'iPhone / iPad':device.android?'Android':'Компьютер'} · ${names[device.browser]}`,steps:[],note:''};
    if(device.browser==='embedded'){
      result.steps=device.ios
        ? ['В меню приложения нажмите «Открыть в Safari» или «Открыть в браузере».','В открывшемся браузере нажмите «Поделиться».','Выберите «На экран Домой», затем «Добавить».']
        : ['В меню приложения нажмите «Открыть в браузере».','В браузере откройте меню и выберите «Установить приложение» или «Добавить на главный экран».','Подтвердите установку.'];
      result.note='Во встроенном браузере установка может быть недоступна. Пункт открытия во внешнем браузере находится в меню приложения.';
    }else if(device.ios){
      const share={safari:'Нажмите «Поделиться» в меню или на панели Safari.',chrome:'Нажмите «Поделиться» справа от адресной строки Chrome.',firefox:'Нажмите значок «Поделиться» в адресной строке Firefox.',yandex:'Откройте меню Яндекс Браузера и нажмите «Поделиться».',edge:'Откройте меню Microsoft Edge и нажмите «Поделиться».',opera:'Откройте меню Opera и нажмите «Поделиться».'};
      result.steps=[share[device.browser]||'Нажмите «Поделиться» в меню или на панели браузера.','Прокрутите список действий и выберите «На экран Домой».','Если есть «Открывать как веб-приложение», включите. Нажмите «Добавить».'];
      result.note='Если пункта «На экран Домой» нет, прокрутите меню «Поделиться» до конца и проверьте «Править действия». Доступность зависит от версии браузера и iOS.';
    }else if(device.android){
      const menus={chrome:['Откройте меню Chrome рядом с адресной строкой.','Выберите «Установить и создать ярлык», затем «Установить».'],firefox:['Откройте меню Firefox.','Выберите «Добавить на домашний экран» или «Установить».'],samsung:['Откройте меню Samsung Internet — три полоски.','Выберите «Добавить страницу в», затем «Главный экран».'],yandex:['Откройте меню Яндекс Браузера.','Найдите «Добавить на главный экран» или «Установить приложение».'],edge:['Откройте меню Microsoft Edge.','Найдите «Добавить на телефон» или «Добавить на главный экран».'],opera:['Откройте меню Opera.','Найдите «Главный экран» или «Добавить на главный экран».']};
      result.steps=[...(menus[device.browser]||['Откройте меню браузера.','Найдите «Установить приложение» или «Добавить на главный экран».']),'Подтвердите добавление.'];
      result.note='Название пункта зависит от версии браузера: «Установить приложение», «На главный экран» или «Добавить ярлык».';
    }else{
      result.steps=['На iPhone: нажмите «Поделиться», затем «На экран Домой» и «Добавить».','На Android: откройте меню браузера, выберите «Установить приложение» или «Добавить на главный экран» и подтвердите.'];
    }
    return result;
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={detect,instructions};
  if(typeof document==='undefined')return;
  const dialog=document.querySelector('[data-install-dialog]'),banner=document.querySelector('[data-install-banner]');
  if(!dialog||!banner)return;
  const device=detect(navigator),launchers=[...document.querySelectorAll('[data-install-open]')],native=dialog.querySelector('[data-install-native]'),status=dialog.querySelector('[data-install-status]');
  const media=window.matchMedia('(display-mode: standalone)'),storageKey='visiooo-install-later';
  let deferred=null,installed=Boolean(navigator.standalone||media.matches),busy=false;
  const storeLater=()=>{try{localStorage.setItem(storageKey,String(Date.now()+7*86400000));}catch{}};
  const later=()=>{try{return Number(localStorage.getItem(storageKey))>Date.now();}catch{return false;}};
  function render(){
    const info=instructions(device);dialog.querySelector('[data-install-browser]').textContent=info.label;
    const steps=dialog.querySelector('[data-install-steps]');steps.replaceChildren(...info.steps.map(text=>{const li=document.createElement('li');li.textContent=text;return li;}));
    const note=dialog.querySelector('[data-install-note]');note.hidden=!info.note;note.textContent=info.note;
    native.hidden=!deferred;status.textContent='';
  }
  function finish(){installed=true;deferred=null;banner.hidden=true;launchers.forEach(button=>button.hidden=true);if(dialog.open)dialog.close();}
  function open(){if(installed||typeof dialog.showModal!=='function')return;render();banner.hidden=true;if(!dialog.open)dialog.showModal();}
  launchers.forEach(button=>{button.hidden=installed;button.addEventListener('click',open);});
  dialog.querySelectorAll('[data-install-close]').forEach(button=>button.addEventListener('click',()=>dialog.close()));
  dialog.addEventListener('close',storeLater);
  banner.querySelector('[data-install-dismiss]').addEventListener('click',()=>{banner.hidden=true;storeLater();});
  dialog.addEventListener('click',event=>{if(event.target!==dialog)return;const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();});
  window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();if(installed)return;deferred=event;if(dialog.open)render();});
  window.addEventListener('appinstalled',finish);media.addEventListener?.('change',event=>{if(event.matches)finish();});
  native.addEventListener('click',async()=>{
    if(!deferred||busy)return;busy=true;native.disabled=true;const prompt=deferred;deferred=null;
    try{await prompt.prompt();const choice=await prompt.userChoice;if(choice.outcome==='accepted')finish();else{storeLater();render();status.textContent='Вы можете установить приложение позже из меню браузера.';}}
    catch{render();status.textContent='Воспользуйтесь инструкцией выше.';}
    finally{busy=false;native.disabled=false;}
  });
  const autoPath=['/','/app/cards','/app/cards/'].includes(window.location.pathname);
  function offer(){
    if(installed||!device.mobile||later()||!autoPath)return;
    if(document.hidden||document.querySelector('dialog[open], [data-analytics-banner]:not([hidden]), input:focus, textarea:focus, select:focus')){setTimeout(offer,3000);return;}
    banner.hidden=false;
  }
  setTimeout(offer,8000);
})();
