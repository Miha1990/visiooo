(() => {
  const guide=document.querySelector('[data-physical-guide]'),writeButton=document.getElementById('nfc-write'),status=document.getElementById('nfc-status'),consent=document.getElementById('nfc-write-consent'),cancelButton=document.getElementById('nfc-cancel');
  let controller,method='qr';
  const supported=Boolean(window.isSecureContext&&typeof window.NDEFReader==='function');
  const localOnly=guide?.dataset.localOnly==='true'||writeButton?.dataset.localOnly==='true';
  const available=supported&&!localOnly;
  function choose(nextMethod='qr'){
    controller?.abort();method=available&&nextMethod==='nfc'?'nfc':'qr';
    guide?.querySelectorAll('[data-bind-method]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.bindMethod===method)));
    for(const [selector,visible]of [['[data-nfc-methods]',available],['[data-guide-qr]',method==='qr'],['[data-guide-nfc]',method==='nfc'],['[data-physical-qr]',method==='qr'],['[data-physical-nfc]',method==='nfc']])document.querySelectorAll(selector).forEach(el=>el.hidden=!visible);
    if(status&&method==='nfc')status.textContent='';
    try{sessionStorage.setItem('physical-method',method);}catch{}
  }
  const capability=guide?.querySelector('[data-nfc-capability]');
  if(capability)capability.textContent=localOnly?'Для записи NFC нужна публичная ссылка сервиса. Сейчас доступен QR-код.':supported?'Браузер поддерживает запись NFC. Вы также можете использовать QR-код.':'Запись NFC недоступна в этом браузере. Используйте QR-код. Уже записанная NFC-карта продолжит открывать свою ссылку.';
  guide?.querySelectorAll('[data-bind-method]').forEach(button=>{button.disabled=button.dataset.bindMethod==='nfc'&&!available;button.addEventListener('click',()=>choose(button.dataset.bindMethod));});
  let preferred;try{preferred=sessionStorage.getItem('physical-method');}catch{}
  choose(available&&preferred!=='qr'?'nfc':'qr');
  window.addEventListener('pagehide',()=>controller?.abort());
  if(!writeButton)return;
  writeButton.disabled=!available;
  cancelButton.addEventListener('click',()=>controller?.abort());
  writeButton.addEventListener('click',async()=>{
    if(writeButton.disabled||!available||method!=='nfc')return;
    if(!consent.checked){status.textContent='Подтвердите замену записи в вашей NFC-метке.';consent.focus();return;}
    writeButton.disabled=true;cancelButton.hidden=false;controller=new AbortController();const current=controller,timeout=setTimeout(()=>current.abort(),60000);
    status.textContent='Приложите NFC-карточку к телефону…';
    try{await new window.NDEFReader().write({records:[{recordType:'url',data:writeButton.dataset.url}]},{overwrite:true,signal:current.signal});status.textContent='Готово. Уберите карточку и приложите снова для проверки.';}
    catch(error){status.textContent=error.name==='AbortError'?'Запись отменена.':'Не удалось записать. Проверьте NFC телефона и возможность перезаписи карточки.';}
    finally{clearTimeout(timeout);writeButton.disabled=!available;cancelButton.hidden=true;if(controller===current)controller=null;}
  });
})();
