// DOM unit tests only: no browser, screenshots, network or hardware execution.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {parseHTML} from 'linkedom';
import {guides} from '../dist/catalog.js';
const evidence=JSON.parse(readFileSync(new URL('../dist/data/evidence.json',import.meta.url)));
const {window,document}=parseHTML(readFileSync(new URL('../dist/index.html',import.meta.url),'utf8'));
const local=new Map();
Object.assign(globalThis,{window,document,location:{hash:'#explore'},localStorage:{getItem:k=>local.get(k),setItem:(k,v)=>local.set(k,v)},HTMLImageElement:window.HTMLImageElement,matchMedia:()=>({matches:true})});
Object.defineProperty(globalThis,'navigator',{value:{},configurable:true});
window.scrollTo=()=>{};
globalThis.fetch=async path=>({ok:path==='data/evidence.json',json:async()=>evidence});
await import('../dist/field.js');
function navigate(hash){location.hash=hash;window.dispatchEvent(new window.Event('hashchange'));}
function click(selector){const el=document.querySelector(selector);assert.ok(el,selector);el.dispatchEvent(new window.Event('click',{bubbles:true}));return el;}

test('Homepage has real routes and valid legacy links',()=>{
 assert.equal(document.querySelectorAll('.catalog-card').length,3);
 for(const a of document.querySelectorAll('a[href^="archive.html#build="]'))assert.ok(guides.some(g=>g.id===a.getAttribute('href').split('=')[1]));
});
test('All device and build pages render chips, source links, images and local assets',()=>{
 for(const d of evidence.devices){navigate('#device/'+d.id);assert.equal(document.querySelector('h1').textContent,d.title);assert.equal(document.querySelectorAll('#chips tbody tr').length,d.chips.length);assert.ok(document.querySelectorAll('#sources a').length>=d.source_ids.length);}
 for(const r of evidence.routes){navigate('#build/'+r.id);assert.equal(document.querySelector('h1').textContent,r.title);assert.equal(document.querySelectorAll('[data-bom]').length,r.requirements.length);assert.equal(document.querySelectorAll('.instruction').length,r.steps.length);assert.equal(document.querySelectorAll('[data-test]').length,r.tests.length);for(const link of document.querySelectorAll('a[download]'))assert.ok(existsSync(new URL('../dist/'+link.getAttribute('href'),import.meta.url)));}
});
test('Catalogue filters and text search update the list',()=>{
 navigate('#devices');click('[data-category="dryer"]');assert.equal(document.querySelectorAll('.catalog-card').length,1);
 click('[data-category="all"]');const input=document.querySelector('#catalog-search');input.value='STM8S207RB';input.dispatchEvent(new window.Event('input',{bubbles:true}));assert.equal(document.querySelectorAll('.catalog-card').length,1);assert.ok(document.querySelector('.catalog-card').textContent.includes('EWX14'));
 input.value='NONEXISTENT1234';input.dispatchEvent(new window.Event('input',{bubbles:true}));assert.ok(document.querySelector('.empty'));
});
test('BOM and acceptance-test marks persist and do not claim hardware validation',()=>{
 navigate('#build/wifi-camera');let input=document.querySelector('[data-bom="uart"]');input.checked=true;input.dispatchEvent(new window.Event('change',{bubbles:true}));assert.ok(document.querySelector('#readiness').textContent.includes('1 из 6'));
 input=document.querySelector('[data-test]');input.checked=true;input.dispatchEvent(new window.Event('change',{bubbles:true}));assert.ok(document.querySelector('#test-result').textContent.includes('1 из 4'));
 navigate('#devices');navigate('#build/wifi-camera');assert.ok(document.querySelector('[data-bom="uart"]').hasAttribute('checked'));assert.ok(JSON.parse(local.get('arc.field.v2')).inventory.uart===1);assert.ok(document.querySelector('.status-line').textContent.includes('На стенде не испытано'));
});
test('Learn, sources, notebook and missing-page states render',()=>{
 navigate('#learn');assert.equal(document.querySelectorAll('.learn-step').length,6);
 navigate('#sources');assert.equal(document.querySelectorAll('.source-row').length,24);
 navigate('#notebook');assert.ok(document.querySelector('#note-form'));assert.ok(document.querySelector('#notebook-import'));
 navigate('#device/missing');assert.ok(document.querySelector('h1').textContent.includes('не найдена'));
});
