((root,factory)=>{const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.CardGeometry=api;})(typeof window!=='undefined'?window:globalThis,()=>{
  const clamp=(v,min,max)=>Math.min(max,Math.max(min,Number(v)||0));
  const round=v=>Math.round(v*100)/100;
  function transform(frame,{dx,dy,handle='move',height=0,snap=1}){
    const result=JSON.parse(JSON.stringify(frame));
    const quantize=v=>Math.round(v/snap)*snap;
    if(handle==='move'){
      result.x=round(clamp(frame.x+quantize(dx)/3.6,0,frame.unit==='%'?100-frame.width:100));
      result.y=clamp(quantize(frame.y+dy),0,4000);return result;
    }
    const west=['1','7','8'].includes(handle),east=['3','4','5'].includes(handle),north=['1','2','3'].includes(handle),south=['5','6','7'].includes(handle);
    if(west||east){
      const original=frame.unit==='%'?frame.width*3.6:frame.width;
      const limit=west?Math.min(frame.unit==='%'?360:720,original+frame.x*3.6):(frame.unit==='%'?(100-frame.x)*3.6:720);
      const width=clamp(quantize(original+(west?-dx:dx)),frame.unit==='%'?28.8:28,limit);
      result.x=west?round(clamp(frame.x+(original-width)/3.6,0,100)):frame.x;
      result.width=frame.unit==='%'?round(Math.min(width/3.6,100-result.x)):width;
    }
    if(north||south){
      const original=frame.height||height,newHeight=clamp(quantize(original+(north?-dy:dy)),20,north?Math.min(2000,frame.y+original):2000);
      result.height=newHeight;result.y=north?Math.max(0,frame.y+original-newHeight):frame.y;
    }
    return result;
  }
  return {transform};
});
