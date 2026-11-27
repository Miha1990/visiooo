const {test}=require('node:test'),assert=require('node:assert/strict');
const {fromHex,toHex}=require('../../static/card-color-picker.js');
test('HSV conversion preserves preset and custom HEX colors including black, white and gray',()=>{
 for(const color of ['#000000','#ffffff','#808080','#ff0000','#00ff00','#0000ff','#963f2b','#315948','#2457db','#683db0'])assert.equal(toHex(fromHex(color)),color);
 for(let i=0;i<256;i++){const color='#'+((i*65793)^0x963f2b).toString(16).padStart(6,'0');assert.equal(toHex(fromHex(color)),color);}
});
test('saturation and brightness reach the gradient boundaries',()=>{
 assert.equal(toHex({h:120,s:1,v:1}),'#00ff00');assert.equal(toHex({h:120,s:0,v:1}),'#ffffff');assert.equal(toHex({h:120,s:1,v:0}),'#000000');
});
