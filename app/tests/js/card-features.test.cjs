const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const window={};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/card-interactions.js'),'utf8'),{window,document:{querySelectorAll:()=>[]},Intl,Date});
const status=window.CardFeatures.workStatus;
test('working status uses business timezone, yesterday overnight hours and exclusive closing boundary',()=>{
 const business={timezone:'Europe/Moscow',hours:[{day:0,open:'20:00',close:'02:00'}]};
 assert.equal(status(business,new Date('2026-11-23T18:00:00Z')),'Открыто до 02:00');
 assert.equal(status(business,new Date('2026-11-23T22:00:00Z')),'Открыто до 02:00');
 assert.equal(status(business,new Date('2026-11-23T23:00:00Z')),'Сейчас закрыто');
 business.timezone='Asia/Vladivostok';assert.equal(status(business,new Date('2026-11-23T22:00:00Z')),'Сейчас закрыто');
});
test('manual status overrides schedule and an empty business has no status',()=>{
 assert.equal(status({status:'Принимаю заказы',hours:[]}), 'Принимаю заказы');
 assert.equal(status({}), '');
});
