/* The editor mirrors server allowlists. The server remains authoritative. */
((root) => {
  function parsed(value){const url=new URL(value);if(url.protocol!=='https:'||url.username||url.password||(url.port&&url.port!=='443')||/[\x00-\x20]/.test(value))throw Error();return [url,url.hostname.replace(/^www\./,'')];}
  function video(value,override=''){
    try{
      const [url,host]=parsed(value),path=url.pathname;
      if(override&&!['vk.com','m.vk.com','vk.ru','m.vk.ru','vkvideo.ru','dailymotion.com','dai.ly','geo.dailymotion.com'].includes(host))return '';
      if(['youtube.com','m.youtube.com','youtu.be','youtube-nocookie.com'].includes(host)){
        const match=path.match(/^\/(?:shorts|embed|live)\/([\w-]{11})\/?$/),id=match?.[1]||(host==='youtu.be'?path.replace(/^\/|\/$/g,''):url.searchParams.get('v'));
        return !override&&/^[\w-]{11}$/.test(id||'')?`https://www.youtube-nocookie.com/embed/${id}`:'';
      }
      if(host==='rutube.ru'){
        const match=path.match(/^\/(?:video\/(?:private\/)?|shorts\/|play\/embed\/)([a-fA-F0-9]{32})\/?$/),key=url.searchParams.get('p');
        return match&&!override&&(!key||/^[\w-]{1,200}$/.test(key))?`https://rutube.ru/play/embed/${match[1]}${key?'/?'+new URLSearchParams({p:key}):''}`:'';
      }
      if(['vk.com','m.vk.com','vk.ru','m.vk.ru','vkvideo.ru'].includes(host)){
        const match=path.match(/^\/(?:video|clip)(-?\d{1,20})_(\d{1,20})\/?$/);if(!match&&path!=='/video_ext.php')return '';
        let playerHost=host,params=match?new URLSearchParams({oid:match[1],id:match[2]}):url.searchParams;
        if(override){const [player,provider]=parsed(override);if(!['vk.com','vk.ru','vkvideo.ru'].includes(provider)||player.pathname!=='/video_ext.php')return '';params=player.searchParams;playerHost=provider;}
        const oid=params.get('oid'),id=params.get('id'),hash=params.get('hash');
        if(!/^-?\d{1,20}$/.test(oid||'')||!/^\d{1,20}$/.test(id||'')||(hash&&!/^[\w-]{1,200}$/.test(hash))||(match&&(oid!==match[1]||id!==match[2])))return '';
        const clean=new URLSearchParams({oid,id});if(hash)clean.set('hash',hash);return `https://${['vk.ru','m.vk.ru'].includes(playerHost)?'vk.ru':'vk.com'}/video_ext.php?${clean}`;
      }
      if(['vimeo.com','player.vimeo.com'].includes(host)){
        const match=path.match(/^\/(?:video\/)?(\d{1,20})(?:\/([A-Za-z0-9]{1,64}))?\/?$/),key=url.searchParams.get('h')||match?.[2]||'';
        return match&&(!key||/^[A-Za-z0-9]{1,64}$/.test(key))?`https://player.vimeo.com/video/${match[1]}${key?'?'+new URLSearchParams({h:key}):''}`:'';
      }
      if(['ok.ru','m.ok.ru'].includes(host)){const match=path.match(/^\/(?:video|videoembed)\/(\d{1,20})\/?$/);return match?'https://ok.ru/videoembed/'+match[1]:'';}
      if(['tiktok.com','m.tiktok.com'].includes(host)){const match=path.match(/^\/(?:@[^/]+\/video\/|player\/v1\/)(\d{1,30})\/?$/);return match?'https://www.tiktok.com/player/v1/'+match[1]:'';}
      if(['dailymotion.com','dai.ly','geo.dailymotion.com'].includes(host)){
        const [player,provider]=parsed(override||value),match=player.pathname.match(/^\/player\/([A-Za-z0-9]{1,40})\.html$/),id=player.searchParams.get('video'),original=path.match(/^\/(?:video\/)?([A-Za-z0-9]{1,40})\/?$/);
        return provider==='geo.dailymotion.com'&&match&&/^[A-Za-z0-9]{1,40}$/.test(id||'')&&(!override||original?.[1]===id)?`https://geo.dailymotion.com/player/${match[1]}.html?`+new URLSearchParams({video:id}):'';
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
  function videoLink(value){try{const [url,host]=parsed(value);return host.includes('.')&&!host.endsWith('.local')&&!host.endsWith('.localhost')&&!/^[\d.]+$/.test(host)&&!host.includes(':')?url.href:'';}catch{return '';}}
  function videoAspect(value){
    try{const [url,host]=parsed(value);if(['vk.com','m.vk.com','vk.ru','m.vk.ru','vkvideo.ru'].includes(host)&&/^\/clip(-?\d{1,20})_(\d{1,20})\/?$/.test(url.pathname))return '9/16';}catch{}
    return '16/9';
  }
  const api={video,map,videoLink,videoAspect};if(typeof module==='object')module.exports=api;else root.CardEmbeds=api;
})(typeof window==='object'?window:globalThis);
