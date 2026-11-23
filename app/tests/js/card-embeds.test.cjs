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
