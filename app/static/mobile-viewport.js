/* Keep mobile dialogs inside the visible viewport when the keyboard opens. */
(() => {
  const root=document.documentElement,viewport=window.visualViewport;
  let frame=0;
  function update(){
    frame=0;
    if(window.innerWidth>780){root.style.removeProperty('--mobile-viewport-height');root.style.removeProperty('--mobile-viewport-top');root.classList.remove('keyboard-open');return;}
    const height=viewport?.height||window.innerHeight,top=viewport?.offsetTop||0;
    root.style.setProperty('--mobile-viewport-height',height+'px');root.style.setProperty('--mobile-viewport-top',top+'px');
    const input=document.activeElement,typing=input?.matches('textarea, [contenteditable="true"], input:not([type=checkbox]):not([type=radio]):not([type=button]):not([type=submit]):not([type=file]):not([type=color]):not([type=range])');
    root.classList.toggle('keyboard-open',Boolean(typing&&viewport&&viewport.scale===1&&window.innerHeight-height>140));
  }
  function schedule(){if(!frame)frame=requestAnimationFrame(update);}
  window.addEventListener('resize',schedule,{passive:true});window.addEventListener('pageshow',schedule);
  viewport?.addEventListener('resize',schedule,{passive:true});viewport?.addEventListener('scroll',schedule,{passive:true});
  document.addEventListener('focusin',schedule);document.addEventListener('focusout',schedule);update();
})();
