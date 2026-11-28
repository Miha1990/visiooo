/* Shared geometry for dragging cards and filling contact rows. */
((root)=>{
  function destination(entries,x,y,buttons=false){
    let best=null,distance=Infinity;
    for(const entry of entries){const r=entry.rect;
      if(!r.width||!r.height)continue;
      const dx=Math.max(r.left-x,0,x-r.right),dy=Math.max(r.top-y,0,y-r.bottom),score=dy*dy+dx*dx;
      if(score<distance){distance=score;best=entry;}
    }
    if(!best)return null;
    const r=best.rect,after=buttons&&y>=r.top&&y<=r.bottom?x>r.left+r.width/2:y>r.top+r.height/2;
    return {element:best.element,after};
  }
  function scrollSpeed(y,top,bottom){
    const edge=Math.min(90,(bottom-top)/4);
    return y<top+edge?-Math.ceil(18*Math.min(1,(top+edge-y)/edge)):y>bottom-edge?Math.ceil(18*Math.min(1,(y-bottom+edge)/edge)):0;
  }
  function contactGap(spans,columns=12){let used=0;for(const span of spans){if(used+span>columns)used=0;used=(used+span)%columns;}return used?columns-used:Math.min(columns,spans.at(-1)||6);}
  const api={destination,scrollSpeed,contactGap};
  if(typeof module==='object')module.exports=api;else root.CardEditorDrag=api;
})(typeof window==='object'?window:globalThis);
