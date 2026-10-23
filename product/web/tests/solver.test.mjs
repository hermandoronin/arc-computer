import test from 'node:test';
import assert from 'node:assert/strict';
import {matchProject,normalizeInventory,searchText} from '../dist/solver.js';
import {guides,parts} from '../dist/catalog.js';
import {readFileSync,existsSync} from 'node:fs';

test('Repeated requirements do not double-count available stock',()=>{
 const plan={bom:[{id:'cmp:relay',quantity:2},{id:'cmp:relay',quantity:3}]};
 const result=matchProject(plan,{'cmp:relay':3});
 assert.equal(result.total,5);assert.equal(result.have,3);assert.equal(result.score,60);
 assert.equal(result.complete,false);assert.equal(result.missing[0].missing,2);
});
test('Similar names and identifier namespaces are not silently interchangeable',()=>{
 const plan={bom:[{id:'cmp:fan_5v',quantity:1}]};
 assert.equal(matchProject(plan,{'comp:fan_5v':1,'cmp:fan_12v':3}).have,0);
});
test('Empty or invalid BOM is not marked buildable',()=>{
 assert.equal(matchProject({bom:[]},{}).complete,false);
 assert.equal(matchProject({bom:[{id:'x',quantity:0}]},{}).score,0);
});
test('Inventory imports reject malformed counts and unscoped keys',()=>{
 assert.deepEqual(normalizeInventory({'part:uno':2,'cmp:relay':-1,'part:fan':1.4,'comp:gear':1000,random:4,'part:pi':'3'}),{'part:uno':2,'part:pi':3});
 assert.deepEqual(normalizeInventory(null),{});assert.deepEqual(normalizeInventory([]),{});
});
test('Curated full kits match and removing a required part creates a deficit',()=>{
 const ids=new Set(parts.map(p=>p.id));
 for(const guide of guides){
   const inventory={};for(const item of guide.bom){assert.ok(ids.has(item.id));inventory[item.id]=(inventory[item.id]||0)+item.quantity;}
   assert.equal(matchProject(guide,inventory).complete,true,guide.id);
   delete inventory[guide.bom[0].id];assert.equal(matchProject(guide,inventory).complete,false,guide.id);
   assert.ok(guide.steps.length>=3);assert.ok(guide.check);assert.ok(guide.note);
   if(guide.firmware)assert.ok(existsSync(new URL('../dist/'+guide.firmware,import.meta.url)));
 }
});
test('Russian and English search matches multiple case-insensitive words',()=>{
 assert.equal(searchText({name:'Камера Raspberry Pi',summary:'Старый модуль'},'камера PI'),true);
 assert.equal(searchText({name:'Камера Raspberry Pi'},'полив'),false);
});
test('Imported corpus matches audit, retains provenance and excludes unreviewed assembly instructions',()=>{
 const read=name=>JSON.parse(readFileSync(new URL('../dist/data/'+name+'.json',import.meta.url)));
 const report=read('manifest');
 for(const kind of ['projects','devices','components']){
  const data=read(kind);assert.equal(data.length,report[kind]);
  for(const d of data){assert.ok(d.id);assert.ok(d.name);assert.equal('assembly_steps' in d,false);}
 }
 for(const p of read('projects')){assert.ok(p.source.startsWith('https://'));assert.equal(p.status,'unreviewed');}
 const devices=read('devices');assert.equal(new Set(devices.map(d=>d.origin)).size,devices.length);
});
