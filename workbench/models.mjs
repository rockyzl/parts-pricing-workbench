// Presentation-only adapters for the existing model registry/result contracts.
const finite = value => typeof value === 'number' && Number.isFinite(value);
export function snapshotModels(items, snapshotId) {
  return items.filter(model => model.snapshot_id === snapshotId).sort((a,b)=>String(a.id).localeCompare(String(b.id)));
}
export function chooseModelId(models, {boundId, preferredId, referenceId}={}) {
  const has=id=>models.some(model=>model.id===id);
  // A plan's null binding deliberately means no model; never borrow another one.
  if(boundId !== undefined) return boundId===null || has(boundId) ? boundId : undefined;
  if(preferredId===null)return null;
  if(preferredId&&has(preferredId))return preferredId;
  if(referenceId&&has(referenceId))return referenceId;
  return models.length===1 ? models[0].id : null;
}
export function modelEvidence(model) {
  if(!model)return {kind:'none',mae:null,baselineMae:null,wape:null,priceAllowed:false};
  const priceAllowed=Array.isArray(model.allowed_uses)&&model.allowed_uses.includes('bounded_price_scenarios');
  if(model.confirmation){
    const confirmation=model.confirmation,demand=confirmation.demand_candidate,comparison=confirmation.comparisons?.[demand];
    const confirmed=comparison?.accepted===true&&finite(comparison.pooled_mae)&&finite(comparison.baseline_mae);
    return {kind:'operational',demandCandidate:demand,priceCandidate:confirmation.price_candidate||null,
      retainedBaseline:demand==='last4mean',mae:confirmed?comparison.pooled_mae:null,
      baselineMae:confirmed?comparison.baseline_mae:null,wape:null,
      priceAllowed:priceAllowed&&Boolean(confirmation.price_candidate),comparisons:confirmation.comparisons||{},
      selectionScores:model.selection?.pooled_mae||{},selectionCandidate:model.selection?.demand_candidate||null};
  }
  return {kind:'reference',mae:finite(model.metrics?.mae)?model.metrics.mae:null,
    baselineMae:finite(model.metrics?.baseline_mae)?model.metrics.baseline_mae:null,
    wape:finite(model.metrics?.wape)?model.metrics.wape:null,priceAllowed};
}
export function recoverTrainingRun(items,snapshotId) {
  // A succeeded/failed worker can still need provider finalization. Only the
  // server's released slot marks that recovery work as complete.
  return items.filter(run=>run.snapshot_id===snapshotId&&run.slot_released===false)
    .sort((a,b)=>String(b.created_at||'').localeCompare(String(a.created_at||''))||String(b.id).localeCompare(String(a.id)))[0]||null;
}
