import test from 'node:test';
import assert from 'node:assert/strict';
import {snapshotModels,chooseModelId,modelEvidence} from '../../workbench/models.mjs';
test('registry discovery filters exact snapshot identity and never guesses newest by list order',()=>{
  const models=snapshotModels([{id:'z',snapshot_id:'wanted'},{id:'reference',snapshot_id:'other'},{id:'a',snapshot_id:'wanted'}],'wanted');
  assert.deepEqual(models.map(m=>m.id),['a','z']);assert.equal(chooseModelId(models),null);
  assert.equal(chooseModelId(models,{preferredId:'z'}),'z');assert.equal(chooseModelId(models,{referenceId:'a'}),'a');
  assert.equal(chooseModelId(models,{boundId:'z',preferredId:'a'}),'z');assert.equal(chooseModelId(models,{boundId:null,referenceId:'a'}),null);
  assert.equal(chooseModelId(models,{boundId:'reference'}),undefined);assert.equal(chooseModelId([models[0]]),'a');
});
test('operational metrics come from the confirmed demand choice, separately from the price candidate',()=>{
  const result=modelEvidence({selection:{pooled_mae:{demand:80,last4mean:100}},confirmation:{demand_candidate:'demand',price_candidate:'price',comparisons:{demand:{pooled_mae:12,baseline_mae:20,accepted:true},price:{pooled_mae:9,baseline_mae:20,accepted:true}}},allowed_uses:['reference_forecast','bounded_price_scenarios'],review_status:'unreviewed_operational'});
  assert.equal(result.kind,'operational');assert.equal(result.mae,12);assert.equal(result.baselineMae,20);assert.equal(result.wape,null);assert.equal(result.priceCandidate,'price');assert.equal(result.priceAllowed,true);assert.equal(result.selectionScores.demand,80);
});
test('baseline retained with empty or rejected comparisons supplies no invented confirmation score',()=>{
  for(const comparisons of [{},{rejected:{pooled_mae:30,baseline_mae:20,accepted:false}}]){
    const result=modelEvidence({confirmation:{demand_candidate:'last4mean',price_candidate:null,comparisons},selection:{demand_candidate:'last4mean',pooled_mae:{last4mean:5}},allowed_uses:['reference_forecast']});
    assert.equal(result.retainedBaseline,true);assert.equal(result.mae,null);assert.equal(result.baselineMae,null);assert.equal(result.wape,null);assert.equal(result.priceAllowed,false);assert.equal(result.selectionScores.last4mean,5);
  }
});
test('price capability requires both the retained candidate and the server allowed use',()=>{
  const model={confirmation:{demand_candidate:'last4mean',price_candidate:'price',comparisons:{}},allowed_uses:['reference_forecast']};
  assert.equal(modelEvidence(model).priceAllowed,false);
  model.allowed_uses.push('bounded_price_scenarios');assert.equal(modelEvidence(model).priceAllowed,true);
});
test('reference metrics remain direct; missing or nonfinite WAPE is never inferred',()=>{
  assert.equal(modelEvidence({metrics:{mae:1,baseline_mae:2}}).wape,null);
  assert.equal(modelEvidence({metrics:{mae:1,baseline_mae:2,wape:.25}}).wape,.25);
  assert.equal(modelEvidence({metrics:{mae:NaN,baseline_mae:2,wape:Infinity}}).mae,null);
});
test('run recovery keeps succeeded and failed workers pending until the provider slot is released',async()=>{
  const {recoverTrainingRun}=await import('../../workbench/models.mjs');
  const runs=[{id:'done',snapshot_id:'s',state:'succeeded',slot_released:true,created_at:'2026-11-18T03:00:00Z'},
    {id:'awaiting',snapshot_id:'s',state:'succeeded',slot_released:false,created_at:'2026-11-18T01:00:00Z'},
    {id:'stopped',snapshot_id:'s',state:'failed',slot_released:false,created_at:'2026-11-18T02:00:00Z'},
    {id:'foreign',snapshot_id:'other',state:'running',slot_released:false,created_at:'2026-11-18T04:00:00Z'}];
  assert.equal(recoverTrainingRun(runs,'s').id,'stopped');assert.equal(recoverTrainingRun(runs,'missing'),null);
});
