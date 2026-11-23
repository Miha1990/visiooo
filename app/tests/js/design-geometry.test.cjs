const {test}=require('node:test');
const assert=require('node:assert/strict');
const {transform}=require('../../static/design-geometry.js');
const frame=()=>({x:10,y:160,width:50,unit:'%',height:100,z:2,corners:[0,0,0,0]});
test('photo can overlap the header while remaining inside the responsive width',()=>{
 const value=transform(frame(),{dx:36,dy:-100,snap:1});
 assert.equal(value.x,20);assert.equal(value.y,60);
 assert.equal(transform(frame(),{dx:9999,dy:-9999}).x,50);
 assert.equal(transform(frame(),{dx:9999,dy:-9999}).y,0);
});
test('resizing from a corner updates both dimensions and preserves the opposite corner',()=>{
 const value=transform(frame(),{dx:36,dy:20,handle:'1',snap:1});
 assert.equal(value.x,20);assert.equal(value.width,40);assert.equal(value.y,180);assert.equal(value.height,80);
 assert.equal(value.x+value.width,frame().x+frame().width);
});
test('adaptive and pixel widths resize in the artboard coordinate system',()=>{
 assert.equal(transform(frame(),{dx:36,dy:0,handle:'4'}).width,60);
 assert.equal(transform({...frame(),unit:'px',width:180},{dx:36,dy:0,handle:'4'}).width,216);
 const bounded=transform(frame(),{dx:900,dy:0,handle:'4'});assert.equal(bounded.x+bounded.width,100);
});
test('minimum widths remain valid and north-west resizing stops at the canvas edge',()=>{
 assert.equal(transform(frame(),{dx:9999,dy:0,handle:'8'}).width,8);
 const value=transform(frame(),{dx:-9999,dy:-9999,handle:'1'});
 assert.equal(value.x,0);assert.equal(value.x+value.width,60);
 assert.equal(value.y,0);assert.equal(value.height,260);
});
