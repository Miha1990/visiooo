/* HSV picker: the original accent input remains the source saved by the form. */
((root)=>{
  const clamp=value=>Math.max(0,Math.min(1,value));
  function fromHex(hex){
    const rgb=hex.replace('#','').match(/../g).map(value=>parseInt(value,16)/255),[r,g,b]=rgb,max=Math.max(...rgb),min=Math.min(...rgb),delta=max-min;
    let h=0;if(delta)h=(max===r?(g-b)/delta+(g<b?6:0):max===g?(b-r)/delta+2:(r-g)/delta+4)*60;
    return {h,s:max?delta/max:0,v:max};
  }
  function toHex({h,s,v}){
    const c=v*s,x=c*(1-Math.abs((h/60)%2-1)),m=v-c;
    const rgb=h<60?[c,x,0]:h<120?[x,c,0]:h<180?[0,c,x]:h<240?[0,x,c]:h<300?[x,0,c]:[c,0,x];
    return '#'+rgb.map(value=>Math.round((value+m)*255).toString(16).padStart(2,'0')).join('');
  }
  function create(anchor,input,parent){
    const doc=anchor.ownerDocument,node=(tag,attrs={},text)=>{const el=doc.createElement(tag);for(const [key,value]of Object.entries(attrs))el.setAttribute(key,value);if(text!==undefined)el.textContent=text;return el;};
    const panel=node('dialog',{class:'builder-color-panel','aria-label':'Свой цвет'}),square=node('div',{class:'color-picker-square',tabindex:'0',role:'slider','aria-label':'Насыщенность и яркость: стрелки влево и вправо меняют насыщенность, вверх и вниз — яркость','aria-valuemin':'0','aria-valuemax':'100'}),marker=node('span',{class:'color-picker-marker','aria-hidden':'true'});
    const controls=node('div',{class:'color-picker-controls'}),hueRow=node('div',{class:'color-picker-hue-row'}),sample=node('span',{class:'color-picker-sample','aria-hidden':'true'}),hue=node('input',{type:'range',min:'0',max:'359',step:'1',class:'color-picker-hue','aria-label':'Оттенок'});
    const hex=node('input',{type:'text',class:'color-picker-hex',maxlength:'7',pattern:'#[0-9a-fA-F]{6}',required:'',spellcheck:'false',autocapitalize:'characters','aria-label':'Цвет HEX',placeholder:'#963F2B'}),label=node('span',{class:'color-picker-format','aria-hidden':'true'},'HEX'),actions=node('div',{class:'color-picker-actions'}),cancel=node('button',{type:'button'},'Отмена'),done=node('button',{type:'button'},'Готово');
    square.append(marker);hueRow.append(sample,hue);actions.append(cancel,done);controls.append(hueRow,hex,label,actions);panel.append(square,controls);parent.append(panel);
    let hsv=fromHex(input.value),original=input.value,dragging=false;
    function paint(write=true){
      const color=toHex(hsv);square.style.backgroundColor=`hsl(${hsv.h} 100% 50%)`;marker.style.left=hsv.s*100+'%';marker.style.top=(1-hsv.v)*100+'%';hue.value=Math.round(hsv.h);sample.style.backgroundColor=color;
      square.setAttribute('aria-valuenow',String(Math.round(hsv.v*100)));square.setAttribute('aria-valuetext',`Насыщенность ${Math.round(hsv.s*100)}%, яркость ${Math.round(hsv.v*100)}%, ${color}`);
      hex.value=color.toUpperCase();hex.setCustomValidity('');
      if(write&&input.value.toLowerCase()!==color){input.value=color;input.dispatchEvent(new Event('input',{bubbles:true}));}
    }
    function finish(commit){
      if(commit&&!hex.reportValidity())return;
      if(!commit&&input.value!==original){input.value=original;input.dispatchEvent(new Event('input',{bubbles:true}));}
      panel.close();anchor.focus();
    }
    function position(){const bounds=anchor.getBoundingClientRect(),width=panel.offsetWidth,height=panel.offsetHeight;panel.style.left=Math.max(12,Math.min(innerWidth-width-12,bounds.right-width))+'px';panel.style.top=Math.max(12,Math.min(innerHeight-height-12,bounds.top-height-12))+'px';}
    const open=()=>{original=input.value;hsv=fromHex(original);paint(false);panel.showModal();position();square.focus({preventScroll:true});};
    function point(event){const rect=square.getBoundingClientRect();hsv.s=clamp((event.clientX-rect.left)/rect.width);hsv.v=1-clamp((event.clientY-rect.top)/rect.height);paint();}
    square.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();dragging=true;square.setPointerCapture(event.pointerId);square.focus({preventScroll:true});point(event);});
    square.addEventListener('pointermove',event=>{if(dragging)point(event);});
    square.addEventListener('pointerup',event=>{if(dragging)point(event);dragging=false;});square.addEventListener('pointercancel',()=>dragging=false);
    square.addEventListener('keydown',event=>{const step=event.shiftKey?0.1:0.01;if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();if(event.key==='ArrowLeft')hsv.s=clamp(hsv.s-step);if(event.key==='ArrowRight')hsv.s=clamp(hsv.s+step);if(event.key==='ArrowUp')hsv.v=clamp(hsv.v+step);if(event.key==='ArrowDown')hsv.v=clamp(hsv.v-step);paint();});
    hue.addEventListener('input',()=>{hsv.h=Number(hue.value);paint();});
    hex.addEventListener('input',()=>{hex.setCustomValidity(/^#[0-9a-f]{6}$/i.test(hex.value)?'':'Укажите цвет в формате #963F2B.');if(hex.checkValidity()){hsv=fromHex(hex.value);paint();}});
    hex.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();finish(true);}});
    cancel.addEventListener('click',()=>finish(false));done.addEventListener('click',()=>finish(true));panel.addEventListener('cancel',event=>{event.preventDefault();finish(false);});
    panel.addEventListener('click',event=>{const rect=panel.getBoundingClientRect();if(event.target===panel&&(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom))finish(false);});
    root.addEventListener('resize',()=>{if(panel.open)position();});
    return {open,panel};
  }
  const api={fromHex,toHex,create};if(typeof module==='object')module.exports=api;else root.CardColorPicker=api;
})(typeof window==='object'?window:globalThis);
