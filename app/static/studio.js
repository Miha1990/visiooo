(() => {
  const form = document.querySelector('#template-form');
  if (!form) return;
  const card = document.querySelector('.studio-preview .contact-card');
  const body = card.querySelector('.design-body');
  const list = form.querySelector('.studio-blocks');
  const get = name => form.elements.namedItem(name)?.value;
  const fonts = {ui:"'Segoe UI',system-ui,sans-serif",serif:'Georgia,serif',rounded:"'Trebuchet MS',Arial,sans-serif"};
  const iconBase = new URL('icons/', document.currentScript.src).href;
  const numeric = {gap:['gap',8,32],radius:['radius',0,36],avatar:['avatarSize',64,144],cover:['coverHeight',60,240],icon:['iconSize',16,36],name:['nameSize',22,40]};
  const update = () => {
    const set = (name, value) => card.style.setProperty(`--${name}`, value);
    for (const [name, field] of Object.entries({accent:'accent','design-bg':'background','design-text':'text'})) {
      if (/^#[a-f0-9]{6}$/i.test(get(field))) set(name, get(field));
    }
    for (const [name,[field,min,max]] of Object.entries(numeric)) set(`design-${name}`,`${Math.max(min,Math.min(max,Number(get(field)) || min))}px`);
    set('design-font',fonts[get('font')]); set('design-align',get('align'));
    set('design-weight',get('weight')); set('design-columns',get('buttonColumns'));
    set('design-avatar-radius',`${({square:0,rounded:16,circle:999})[get('avatarShape')]}px`);
    set('design-button-radius',`${({rect:0,rounded:12,pill:999})[get('buttonShape')]}px`);
    card.dataset.buttonStyle=get('buttonStyle');card.dataset.iconPosition=get('iconPosition');card.dataset.socialMode=get('socialMode');
    const hidden = [...form.querySelectorAll('[name=hidden]:checked')].map(input=>input.value);
    const order = [...list.children].map(item=>item.dataset.block);
    form.elements.namedItem('block_order').value=order.join(',');
    for (const key of order) {
      const block=body.querySelector(`[data-design-block="${key}"]`);
      block.hidden=hidden.includes(key);body.append(block);
      const align=get(`block_${key}_align`) || 'inherit';
      const position=get(`block_${key}_iconPosition`) || 'inherit';
      block.dataset.blockAlign=align;block.dataset.blockIcons=position==='inherit'?get('iconPosition'):position;
      const size=Number(get(`block_${key}_iconSize`)) || Number(get('iconSize'));
      block.style?.setProperty('--design-icon',`${Math.max(16,Math.min(36,size))}px`);
      const icon=block.querySelector?.('[data-block-icon]');
      if(icon){
        const value=get(`block_${key}_icon`);
        icon.hidden=!value;
        if(value)icon.src=`/template-icons/${value}.svg`;else icon.removeAttribute('src');
      }
    }
    card.querySelectorAll('[data-design-label]').forEach(node=>node.textContent=get(node.dataset.designLabel));
    card.querySelectorAll('[data-design-icon]').forEach(node=>{
      const value=get(`icon_${node.dataset.designIcon}`);
      node.src=value?`/template-icons/${value}.svg`:`${iconBase}${node.dataset.designIcon}.svg`;
    });
  };
  form.addEventListener('input',update);form.addEventListener('change',update);
  list.addEventListener('click',event=>{
    const button=event.target.closest('[data-move]');if(!button)return;
    const item=button.closest('li');
    if(button.dataset.move==='up' && item.previousElementSibling) list.insertBefore(item,item.previousElementSibling);
    if(button.dataset.move==='down' && item.nextElementSibling) list.insertBefore(item.nextElementSibling,item);
    update();
  });
  let dragged=null;
  list.addEventListener('dragstart',event=>{dragged=event.target.closest('li');if(dragged)event.dataTransfer.setData('text/plain',dragged.dataset.block);});
  list.addEventListener('dragover',event=>{if(dragged)event.preventDefault();});
  list.addEventListener('drop',event=>{event.preventDefault();const item=event.target.closest('li');if(dragged && item && dragged!==item){list.insertBefore(dragged,item);update();}dragged=null;});
  list.addEventListener('dragend',()=>dragged=null);
  document.querySelectorAll('[data-preview-width]').forEach(button=>button.addEventListener('click',()=>{
    document.querySelector('.studio-width').dataset.wide=String(button.dataset.previewWidth==='wide');
  }));
  update();
})();
