const {test}=require('node:test');const assert=require('node:assert/strict');
const {href,icon,normalize}=require('../../static/card-buttons.js');
test('typed buttons preserve their action and normalize phone or web values',()=>{
 assert.equal(href({kind:'phone',value:'8 (928) 909-18-17'}),'tel:+79289091817');
 assert.equal(href({kind:'other_phone',value:'+74951234567'}),'tel:+74951234567');
 assert.equal(href({kind:'telegram',value:'t.me/person'}),'https://t.me/person');
 assert.equal(href({kind:'email',value:'a@example.test'}),'mailto:a@example.test');
 assert.equal(href({kind:'file',value:''},'/owned/file.pdf'),'/owned/file.pdf');
 assert.equal(icon('other_phone'),'phone');assert.equal(icon('other_social'),'website');
});
test('incomplete file and unsafe values do not create public buttons',()=>{
 for(const item of [{kind:'file',value:''},{kind:'phone',value:'abc'},{kind:'link',value:'javascript:alert(1)'},{kind:'unknown',value:'https://example.com'}])assert.equal(href(item),'');
});

test('network usernames and phone numbers become canonical contact links',()=>{
 assert.equal(normalize('whatsapp','+7 (928) 909-18-17'),'https://wa.me/79289091817');
 assert.equal(normalize('whatsapp','https://api.whatsapp.com/send?phone=79289091817'),'https://wa.me/79289091817');
 assert.equal(normalize('telegram','@person'),'https://t.me/person');
 assert.equal(normalize('telegram','person.t.me'),'https://t.me/person');
 assert.equal(normalize('instagram','person.name'),'https://www.instagram.com/person.name');
 assert.equal(normalize('vk','id123456'),'https://vk.com/id123456');
 assert.equal(normalize('youtube','@channel'),'https://www.youtube.com/@channel');
 assert.equal(href({kind:'phone',value:'89289091817',extension:'123'}),'tel:+79289091817;ext=123');
});

test('wrong social domains, incomplete Russian numbers and extension injection are rejected',()=>{
 for(const [kind,value]of [['telegram','hello world'],['vk','https://vk.com.evil.test/user'],['instagram','https://evil.test/person'],['phone','+79289091'],['whatsapp','https://evil.test/79289091817']])assert.equal(normalize(kind,value),'');
 assert.equal(href({kind:'phone',value:'89289091817',extension:'1;ext=2'}),'');
});
