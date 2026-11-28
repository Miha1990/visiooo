const {test}=require('node:test');
const assert=require('node:assert/strict');
const embeds=require('../../static/card-embeds.js');
test('VK clips use portrait proportions while ordinary videos keep landscape proportions',()=>{
 for(const domain of ['vkvideo.ru','vk.com','vk.ru','m.vk.com','m.vk.ru']){
  assert.equal(embeds.videoAspect(`https://${domain}/clip-243793209_456239017?sh=4`),'9/16');
  assert.equal(embeds.videoAspect(`https://${domain}/video-243793209_456239017`),'16/9');
 }
 assert.equal(embeds.videoAspect('https://vkvideo.ru.evil.test/clip-243793209_456239017'),'16/9');
});

test('live preview gives each video slide its own aspect ratio',()=>{
 const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
 const createElement=()=>({attrs:{},children:[],setAttribute(key,value){this.attrs[key]=value;},append(...children){this.children.push(...children);}});
 const track={dataset:{},replaceChildren(...children){this.children=children;}},controls={};
 const section={dataset:{},querySelector:selector=>selector==='[data-video-track]'?track:controls};
 const window={CardEmbeds:embeds};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/card-videos.js'),'utf8'),{window,document:{createElement,getElementById:()=>null}});
 window.CardVideos.render(section,[{url:'https://vkvideo.ru/clip-243793209_456239017?sh=4'},{url:'https://vkvideo.ru/video-243793209_456239017'}]);
 assert.equal(track.children[0].attrs['data-video-aspect'],'9/16');
 assert.equal(track.children[1].attrs['data-video-aspect'],'16/9');
});
test('VK clip share links embed and validate the matching player',()=>{
 for(const domain of ['vkvideo.ru','vk.com','vk.ru','m.vk.com','m.vk.ru']){
  const clip=`https://${domain}/clip-243793209_456239017?sh=4`;
  const player='https://vk.ru/video_ext.php?oid=-243793209&id=456239017&hash=18d01ce3990d425a';
  const expectedDomain=['vk.ru','m.vk.ru'].includes(domain)?'vk.ru':'vk.com';
  assert.equal(embeds.video(clip),`https://${expectedDomain}/video_ext.php?oid=-243793209&id=456239017`);
  assert.equal(embeds.video(clip,player),player);
  assert.equal(embeds.video(clip,player.replace('id=456239017','id=1')),'');
 }
 for(const url of ['https://vkvideo.ru/clips-243793209_456239017','https://vkvideo.ru/clip-243793209_bad','https://vkvideo.ru.evil.test/clip-243793209_456239017'])assert.equal(embeds.video(url),'');
});
test('normalizes supported video URLs without arbitrary iframe sources',()=>{
 assert.equal(embeds.video('https://youtu.be/dQw4w9WgXcQ'),'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ');
 assert.equal(embeds.video('https://rutube.ru/video/'+ 'a'.repeat(32)+'/'),'https://rutube.ru/play/embed/'+ 'a'.repeat(32));
 assert.equal(embeds.video('https://vkvideo.ru/video-1_23','https://vk.com/video_ext.php?oid=-1&id=23&hash=abc'),'https://vk.com/video_ext.php?oid=-1&id=23&hash=abc');
 for(const url of ['https://evil.test/watch?v=dQw4w9WgXcQ','javascript:alert(1)','https://user@youtube.com/watch?v=dQw4w9WgXcQ'])assert.equal(embeds.video(url),'');
 assert.equal(embeds.video('https://vkvideo.ru/video-1_23','https://vk.com/video_ext.php?oid=-2&id=23'),'');
});
test('map uses encoded address or explicit pin',()=>{
 assert.equal(new URL(embeds.map({address:'Город & улица'})).searchParams.get('text'),'Город & улица');
 assert.equal(new URL(embeds.map({address:'Дом',latitude:47.2,longitude:39.7})).searchParams.get('pt'),'39.7,47.2,pm2rdm');
});

test('VK ru player links preserve their domain and hash without forcing autoplay',()=>{
 const player='https://vk.ru/video_ext.php?oid=-243793209&id=456239017&hash=18d01ce3990d425a&hd=4&autoplay=1';
 const expected='https://vk.ru/video_ext.php?oid=-243793209&id=456239017&hash=18d01ce3990d425a';
 assert.equal(embeds.video(player),expected);
 assert.equal(embeds.video('https://vkvideo.ru/video-243793209_456239017',player),expected);
 assert.equal(embeds.video('https://vk.ru/video-243793209_456239017'),'https://vk.ru/video_ext.php?oid=-243793209&id=456239017');
 assert.equal(embeds.video('https://vk.ru/video-243793209_1',player),'');
 assert.equal(embeds.video(player.replace('vk.ru','vk.ru.evil.test')),'');
 assert.equal(embeds.video('https://vk.ru/video-243793209_456239017',player.replace('vk.ru','vk.ru.evil.test')),'');
});

test('additional video providers preserve private hashes and validate player identities',()=>{
 assert.equal(embeds.video('https://vimeo.com/123456789/abc123'),'https://player.vimeo.com/video/123456789?h=abc123');
 assert.equal(embeds.video('https://player.vimeo.com/video/123456789?h=abc123'),'https://player.vimeo.com/video/123456789?h=abc123');
 assert.equal(embeds.video('https://ok.ru/video/123456789'),'https://ok.ru/videoembed/123456789');
 assert.equal(embeds.video('https://www.tiktok.com/@person/video/6718335390845095173'),'https://www.tiktok.com/player/v1/6718335390845095173');
 assert.equal(embeds.video('https://dailymotion.com/video/x84sh87','https://geo.dailymotion.com/player/x8lr5.html?video=x84sh87'),'https://geo.dailymotion.com/player/x8lr5.html?video=x84sh87');
 assert.equal(embeds.video('https://dailymotion.com/video/x84sh87','https://geo.dailymotion.com/player/x8lr5.html?video=other'),'');
 assert.equal(embeds.video('https://vimeo.com/123','https://evil.test/player'),'');
});

test('other video services can be linked without loading arbitrary frames',()=>{
 for(const url of ['https://dzen.ru/video/watch/abc','https://www.twitch.tv/videos/123','https://www.instagram.com/reel/abc/','https://vm.tiktok.com/abc/']){
  assert.equal(embeds.videoLink(url),url);assert.equal(embeds.video(url),'');
 }
 for(const url of ['javascript:alert(1)','http://example.com/video','https://user@example.com/video','https://127.0.0.1/video','https://example.local/video'])assert.equal(embeds.videoLink(url),'');
});
