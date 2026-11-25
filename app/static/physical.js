(() => {
  const guide=document.querySelector('[data-physical-guide]'),writeButton=document.getElementById('nfc-write'),status=document.getElementById('nfc-status'),consent=document.getElementById('nfc-write-consent'),cancelButton=document.getElementById('nfc-cancel');
  let controller,phone='',method='qr';
  const available=Boolean(window.isSecureContext&&'NDEFReader' in window&&writeButton?.dataset.localOnly!=='true');
  function choose(nextPhone,nextMethod='qr'){
    if(!['iphone','android'].includes(nextPhone))return;
    controller?.abort();phone=nextPhone;method=phone==='iphone'?'qr':nextMethod==='nfc'?'nfc':'qr';
    guide?.querySelectorAll('[data-phone]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.phone===phone)));
    guide?.querySelectorAll('[data-bind-method]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.bindMethod===method)));
    for(const [selector,visible]of [['[data-android-methods]',phone==='android'],['[data-guide-qr]',method==='qr'],['[data-guide-nfc]',method==='nfc'],['[data-physical-qr]',method==='qr'],['[data-physical-nfc]',phone==='android'&&method==='nfc']])document.querySelectorAll(selector).forEach(el=>el.hidden=!visible);
    if(status&&method==='nfc')status.textContent=writeButton.dataset.localOnly==='true'?'Для записи нужна публичная ссылка сервиса.':!available?'Откройте эту страницу в Chrome на Android или выберите QR-код.':'';
    try{sessionStorage.setItem('physical-phone',phone);sessionStorage.setItem('physical-method',method);}catch{}
  }
  guide?.querySelectorAll('[data-phone]').forEach(button=>button.addEventListener('click',()=>choose(button.dataset.phone)));
  guide?.querySelectorAll('[data-bind-method]').forEach(button=>button.addEventListener('click',()=>choose(phone,button.dataset.bindMethod)));
  try{choose(sessionStorage.getItem('physical-phone'),sessionStorage.getItem('physical-method'));}catch{}
  window.addEventListener('pagehide',()=>controller?.abort());
  if(!writeButton)return;
  writeButton.disabled=!available;
  cancelButton.addEventListener('click',()=>controller?.abort());
  writeButton.addEventListener('click',async()=>{
    if(writeButton.disabled||phone!=='android'||method!=='nfc')return;
    if(!consent.checked){status.textContent='Подтвердите замену записи в вашей NFC-метке.';consent.focus();return;}
    writeButton.disabled=true;cancelButton.hidden=false;controller=new AbortController();const current=controller,timeout=setTimeout(()=>current.abort(),60000);
    status.textContent='Приложите NFC-карточку к телефону…';
    try{await new window.NDEFReader().write({records:[{recordType:'url',data:writeButton.dataset.url}]},{overwrite:true,signal:current.signal});status.textContent='Готово. Уберите карточку и приложите снова для проверки.';}
    catch(error){status.textContent=error.name==='AbortError'?'Запись отменена.':'Не удалось записать. Проверьте NFC телефона и возможность перезаписи карточки.';}
    finally{clearTimeout(timeout);writeButton.disabled=!available;cancelButton.hidden=true;if(controller===current)controller=null;}
  });
})();
