/** Run with `node tests/frontend.test.mjs`.
 * Exercises the shipped frontend against a small DOM test double. Real browser
 * layout and assistive-technology behavior remain separate manual checks.
 */
import fs from 'node:fs/promises';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {performance} from 'node:perf_hooks';
import {randomUUID} from 'node:crypto';

class Element {
  constructor(id, document) {this.id=id;this.document=document;this.value='';this.hidden=false;this.open=false;this.dataset={};this.listeners={};this.attributes={};this.children=[];this.parts={};this._html='';this.textContent='';}
  set innerHTML(value) {
    this._html=value;
    if(this.id==='suggestions')this.children=[...value.matchAll(/<li id="([^\"]+)"/g)].map(match=>new Element(match[1],this.document));
    if(['buyer','log-team'].includes(this.id))this.value=value.match(/<option value="([^\"]*)"/)?.[1]||'';
  }
  get innerHTML(){return this._html;}
  addEventListener(type,handler){(this.listeners[type]??=[]).push(handler);}
  async dispatch(type,event={}){event.target??=this;event.preventDefault??=()=>{};for(const handler of this.listeners[type]||[])await handler(event);}
  setAttribute(key,value){this.attributes[key]=value;}
  removeAttribute(key){delete this.attributes[key];}
  focus(){this.document.activeElement=this;}
  querySelector(selector){return this.parts[selector]??=new Element(this.id+' '+selector,this.document);}
  querySelectorAll(){return [];}
  classList={toggle(){}};
  showModal(){this.open=true;}
  close(){this.open=false;}
  scrollIntoView(){}
  closest(selector){if(selector==='button,[data-suggest]'&&this.id.startsWith('button-'))return this;return null;}
  hasAttribute(name){return Object.hasOwn(this.attributes,name);}
}

export async function runFrontEndTests() {
 const source=await fs.readFile(new URL('../src/project/web/static/app.js',import.meta.url),'utf8');
 const elements=new Map();
 const document={activeElement:null,listeners:{},getElementById(id){if(!elements.has(id))elements.set(id,new Element(id,this));return elements.get(id);},addEventListener(type,handler){(this.listeners[type]??=[]).push(handler);}};
 const storage=new Map(),calls=[];
 const allRoles=['Por','Dd','Ds','Dc','B','E','M','C','W','T','A','Pc'];
 const makePlayer=(id,name,roles,score)=>({player_id:id,player_name:name,current_team:'Inter',roles,score,provisional:false,historical_contribution:score||0,opening_contribution:null,history:[{performance_season:2025,mean_fv:7,rated_matches:20,fv_matches:20,goals:4,assists:3,complete_matchdays:38,imported_fixtures:380}],opening:{mean_fv:null,rated_matches:null,fv_matches:null,goals:null,assists:null,complete_matchdays:0,imported_fixtures:0},context:{}});
 const catalogue=allRoles.map((r,i)=>makePlayer(i+1,`Player ${i+1}`,r==='M'?['M','C']:[r],i+1));
 catalogue.push(makePlayer(13,'Lautaró Martinez',['Pc'],15),makePlayer(14,'<img src=x onerror=alert(1)>',['A'],null));
 const start={settings:{my_team_id:1,revision:1},teams:[{id:1,name:'Mine',sales:[],remaining_budget:500,spent:0,goalkeepers:0,outfield:0,mandatory_remaining:23,max_bid_goalkeeper:478,max_bid_outfield:478},{id:2,name:'Opponent',sales:[],remaining_budget:500,spent:0,goalkeepers:0,outfield:0,mandatory_remaining:23,max_bid_goalkeeper:478,max_bid_outfield:478}],sales:[]};
 let responder=(url)=>url.endsWith('/catalogue')?catalogue:start;
 const context=vm.createContext({document,localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},crypto:{randomUUID},performance,URL,console,window:{},fetch:async(url,options)=>{calls.push({url,options});const answer=await responder(url,options);return {ok:!answer.error,json:async()=>structuredClone(answer.error?{detail:answer.error}:answer)};}});
 new vm.Script(source).runInContext(context);
 const evaluate=code=>vm.runInContext(code,context);
 const el=id=>document.getElementById(id);
 const tick=async()=>{for(let i=0;i<12;i++)await new Promise(resolve=>setTimeout(resolve,0));};
 await tick();
 assert.equal(evaluate('players.length'),14);
 assert.equal(evaluate('filtered()[0].player_id'),13);
 assert.equal(evaluate('filtered().at(-1).player_id'),14,'Unranked remains last');
 evaluate('direction=1');assert.equal(evaluate('filtered().at(-1).player_id'),14);
 for(const r of allRoles){evaluate(`role=${JSON.stringify(r)};renderTable()`);assert.ok(evaluate('filtered().every(p=>p.roles.includes(role))'));assert.ok(evaluate('filtered().length')>0);}
 evaluate("role='C'");assert.equal(evaluate('filtered().length'),2,'Role membership includes multi-role players');
 evaluate("role='All';direction=-1");
 el('search').value='not a player';await el('search').dispatch('input');assert.match(el('player-table').querySelector('tbody').innerHTML,/No available players/);
 el('search').value='';await el('search').dispatch('input');assert.ok(!el('player-table').querySelector('tbody').innerHTML.includes('<img src=x'));
 const beforeFilterCalls=calls.length;
 el('player-input').value='LAUTARO';await el('player-input').dispatch('input');assert.equal(el('suggestions').hidden,false);
 await el('player-input').dispatch('keydown',{key:'ArrowDown'});await el('player-input').dispatch('keydown',{key:'Enter'});
 assert.equal(el('player-input').value,'Lautaró Martinez');assert.equal(el('suggestions').hidden,true);
 assert.equal(calls.length,beforeFilterCalls,'Autocomplete and filters use the loaded catalogue');
 el('price').value='45';
 responder=()=>({error:'Simulated save failure'});
 await el('sale-form').dispatch('submit');
 assert.equal(el('price').value,'45');assert.equal(el('player-input').value,'Lautaró Martinez');assert.equal(evaluate('state.sales.length'),0);
 assert.match(el('sale-error').textContent,/Simulated save failure/);
 const firstRequest=JSON.parse(calls.at(-1).options.body);
 const after=structuredClone(start);after.sales=[{id:1,player_id:13,player_name:'Lautaró Martinez',buyer_id:1,price:45,role_group:'outfield',recorded_at:'2026-10-06T12:00:00Z'}];after.teams[0].sales=after.sales;after.teams[0].remaining_budget=455;after.teams[0].outfield=1;
 responder=()=>after;
 await el('sale-form').dispatch('submit');
 assert.equal(JSON.parse(calls.at(-1).options.body).idempotency_key,firstRequest.idempotency_key,'Uncertain retry retains key');
 assert.equal(el('player-input').value,'');assert.equal(document.activeElement.id,'player-input');assert.equal(evaluate('state.sales.length'),1);assert.ok(evaluate('!filtered().some(p=>p.player_id===13)'));
 el('show-sold').checked=true;await el('show-sold').dispatch('input');assert.ok(evaluate('filtered().some(p=>p.player_id===13)'));
 el('player-input').value='lautaro';await el('player-input').dispatch('input');assert.match(el('suggestions').innerHTML,/Already sold to Mine for 45/);
 await el('player-input').dispatch('keydown',{key:'Enter'});assert.equal(el('record').textContent,'Save correction');assert.equal(el('price').value,45);
 el('price').value='46';await el('sale-form').dispatch('submit');assert.equal(calls.at(-1).options.method,'PUT');assert.equal(calls.at(-1).url,'/api/sales/1');
 el('player-input').value='Player';await el('player-input').dispatch('input');await el('player-input').dispatch('keydown',{key:'Escape'});assert.equal(el('suggestions').hidden,true);
 const benchmark=evaluate('window.mantraBenchmark()');assert.ok(benchmark.filtering_ms<100);assert.ok(benchmark.autocomplete_ms<100);
 assert.match(el('top-summary').innerHTML,/455/);assert.match(el('squads').innerHTML,/optional/i);
 responder=()=>{throw new Error('Simulated load failure');};await evaluate('load()');assert.equal(el('load-error').hidden,false);assert.match(el('load-error').querySelector('span').textContent,/Simulated load failure/);
 responder=url=>url.endsWith('/catalogue')?catalogue:after;await el('retry').onclick();assert.equal(el('load-error').hidden,true);
 return {checks:'Local sorting, all roles, accent matching, keyboard selection, sold editing, failure recovery, idempotent retry, focus return, escaped content, retry loading',benchmark};
}

if (typeof process !== 'undefined' && import.meta.url === `file://${process.argv[1]}`) console.log(await runFrontEndTests());
