import {snapshotModels, chooseModelId, modelEvidence, recoverTrainingRun} from './models.mjs';
import {ApiClient, ApiError, OperationCancelled, Session} from './api.mjs';
import {escapeHTML as h, number as n, titleCase, rowId, decision, rowReason, reasonText, visibleRows, splitBatches, lineChart, errorCopy, statusText} from './ui.mjs';

const app = document.querySelector('#app');
const dialog = document.querySelector('#sign-in-dialog');
const state = {
  chinese:false, step:2, config:null, sample:null, me:null, workspace:null, snapshots:[], plans:[], pricebooks:[],
  snapshot:null, model:null, models:[], modelSelections:{}, plan:null, rows:[], catalog:[], selected:null, detail:null, history:null, events:[],
  query:'', filter:'all', selectedReviews:new Set(), busy:'', error:null, message:'', drafts:{}, dirty:false,
  run:null, trainingRecoveryUnavailable:false, reviewProgress:null, pricebook:null, guest:true, detailLoading:false, teachingAccepted:false,
};
try { state.chinese = localStorage.getItem('pricing-language') === 'zh'; } catch {}
let session, api, pollTimer, detailSequence = 0, identityGeneration = 0, modelSelectionGeneration = 0;
const t = (en,zh) => state.chinese ? zh : en;
const prefix = () => `/api/v1/workspaces/${encodeURIComponent(state.workspace.workspace_id)}`;
const cap = action => !state.guest && (state.workspace?.capabilities || []).includes(action);
const safe = value => h(value);
const label = (en,zh) => h(t(en,zh));
const btn = (action,en,zh,{primary=false,disabled=false,extra=''}={}) => `<button class="btn${primary?' primary':''}" data-action="${action}" ${disabled?'disabled':''} ${extra}>${label(en,zh)}</button>`;
const badge = row => `<span class="pill ${decision(row)}">${label(...({change:['Change','调价'],hold:['Hold','保持'],needs_data:['Needs data','缺少数据'],conflict:['Rule conflict','规则冲突'],excluded:['Excluded','已排除'],uncalculated:['Not compared','尚未比较']}[decision(row)]))}</span>`;
const stats = () => state.snapshot?.analysis?.catalog_stats || {};
const period = () => (state.step===5 ? state.pricebook?.period : null) || state.plan?.period || state.snapshot?.period || [];
const currentRows = () => state.rows.length ? state.rows : state.catalog;
const fact = (value,en,zh,sub='') => `<div class="fact"><strong class="fact-value">${safe(value)}</strong><span class="fact-label">${label(en,zh)}</span>${sub?`<small>${safe(sub)}</small>`:''}</div>`;
const jsonDetails = (en,zh,value) => value ? `<details class="details"><summary>${label(en,zh)}</summary><pre>${safe(JSON.stringify(value,null,2))}</pre></details>` : '';
const currentRow = () => currentRows().find(row => rowId(row) === state.selected);
const pendingCount = () => state.rows.filter(row => !['approve_change','approve_hold','reject','exclude'].includes(row.review?.action)).length;
function preserveForms() {
  if (state.resetForms) return;
  app.querySelectorAll('input[id],textarea[id],select[id]').forEach(input => {
    if (['password','file','checkbox'].includes(input.type) || ['catalog-query','catalog-filter','model-picker'].includes(input.id)) return;
    state.drafts[input.id] = input.value;
  });
}
function restoreForms() {
  Object.entries(state.drafts).forEach(([id,value]) => { const input = document.getElementById(id); if (input && !['password','file'].includes(input.type)) input.value = value; });
}
function announce(message) { document.querySelector('#announcer').textContent = message; }
function render() {
  preserveForms(); state.resetForms=false;
  document.documentElement.lang = state.chinese ? 'zh-CN' : 'en';
  const count = stats().series ?? state.plan?.summary?.scope_count;
  const contextTitle = state.guest ? t('Orange juice example','橙汁示例') : t('Private pricing workspace','私密定价工作区');
  app.innerHTML = `<header class="topbar"><div class="wordmark"><span class="brand-icon" aria-hidden="true">↗</span>Pricing <span>/ workbench</span></div><div class="account-actions">${state.me ? `<span class="account-name small muted">${safe(statusText(state.workspace?.role,state.chinese) || t('No workspace access','无工作区权限'))}</span>` : ''}${btn('language',state.chinese?'English':'中文讲解',state.chinese?'English':'中文讲解',{extra:`aria-label="${state.chinese?'Switch to English':'切换到中文讲解'}"`})}${state.me ? btn('logout','Sign out','退出登录') : btn('login','Sign in','登录')}</div></header>
  <div class="contextbar"><div><div class="context-title">${safe(contextTitle)}${count !== undefined ? ` <span class="muted">·</span> ${safe(n(stats().items,0))} ${label('brands','个品牌')} <span class="muted">·</span> ${safe(n(stats().sites,0))} ${label('stores','家门店')} <span class="muted">·</span> ${safe(n(count,0))} ${label('store–brand entries','个门店与品牌组合')}` : ''}</div><p>${state.snapshot ? `${label('History: source weeks','历史：原始周编号')} ${stats().first_week_index!==undefined?safe(stats().first_week_index)+'–':''}${safe(state.snapshot.cutoff)} · ${label('Plan for source weeks','计划覆盖周编号')} ${safe(period().join(' · '))}` : label('Choose a saved example or import weekly sales.','选择保存的示例，或导入每周销售记录。')}</p></div><div class="actions"><span class="pill saved">${label(state.guest?'Saved example · Read only':'Private workspace',state.guest?'保存的示例 · 只读':'私密工作区')}</span>${state.me ? btn(state.guest?'workspace':'example',state.guest?'Open my workspace':'View example',state.guest?'进入我的工作区':'查看示例') : ''}</div></div>
  ${state.busy ? `<div class="busy-line" role="status"><span class="loading-mark" aria-hidden="true"></span>${safe(state.busy)}</div>` : ''}
  <div class="shell"><nav class="steps" aria-label="${label('Pricing workflow','定价流程')}">${[['Import','导入'],['Check data & model','检查数据与模型'],['Plan prices','制定价格'],['Review','审核'],['Publish','发布']].map(([en,zh],i)=>`<button class="step" data-step="${i+1}" ${state.step===i+1?'aria-current="step"':''}><span class="step-number" aria-hidden="true">${i+1}</span><span>${label(en,zh)}</span></button>`).join('')}</nav>
  <main id="main" tabindex="-1">${renderError()}${state.message ? `<div class="notice neutral" role="status">${safe(state.message)}</div>` : ''}${state.dirty ? `<div class="notice">${label('You have unsaved changes. Saving creates a new revision and clears every approval for this plan.','存在未保存的修改。保存会创建新版本，并清除整个方案的审核批准。')}</div>` : ''}${[null,renderImport,renderCheck,renderPlan,renderReview,renderPublish][state.step]()}</main>
  <footer class="footer"><span>${label('A price plan is a decision to review. Estimates are not realized profit.','价格方案需要审核。估计值不是已实现的利润。')}</span><span>${label('Source units preserved · Private Demo ledger','保留原始单位 · 私密演示台账')}</span></footer></div>`;
  restoreForms();
  app.querySelectorAll('button[data-action],button[data-step]').forEach(button => { if (state.busy && !['language','login','logout'].includes(button.dataset.action)) button.disabled = true; });
}
function renderError() {
  if (!state.error) return '';
  const error = state.error;
  return `<section class="notice error" role="alert"><strong>${safe(errorCopy(error,state.chinese))}</strong>${error.fields ? `<pre class="error-fields">${safe(JSON.stringify(error.fields,null,2))}</pre>` : ''}<p class="small">${label('Reference','参考编号')}: ${safe(error.code)}${error.requestId ? ` · ${safe(error.requestId)}` : ''}</p><div class="actions">${error.status===401 ? btn('login','Sign in again','重新登录') : ''}${btn('reload','Reload current version','载入最新版本')}${btn('dismiss-error','Dismiss','关闭')}</div></section>`;
}
function heading(step,en,zh,desc,descZh,action='') {
  return `<div class="page-heading"><div><p class="eyebrow">${label(`Step ${step} / 5`,`第 ${step} 步／共 5 步`)}</p><h1>${label(en,zh)}</h1><p>${label(desc,descZh)}</p></div>${action}</div>`;
}
function guestNote() {
  return `<div class="notice neutral"><strong>${label('You are exploring a saved scenario.','正在浏览保存的情景。')}</strong><p>${label('The results below were calculated earlier using the stated assumptions. An invited account lets you upload records, run a model and save a private plan.','以下结果已按声明的假设预先计算。受邀账号可上传记录、运行模型并保存私密方案。')}</p></div>`;
}
function renderImport() {
  return heading(1,'Start with weekly sales','从每周销售记录开始','Each catalog entry follows one brand at one store. Keep all entries together through planning and review.','每条目录记录对应一个品牌在一家门店的历史。制定方案和审核时，保留全部记录。') +
  `<div class="two-columns"><section class="panel"><div class="panel-body"><h2>${label('Import your records','导入你的记录')}</h2><p class="explanation">${label('Use a UTF-8 CSV with weekly prices and recorded sales. Your records and results stay in this workspace.','使用包含每周价格和记录销量的 UTF-8 CSV。记录与结果仅保存在此工作区。')}</p><form id="upload-form"><div class="upload-area"><label for="csv-file" class="field-label">${label('Weekly sales CSV','每周销售 CSV')}</label><input id="csv-file" name="file" type="file" accept=".csv,text/csv" required ${!cap('upload')?'disabled':''}><p>${label('Up to 10 MiB · 100,000 records · 2,000 entries. Model training and price comparison support up to 300 entries.','最多 10 MiB、100,000 条记录、2,000 个组合。模型训练与价格比较最多支持 300 个组合。')}</p></div><label><span class="field-label">${label('Last complete source week to use','使用的最后一个完整原始周编号')}</span><input id="upload-cutoff" name="cutoff" type="number" step="1" required placeholder="160" ${!cap('upload')?'disabled':''}></label><p class="form-note">${label('For date-based CSVs, use the week offset from Monday 1970-01-05. Only records known by the cutoff enter this snapshot.','日期格式 CSV 使用自 1970-01-05（周一）起的周偏移量。快照只包括截至该时点已知的记录。')}</p><div class="actions space-top"><button class="btn primary" type="submit" ${!cap('upload')?'disabled':''}>${label('Save dataset and check data','保存数据并检查')}</button>${btn('template','Download CSV template','下载 CSV 模板')}<a class="btn" href="/workbench/downloads/synthetic-weekly-teaching.csv" download>${label('Download synthetic 100-week CSV','下载 100 周合成示例 CSV')}</a></div><p class="form-note">${label('The synthetic CSV contains 2 invented products and 200 records over 100 weeks. Use cutoff 100. Its USD values are invented test data, separate from the orange juice source.','合成 CSV 包含 2 个虚构商品、100 周共 200 条记录。请使用截至周编号 100。USD 数值是虚构测试数据，与橙汁原始数据无关。')}</p></form>${!cap('upload')?`<p class="form-note">${label('Upload requires an invited account with upload access.','上传需要具有上传权限的受邀账号。')}</p>`:''}${jsonDetails('CSV columns and validation','CSV 字段与校验',{required:['item_id','price','units','currency','unit','price_basis','source_id'],time:'week_index + known_at_index OR week_start + known_at_date',optional:['site_id','feature_ad','returns_units'],unknown_columns:'rejected',missing_values:'preserved, never converted to zero'})}</div></section>
  <section class="panel"><div class="panel-body"><h2>${label('Continue with saved work','继续已保存的工作')}</h2>${state.guest ? `<p class="explanation">${label('The prepared orange juice example starts at the data check. Nothing you view changes store prices.','准备好的橙汁示例从数据检查开始。浏览示例不会更改门店价格。')}</p>${btn('check','Inspect the saved example','检查保存的示例',{primary:true,extra:'style="margin-top:18px"'})}` : `<div class="choice-list">${state.snapshots.map(snapshot=>`<div class="choice"><div><strong>${label('Snapshot','快照')} ${safe(snapshot.cutoff)}</strong><p>${safe(snapshot.id)} · ${n(snapshot.scope_count,0)} ${label('entries','个组合')}</p></div>${btn('open-snapshot','Open','打开',{extra:`data-id="${safe(snapshot.id)}"`})}</div>`).join('') || `<p class="empty">${label('Import a CSV to create your first snapshot.','导入 CSV，创建首个快照。')}</p>`}</div><h3 class="space-top">${label('Saved plans','已保存的方案')}</h3><div class="choice-list">${state.plans.map(plan=>`<div class="choice"><div><strong>${label('Revision','版本')} ${safe(plan.revision)} · ${safe(statusText(plan.state,state.chinese))}</strong><p>${safe(plan.id)}</p></div>${btn('open-plan','Open','打开',{extra:`data-id="${safe(plan.id)}"`})}</div>`).join('') || `<p class="empty">${label('No saved plan yet. Check a snapshot, then create a plan.','尚无保存的方案。检查快照后，即可创建方案。')}</p>`}</div>`}</div></section></div>`;
}
function renderCheck() {
  const analysis = state.snapshot?.analysis;
  const s = stats();
  return heading(2,'See the sales behind this plan','查看这份方案依据的销售记录','Check what was recorded, what is missing, and how close past predictions came to actual sales.','检查已有记录、缺失信息，以及历史预测与记录销量的差距。',btn('plan','View price plan','查看价格方案',{primary:true,disabled:!state.snapshot})) +
  (state.guest ? guestNote() : '') + (!analysis ? `<div class="panel panel-body"><p class="empty">${label('No snapshot is loaded. Import weekly records or choose a saved snapshot.','尚未载入快照。请导入每周记录或选择保存的快照。')}</p>${btn('import','Choose records','选择记录',{primary:true})}</div>` :
  `<div class="facts">${fact(n(s.observed_rows,0),'Recorded observations','条观测记录')}${fact(n(s.series,0),'Catalog entries','个目录组合')}${fact(n(s.missing_after_first_observation_rows,0),'Missing weeks after first record','首次记录后缺失的周')}${fact(n(analysis.outliers?.flagged_rows,0),'Unusual values retained for inspection','保留待检查的异常值')}</div>
  <div class="two-columns"><section class="panel"><div class="panel-body"><div class="chart-title"><h2>${label('Recorded sales by week','每周记录销量')}</h2><span>${label('All catalog entries','全部目录组合')}</span></div>${lineChart(analysis.weekly_history || [],'units',{label:t('Recorded source sales by source week; missing observations remain gaps.','按原始周编号展示的记录销量；缺失观测保留为空缺。'),chinese:state.chinese})}<p class="explanation">${label('Source sales units. Missing weeks are unknown, not zero sales. Seasonal patterns and advertising can move together with price; this chart does not separate their effects.','原始销量单位。缺失周是未知值，不是零销量。季节波动和广告可能与价格共同变化，此图无法分离各自影响。')}</p><ul class="factor-list"><li><span>${label('Price & recorded sales','价格与记录销量')}</span><span class="factor-state">${label('Available','已有记录')}</span></li><li><span>${label('Feature advertising','广告投放标记')}</span><span class="factor-state">${safe(statusText(analysis.factors?.feature_advertising?.status || 'unknown',state.chinese))}</span></li><li><span>${label('Cost · stock · promotion spend','成本 · 库存 · 促销费用')}</span><span class="factor-state">${label('Missing business inputs','缺少经营输入')}</span></li></ul><details class="details"><summary>${label('Understand the data and seasonality','理解数据和季节性')}</summary><p>${label('The example uses source weeks, not verified calendar dates. Feature advertising describes only the supplied ad flag; coupons, other promotions, competitors, stock and realized profit are not observed. The model may use repeated historical patterns, but future accuracy is unknown.','示例使用原始周编号，没有核实对应日历日期。广告字段仅表示提供的广告标记；优惠券、其他促销、竞争对手、库存和已实现利润均未观测。模型可参考历史重复模式，但未来准确度未知。')}</p></details></div></section>
  <section class="panel"><div class="panel-body"><h2>${label('Check predictions against past sales','用历史销量检查预测')}</h2>${renderModelPicker()}${renderModelEvidence()}<details class="details"><summary>${label('Learn how the model uses limited history','了解模型如何处理有限历史')}</summary><p>${label('A model can share a brand’s price–sales relationship across stores, while using each store’s recent sales. That does not replace missing facts or make every entry safe to reprice. Entries without enough support remain visible as holds or explicit business decisions. No prediction intervals are available.','模型可合并同品牌在不同门店的价格与销量关系，同时使用各店近期销量。这不能替代缺失事实，也不意味着每条记录都适合调价。支持不足的记录仍保留为保持项或明确的经营决定。此处没有预测区间。')}</p></details>${jsonDetails('Model evidence and provenance','模型依据与来源',state.model)}${!state.guest ? renderTraining() : ''}</div></section></div>
  <section class="space-top">${renderCatalog(true)}</section>${jsonDetails('Source details and data quality','数据出处与质量',{provenance:analysis.provenance,factors:analysis.factors,concentration:analysis.concentration,catalog_stats:s})}`);
}
function renderModelPicker() {
  if(state.guest)return '';
  const selected=state.model?.id||'',bound=Boolean(state.plan);
  return `<div class="model-picker space-top"><label><span class="field-label">${label('Saved model for this snapshot','此快照的已保存模型')}</span><select id="model-picker" class="full-width" ${bound||state.busy?'disabled':''}><option value="">${label('No model selected · holds and explicit rules','未选择模型 · 保持价格和明确规则')}</option>${state.models.map(model=>`<option value="${safe(model.id)}" ${selected===model.id?'selected':''}>${safe(model.id)} · ${label(model.allowed_uses?.includes('bounded_price_scenarios')?'Price scenarios available':'Forecast only',model.allowed_uses?.includes('bounded_price_scenarios')?'可比较价格情景':'仅预测')}</option>`).join('')}</select></label><p class="form-note">${bound?label('This plan keeps its saved model binding. Choosing a model for a new draft leaves this saved plan unchanged.','此方案保留已保存的模型绑定。为新草稿选择模型不会修改此已保存方案。'):state.models.length>1&&!selected?label('Several saved models match this snapshot. Choose one explicitly; the list does not imply which is newest or best.','有多个保存模型匹配此快照。请明确选择；列表顺序不表示哪个最新或最好。'):label('Only models registered to this exact snapshot are listed. Training results are rediscovered from the workspace after sign-in or reload.','仅列出注册到此快照的模型。登录或重新载入后，会从工作区重新查找训练结果。')}</p>${bound?btn('new-model-draft','Choose a model for a new draft','为新草稿选择模型',{disabled:!cap('edit')}):''}</div>`;
}
function renderModelEvidence() {
  const evidence=modelEvidence(state.model);
  if(evidence.kind==='none')return `<p class="empty">${label(state.models.length?'Choose a saved model above to inspect its own evidence.':'No saved model is available for this snapshot. Train one or continue with explicit business rules.',state.models.length?'请在上方选择保存模型，检查其独立依据。':'此快照没有可用的保存模型。可以训练模型，或继续采用明确的经营规则。')}</p>`;
  const operational=evidence.kind==='operational',reviewed=state.model?.review_status==='reviewed_reference_demo';
  const scoreAvailable=evidence.mae!==null&&evidence.baselineMae!==null;
  const bar=evidence.baselineMae>0?Math.min(100,100*evidence.mae/evidence.baselineMae):0;
  const modelLabel=operational?t('Confirmed demand estimate','确认阶段保留的销量估计'):reviewed?t('Reviewed reference model','经过检查的参考模型'):t('Saved model estimate','保存的模型估计');
  let output=`<p class="explanation">${label('Lower average error means predictions were closer to recorded sales. Compare the model with a simple recent-sales estimate.','平均误差越小，预测越接近记录销量。将模型与近期销量的简单估计作比较。')}</p>`;
  if(operational)output+=`<div class="notice neutral space-top"><strong>${label(evidence.retainedBaseline?'Recent-sales baseline retained':'Operational result · automatic confirmation rule',evidence.retainedBaseline?'保留近期销量基准':'运行结果 · 自动确认规则')}</strong><p>${label(evidence.retainedBaseline?'The saved forecasting choice is the recent-sales baseline. No learned demand model was retained after the automatic checks.':'The saved demand candidate passed the configured historical confirmation rule.',evidence.retainedBaseline?'保存的预测方法是近期销量基准。自动检查后，没有保留学习型销量模型。':'保存的销量候选模型通过了配置的历史确认规则。')}</p><p>${label('This training result has not been independently reviewed. It is not evidence of a causal gain or permission to publish prices.','此训练结果尚未经独立审核，不能证明因果增益，也不构成发布价格的许可。')}</p></div>`;
  if(scoreAvailable)output+=`<table class="metrics"><caption class="sr-only">${label(operational?'Confirmation-stage historical prediction error':'Historical prediction error',operational?'确认阶段历史预测误差':'历史预测误差')}</caption><thead><tr><th>${label(operational?'Confirmation check':'Historical check',operational?'确认阶段检验':'历史检验')}</th><th>${label('Average absolute error','平均绝对误差')}</th></tr></thead><tbody><tr><td>${label('Recent-sales estimate','近期销量估计')}<div class="metric-bar baseline"><i style="width:100%"></i></div></td><td>${n(evidence.baselineMae,3)}</td></tr><tr><td><strong>${safe(modelLabel)}</strong><div class="metric-bar"><i style="width:${bar}%"></i></div></td><td><strong>${n(evidence.mae,3)}</strong></td></tr></tbody></table>`;
  else output+=`<p class="explanation">${label(operational&&evidence.retainedBaseline?'The response does not provide a pooled confirmation score for the retained baseline. Selection-stage scores, when present, are shown separately below.':'No comparable historical error pair is supplied for the selected model.',operational&&evidence.retainedBaseline?'响应没有提供所保留基准的合并确认分数。如有选择阶段分数，会在下方单独列出。':'所选模型没有提供可比较的历史误差对。')}</p>`;
  if(evidence.wape!==null)output+=`<p class="explanation">${label('Weighted absolute error','加权绝对误差')}: ${n(evidence.wape*100,4)}%.</p>`;
  output+=`<p class="explanation">${label('Recorded prices and feature advertising were supplied for the historical check. This does not prove that changing prices causes a gain. Future accuracy is unknown.','历史检验使用已记录的价格与广告状态，并不能证明调价会带来增益。未来准确度未知。')}</p><div class="notice space-top"><strong>${label(evidence.priceAllowed?'Bounded price scenarios available':'Forecast only · no supported price-response model',evidence.priceAllowed?'可比较有范围限制的价格情景':'仅预测 · 没有受支持的价格响应模型')}</strong><p>${label(evidence.priceAllowed?'Price comparisons use a separately retained price candidate and still require support for each entry. Every price plan needs independent human review.':'Keep feasible reference prices or record explicit business rules. Forecast accuracy alone does not support changing prices.',evidence.priceAllowed?'价格比较使用另行保留的价格候选模型，且每条记录仍需足够支持。每份价格方案都需要独立人工审核。':'保持符合规则的参考价，或记录明确的经营规则。仅有预测准确度不能支持调价。')}</p></div>`;
  if(operational){
    output+=`<details class="details"><summary>${label('Demand choice, price capability and stage-specific evidence','销量选择、定价能力和各阶段依据')}</summary><dl class="dl"><dt>${label('Retained demand candidate','保留的销量候选')}</dt><dd>${safe(evidence.demandCandidate)}</dd><dt>${label('Retained price candidate','保留的价格候选')}</dt><dd>${safe(evidence.priceCandidate||t('None','无'))}</dd></dl>`;
    const comparisons=Object.entries(evidence.comparisons);
    if(comparisons.length)output+=`<h3>${label('Confirmation-stage comparisons','确认阶段比较')}</h3><table class="candidate-table"><thead><tr><th>${label('Candidate','候选')}</th><th>${label('Error','误差')}</th><th>${label('Baseline','基准')}</th><th>${label('Rule passed','通过规则')}</th></tr></thead><tbody>${comparisons.map(([name,value])=>`<tr><td>${safe(name)}</td><td>${n(value.pooled_mae,3)}</td><td>${n(value.baseline_mae,3)}</td><td>${label(value.accepted?'Yes':'No',value.accepted?'是':'否')}</td></tr>`).join('')}</tbody></table>`;
    const scores=Object.entries(evidence.selectionScores);
    if(scores.length)output+=`<h3 class="space-top">${label('Selection-stage error · earlier model selection','选择阶段误差 · 较早的模型选择')}</h3><p>${label('These scores belong to model selection. They are not confirmation scores or future accuracy.','这些分数属于模型选择阶段，并非确认阶段分数，也不是未来准确度。')}</p><table class="candidate-table"><thead><tr><th>${label('Candidate','候选')}</th><th>${label('Selection error','选择阶段误差')}</th></tr></thead><tbody>${scores.map(([name,score])=>`<tr><td>${safe(name)}</td><td>${n(score,3)}</td></tr>`).join('')}</tbody></table>`;
    output+='</details>';
  }
  return output;
}
function renderTraining() {
  const run = state.run;
  const pipelines = state.config?.training?.pipeline_versions || state.config?.pipeline_versions || (state.config?.pipeline_version ? [state.config.pipeline_version] : []);
  return `<div class="details"><h3>${label('Train on this snapshot','使用此快照训练')}</h3><p class="explanation training-copy">${label('Start the fixed weekly model pipeline. It needs at least 80 weeks and at most 300 entries. A completed run is saved as unreviewed; it does not approve price changes.','启动固定每周模型流程。至少需要 80 周，最多 300 个组合。完成结果保存为未审核状态，不会自动批准调价。')}</p><div class="actions space-top">${btn('train','Start model training','开始模型训练',{disabled:!cap('train') || !state.snapshot || !pipelines.length,extra:`data-pipeline="${safe(pipelines[0])}"`})}</div>${state.trainingRecoveryUnavailable?`<p class="form-note">${label('Saved training status is unavailable in this service. Existing snapshots and models remain available.','此服务暂不能提供保存的训练状态，已有快照和模型仍可访问。')}</p>`:''}${run ? `<div class="run-status" role="status"><strong>${safe(run.slot_released===false&&['succeeded','failed'].includes(run.state)?t('Worker stopped · job completion needs checking','工作进程已停止 · 需核对任务完成状态'):statusText(run.state,state.chinese))}</strong><p>${label('Current task','当前任务')}: ${safe(statusText(run.phase || 'awaiting_reconciliation',state.chinese))}</p><p>${n(run.completed_tasks,0)}${run.total_tasks ? ` / ${n(run.total_tasks,0)}` : ''} ${label('tasks completed','项任务已完成')}</p>${run.total_tasks ? `<progress value="${Number(run.completed_tasks)||0}" max="${Number(run.total_tasks)}">${n(run.completed_tasks,0)}</progress>` : ''}${run.error_code ? `<p>${safe(reasonText(run.error_code,state.chinese))}</p>` : ''}<div class="actions space-top">${btn('reconcile-run','Check job completion','核对任务完成状态',{disabled:!cap('train')})}${!['succeeded','failed','cancelled','timed_out'].includes(run.state)?btn('cancel-run','Cancel training','取消训练',{disabled:!cap('train')}):''}</div><p>${label('Status reflects completed server tasks. If completion is uncertain, check it before starting another run.','状态反映服务器实际完成的任务。若完成情况不明确，请先核对，再开始其他运行。')}</p></div>` : ''}</div>`;
}
function renderAssumptions() {
  const usingExample = state.plan?.assumption_mode === 'teaching_60pct_v1' || state.guest && Boolean(state.sample?.assumptions);
  const r=Object.fromEntries(Object.entries(state.plan?.rules || {}).map(([key,value])=>[key,value?.value ?? value]));
  const description = `<ul><li>${label('Cost is 60% of the frozen reference price. It is an invented cost for this exercise.','成本为冻结参考价的 60%，是为练习设置的假设。')}</li><li>${label('Keep the last recorded feature-advertising state for all four weeks; unknown stays unknown. Assume zero additional advertising spend each week.','四周沿用最近记录的广告状态；未知仍为未知。假设每周新增广告费用为零。')}</li><li>${label('Treat the price as receipts for one source sales unit. This is a hypothetical unit mapping; currency and package size are not verified.','假设每个原始销量单位收到对应价格金额。这是假设的单位映射；币种和包装规格未核实。')}</li><li>${label('Stock remains unknown. Stock feasibility is not checked.','库存保持未知，未检查供货能否支持方案。')}</li></ul>`;
  return `<div class="assumptions"><h3>${label(usingExample?'Saved scenario · example assumptions':'Choose business assumptions explicitly',usingExample?'保存的情景 · 示例假设':'明确选择经营假设')}</h3>${usingExample?`<p class="explanation">${label('Assumed cost','假设成本')} 60% · ${n(Number(r.minimum_margin ?? .2)*100)}% ${label('minimum margin','最低毛利率')} · −${n(Number(r.maximum_decrease_bps ?? 500)/100)}% / +${n(Number(r.maximum_increase_bps ?? 500)/100)}% · ${n(r.max_changed_series ?? 20,0)} ${label('maximum changes','个组合最多调价')} · ${n(r.price_tick ?? '.01',8)} ${label('price step','价格步长')}</p><p class="form-note">${label('Hypothetical receipts and cost · zero extra ad spend · stock unknown. No new calculation runs while you view this saved example.','收款与成本是假设 · 新增广告费用为零 · 库存未知。查看保存的示例不会触发新计算。')}</p><details class="details"><summary>${label('Read the assumptions behind these results','查看结果采用的假设')}</summary>${description}</details>`:`<p class="explanation">${label('Sales records do not supply costs, stock or future advertising. The optional example below makes these assumptions; it does not turn them into observed facts.','销售记录不提供成本、库存或未来广告。以下可选示例会采用这些假设，但不会将其变为已观测事实。')}</p>${description}<p class="form-note">${label('The example also sets a 20% minimum margin, ±5% price bounds, at most 20 changes and a 0.01 source-unit price step.','示例同时设置最低毛利率 20%、调价幅度 ±5%、最多调价 20 个组合、价格步长 0.01 个原始单位。')}</p>`}${!state.guest?`<div class="actions space-top">${!usingExample?btn('assumptions','Use example business assumptions','使用示例经营假设',{disabled:!cap('edit') || !state.snapshot}):''}${usingExample?btn('clear-assumptions','Remove example assumptions','移除示例假设',{disabled:!cap('edit')}):''}</div>`:''}</div>`;
}

function renderRules() {
  const r = Object.fromEntries(Object.entries(state.plan?.rules || {}).map(([key,value])=>[key,value?.value ?? value]));
  const input = (id,en,zh,value,{step='any',min='0',max=''}={}) => `<label><span class="field-label">${label(en,zh)}</span><input id="${id}" type="number" value="${safe(value)}" step="${step}" min="${min}" ${max?`max="${max}"`:''} required ${!cap('edit')?'disabled':''}></label>`;
  return `<details class="details" ${!state.plan?'open':''}><summary>${label('Set price rules and save a new version','设置价格规则并保存新版本')}</summary><p>${label('These are explicit planning rules. They do not fill missing cost or stock. Changes invalidate all earlier approvals.','这些是明确的规划规则，不会补齐缺失的成本或库存。修改会使之前的全部批准失效。')}</p><form id="rules-form"><div class="form-grid">${input('rule-down','Maximum decrease (%)','最大降价幅度（%）',Number(r.maximum_decrease_bps ?? 500)/100,{max:'99.99'})}${input('rule-up','Maximum increase (%)','最大涨价幅度（%）',Number(r.maximum_increase_bps ?? 500)/100)}${input('rule-margin','Minimum margin (%)','最低毛利率（%）',Number(r.minimum_margin ?? .2)*100,{max:'99.99'})}${input('rule-cap','Maximum changed entries','最多调价组合数',r.max_changed_series ?? 20,{step:'1'})}${input('rule-tick','Price step (source units)','价格步长（原始单位）',r.price_tick ?? '.01',{min:'0.00000001'})}${input('rule-age','Maximum reference age (weeks)','参考价最长时效（周）',r.maximum_reference_age_weeks ?? 4,{step:'1'})}</div><p class="form-note">${label('Stock checks remain unavailable when stock is missing. Price and sales units stay as supplied by the source.','缺少库存时，无法完成库存检查。价格与销量保留数据来源提供的单位。')}</p><div class="actions space-top"><button class="btn" type="submit" ${!cap('edit')?'disabled':''}>${label(state.plan?'Save rules as new revision':'Create private draft',state.plan?'将规则保存为新版本':'创建私密草稿')}</button></div></form></details>`;
}
function renderPlan() {
  const summary = state.plan?.summary || {}, totals = summary.totals || {};
  return heading(3,'Choose a four-week price plan','制定四周价格方案','Every catalog entry gets a decision and a reason. Compare allowed alternatives while keeping unchanged prices visible.','每条目录记录都要有处理结果和理由。比较允许的候选价，同时保留不调价的记录。',state.guest ? btn('review','View review step','查看审核步骤',{primary:true}) : btn('compare','Compare prices','比较价格',{primary:true,disabled:!cap('compare')||!state.plan||state.dirty})) +
  (!state.snapshot?`<div class="panel panel-body"><p class="empty">${label('Load a snapshot before planning prices.','制定价格前，请先载入快照。')}</p>${btn('import','Choose records','选择记录')}</div>`:
  `<section class="panel"><div class="panel-body"><div class="status-line"><span class="status-dot"></span>${label('One price per entry for all four weeks','每个组合在四周内使用同一个价格')}${state.plan ? ` · ${label('Revision','版本')} ${safe(state.plan.revision ?? 'saved')} · ${safe(statusText(state.plan.state || 'read_only_sample',state.chinese))}` : ''}</div>${renderAssumptions()}${!state.guest?renderRules():''}</div></section>
  ${state.plan ? `<section class="space-top"><div class="facts">${fact(n(summary.changed_series,0),'Proposed changes','建议调价')}${fact(n(summary.disposition_counts?.hold,0),'Hold reference price','保持参考价')}${fact(n(summary.scope_count,0),'Entries in full scope','全目录范围内组合')}${fact(totals.difference===undefined?'—':n(totals.difference,2),'Estimated scenario difference','情景估计差额',t('Source-scale units · not realized profit','原始尺度单位 · 不是已实现利润'))}</div>${totals.difference !== null && totals.difference !== undefined ? `<p class="explanation">${label('Comparison covers','比较涵盖')} ${n(totals.matched_series_count,0)} ${label('matched entries;','个匹配组合；')} ${n(totals.missing_series_count,0)} ${label('are not included in the contribution estimate. Estimates depend on the declared cost, advertising and unit assumptions. Future accuracy is unknown.','个组合不计入贡献额估计。估计取决于声明的成本、广告和单位假设，未来准确度未知。')}</p>` : `<div class="notice">${label('Contribution is unavailable when required assumptions or model support are missing. This does not turn missing entries into zero.','缺少必要假设或模型支持时，无法估算贡献额。缺失组合不会被视为零。')}</div>`}</section>`:''}
  <section class="space-top">${renderCatalog(false)}</section><div class="guide"><p><strong>${label('Next: another person checks the whole plan','下一步：由另一人审核整个方案')}</strong>${label('Save and compare any revision first. Every entry must be approved, rejected or excluded before publication.','先保存并比较新版本。发布前，每条记录都必须获批、被拒绝或有理由地排除。')}</p>${state.guest ? btn('review','View review step','查看审核步骤',{primary:true}) : btn('submit','Send for review','提交审核',{primary:true,disabled:!cap('submit')||!state.plan||state.dirty||!state.plan.proposal_hash})}</div>`);
}
function renderCatalog(dataMode = false) {
  const rows = visibleRows(currentRows(),state.query,dataMode?'all':state.filter);
  return `<div class="catalog-layout"><div class="catalog-main"><div class="panel-head"><div><h2>${label('Whole catalog','完整目录')}</h2><p>${label('Select an entry to understand its history and decision.','选择一条记录，查看其历史和决定依据。')}</p></div><span class="pill">${n(currentRows().length,0)} ${label('entries','个组合')}</span></div><div class="catalog-toolbar"><label><span class="field-label">${label('Find a store or brand','查找门店或品牌')}</span><input id="catalog-query" type="search" value="${safe(state.query)}" placeholder="${label('Search the whole catalog','搜索完整目录')}"></label>${!dataMode?`<label><span class="field-label">${label('Show decisions','显示决定')}</span><select id="catalog-filter">${[['all','All entries','所有记录'],['change','Changes','调价'],['hold','Holds','保持'],['needs_data','Needs data','缺少数据'],['conflict','Rule conflicts','规则冲突'],['excluded','Excluded','已排除'],['pending','Awaiting review','等待审核']].map(([value,en,zh])=>`<option value="${value}" ${state.filter===value?'selected':''}>${label(en,zh)}</option>`).join('')}</select></label>`:''}</div>${state.step===4&&!state.guest?renderReviewBar(rows):''}<div class="table-scroll"><table class="catalog-table"><caption class="sr-only">${label('All catalog entries, including unchanged prices','全部目录记录，包括不调价项')}</caption><thead><tr>${state.step===4&&!state.guest?`<th>${label('Select','选择')}</th>`:''}<th>${label('Store / brand','门店／品牌')}</th><th class="numeric">${label('Reference','参考价')}</th>${dataMode?`<th class="numeric">${label('Observed weeks','观测周数')}</th><th class="numeric">${label('Price changes','价格变化次数')}</th>`:`<th class="numeric">${label('Plan price','计划价')}</th><th>${label('Decision','决定')}</th>${state.step===4?`<th>${label('Review','审核')}</th>`:''}`}</tr></thead><tbody>${rows.map(row=>renderRow(row,dataMode)).join('') || `<tr><td colspan="7"><p class="empty">${label('No entries match this filter. Clear the search or choose all entries.','没有符合筛选条件的记录。请清除搜索或选择所有记录。')}</p></td></tr>`}</tbody></table></div><div class="table-footer">${n(rows.length,0)} ${label('shown of','条显示／共')} ${n(currentRows().length,0)} · ${label('Missing values stay unknown. Prices use source units.','缺失值保留为未知；价格使用原始单位。')}</div></div><aside class="detail-pane" aria-label="${label('Selected entry details','所选记录详情')}">${renderDetail(dataMode)}</aside></div>`;
}
function renderRow(row,dataMode) {
  const card = state.catalog.find(card=>card.series_id===row.series_id) || row;
  const selected = row.selected_candidate;
  return `<tr ${state.selected===rowId(row)?'aria-selected="true"':''}>${state.step===4&&!state.guest?`<td><input type="checkbox" data-review-id="${safe(rowId(row))}" aria-label="${safe(t('Select','选择')+' '+(row.site_id||'')+' '+row.item_id)}" ${state.selectedReviews.has(rowId(row))?'checked':''} ${!canReview()?'disabled':''}></td>`:''}<td><button class="entry-button" data-action="select-row" data-id="${safe(rowId(row))}"><strong>${safe(titleCase(row.item_id))}</strong><small>${row.site_id?`${label('Store','门店')} ${safe(row.site_id)}`:label('All sites','全部地点')}</small></button></td><td class="numeric">${n(row.reference_price ?? card.last_observed_price,3)}</td>${dataMode?`<td class="numeric">${n(card.observed_weeks,0)}</td><td class="numeric">${n(card.consecutive_week_price_changes,0)}</td>`:`<td class="numeric">${n(selected?.schedule?.[0]?.price ?? row.selected_price,3)}</td><td>${badge(row)}</td>${state.step===4?`<td>${safe(statusText(row.review?.action || 'pending',state.chinese))}</td>`:''}`}</tr>`;
}
function renderDetail(dataMode) {
  const row = currentRow();
  if (!row) return `<h2>${label('Choose an entry','选择一条记录')}</h2><p class="explanation">${label('Open a row to inspect its prices, history, assumptions and reasons.','打开一行，查看价格、历史、假设和理由。')}</p>`;
  const detail = state.detail?.row || state.detail || row;
  const chosen = detail.selected_candidate || row.selected_candidate;
  const hold = detail.hold_candidate || row.hold_candidate;
  const history = state.history?.history || [];
  const candidates = state.detail?.candidates || detail.candidates || [chosen,hold].filter((x,i,a)=>x&&a.findIndex(y=>y?.id===x.id)===i);
  return `<p class="eyebrow">${label('Selected entry','所选记录')}</p><h2>${safe(titleCase(row.item_id))} ${row.site_id?`/ ${label('Store','门店')} ${safe(row.site_id)}`:''}</h2>${!dataMode?badge(row):''}<p class="explanation">${safe(dataMode?t('Look for recorded price changes, gaps and advertising before planning.','制定方案前，请检查价格变化、缺失周和广告记录。'):rowReason(row,state.chinese))}</p>${state.detailLoading?`<p class="explanation" role="status">${label('Loading saved evidence…','正在载入保存的依据…')}</p>`:''}
  ${!dataMode?`<div class="week-strip">${period().map((week,i)=>`<div class="week-cell"><span>${label('Week','周')} ${safe(week)}</span><strong>${n(chosen?.schedule?.[i]?.price,3)}</strong></div>`).join('')}</div><dl class="dl"><dt>${label('Reference price','参考价')}</dt><dd>${n(row.reference_price,4)} · ${label('week','周')} ${safe(row.reference_week)}</dd><dt>${label('Approach','方法')}</dt><dd>${safe(statusText(row.strategy,state.chinese))}</dd><dt>${label('Stock check','库存检查')}</dt><dd>${label(chosen?.inventory_check==='not_checked'?'Not checked':titleCase(chosen?.inventory_check || 'unknown'),chosen?.inventory_check==='not_checked'?'未检查':titleCase(chosen?.inventory_check || '未知'))}</dd><dt>${label('Scenario contribution','情景贡献额')}</dt><dd>${n(chosen?.objective_value,2)}</dd><dt>${label('Reference scenario','参考价格情景')}</dt><dd>${n(hold?.objective_value,2)}</dd></dl><p class="form-note">${label('Future plan scenario · source-scale units. These are conditional estimates, not later observations.','未来计划情景 · 原始尺度单位。这些是条件估计，不是后续实际观测。')}</p>`:''}
  <p class="detail-label">${label('Recorded sales history','已记录的销量历史')}</p>${history.length?lineChart(history,'units',{label:t('Selected entry recorded sales; missing observations are gaps.','所选记录的销量历史；缺失观测保留为空缺。'),chinese:state.chinese,compact:true}):`<p class="explanation">${label(state.guest?'Entry-level history is not part of this public extract. Step 2 shows the allowed catalog aggregate.':'No entry-level history has been loaded.','此公开摘要未提供逐条历史。第 2 步显示允许公开的目录汇总。')}</p>`}
  ${history.length?`<p class="detail-label">${label('Observed price by week','每周记录价格')}</p>${lineChart(history,'price',{label:t('Observed prices by source week','按原始周编号展示记录价格'),chinese:state.chinese,compact:true})}<details class="details"><summary>${label('Inspect recorded weeks and gaps','查看记录周和缺失周')}</summary><div class="table-scroll"><table class="candidate-table"><thead><tr><th>${label('Week','周')}</th><th>${label('Sales','销量')}</th><th>${label('Price','价格')}</th><th>${label('Ad','广告')}</th></tr></thead><tbody>${history.map(r=>`<tr><td>${safe(r.week_index)}</td><td>${n(r.units,0)}</td><td>${n(r.price,3)}</td><td>${r.feature_ad===null||r.feature_ad===undefined?'?':safe(r.feature_ad)}</td></tr>`).join('')}</tbody></table></div></details>`:''}
  ${!dataMode&&candidates.length?`<details class="details"><summary>${label('Compare tested prices','比较测试候选价')} (${candidates.length})</summary><p>${label('Only returned candidates are shown. A rule-breaking price cannot be selected.','仅显示服务器返回的候选价。违反规则的价格不能选入方案。')}</p><table class="candidate-table"><thead><tr><th>${label('Price','价格')}</th><th>${label('Contribution','贡献额')}</th><th>${label('Allowed','可用')}</th></tr></thead><tbody>${candidates.map(c=>`<tr class="${c.id===chosen?.id?'selected':''}"><td>${n(c.schedule?.[0]?.price,4)}${c.kind==='hold'?` ${label('(hold)','（保持）')}`:''}</td><td>${n(c.objective_value,1)}</td><td>${label(c.hard_feasible?'Yes':'No',c.hard_feasible?'是':'否')}${c.hard_reasons?.length?`<br>${safe(c.hard_reasons.map(x=>reasonText(x,state.chinese)).join(', '))}`:''}</td></tr>`).join('')}</tbody></table></details>`:''}
  ${!dataMode&&chosen?.forecast?.length?`<details class="details"><summary>${label('Future scenario and seasonal comparison','未来情景与季节参考')}</summary><p>${label('Predictions use the entered prices and advertising. Recent sales and the same source week 52 weeks earlier are comparison estimates when supported.','预测使用设定的价格和广告状态。在有支持记录时，近期销量及 52 周前同一原始周的销量作为参考估计。')}</p><table class="candidate-table"><thead><tr><th>${label('Week','周')}</th><th>${label('Scenario','情景')}</th><th>${label('Recent','近期')}</th><th>${label('52 weeks','52 周前')}</th></tr></thead><tbody>${chosen.forecast.map(f=>`<tr><td>${safe(f.week_index)}</td><td>${n(f.prediction,0)}</td><td>${n(f.recent_mean_control,0)}</td><td>${f.seasonal52_supported?n(f.seasonal52_control,0):'—'}</td></tr>`).join('')}</tbody></table></details>`:''}
  ${!dataMode&&!state.guest&&state.plan&&cap('edit')&&row.row_etag?`<details class="details"><summary>${label('Record a manual decision','记录人工决定')}</summary><form id="manual-form"><label><span class="field-label">${label('Price for all four weeks','四周统一价格')}</span><input id="manual-price" type="number" min="0.000001" step="any" required></label><label><span class="field-label">${label('Reason for this decision','决定理由')}</span><textarea id="manual-reason" rows="3" maxlength="500" required></textarea></label><div class="actions space-top"><button class="btn" type="submit">${label('Save as new revision','保存为新版本')}</button>${btn('exclude-row','Exclude with this reason','按此理由排除')}</div><p class="form-note">${label('A manual price keeps the saved advertising conditions and must pass the server rules. All previous approvals are cleared.','人工价格保留已保存的广告条件，并须通过服务器规则。所有之前的批准都会清除。')}</p></form></details>`:''}${jsonDetails('Decision evidence','决定依据',{reason_codes:row.reason_codes,qualification_reasons:row.qualification_reasons,reference_week:row.reference_week,weekly_bounds:row.weekly_bounds,review:row.review})}`;
}
function canReview() {
  const editors = state.plan?.editor_uids || state.plan?.editor_ids || [];
  return cap('review') && state.plan?.state === 'submitted' && state.plan?.author_id !== state.me?.actor_id && !editors.includes(state.me?.actor_id);
}
function renderReviewBar(rows) {
  return `${state.reviewProgress ? `<div class="review-progress" role="status">${state.reviewProgress.saved} / ${state.reviewProgress.total} ${label('selected entries saved. Each group is saved separately; an interrupted review keeps completed groups.','条所选记录已保存。各组分别保存；审核中断时，已完成的组会保留。')}<progress value="${state.reviewProgress.saved}" max="${state.reviewProgress.total}"></progress></div>` : ''}<div class="review-bar"><strong>${state.selectedReviews.size} ${label('selected','条已选')}</strong>${btn('select-filtered','Select shown entries','选择当前显示的记录',{disabled:!canReview()})}${btn('clear-selection','Clear','清除',{disabled:!state.selectedReviews.size})}<input id="review-reason" maxlength="500" aria-label="${label('Review reason, required for rejection or exclusion','审核理由，拒绝或排除时必填')}" placeholder="${label('Reason (required to reject or exclude)','理由（拒绝或排除时必填）')}">${btn('approve','Approve selected','批准所选',{primary:true,disabled:!canReview()||!state.selectedReviews.size})}${btn('reject','Reject selected','拒绝所选',{disabled:!canReview()||!state.selectedReviews.size})}${btn('review-exclude','Exclude selected','排除所选',{disabled:!canReview()||!state.selectedReviews.size})}${btn('request-revision','Request a revision','要求修改',{disabled:!canReview()||!state.selectedReviews.size})}</div>`;
}
function renderReview() {
  return heading(4,'Review the whole price plan','审核整个价格方案','A different authorized person checks each proposed change and feasible hold. Every entry needs an outcome.','由另一位具有权限的人检查每项调价和符合规则的保持项。每条记录都需要处理结果。',btn('publish-step','Continue to publication','继续到发布',{primary:true,disabled:!state.plan})) +
  (state.guest ? `<div class="notice neutral"><strong>${label('This is a saved price comparison, not a completed human review.','这是保存的价格比较，不是已完成的人工审核。')}</strong><p>${label('In a private workspace, the author sends a version to a different reviewer. A guest cannot approve or publish it.','在私密工作区中，作者将指定版本提交给另一位审核人。访客不能批准或发布。')}</p></div>` : `<div class="notice neutral"><strong>${label('Every entry must be approved, rejected or excluded.','每条记录都必须获批、被拒绝或排除。')}</strong><p>${label('Approved feasible holds are included in the pricebook. Rejections and exclusions need a reason. Editing any executable part of the plan clears all approvals.','获批且符合规则的保持项会进入价格表。拒绝和排除需要理由。修改方案中任何执行内容都会清除所有批准。')}</p>${!canReview()?`<p>${label('Your current account cannot review this version. The server checks permission and separation from its author and editors.','当前账号不能审核此版本。服务器会校验权限，以及审核人与作者、编辑者的身份分离。')}</p>`:''}</div>`) +
  (state.plan ? `<div class="facts">${fact(n(state.rows.length,0),'Total entries','全部记录')}${fact(n(state.rows.filter(r=>['approve_change','approve_hold'].includes(r.review?.action)).length,0),'Approved','已批准')}${fact(n(state.rows.filter(r=>['reject','exclude'].includes(r.review?.action)).length,0),'Rejected or excluded','已拒绝或排除')}${fact(n(pendingCount(),0),'Awaiting an outcome','等待处理结果')}</div>${renderCatalog(false)}${state.events.length?`<section class="panel space-top"><div class="panel-body"><h2>${label('Saved review history','已保存的审核历史')}</h2><ul class="event-list space-top">${state.events.slice(-15).map(e=>`<li><strong>${safe(statusText(e.action || e.kind || e.type,state.chinese))}</strong><small>${safe(e.actor_id || e.actor_uid || e.actor)} · ${safe(e.at || e.created_at || e.timestamp)} · ${label('revision','版本')} ${safe(e.revision)}</small>${e.reason?`<p>${safe(e.reason)}</p>`:''}</li>`).join('')}</ul></div></section>`:''}` : `<p class="empty">${label('Create and compare a plan before sending it for review.','先创建并比较方案，再提交审核。')}</p>`);
}
function renderPublish() {
  const book = state.pricebook;
  return heading(5,'Record the approved pricebook','保存已批准的价格表','Save the approved four-week version in this private workspace, with a complete record of every entry.','在私密工作区保存获批的四周版本，并完整记录每条目录记录的处理结果。')+
  `<div class="two-columns"><section class="panel"><div class="panel-body"><p class="eyebrow">${label('Destination','目标位置')}</p><h2 class="space-top">${label('Private Demo ledger','私密演示价格台账')}</h2><p class="explanation">${label('Publication saves an immutable version for download. Store prices and ERP systems are not updated. Your records remain private.','发布会保存不可变版本，供下载使用。不会更新门店价格或 ERP 系统，记录仍保持私密。')}</p><div class="week-strip">${period().map(week=>`<div class="week-cell"><span>${label('Source week','原始周')}</span><strong>${safe(week)}</strong></div>`).join('')}</div>${book?`<div class="notice neutral"><strong>${label('Published to Demo ledger','已发布到演示价格台账')}</strong><p>${label('Version','版本')}: ${safe(book.id)}<br>${label('Published by','发布人')}: <span class="mono">${safe(book.publisher_id || book.published_by || book.actor_id || book.actor_uid || book.created_by)}</span><br>${safe(book.published_at || book.at || book.created_at)}</p></div><div class="actions">${btn('download-pricebook','Download pricebook','下载价格表',{primary:true})}${btn('download-coverage','Download coverage report','下载全目录报告')}</div>`:state.guest?`<div class="notice"><p>${label('This public example has not been published. Sign in with an invited account to create a private plan and complete independent review.','此公开示例尚未发布。受邀账号登录后，可以创建私密方案并完成独立审核。')}</p></div>`:`<p class="explanation">${pendingCount()} ${label('entries still need an outcome. Any unresolved conflict blocks publication.','条记录仍需处理。任何未解决的冲突都会阻止发布。')}</p><div class="actions space-top">${btn('publish','Publish to Demo ledger','发布到演示价格台账',{primary:true,disabled:!cap('publish')||!state.plan||state.plan.state!=='submitted'||pendingCount()>0||state.dirty})}${btn('review','Return to review','返回审核')}</div>`}<p class="form-note">${label('The pricebook includes approved changes and allowed holds. The coverage report also retains rejected and excluded entries with their reasons.','价格表包含获批的调价和允许的保持项。全目录报告还保留拒绝及排除项和对应理由。')}</p></div></section><section class="panel"><div class="panel-body"><h2>${label('What happens after publication?','发布后会发生什么？')}</h2><p class="explanation">${label('No later sales records are loaded for the example. The future scenario has not become an observed result. Revisit performance only when later records are available.','示例没有载入后续销量记录。未来情景尚未成为实际观测结果。只有获得后续记录后，才能检查实际表现。')}</p><div class="notice neutral space-top">${label('No later sales records loaded.','尚未载入后续销售记录。')}</div>${!state.guest&&state.pricebooks.length?`<h3 class="space-top">${label('Saved pricebooks','已保存的价格表')}</h3><div class="choice-list">${state.pricebooks.map(p=>`<div class="choice"><div><strong>${label('Revision','版本')} ${safe(p.revision)}</strong><p>${safe(p.id)}</p></div>${btn('open-pricebook','Open','打开',{extra:`data-id="${safe(p.id)}"`})}</div>`).join('')}</div>`:''}${jsonDetails('Publication evidence','发布依据',book)}</div></section></div>`;
}
function identityContext() {
  const generation=identityGeneration, client=api.scoped();
  return {api:client,check:()=>{if(generation!==identityGeneration)throw new OperationCancelled();}};
}
function invalidateIdentity({purge=false,clearPending=false}={}) {
  identityGeneration++; modelSelectionGeneration++; detailSequence++; clearTimeout(pollTimer);
  api?.invalidate({clearPending}); state.busy='';
  if (purge) {
    Object.assign(state,{me:null,workspace:null,snapshots:[],plans:[],pricebooks:[],snapshot:null,model:null,models:[],modelSelections:{},plan:null,
      rows:[],catalog:[],selected:null,detail:null,history:null,events:[],query:'',filter:'all',selectedReviews:new Set(),
      error:null,message:'',drafts:{},dirty:false,run:null,trainingRecoveryUnavailable:false,reviewProgress:null,pricebook:null,guest:true,detailLoading:false,
      teachingAccepted:false,resetForms:true,step:2});
    announce('');
  }
}
async function perform(message, operation) {
  if (state.busy) return;
  const context=identityContext();
  preserveForms(); state.busy = message; state.error = null; state.message = ''; render();
  try { await operation(context); context.check(); }
  catch (error) {
    if(error instanceof OperationCancelled)return;
    try {context.check();} catch{return;}
    state.error = error instanceof ApiError ? error : new ApiError(0,{error:{code:'REQUEST_FAILED'}});
    announce(errorCopy(state.error,state.chinese));
  } finally {
    try {context.check();state.busy = '';render();} catch{/* An old task must not repaint the current identity. */}
  }
}
function setPlan(data,etag) {
  state.plan = {...data,etag:etag || data.etag};
  state.pricebook = data.pricebook || null;
}
function showCachedExample() {
  state.guest=true;
  if(!state.sample)return;
  state.snapshot=state.sample.snapshot;state.model=state.sample.model;state.models=[];state.plan=state.sample.plan || null;
  state.catalog=state.sample.snapshot?.analysis?.series || [];state.rows=state.sample.rows || [];
  state.selected=null;state.detail=null;state.history=null;state.events=[];state.pricebook=null;
  state.dirty=false;state.drafts={};state.resetForms=true;state.query='';state.filter='all';
  state.selectedReviews.clear();state.step=2;clearTimeout(pollTimer);
}
async function loadExample(context=identityContext()) {
  context.check();
  if (!state.sample) {
    const {data:list}=await context.api.request('/api/v1/samples',{publicAccess:true});context.check();
    if (!list.items?.length) throw new ApiError(503,{error:{code:'EXAMPLE_UNAVAILABLE'}});
    const {data}=await context.api.request(`/api/v1/samples/${encodeURIComponent(list.items[0].id)}`,{publicAccess:true});context.check();
    state.sample=data;
  }
  context.check();showCachedExample();
}
async function loadWorkspace(context=identityContext()) {
  context.check();
  if (!state.me) throw new ApiError(401,{error:{code:'SIGN_IN_REQUIRED'}});
  const memberships=(state.me.memberships || []).filter(member=>member.capabilities?.includes('read'));
  if(!memberships.length)throw new ApiError(403,{error:{code:'WORKSPACE_INVITATION_REQUIRED'}});
  state.workspace ||= memberships[0];state.guest=false;state.query='';state.filter='all';
  const base=prefix();
  const [snapshots,plans,pricebooks]=await Promise.all([context.api.all(`${base}/snapshots`),context.api.all(`${base}/plans`),context.api.all(`${base}/pricebooks`)]);
  context.check();
  Object.assign(state,{snapshots,plans,pricebooks,snapshot:null,model:null,plan:null,rows:[],catalog:[],selected:null,detail:null,history:null,drafts:{},resetForms:true,dirty:false,pricebook:null});
  state.selectedReviews.clear();
  if(plans.length){await loadPlan(plans[0].id,{},context);context.check();state.step=plans[0].state==='submitted'?4:3;}
  else if(snapshots.length){await loadSnapshot(snapshots[0].id,context);context.check();state.step=2;}
  else state.step=1;
}
async function savedModels(snapshot,context,{boundId,preferredId}={}) {
  context.check();const base=prefix();
  const registered=await context.api.all(`${base}/models`);context.check();
  const models=snapshotModels(registered,snapshot.id);
  const id=chooseModelId(models,{boundId,preferredId,referenceId:snapshot.model_id});
  if(id===undefined)throw new ApiError(409,{error:{code:'MODEL_SNAPSHOT_MISMATCH'}});
  const model=id?(await context.api.request(`${base}/models/${encodeURIComponent(id)}`)).data:null;context.check();
  if(model&&((model.snapshot_id&&model.snapshot_id!==snapshot.id)||(model.origin!==undefined&&model.origin!==snapshot.cutoff)))throw new ApiError(409,{error:{code:'MODEL_SNAPSHOT_MISMATCH'}});
  return {models,model};
}
async function savedTrainingRun(snapshotId,context) {
  try {
    const runs=await context.api.all(`${prefix()}/training-runs`);context.check();
    return {run:recoverTrainingRun(runs,snapshotId),unavailable:false};
  }catch(error){
    if(error instanceof ApiError&&error.status===503&&error.code==='training_unavailable')return {run:null,unavailable:true};
    throw error;
  }
}
function restoreRun(recovered,context) {
  state.run=recovered.run;state.trainingRecoveryUnavailable=recovered.unavailable;
  if(state.run&&!['succeeded','failed','cancelled','timed_out'].includes(state.run.state))scheduleRunPoll(context);
}
function scheduleRunPoll(context) {
  const generation=modelSelectionGeneration;clearTimeout(pollTimer);
  pollTimer=setTimeout(()=>refreshRun(context,generation),1500);
}
async function loadSnapshot(id,context=identityContext(),{boundId}={}) {
  context.check();modelSelectionGeneration++;clearTimeout(pollTimer);state.run=null;const base=prefix();
  const {data}=await context.api.request(`${base}/snapshots/${encodeURIComponent(id)}`);context.check();
  const [catalog,saved,recovered]=await Promise.all([
    context.api.all(`${base}/snapshots/${encodeURIComponent(id)}/catalog`),
    savedModels(data,context,{boundId,preferredId:state.modelSelections[id]}),
    savedTrainingRun(id,context),
  ]);context.check();
  Object.assign(state,{query:'',filter:'all',snapshot:data,catalog,model:saved.model,models:saved.models,plan:null,rows:[],selected:null,detail:null,history:null,pricebook:null,dirty:false,drafts:{},resetForms:true});
  state.modelSelections[id]=saved.model?.id||null;state.selectedReviews.clear();restoreRun(recovered,context);
}
async function loadPlan(id,{preserveDraft=false}={},context=identityContext()) {
  context.check();modelSelectionGeneration++;clearTimeout(pollTimer);state.run=null;const base=prefix();
  const {data,etag}=await context.api.request(`${base}/plans/${encodeURIComponent(id)}`);context.check();
  let saved,recovered;
  if(data.snapshot_id&&state.snapshot?.id!==data.snapshot_id){await loadSnapshot(data.snapshot_id,context,{boundId:data.model_id||null});context.check();saved={models:state.models,model:state.model};recovered={run:state.run,unavailable:state.trainingRecoveryUnavailable};}
  const [rows,registry,events,book,training]=await Promise.all([
    (data.comparison_ref||data.proposal_hash)?context.api.all(`${base}/plans/${encodeURIComponent(id)}/rows`):[],
    saved||savedModels(state.snapshot,context,{boundId:data.model_id||null}),
    context.api.all(`${base}/plans/${encodeURIComponent(id)}/events`).catch(error=>{if(error instanceof OperationCancelled)throw error;return [];}),
    data.pricebook_id?context.api.request(`${base}/pricebooks/${encodeURIComponent(data.pricebook_id)}`).then(result=>result.data):null,
    recovered||savedTrainingRun(state.snapshot.id,context),
  ]);context.check();
  setPlan(data,etag);state.rows=rows;state.model=registry.model;state.models=registry.models;state.events=events;state.pricebook=book;
  state.modelSelections[state.snapshot.id]=registry.model?.id||null;restoreRun(training,context);
  if(!preserveDraft){state.dirty=false;state.drafts={};state.resetForms=true;}
  if(!rows.some(row=>rowId(row)===state.selected)){state.selected=null;state.detail=null;state.history=null;}
}
async function loadRow(id) {
  const context=identityContext(),sequence=++detailSequence;
  preserveForms();delete state.drafts['manual-price'];delete state.drafts['manual-reason'];state.resetForms=true;
  state.selected=id;state.detail=null;state.history=null;state.detailLoading=true;render();
  try {
    if(state.guest){const row=currentRow();state.detail=row;state.history=state.sample.histories?.[id]||state.sample.histories?.[row?.series_id]||null;}
    else {
      const row=currentRow(),catalogRow=state.catalog.find(card=>card.series_id===row?.series_id),base=prefix();
      const historyId=catalogRow?.row_id||id;
      const tasks=[context.api.all(`${base}/snapshots/${encodeURIComponent(state.snapshot.id)}/series/${encodeURIComponent(historyId)}`)];
      if(state.plan?.comparison_ref||state.plan?.proposal_hash)tasks.push(context.api.request(`${base}/plans/${encodeURIComponent(state.plan.id)}/rows/${encodeURIComponent(id)}`));
      const result=await Promise.all(tasks);context.check();if(sequence!==detailSequence)return;
      state.history={history:result[0]};state.detail=result[1]?.data||row;
    }
  } catch(error){if(!(error instanceof OperationCancelled)&&sequence===detailSequence)state.error=error;}
  finally{if(sequence===detailSequence){state.detailLoading=false;render();}}
}
function readRules() {
  const read=(id,fallback)=>document.getElementById(id)?.value??state.drafts[id]??fallback;
  return {price_tick:String(read('rule-tick','0.01')),maximum_decrease_bps:String(Number(read('rule-down','5'))*100),maximum_increase_bps:String(Number(read('rule-up','5'))*100),minimum_margin:String(Number(read('rule-margin','20'))/100),maximum_reference_age_weeks:Number(read('rule-age','4')),max_changed_series:Number(read('rule-cap','20')),inventory_required:false};
}
async function createPlan(assumptionMode='none',rules=readRules(),context=identityContext()) {
  context.check();const base=prefix();
  const {data}=await context.api.request(`${base}/plans`,{method:'POST',body:{snapshot_id:state.snapshot.id,model_id:state.model?.id||null,period:state.snapshot.period,assumption_mode:assumptionMode,rules}});context.check();
  await loadPlan(data.id,{},context);context.check();state.step=3;
  state.message=t('Private draft saved. Compare prices to calculate every entry under these rules.','私密草稿已保存。点击比较价格，按这些规则计算每条记录。');
}
async function saveRevision(changes=[],extra={},context=identityContext()) {
  context.check();const oldPlan=state.plan,base=prefix();
  await context.api.request(`${base}/plans/${encodeURIComponent(oldPlan.id)}/revisions`,{method:'POST',etag:oldPlan.etag,body:{base_revision:oldPlan.revision,changes,...extra}});context.check();
  await loadPlan(oldPlan.id,{},context);context.check();state.selectedReviews.clear();
  state.message=t('New revision saved. Earlier approvals are cleared. Compare prices and send this version for review.','新版本已保存，之前的批准已清除。请比较价格，再将此版本提交审核。');
}
async function planAction(action,body,context=identityContext()) {
  context.check();const plan=state.plan;
  const result=await context.api.request(`${prefix()}/plans/${encodeURIComponent(plan.id)}/${action}`,{method:'POST',etag:plan.etag,body});context.check();return result;
}
async function reviewSelected(action) {
  const reason=(document.querySelector('#review-reason')?.value||state.drafts['review-reason']||'').trim();
  if(['reject','exclude','request_revision'].includes(action)&&!reason){document.querySelector('#review-reason')?.setCustomValidity(t('Enter a reason.','请填写理由。'));document.querySelector('#review-reason')?.reportValidity();return;}
  const selected=state.rows.filter(row=>state.selectedReviews.has(rowId(row)));if(!selected.length)return;
  const batches=splitBatches(selected);
  await perform(t('Saving catalog review…','正在保存目录审核…'),async context=>{
    state.reviewProgress={total:selected.length,saved:0};
    for(const batch of batches){
      context.check();const plan=state.plan;
      const body={revision:plan.revision,proposal_hash:plan.proposal_hash,review_generation:plan.review_generation,rows:batch.map(row=>({row_id:rowId(row),row_etag:row.row_etag,action:action==='approve'?(decision(row)==='hold'?'approve_hold':'approve_change'):action,...(reason?{reason}:{})}))};
      const {data,etag}=await planAction('reviews',body,context);context.check();
      if(data.plan)setPlan(data.plan,etag);else if(data.id)setPlan(data,etag);else state.plan={...state.plan,...data,etag:etag||data.etag};
      state.reviewProgress.saved+=batch.length;batch.forEach(row=>state.selectedReviews.delete(rowId(row)));
      await loadPlan(plan.id,{preserveDraft:true},context);context.check();render();
      announce(`${state.reviewProgress.saved} / ${state.reviewProgress.total} ${t('review decisions saved','条审核决定已保存')}`);
    }
    context.check();state.message=t('Review saved for this version. Every completed group is now stored on the server.','此版本的审核已保存，每个完成的组都已存储在服务器。');
  });
}
async function refreshRun(context=identityContext(),expectedSelection=modelSelectionGeneration) {
  let current=()=>false;
  try {
    context.check();if(expectedSelection!==modelSelectionGeneration||!state.run||state.guest||!session.idToken)return;
    const base=prefix(),runId=state.run.id,snapshotId=state.snapshot?.id,selectionGeneration=expectedSelection,planId=state.plan?.id||null,boundModelId=state.plan?.model_id||null,planRevision=state.plan?.revision??null;
    current=()=>{context.check();return state.run?.id===runId&&state.snapshot?.id===snapshotId&&modelSelectionGeneration===selectionGeneration&&(state.plan?.id||null)===planId&&(state.plan?.model_id||null)===boundModelId&&(state.plan?.revision??null)===planRevision;};
    const {data}=await context.api.request(`${base}/training-runs/${encodeURIComponent(runId)}`);if(!current()||(data.snapshot_id&&data.snapshot_id!==snapshotId))return;
    const runContext={...context,check:()=>{if(!current())throw new OperationCancelled();}};
    const saved=data.model_id?await savedModels(state.snapshot,runContext,state.plan?{boundId:state.plan.model_id||null}:{preferredId:data.model_id}):null;if(!current())return;
    state.run=data;if(saved){state.model=saved.model;state.models=saved.models;state.modelSelections[state.snapshot.id]=saved.model?.id||null;}if(state.step===2&&!state.busy)render();
    if(!['succeeded','failed','cancelled','timed_out'].includes(data.state))pollTimer=setTimeout(()=>refreshRun(context,selectionGeneration),5000);
  }catch(error){if(error instanceof OperationCancelled)return;try{if(!current())return;}catch{return;}state.error=error;if(!state.busy)render();}
}
async function downloadPricebook(kind,context=identityContext()) {
  context.check();const book=state.pricebook;
  const {data}=await context.api.request(`${prefix()}/pricebooks/${encodeURIComponent(book.id)}/${kind}.csv`,{download:true});context.check();saveDownload(data,`${kind}-${book.id}.csv`);
}
function saveDownload(blob,name) {
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function showSignIn() {
  dialog.innerHTML=`<h2 id="sign-in-title">${label('Sign in to your pricing workspace','登录定价工作区')}</h2><p>${label('Use your invited account. Your workspace and published pricebooks remain private.','请使用受邀账号。工作区和发布的价格表保持私密。')}</p><form id="sign-in-form"><label><span class="field-label">${label('Email','邮箱')}</span><input id="login-email" type="email" name="email" autocomplete="username" required></label><label><span class="field-label">${label('Password','密码')}</span><input id="login-password" type="password" name="password" autocomplete="current-password" required></label><div id="login-error" role="alert"></div><div class="actions"><button class="btn primary" type="submit">${label('Sign in','登录')}</button><button class="btn" type="button" data-close-dialog>${label('Cancel','取消')}</button></div></form><p class="form-note space-top">${label('No public signup or role selection. Access comes from your workspace invitation.','不提供公开注册或角色选择；权限来自工作区邀请。')}</p>`;
  const cancel=()=>{invalidateIdentity();session.generation++;session.refreshing=null;dialog.close();render();};
  dialog.querySelector('[data-close-dialog]').addEventListener('click',cancel);
  dialog.oncancel=event=>{event.preventDefault();cancel();};
  dialog.querySelector('form').addEventListener('submit',async event=>{
    event.preventDefault();const form=event.currentTarget,button=form.querySelector('[type=submit]');button.disabled=true;
    const email=form.elements.email.value,password=form.elements.password.value;
    const previousUid=state.me?.uid||session.uid,previousWorkspace=state.workspace?.workspace_id;
    form.elements.password.value='';preserveForms();
    // Stop every earlier logical operation before replacing authentication.
    // Same-actor reauthentication retains draft fields and interrupted request keys.
    invalidateIdentity();let context=identityContext();
    try {
      await session.signIn(email,password);context.check();
      const actorChanged=previousUid!==session.uid;
      if(actorChanged){invalidateIdentity({purge:true,clearPending:true});context=identityContext();showCachedExample();render();}
      const {data:me}=await context.api.request('/api/v1/me');context.check();
      state.me=me;state.workspace=(me.memberships||[]).find(m=>m.workspace_id===previousWorkspace)||me.memberships?.[0]||null;
      dialog.close();
      await perform(t('Opening your private workspace…','正在打开私密工作区…'),async current=>{
        if(!actorChanged&&state.plan&&!state.guest&&state.workspace?.workspace_id===previousWorkspace){
          await loadPlan(state.plan.id,{preserveDraft:true},current);current.check();
          state.message=t('Signed in. Current permissions and the saved revision have been reloaded. Check unsaved edits before retrying.','已登录，并载入当前权限和保存版本。重试前请检查未保存的修改。');
        }else await loadWorkspace(current);
      });
    }catch(error){
      if(error instanceof OperationCancelled)return;
      try{context.check();}catch{return;}
      if(form.isConnected)form.querySelector('#login-error').innerHTML=`<div class="notice error">${safe(errorCopy(error,state.chinese))}</div>`;
    }finally{if(form.isConnected)button.disabled=false;}
  });
  dialog.showModal();dialog.querySelector('input').focus();
}
const actions={
  language:async()=>{state.chinese=!state.chinese;try{localStorage.setItem('pricing-language',state.chinese?'zh':'en');}catch{}render();},
  login:async()=>showSignIn(),
  logout:async()=>{
    invalidateIdentity({purge:true,clearPending:true});session.clear();dialog.close();dialog.innerHTML='';
    showCachedExample();render();
    if(!state.sample)await perform(t('Opening the saved example…','正在打开保存的示例…'),context=>loadExample(context));
  },
  example:async()=>perform(t('Loading saved example…','正在载入保存的示例…'),context=>loadExample(context)),
  workspace:async()=>perform(t('Loading private workspace…','正在载入私密工作区…'),context=>loadWorkspace(context)),
  import:async()=>{state.step=1;render();},check:async()=>{state.step=2;state.filter='all';render();},plan:async()=>{state.step=3;render();},review:async()=>{state.step=4;render();},'publish-step':async()=>{state.step=5;render();},
  'dismiss-error':async()=>{state.error=null;render();},
  reload:async()=>perform(t('Reloading current saved version…','正在载入当前保存版本…'),async context=>{
    if(state.guest){state.sample=null;await loadExample(context);}
    else{
      const workspaceId=state.workspace.workspace_id;
      const {data}=await context.api.request('/api/v1/me');context.check();
      state.me=data;state.workspace=data.memberships.find(m=>m.workspace_id===workspaceId);
      if(state.plan)await loadPlan(state.plan.id,{preserveDraft:true},context);else if(state.snapshot)await loadSnapshot(state.snapshot.id,context);else await loadWorkspace(context);
    }
  }),
  'open-snapshot':async element=>perform(t('Loading snapshot…','正在载入快照…'),async context=>{await loadSnapshot(element.dataset.id,context);context.check();state.step=2;}),
  'open-plan':async element=>perform(t('Loading saved plan…','正在载入保存的方案…'),async context=>{await loadPlan(element.dataset.id,{},context);context.check();state.step=3;}),
  'open-pricebook':async element=>perform(t('Loading saved pricebook…','正在载入价格表…'),async context=>{const {data}=await context.api.request(`${prefix()}/pricebooks/${encodeURIComponent(element.dataset.id)}`);context.check();state.pricebook=data;state.step=5;}),
  'select-row':async element=>loadRow(element.dataset.id),
  'new-model-draft':async()=>perform(t('Opening the snapshot for a new draft…','正在打开快照以创建新草稿…'),async context=>{await loadSnapshot(state.snapshot.id,context);context.check();state.step=2;}),
  assumptions:async()=>perform(t('Saving example business assumptions…','正在保存示例经营假设…'),async context=>{
    const rules={price_tick:'0.01',maximum_decrease_bps:'500',maximum_increase_bps:'500',minimum_margin:'0.20',max_changed_series:20,maximum_reference_age_weeks:4,inventory_required:false};
    if(state.plan)await saveRevision([],{assumption_mode:'teaching_60pct_v1',rules},context);else await createPlan('teaching_60pct_v1',rules,context);
  }),
  'clear-assumptions':async()=>perform(t('Removing example assumptions in a new revision…','正在创建移除示例假设的新版本…'),context=>saveRevision([],{assumption_mode:'none'},context)),
  compare:async()=>perform(t('Comparing the whole catalog. Waiting for actual server results…','正在比较完整目录，等待服务器实际结果…'),async context=>{
    const id=state.plan.id;await planAction('compare',{revision:state.plan.revision},context);context.check();await loadPlan(id,{},context);context.check();state.message=t('Comparison saved. Inspect changes, holds and any unresolved entries before review.','比较结果已保存。提交审核前，请检查调价、保持和未解决项。');
  }),
  submit:async()=>perform(t('Sending this version for independent review…','正在提交此版本供独立审核…'),async context=>{
    const id=state.plan.id;await planAction('submit',{revision:state.plan.revision,proposal_hash:state.plan.proposal_hash},context);context.check();await loadPlan(id,{},context);context.check();state.step=4;state.message=t('This version is submitted. A different authorized reviewer must check it.','此版本已提交，须由另一位具有权限的审核人检查。');
  }),
  'select-filtered':async()=>{visibleRows(state.rows,state.query,state.filter).forEach(row=>state.selectedReviews.add(rowId(row)));render();announce(`${state.selectedReviews.size} ${t('entries selected','条记录已选')}`);},
  'clear-selection':async()=>{state.selectedReviews.clear();render();},
  approve:async()=>reviewSelected('approve'),reject:async()=>reviewSelected('reject'),'review-exclude':async()=>reviewSelected('exclude'),'request-revision':async()=>reviewSelected('request_revision'),
  publish:async()=>perform(t('Recording the approved version in the private Demo ledger…','正在将获批版本写入私密演示台账…'),async context=>{
    const {data}=await planAction('publish',{revision:state.plan.revision,proposal_hash:state.plan.proposal_hash,review_generation:state.plan.review_generation,destination:'demo_ledger'},context);context.check();
    const pricebooks=await context.api.all(`${prefix()}/pricebooks`);context.check();state.pricebook=data.pricebook||data;state.pricebooks=pricebooks;state.message=t('Published to Demo ledger. The saved version remains private.','已发布到演示价格台账。保存版本仍保持私密。');
  }),
  'download-pricebook':async()=>perform(t('Preparing authorized download…','正在准备授权下载…'),context=>downloadPricebook('pricebook',context)),
  'download-coverage':async()=>perform(t('Preparing coverage report…','正在准备全目录报告…'),context=>downloadPricebook('coverage',context)),
  train:async element=>perform(t('Requesting model training…','正在请求模型训练…'),async context=>{
    const {data}=await context.api.request(`${prefix()}/training-runs`,{method:'POST',body:{snapshot_id:state.snapshot.id,pipeline_version:element.dataset.pipeline}});context.check();state.run=data;scheduleRunPoll(context);
  }),
  'reconcile-run':async()=>perform(t('Checking the recorded job state…','正在核对已记录的任务状态…'),async context=>{
    const {data}=await context.api.request(`${prefix()}/training-runs/${encodeURIComponent(state.run.id)}/reconcile`,{method:'POST',body:{}});context.check();state.run=data;await refreshRun(context);
  }),
  'cancel-run':async()=>perform(t('Requesting training cancellation…','正在请求取消训练…'),async context=>{
    const {data}=await context.api.request(`${prefix()}/training-runs/${encodeURIComponent(state.run.id)}/cancel`,{method:'POST',body:{}});context.check();state.run=data;scheduleRunPoll(context);
  }),
  'exclude-row':async()=>{
    const reason=document.querySelector('#manual-reason')?.value.trim();if(!reason){document.querySelector('#manual-reason')?.reportValidity();return;}
    const row=currentRow();await perform(t('Saving exclusion as a new revision…','正在将排除项保存为新版本…'),context=>saveRevision([{row_id:rowId(row),row_etag:row.row_etag,disposition:'exclude',reason}],{},context));
  },
  template:async()=>saveDownload(new Blob(['item_id,site_id,week_index,known_at_index,price,units,currency,unit,price_basis,source_id,feature_ad,returns_units\n'],{type:'text/csv;charset=utf-8'}),'weekly-pricing-template.csv'),
};
app.addEventListener('click',async event=>{
  const step=event.target.closest('[data-step]');
  if(step&&!state.busy){preserveForms();state.step=Number(step.dataset.step);if(state.step===2)state.filter='all';render();document.querySelector('#main').focus();return;}
  const element=event.target.closest('[data-action]');if(!element||element.disabled)return;
  const action=actions[element.dataset.action],generation=identityGeneration;if(action)try{await action(element);}catch(error){if(error instanceof OperationCancelled||generation!==identityGeneration)return;state.error=error;render();}
});
app.addEventListener('input',event=>{
  const input=event.target;
  if(input.id==='catalog-query'){
    state.query=input.value;const start=input.selectionStart;render();const next=document.querySelector('#catalog-query');next.focus();next.setSelectionRange(start,start);return;
  }
  if(input.id==='review-reason')input.setCustomValidity('');
  if(input.id.startsWith('rule-') || input.id.startsWith('manual-')) {state.dirty=true;app.querySelectorAll('[data-action=compare],[data-action=submit],[data-action=publish]').forEach(button=>button.disabled=true);announce(t('Unsaved changes. Save a new revision before comparing or submitting.','修改未保存。比较或提交前，请先保存新版本。'));}
});
app.addEventListener('change',event=>{
  if(event.target.id==='model-picker'){modelSelectionGeneration++;clearTimeout(pollTimer);const id=event.target.value;void perform(t('Loading saved model evidence…','正在载入已保存的模型依据…'),async context=>{const saved=await savedModels(state.snapshot,context,{boundId:id||null});context.check();state.model=saved.model;state.models=saved.models;state.modelSelections[state.snapshot.id]=id||null;});return;}
  if(event.target.id==='catalog-filter'){state.filter=event.target.value;render();document.querySelector('#catalog-filter')?.focus();}
  if(event.target.dataset.reviewId){if(event.target.checked)state.selectedReviews.add(event.target.dataset.reviewId);else state.selectedReviews.delete(event.target.dataset.reviewId);render();}
});
app.addEventListener('submit',async event=>{
  event.preventDefault();const form=event.target;if(!form.reportValidity())return;
  if(form.id==='upload-form'){
    const file=document.querySelector('#csv-file').files[0], cutoff=Number(document.querySelector('#upload-cutoff').value);
    if(!file)return;
    await perform(t('Validating and saving weekly records…','正在校验并保存每周记录…'),async context=>{
      if(file.size>10*1024*1024)throw new ApiError(413,{error:{code:'UPLOAD_TOO_LARGE'}});
      const text=await file.text();context.check();
      const {data:dataset}=await context.api.request(`${prefix()}/datasets`,{method:'POST',body:text,raw:true});context.check();
      const {data:snapshot}=await context.api.request(`${prefix()}/snapshots`,{method:'POST',body:{dataset_id:dataset.id,cutoff}});context.check();
      const snapshots=await context.api.all(`${prefix()}/snapshots`);context.check();state.snapshots=snapshots;await loadSnapshot(snapshot.id,context);context.check();state.step=2;
      state.message=t('Dataset saved. Check the observed and missing records before planning.','数据集已保存。制定方案前，请检查已有和缺失记录。');
    });
  } else if(form.id==='rules-form'){
    const rules=readRules();await perform(t('Saving explicit price rules…','正在保存明确的价格规则…'),async context=>{if(state.plan)await saveRevision([],{rules},context);else await createPlan('none',rules,context);});
  } else if(form.id==='manual-form'){
    const price=document.querySelector('#manual-price').value,reason=document.querySelector('#manual-reason').value.trim(),row=currentRow();
    const savedSchedule=row.selected_candidate?.schedule || row.hold_candidate?.schedule;
    const price_schedule=period().map((week,i)=>({week_index:week,price,feature_ad:savedSchedule?.[i]?.feature_ad ?? null}));
    await perform(t('Saving manual price as a new revision…','正在将人工价格保存为新版本…'),context=>saveRevision([{row_id:rowId(row),row_etag:row.row_etag,price_schedule,reason}],{},context));
  }
});
window.addEventListener('beforeunload',event=>{if(state.dirty){event.preventDefault();event.returnValue='';}});
async function boot() {
  try {
    const response=await fetch('/api/v1/config',{cache:'no-store'});
    if(!response.ok)throw new ApiError(response.status,{error:{code:'SERVICE_UNAVAILABLE'}});
    state.config=await response.json();session=new Session(state.config.firebase);api=new ApiClient(session);
    await loadExample();render();
  } catch(error) {
    state.error=error;render();
    if(!session){session=new Session({});api=new ApiClient(session);}
  }
}
boot();
