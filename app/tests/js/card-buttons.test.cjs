const {test}=require('node:test');const assert=require('node:assert/strict');
const {href,icon}=require('../../static/card-buttons.js');
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
