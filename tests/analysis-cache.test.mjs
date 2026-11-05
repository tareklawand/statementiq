import test from 'node:test';
import assert from 'node:assert/strict';
import {analysisCacheKey,readAnalysisCache,writeAnalysisCache} from '../src/analysis-cache.js';
const env={CF_VERSION_METADATA:{id:'release-one'}};
function memory(){const values=new Map();return {async match(key){return values.get(key.url)?.clone();},async put(key,value){values.set(key.url,value);}};}
const request=query=>new Request('https://statementiq-lb.com/api/analyze?'+query);
const result=deadline=>Response.json({symbol:'EXAMPLE',metrics:{revenue:123}}, {headers:{'x-statementiq-cache-until':String(deadline)}});

test('public cached analyses keep their original source deadline and financial values',async()=>{
 const cache=memory(),req=request('ticker=example');
 await writeAnalysisCache(req,env,result(1200),cache,1000*1000);
 const hit=await readAnalysisCache(request('ticker=EXAMPLE'),env,cache,1199*1000);
 assert.equal(hit.headers.get('cache-control'),'no-store');assert.equal(hit.headers.get('x-statementiq-cache'),'hit');
 assert.deepEqual(await hit.json(),{symbol:'EXAMPLE',metrics:{revenue:123}});
 assert.equal(await readAnalysisCache(req,env,cache,1200*1000),null);
 assert.equal(await readAnalysisCache(req,{CF_VERSION_METADATA:{id:'release-two'}},cache,1100*1000),null);
});
test('refresh bypasses saved analysis; private inputs, POSTs and invalid symbols never enter the shared cache',async()=>{
 const cache=memory(),req=request('ticker=EXAMPLE');
 await writeAnalysisCache(req,env,result(1200),cache,1000*1000);
 assert.equal(await readAnalysisCache(request('ticker=EXAMPLE&refresh=true'),env,cache,1100*1000),null);
 assert.equal(await readAnalysisCache(request('ticker=EXAMPLE&refresh=TRUE'),env,cache,1100*1000),null);
 assert.equal(analysisCacheKey(request('ticker=EXAMPLE&refresh=invalid'),env),null);
 assert.equal(analysisCacheKey(request('ticker=EXAMPLE&ticker=OTHER'),env),null);
 assert.equal(analysisCacheKey(request('ticker=EXAMPLE&refresh=false&refresh=true'),env),null);
 for(const r of [request('ticker=EXAMPLE&api_key=private'),request('ticker=%3Cscript%3E'),new Request(req,{method:'POST',body:'private notes'}),new Request(req,{headers:{authorization:'Bearer private'}})]){
  assert.equal(analysisCacheKey(r,env),null);
 }
});
test('expired responses, errors and source windows over five minutes are not cached; cache outages fail open',async()=>{
 const cache=memory(),req=request('ticker=EXAMPLE');
 for(const response of [result(900),result(1400),Response.json({error:'upstream unavailable'},{status:503})])await writeAnalysisCache(req,env,response,cache,1000*1000);
 assert.equal(await readAnalysisCache(req,env,cache,1000*1000),null);
 const broken={async match(){throw Error('cache unavailable');},async put(){throw Error('cache unavailable');}};
 assert.equal(await readAnalysisCache(req,env,broken,1000*1000),null);
 await writeAnalysisCache(req,env,result(1200),broken,1000*1000);
});
