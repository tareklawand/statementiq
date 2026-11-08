import test from 'node:test';
import assert from 'node:assert/strict';
import worker,{extractPeriodicDocument} from '../src/index.js';

function submission(chunks){
 let index=0,cancelled=false;
 const stream=new ReadableStream({pull(controller){if(index<chunks.length)controller.enqueue(new TextEncoder().encode(chunks[index++]));else controller.close();},cancel(){cancelled=true;}},{highWaterMark:0});
 return {response:new Response(stream),cancelled:()=>cancelled,reads:()=>index};
}

test('periodic extraction stops and closes the submission before unrelated exhibits',async()=>{
 const input=submission(['<DOCUMENT>\n<TYPE>EX-99\n<TEXT>exhibit</TEXT>\n</DOCUMENT>\n<DOCU','MENT>\n<TYPE>10-K\n<TEXT>Exact annual report</TEXT>\n</DOCUMENT>',...Array(20).fill('unrelated exhibit')]);
 assert.equal(await extractPeriodicDocument(input.response),'Exact annual report');
 assert.equal(input.cancelled(),true);assert.equal(input.reads(),2);
});

test('malformed submission headers and oversized annual text are bounded and cancelled',async()=>{
 for(const content of ['<DOCUMENT>'+ 'x'.repeat(65537),'<DOCUMENT>\n<TYPE>10-K\n'+'x'.repeat(65537),'<DOCUMENT>\n<TYPE>10-K\n<TEXT>'+'x'.repeat(17*1024*1024)]){
  const input=submission([content,'must not be read']);
  await assert.rejects(extractPeriodicDocument(input.response),RangeError);
  assert.equal(input.cancelled(),true);assert.equal(input.reads(),1);
 }
});

test('an incomplete submission is not returned as a complete annual report',async()=>{
 const input=submission(['<DOCUMENT>\n<TYPE>10-K\n<TEXT>Partial report']);
 await assert.rejects(extractPeriodicDocument(input.response),/closing marker/);
 assert.equal(input.response.body.locked,false);
});

const url='https://statementiq-lb.com/api/sec-filing-text?url='+encodeURIComponent('https://www.sec.gov/Archives/edgar/data/123/000000012326000001/annual.htm');

test('concurrent edge text reviews are bounded and capacity is restored',async t=>{
 let release,calls=0;
 t.mock.method(globalThis,'fetch',async()=>{calls++;if(calls===1)await new Promise(resolve=>{release=resolve;});return new Response('<p>Annual report</p>');});
 const first=worker.fetch(new Request(url),{});
 await new Promise(setImmediate);
 try{
  const busy=await worker.fetch(new Request(url),{});
  assert.equal(busy.status,503);assert.equal(busy.headers.get('retry-after'),'5');assert.equal(calls,1);
 }finally{release();}
 assert.equal((await first).status,200);
 assert.equal((await worker.fetch(new Request(url),{})).status,200);
});

test('edge source connection failures return retryable JSON instead of crashing',async t=>{
 t.mock.method(globalThis,'fetch',async()=>{throw new TypeError('network unavailable');});
 t.mock.method(console,'error',()=>{});
 for(let i=0;i<2;i++){
  const response=await worker.fetch(new Request(url),{});
  assert.equal(response.status,502);assert.equal(response.headers.get('retry-after'),'5');
  assert.equal((await response.json()).code,'sec_text_temporarily_unavailable');
 }
});
