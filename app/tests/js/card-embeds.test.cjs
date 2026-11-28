const {test}=require('node:test');
const assert=require('node:assert/strict');
const embeds=require('../../static/card-embeds.js');
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
