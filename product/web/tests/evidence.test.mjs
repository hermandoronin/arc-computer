import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {escapeHTML,safeURL,matches,readiness,normalizeCases,planText} from '../dist/evidence-logic.js';
const data=JSON.parse(readFileSync(new URL('../dist/data/evidence.json',import.meta.url)));

test('Exact requirements do not turn similar modules into compatible stock',()=>{
 const r=data.routes.find(r=>r.id==='wifi-camera');
 assert.equal(readiness(r,{'pi-cam2':1,'ps3-camera':1}).have,0);
 const full=Object.fromEntries(r.requirements.map(x=>[x.id,x.qty]));
 assert.equal(readiness(r,full).complete,true);
 full.uart=-1;assert.equal(readiness(r,full).complete,false);
 full.uart=Infinity;assert.equal(readiness(r,full).rows.find(x=>x.id==='uart').have,0);
 assert.equal(readiness({requirements:[]},{}).complete,false);
});
test('Every claim preserves evidence scope and each route remains untested',()=>{
 const ids=new Set(data.sources.map(s=>s.id));
 for(const device of data.devices)for(const claim of device.claims){assert.ok(claim.scope);assert.ok(claim.source_ids.length);for(const id of claim.source_ids)assert.ok(ids.has(id));}
 for(const r of data.routes){assert.equal(r.bench_tested,false);assert.ok(r.steps.length);assert.ok(r.tests.length);assert.ok(r.requirements.every(r=>r.where&&r.check));}
 const washer=data.devices.find(d=>d.id==='ewf12844');
 assert.ok(!washer.chips.some(c=>c.name==='STM8S207RB'),'Family observation must not leak into exact PNC BOM');
 assert.ok(data.devices.find(d=>d.id==='ps3-eye').limits.some(x=>x.includes('UVC')));
});
test('Search finds part markings, Russian category and model IDs',()=>{
 assert.ok(matches(data.devices.find(d=>d.id==='ewx14-sample'),'stm8s207rb'));
 assert.ok(matches(data.devices.find(d=>d.id==='aeg-t55640'),'сушилка LNK304'));
 assert.ok(matches(data.devices.find(d=>d.id==='ewf12844'),'914900650'));
});
test('Notebook input and source URLs cannot inject active markup',()=>{
 assert.equal(safeURL('javascript:alert(1)'),'#');assert.equal(safeURL('data:text/html,bad'),'#');
 assert.equal(escapeHTML('<img onerror="x">'),'&lt;img onerror=&quot;x&quot;&gt;');
 assert.deepEqual(normalizeCases(null),[]);
 const records=normalizeCases([{model:'camera',url:'javascript:alert(1)',note:'<b>user text</b>'},null,{model:4}]);
 assert.equal(records.length,1);assert.equal(records[0].url,'');
 assert.equal(records[0].note,'<b>user text</b>');
});
test('Export retains procurement, compatibility, steps, firmware and source URLs',()=>{
 for(const r of data.routes){const txt=planText(r,{},data.sources);assert.ok(txt.includes(r.title));assert.ok(txt.includes('на стенде ARC не испытан'));assert.ok(txt.includes(r.requirements[0].check));assert.ok(txt.includes(r.steps[0][2]));assert.ok(txt.includes('https://'));}
 assert.ok(planText(data.routes[0],{},data.sources).includes('board_config.h'));
});
test('Local evidence assets and configured firmware archive exist',()=>{
 for(const a of data.assets){if(!a.src.startsWith('https://'))assert.ok(existsSync(new URL('../dist/'+a.src,import.meta.url)),a.src);assert.ok(a.credit);}
 for(const r of data.routes)if(r.firmware)assert.ok(existsSync(new URL('../dist/'+r.firmware.download,import.meta.url)));
});
