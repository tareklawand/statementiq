import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const keys=['revenue_growth','gross_margin','operating_margin','tax_rate','capex_rate','da_rate','sbc_rate','receivables_days','inventory_days','payables_days','interest_rate','debt_draw','debt_repayment','equity_issuance','dividends','buybacks'];
const valuationKeys=['wacc','terminal_growth','terminal_roic','cash_in_bridge','nonoperating_assets','other_claims'];
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function app(){
 const elements=new Map(),events={};let resolvePost,body,baselineOptions;
 const element=id=>{if(!elements.has(id))elements.set(id,{id,value:id==='modelYear'?'0':'',innerHTML:'',textContent:'',disabled:false,hidden:false,dataset:{}});return elements.get(id);};
 const baseline={symbol:'ONE',status:'ready',missing:[],company_name:'Example',currency:'USD',period:'2025-12-31',values:{cash:20},provenance:{},historical_drivers:{},input_sha256:'a'.repeat(64),scope:'Example'};
 const context=vm.createContext({document:{getElementById:element,addEventListener:(type,fn)=>{events[type]=fn;}},StatementIQRequests:{requestJson:async(url,options)=>{baselineOptions=options;assert.equal(options.validate(baseline),true);return baseline;}},AbortController,setTimeout,clearTimeout,Blob,URL,console,
  fetch:async(url,options)=>{body=JSON.parse(options.body);return new Promise(resolve=>{resolvePost=resolve;});}});
 vm.runInContext(fs.readFileSync(new URL('../static/forecast-workspace.js',import.meta.url),'utf8'),context);
 const click=id=>events.click({target:{closest:()=>({id})}});
 const input=(id,value,type,key)=>{const target=element(id);target.value=String(value);target.dataset={unit:type,...(key?{[id.startsWith('driver_')?'driver':'valuation']:key}:{})};events.input({target});};
 async function ready(){vm.runInContext("ForecastWorkspace.setCompany({symbol:'ONE'})",context);click('loadModelBaselineBtn');await flush();await flush();
  for(const key of keys)input('driver_'+key,0,'days',key);
  click('copyModelYearBtn');for(const key of valuationKeys)input('value_'+key,1,'days',key);
  element('modelRationale').value='Explicit test assumptions';
 }
 const reply=()=>resolvePost({ok:true,json:async()=>({dcf:{status:'ready',valuation_date:'2025-12-31',enterprise_value:10,equity_value:10,value_per_share:1,terminal_reinvestment_rate:0,terminal_nopat:1,terminal_fcff:1},forecasts:[],warnings:[],methodology_sources:[],scope:'Example'})});
 return {ready,context,click,input,element,events,reply,body:()=>body,baselineOptions:()=>baselineOptions};
}

test('DCF baseline uses startup recovery and validates the company and complete response shape',async()=>{
 const a=app();await a.ready();const options=a.baselineOptions();
 assert.equal(options.startupRecovery,true);assert.equal(options.maxAttempts,undefined);
 assert.equal(options.validate({symbol:'TWO',status:'ready',values:{},provenance:{},missing:[]}),false);
 assert.ok(!options.validate({symbol:'ONE',status:'ready'}));
 assert.equal(options.validate({symbol:'ONE',status:'unavailable',values:{},provenance:{},missing:['Missing source input']}),true);
});

test('five-year copy preserves explicit zeroes and sends no invented later-year assumptions',async()=>{
 const a=app();await a.ready();a.events.submit({target:{id:'forecastForm'},preventDefault(){}});await flush();
 assert.equal(a.body().years.length,5);assert.ok(a.body().years.every(year=>keys.every(key=>year[key]===0)));
 a.reply();await flush();assert.equal(a.element('downloadModelJsonBtn').disabled,false);
});

test('editing assumptions invalidates an in-flight result and its downloads',async()=>{
 const a=app();await a.ready();a.events.submit({target:{id:'forecastForm'},preventDefault(){}});await flush();
 a.input('driver_revenue_growth',2,'rate','revenue_growth');a.reply();await flush();await flush();
 assert.equal(a.element('modelResults').innerHTML,'');assert.equal(a.element('downloadModelExcelBtn').disabled,true);
});

test('a response for the prior ticker cannot appear in a newly selected company',async()=>{
 const a=app();await a.ready();a.events.submit({target:{id:'forecastForm'},preventDefault(){}});await flush();
 vm.runInContext("ForecastWorkspace.setCompany({symbol:'TWO'})",a.context);a.reply();await flush();await flush();
 assert.equal(a.element('modelResults').innerHTML,'');assert.match(a.element('modelStatus').textContent,/TWO/);
});
