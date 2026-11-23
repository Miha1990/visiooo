/* Save text before a separate upload/reorder operation, retaining server versions. */
(() => {
  const form=document.getElementById('editor-form');if(!form)return;
  const fingerprint=()=>JSON.stringify([...new FormData(form)].filter(([key])=>!['draft_version','csrfmiddlewaretoken'].includes(key)));
  let saved=fingerprint(),busy=false,leaving=false;
  const approved=new WeakSet();
  const reveal=input=>{let parent=input?.parentElement;while(parent){if(parent.tagName==='DETAILS')parent.open=true;if(parent.tagName==='DIALOG'&&!parent.open)parent.showModal();parent=parent.parentElement;}input?.focus();};
  const showError=(text,input)=>{
    let notice=form.querySelector('[data-save-error]');if(!notice){notice=document.createElement('p');notice.dataset.saveError='';notice.className='editor-form-error';notice.setAttribute('role','alert');form.prepend(notice);}
    notice.textContent=text;reveal(input);notice.scrollIntoView({block:'center',behavior:'smooth'});
  };
  form.addEventListener('submit',event=>{if(!event.defaultPrevented)leaving=true;});
  form.addEventListener('input',event=>event.target.setCustomValidity?.(''));
  const editor=form.closest('.editor');
  editor.querySelectorAll('form[enctype="multipart/form-data"],form[action*="/content-media"],form[action$="/avatar/remove"],form[action$="/publish"]').forEach(target=>{
    target.addEventListener('submit',async event=>{
      if(approved.has(target)){approved.delete(target);leaving=true;return;}
      if(fingerprint()===saved&&!(form.dataset?.pendingBuilder==='true'&&target.action?.endsWith('/publish'))){leaving=true;return;}
      event.preventDefault();if(busy)return;
      if(!form.checkValidity()){reveal(form.querySelector(':invalid'));form.reportValidity();return;}
      busy=true;const submitter=event.submitter,payload=new FormData(form),sent=fingerprint();
      form.inert=true;target.inert=true;if(submitter)submitter.disabled=true;
      try{
        const response=await fetch(form.action||location.href,{method:'POST',body:payload,headers:{Accept:'application/json'}});
        const result=await response.json();
        if(!response.ok||!result.version){
          const errors=result.errors||{};let first=null;
          for(const [name,items]of Object.entries(errors)){const input=form.elements.namedItem(name);if(input&&input.type!=='hidden'){input.setCustomValidity(items.map(item=>item.message).join(' '));first??=input;}}
          form.inert=false;
          showError(Object.values(errors).flat().map(item=>item.message).join(' ')||result.error||'Не удалось сохранить правки.',first);
          return;
        }
        saved=sent;if(form.dataset)delete form.dataset.pendingBuilder;editor.querySelectorAll('input[name="draft_version"]').forEach(input=>input.value=result.version);
        form.inert=false;target.inert=false;if(submitter)submitter.disabled=false;
        approved.add(target);target.requestSubmit(submitter||undefined);
      }catch{form.inert=false;showError('Не удалось сохранить данные. Проверьте соединение и повторите загрузку. Введённые данные остались в форме.');}
      finally{busy=false;form.inert=false;target.inert=false;if(submitter)submitter.disabled=false;}
    });
  });
  window.addEventListener('beforeunload',event=>{if(!leaving&&fingerprint()!==saved){event.preventDefault();event.returnValue='';}});
})();
