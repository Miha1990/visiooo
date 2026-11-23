/* The editor mirrors server allowlists. The server remains authoritative. */
((root) => {
  function parsed(value){const url=new URL(value);if(url.protocol!=='https:'||url.username||url.password||(url.port&&url.port!=='443')||/[\x00-\x20]/.test(value))throw Error();return [url,url.hostname.replace(/^www\./,'')];}
  function video(value,override=''){
    try{
      const [url,host]=parsed(value),path=url.pathname;
      if(['youtube.com','m.youtube.com','youtu.be','youtube-nocookie.com'].includes(host)){
        const match=path.match(/^\/(?:shorts|embed|live)\/([\w-]{11})\/?$/),id=match?.[1]||(host==='youtu.be'?path.replace(/^\/|\/$/g,''):url.searchParams.get('v'));
        return !override&&/^[\w-]{11}$/.test(id||'')?`https://www.youtube-nocookie.com/embed/${id}`:'';
      }
      if(host==='rutube.ru'){
        const match=path.match(/^\/(?:video\/(?:private\/)?|play\/embed\/)([a-fA-F0-9]{32})\/?$/),key=url.searchParams.get('p');
        return match&&!override&&(!key||/^[\w-]{1,200}$/.test(key))?`https://rutube.ru/play/embed/${match[1]}${key?'/?'+new URLSearchParams({p:key}):''}`:'';
      }
      if(['vk.com','m.vk.com','vkvideo.ru'].includes(host)){
        const match=path.match(/^\/video(-?\d{1,20})_(\d{1,20})\/?$/);if(!match&&path!=='/video_ext.php')return '';
        let params=match?new URLSearchParams({oid:match[1],id:match[2]}):url.searchParams;
        if(override){const [player,provider]=parsed(override);if(!['vk.com','vkvideo.ru'].includes(provider)||player.pathname!=='/video_ext.php')return '';params=player.searchParams;}
        const oid=params.get('oid'),id=params.get('id'),hash=params.get('hash');
        if(!/^-?\d{1,20}$/.test(oid||'')||!/^\d{1,20}$/.test(id||'')||(hash&&!/^[\w-]{1,200}$/.test(hash))||(match&&(oid!==match[1]||id!==match[2])))return '';
        const clean=new URLSearchParams({oid,id});if(hash)clean.set('hash',hash);return `https://vk.com/video_ext.php?${clean}`;
      }
    }catch{}return '';
  }
  function map(location){
    if(!location.address)return '';
    let params;
    if(Number.isFinite(location.latitude)&&Number.isFinite(location.longitude)){
      const point=`${location.longitude},${location.latitude}`;params={ll:point,pt:point+',pm2rdm',z:16};
    }else params={text:location.address,z:16};
    return 'https://yandex.ru/map-widget/v1/?'+new URLSearchParams(params);
  }
  const api={video,map};if(typeof module==='object')module.exports=api;else root.CardEmbeds=api;
})(typeof window==='object'?window:globalThis);
