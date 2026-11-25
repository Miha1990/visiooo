/* Keep native form validation, password managers and server-side throttling. */
(() => {
  const passwords=[];
  document.querySelectorAll('input[type="password"]').forEach((input,index)=>{
    if(input.dataset.visibilityReady)return;
    input.dataset.visibilityReady='true';if(!input.id)input.id='password-field-'+index;
    const wrapper=document.createElement('div'),toggle=document.createElement('button');
    wrapper.className='password-control';toggle.type='button';toggle.className='password-visibility';
    toggle.setAttribute('aria-controls',input.id);
    const set=visible=>{input.type=visible?'text':'password';toggle.textContent=visible?'Скрыть':'Показать';toggle.setAttribute('aria-pressed',String(visible));toggle.setAttribute('aria-label',visible?'Скрыть пароль':'Показать пароль');};
    input.before(wrapper);wrapper.append(input,toggle);set(false);passwords.push(()=>set(false));
    toggle.addEventListener('click',()=>set(input.type==='password'));
  });
  const controllers=[];
  document.querySelectorAll('[data-code-request]').forEach(form=>{
    const button=form.querySelector('[data-code-request-button]');if(!button)return;
    const label=button.textContent.trim(),email=form.elements.namedItem('email');
    let deadline=Date.now()+Math.max(0,Number(form.dataset.retrySeconds)||0)*1000;
    let scope=(form.dataset.retryEmail||'').trim().toLowerCase(),busy=false;
    const remaining=()=>email&&scope&&email.value.trim().toLowerCase()!==scope?0:Math.max(0,Math.ceil((deadline-Date.now())/1000));
    const update=()=>{const seconds=remaining();button.disabled=busy||seconds>0;button.setAttribute('aria-busy',String(busy));button.textContent=seconds?'Повторная отправка через '+Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0'):busy?'Отправляем код…':label;};
    form.addEventListener('submit',event=>{
      if(event.defaultPrevented)return;
      if(busy||remaining()>0){event.preventDefault();return;}
      if(!form.checkValidity()){event.preventDefault();form.reportValidity();return;}
      busy=true;scope=email?.value.trim().toLowerCase()||'';deadline=Date.now()+60000;update();
    });
    email?.addEventListener('input',update);update();
    controllers.push({update,resume:()=>{busy=false;update();}});
  });
  if(controllers.length)setInterval(()=>controllers.forEach(controller=>controller.update()),250);
  document.addEventListener('visibilitychange',()=>controllers.forEach(controller=>controller.update()));
  window.addEventListener('pageshow',event=>{passwords.forEach(hide=>hide());controllers.forEach(controller=>event.persisted?controller.resume():controller.update());});
  window.addEventListener('pagehide',()=>passwords.forEach(hide=>hide()));
})();
