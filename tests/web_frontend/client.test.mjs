import test from 'node:test';
import assert from 'node:assert/strict';
import {ApiClient,ApiError,OperationCancelled,Session} from '../../workbench/api.mjs';
import {escapeHTML,number,visibleRows,splitBatches,lineChart,decision,errorCopy} from '../../workbench/ui.mjs';
const json=(data,status=200,headers={})=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json',...headers}});
const memory=()=>{const values=new Map();return {getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k),get length(){return values.size;},key:i=>[...values.keys()][i],values};};
const identity={uid:'unit-test-user',token:async()=>'test-token'};
test('Firebase credentials use official endpoint; refresh uses form data; logout clears tokens',async()=>{
  const calls=[];
  const session=new Session({api_key:'public-test-key'},async(url,init)=>{calls.push({url,init});return calls.length===1?json({idToken:'first',refreshToken:'refresh',localId:'u',expiresIn:'1'}):json({id_token:'second',refresh_token:'rotated',expires_in:'3600'});});
  await session.signIn('unit@example.invalid','test-only');assert.equal(session.idToken,'first');
  assert.equal(await session.token(),'second');assert.match(calls[0].url,/identitytoolkit.googleapis.com\/v1\/accounts:signInWithPassword/);
  assert.equal(JSON.parse(calls[0].init.body).returnSecureToken,true);
  assert.match(calls[1].url,/securetoken.googleapis.com\/v1\/token/);
  assert.equal(calls[1].init.body.get('grant_type'),'refresh_token');
  session.clear();assert.equal(session.idToken,null);assert.equal(session.refreshToken,null);await assert.rejects(()=>session.token(),{code:'SIGN_IN_REQUIRED'});
});
test('concurrent requests share one refresh and a logout fences its completion',async()=>{
  let resolve,refreshCount=0;
  const session=new Session({api_key:'test'},async()=>{refreshCount++;return new Promise(r=>resolve=r);});
  session.idToken='old';session.refreshToken='old-refresh';session.expiresAt=0;
  const first=session.token(),second=session.token();session.clear();resolve(json({id_token:'late',refresh_token:'late-refresh',expires_in:3600}));
  await Promise.all([assert.rejects(()=>first,{code:'SESSION_EXPIRED'}),assert.rejects(()=>second,{code:'SESSION_EXPIRED'})]);
  assert.equal(refreshCount,1);assert.equal(session.idToken,null);
});
test('lost mutation response keeps one idempotency key across client reload and updated ETag; no blind retry',async()=>{
  const storage=memory(),calls=[];
  const failing=new ApiClient(identity,{storage,fetcher:async(path,init)=>{calls.push(init);throw new TypeError('offline');}});
  await assert.rejects(()=>failing.request('/api/v1/workspaces/w/plans/p/compare',{method:'POST',etag:'head-1',body:{revision:1}}),{code:'CONNECTION_LOST'});
  assert.equal(calls.length,1);assert.equal(storage.values.size,1);
  const restored=new ApiClient(identity,{storage,fetcher:async(path,init)=>{calls.push(init);return json({id:'p',etag:'head-2'});}});
  await restored.request('/api/v1/workspaces/w/plans/p/compare',{method:'POST',etag:'head-2',body:{revision:1}});
  assert.equal(calls[0].headers['Idempotency-Key'],calls[1].headers['Idempotency-Key']);assert.equal(storage.values.size,0);
  assert.equal(calls[1].headers.Authorization,'Bearer test-token');assert.equal(calls[1].headers['If-Match'],'head-2');
});
test('private pagination follows opaque cursors and public sample requests never attach a token',async()=>{
  const calls=[],client=new ApiClient(identity,{storage:memory(),fetcher:async(path,init)=>{calls.push({path,init});return json(path.includes('cursor=')?{items:[{id:2}],next_cursor:null}:{items:[{id:1}],next_cursor:'opaque+/'});}});
  assert.equal((await client.all('/api/v1/samples',{publicAccess:true})).length,2);
  assert.equal(calls[0].init.headers.Authorization,undefined);assert.match(calls[1].path,/cursor=opaque%2B%2F/);
  await assert.rejects(()=>client.request('https://example.invalid/token'),/same-origin/);
});
test('server error retains code, row fields, and revision for an actionable conflict',async()=>{
  const client=new ApiClient(identity,{storage:memory(),fetcher:async()=>json({error:{code:'stale_etag',fields:[{row:3,field:'price'}],current_revision:7}},412)});
  await assert.rejects(()=>client.request('/api/v1/workspaces/w/plans/p'),e=>e instanceof ApiError && e.currentRevision===7 && e.fields[0].row===3 && /saved plan changed/.test(errorCopy(e)) && /方案已变化/.test(errorCopy(e,true)));
});
test('review batches resolve every selected row once, never exceed 40, and holds remain in filters',()=>{
  const rows=Array.from({length:249},(_,i)=>({row_id:String(i),item_id:i%2?'Brand A':'Brand B',site_id:String(i),disposition:i<20?'change_proposed':'hold',review:{action:i<40?'approve_hold':'pending'}}));
  const batches=splitBatches(rows);assert.deepEqual(batches.map(x=>x.length),[40,40,40,40,40,40,9]);assert.equal(new Set(batches.flat().map(x=>x.row_id)).size,249);
  assert.equal(visibleRows(rows,'','hold').length,229);assert.equal(visibleRows(rows,'','pending').length,209);
  assert.equal(visibleRows(rows,'Brand A','all').length,124);assert.throws(()=>splitBatches(rows,41));
});
test('display preserves unknown values, escapes untrusted text, and separates gaps in charts',()=>{
  assert.equal(number(null),'—');assert.equal(number(0),'0');assert.equal(decision({item_id:'A'}),'uncalculated');
  assert.equal(escapeHTML('<script>"&'), '&lt;script&gt;&quot;&amp;');
  const chart=lineChart([{week_index:1,units:0},{week_index:2,units:null},{week_index:3,units:3}],'units',{label:'<b>history</b>'});
  assert.equal((chart.match(/<polyline/g)||[]).length,2);assert.match(chart,/&lt;b&gt;history/);assert.doesNotMatch(chart,/NaN|Infinity/);
});
test('successful headers with rejected JSON or Blob retain the same mutation key until body acceptance',async()=>{
  for(const download of [false,true]){
    const storage=memory(),calls=[];let first=true;
    const client=new ApiClient(identity,{storage,fetcher:async(path,init)=>{
      calls.push(init);
      if(first){first=false;return {ok:true,status:200,headers:new Headers(),json:async()=>{throw new TypeError('body interrupted');},blob:async()=>{throw new TypeError('body interrupted');}};}
      return json({id:'accepted'});
    }});
    const options={method:'POST',body:{revision:1},download};
    await assert.rejects(()=>client.request('/api/v1/workspaces/w/plans/p/compare',options),{code:'RESPONSE_INTERRUPTED'});
    assert.equal(storage.values.size,1);
    await client.request('/api/v1/workspaces/w/plans/p/compare',options);
    assert.equal(calls[0].headers['Idempotency-Key'],calls[1].headers['Idempotency-Key']);assert.equal(storage.values.size,0);
  }
});
test('identity invalidation aborts requests and fences late bodies even when transport ignores abort',async()=>{
  let resolveBody,signal;const storage=memory();
  const client=new ApiClient(identity,{storage,fetcher:async(path,init)=>{signal=init.signal;return {ok:true,status:200,headers:new Headers(),json:()=>new Promise(resolve=>resolveBody=resolve)};}});
  const scoped=client.scoped(),pending=scoped.request('/api/v1/workspaces/w/plans/p',{method:'POST',body:{revision:1}});
  while(!resolveBody)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(storage.length,1);client.invalidate({clearPending:true});assert.equal(signal.aborted,true);assert.equal(storage.length,0);
  resolveBody({id:'old-private-plan'});
  await assert.rejects(()=>pending,OperationCancelled);
  await assert.rejects(()=>scoped.request('/api/v1/workspaces/w/plans/p/submit',{method:'POST',body:{revision:1}}),OperationCancelled);
  assert.equal(storage.length,0);
});
test('same-actor reauthentication keeps pending retry keys; actor change clears persisted keys across client instances',async()=>{
  const storage=memory();storage.setItem('pricing-language','zh');
  const client=new ApiClient(identity,{storage,fetcher:async()=>{throw new TypeError('offline');}});
  await assert.rejects(()=>client.request('/api/v1/workspaces/w/plans',{method:'POST',body:{snapshot_id:'s'}}));
  const key=[...storage.values.entries()].find(([name])=>name.startsWith('pricing-request:'));
  client.invalidate();assert.equal(storage.getItem(key[0]),key[1]);
  const next=new ApiClient(identity,{storage,fetcher:async()=>json({})});next.invalidate({clearPending:true});
  assert.equal(storage.getItem(key[0]),undefined);assert.equal(storage.getItem('pricing-language'),'zh');
});
test('an old request cannot acquire a newer actor token while waiting for authentication',async()=>{
  let resolveToken,calls=0;const principal={uid:'old',token:()=>new Promise(resolve=>resolveToken=resolve)};
  const client=new ApiClient(principal,{storage:memory(),fetcher:async()=>{calls++;return json({});}});
  const pending=client.scoped().request('/api/v1/workspaces/old/plans',{method:'POST',body:{revision:1}});
  client.invalidate({clearPending:true});principal.uid='new';resolveToken('new-token');
  await assert.rejects(()=>pending,OperationCancelled);assert.equal(calls,0);
});
