const {test}=require('node:test');
const assert=require('node:assert/strict');
const {normalize}=require('../../static/web-links.js');
test('bare domains, social links and ports receive HTTPS without adding www',()=>{
 assert.equal(normalize('google.com'),'https://google.com/');
 assert.equal(normalize('t.me/person'),'https://t.me/person');
 assert.equal(normalize('example.com:8443/path'),'https://example.com:8443/path');
 assert.equal(normalize('//example.com/path'),'https://example.com/path');
 assert.equal(normalize('http://example.com/path'),'http://example.com/path');
});
test('unsafe schemes, credentials and embedded whitespace never become preview links',()=>{
 for(const value of ['javascript:alert(1)','data:text/html,test','ftp://example.com','https://user:pass@example.com','https://example.com/a\nb','exa mple.com']) assert.equal(normalize(value),'');
});
