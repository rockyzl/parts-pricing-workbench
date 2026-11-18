export const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const number = (value, digits = 2) => value === null || value === undefined || value === '' || !Number.isFinite(Number(value)) ? '—' : new Intl.NumberFormat('en-US',{maximumFractionDigits:digits}).format(Number(value));
export const titleCase = value => String(value || '').replaceAll('_',' ').replace(/\b\w/g, s => s.toUpperCase());
export const rowId = row => row.row_id || row.series_id;
export function decision(row) {
  if (!row.disposition) return 'uncalculated';
  if (row.coverage?.excluded || row.disposition === 'excluded') return 'excluded';
  if (['change_proposed','change','manual'].includes(row.disposition)) return 'change';
  if (row.disposition === 'hold') return 'hold';
  if (row.disposition === 'needs_data') return 'needs_data';
  return 'conflict';
}
export function statusText(value, chinese=false) {
  const values={
    pending:['Awaiting review','等待审核'],approve_change:['Change approved','调价已批准'],approve_hold:['Hold approved','保持已批准'],request_revision:['Revision requested','要求修改'],reject:['Rejected','已拒绝'],exclude:['Excluded','已排除'],
    draft:['Draft','草稿'],submitted:['Submitted for review','已提交审核'],published:['Published','已发布'],publishing:['Publication in progress','正在发布'],read_only_sample:['Saved example','保存的示例'],
    analyst:['Analyst','分析人员'],reviewer:['Reviewer','审核人员'],owner:['Owner','负责人'],hold:['Keep reference price','保持参考价'],model:['Model comparison','模型比较'],manual:['Manual decision','人工决定'],rule:['Business rule','经营规则'],
    queued:['Waiting to start','等待开始'],dispatching:['Starting training','正在启动训练'],dispatch_unknown:['Start status needs checking','需要核对启动状态'],running:['Training in progress','正在训练'],succeeded:['Training completed','训练已完成'],failed:['Training failed','训练失败'],cancel_requested:['Cancellation requested','已请求取消'],cancelling:['Stopping training','正在停止训练'],cancelled:['Training cancelled','训练已取消'],timed_out:['Time limit reached','已达时间限制'],
    admitted:['Request accepted','请求已受理'],dispatch:['Starting the job','正在启动任务'],preflight:['Checking the records','正在检查记录'],selection:['Comparing model choices','正在比较模型选择'],confirmation:['Checking historical predictions','正在检查历史预测'],refit:['Fitting the final model','正在拟合最终模型'],awaiting_reconciliation:['Waiting for a completion check','等待核对完成状态'],awaiting_provider_terminal:['Training finished; confirm the job has stopped','训练已完成，请确认任务已停止'],terminal:['Job completed','任务已结束'],worker_stopped:['Training stopped','训练已停止'],observed:['Observed','已观测'],unavailable:['Unavailable','不可用'],unknown:['Unknown','未知'],not_checked:['Not checked','未检查'],
  };
  return values[value]?.[chinese?1:0] || String(value||'').replaceAll('_',' ');
}
const reasons = {
  opening_stock_missing:['Opening stock is missing.','缺少期初库存。'], replenishment_missing:['Incoming stock is missing.','缺少补货记录。'],
  inventory_not_checked:['Stock feasibility has not been checked.','尚未检查库存是否足够。'], catalog_selection_infeasible:['The full plan cannot meet its rules. Revise the inputs or record an exclusion.','完整方案无法同时满足规则。请修改输入或记录排除理由。'],
  stale_reference_price:['The last recorded price is too old for this rule.','最近记录的价格超过规则允许的时间。'],
  unit_variable_cost_missing:['Unit cost is missing. Add a business assumption or supplied cost.','缺少单位成本。请提供成本或明确的经营假设。'],
  model_unavailable:['No compatible price model is available for this entry.','该记录没有可用的兼容价格模型。'],
  feature_ad_missing:['The future feature-advertising state is unknown.','未来广告状态未知。'],
  nonpositive_model_gain:['The tested alternatives do not improve the scenario comparison.','测试候选价未改善情景比较结果。'],
  change_cap_reached:['Other changes use the plan’s allowed change count.','其他调价已占用允许的调价数量。'],
};
export function reasonText(code, chinese = false) { return reasons[code]?.[chinese ? 1 : 0] || String(code || '').replaceAll('_',' '); }
export function rowReason(row, chinese = false) {
  if (row.exclusion?.reason) return row.exclusion.reason;
  if (row.reason_codes?.length) return row.reason_codes.map(code => reasonText(code,chinese)).join(' · ');
  if (decision(row) === 'hold') return chinese ? '保持参考价；在规则和调价数量限制内，未选中其他价格。' : 'Keep the reference price; no alternative was selected within the rules and change limit.';
  if (decision(row) === 'change') return chinese ? '根据已声明的假设和规则，选中这个允许的价格。' : 'This allowed price was selected under the stated assumptions and rules.';
  return chinese ? '检查缺少的输入和规则后，再作决定。' : 'Check the missing inputs and rules before deciding.';
}
export function visibleRows(rows, query, filter) {
  const needle = query.trim().toLocaleLowerCase();
  return rows.filter(row => (!needle || [row.item_id,row.site_id,row.series_id].join(' ').toLocaleLowerCase().includes(needle)) &&
    (!filter || filter === 'all' || (filter === 'pending' ? !row.review || ['pending','request_revision'].includes(row.review.action) : decision(row) === filter)));
}
export function splitBatches(rows, size = 40) {
  if (!Number.isInteger(size) || size < 1 || size > 40) throw new Error('Review batches must contain 1–40 rows');
  return Array.from({length:Math.ceil(rows.length/size)}, (_,i) => rows.slice(i*size,(i+1)*size));
}
export function lineChart(records, field, {label = '', chinese = false, compact = false} = {}) {
  const finite = records.filter(row => row[field] !== null && row[field] !== undefined && Number.isFinite(Number(row[field])));
  if (!finite.length) return `<p class="empty">${chinese ? '没有可显示的记录。' : 'No recorded values available.'}</p>`;
  const width = 620, height = compact ? 100 : 174, padding = 28;
  const minWeek = Math.min(...records.map(r=>Number(r.week_index))), maxWeek = Math.max(...records.map(r=>Number(r.week_index)));
  const max = Math.max(...finite.map(r=>Number(r[field])),1);
  const x = week => padding + (Number(week)-minWeek)/Math.max(1,maxWeek-minWeek)*(width-padding*2);
  const y = value => height-padding-Number(value)/max*(height-padding*2);
  let segments = [], current = [];
  for (const row of records) {
    if (row[field] === null || row[field] === undefined || !Number.isFinite(Number(row[field]))) { if (current.length) segments.push(current); current=[]; }
    else current.push(`${x(row.week_index).toFixed(2)},${y(row[field]).toFixed(2)}`);
  }
  if (current.length) segments.push(current);
  return `<svg class="trend" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHTML(label)}"><title>${escapeHTML(label)}</title>
    <line class="chart-grid" x1="${padding}" x2="${width-padding}" y1="${height-padding}" y2="${height-padding}"/>
    <line class="chart-grid" x1="${padding}" x2="${width-padding}" y1="${padding}" y2="${padding}"/>
    ${segments.map(segment=>`<polyline class="chart-line" points="${segment.join(' ')}"/>`).join('')}
    <text x="${padding}" y="${height-6}">${chinese?'周':'Week'} ${minWeek}</text><text x="${width-padding}" y="${height-6}" text-anchor="end">${maxWeek}</text>
    <text x="${padding}" y="18">${number(max,0)}</text></svg>`;
}
export function errorCopy(error, chinese = false) {
  const code = error.code || 'REQUEST_FAILED';
  const messages = {
    MODEL_SNAPSHOT_MISMATCH:['The saved model does not match this snapshot’s registry or cutoff. Reload the snapshot and choose a matching saved model.','保存模型与此快照的注册记录或截止周不匹配。请重新载入快照并选择匹配模型。'],
    INFEASIBLE_APPROVAL:['A selected entry has no allowed executable price. Inspect its reasons, then revise, reject or exclude it.','某条所选记录没有可执行的合规价格。请检查理由，然后修改、拒绝或排除。'],
    COMPARISON_REQUIRED:['Compare this revision before sending it for review.','提交审核前，请先比较此版本。'],
    TRAINING_UNAVAILABLE:['Model training is currently unavailable. Your saved records and plans remain available.','模型训练暂不可用，已保存的记录和方案仍可访问。'],
    WORKSPACE_INVITATION_REQUIRED:['This account has no workspace access. You can still explore the saved example.','此账号尚无工作区权限，仍可查看保存的示例。'],
    SIGN_IN_UNAVAILABLE:['Sign-in is not configured. The saved example is still available.','登录尚未配置，仍可查看保存的示例。'],
    SIGN_IN_FAILED:['Sign-in failed. Check the email and password for your invited account.','登录失败，请检查受邀账号的邮箱和密码。'],
    RESPONSE_INTERRUPTED:['The response was interrupted before it could be read. Reload the current version before retrying; the same action keeps its request key.','响应在读取完成前中断。重试前请载入当前版本；相同操作会保留原请求编号。'],
    CONNECTION_LOST:['The connection was interrupted. Reload the current version before retrying. A retry of the same action keeps its request key.','连接中断。重试前请重新载入当前版本；相同操作的重试会沿用请求编号。'],
    AUTH_NETWORK_UNAVAILABLE:['Sign-in could not refresh while offline. Check the connection and retry.','离线时无法刷新登录，请检查网络后重试。'],
  };
  let message = messages[code] || messages[code.toUpperCase()];
  if (!message && error.status === 401) message = ['Your session needs sign-in. Unsent form values remain here; reload the saved version after signing in.','请重新登录。未保存的表单仍保留在此页面；登录后需载入服务器最新版本。'];
  if (!message && error.status === 403) message = ['This account cannot perform this action. Approvals require a different authorized person from the author and editors.','此账号无权执行此操作。批准人必须具有审核权限，且不能是作者或编辑者。'];
  if (!message && [409,412].includes(error.status)) message = ['The saved plan changed or this action conflicts with its current state. Reload the current version and review your unsaved changes.','方案已变化，或此操作与当前状态冲突。请载入最新版本，再检查未保存的修改。'];
  if (!message && error.status === 413) message = ['The file is too large. Import a CSV no larger than 10 MiB.','文件过大，请导入不超过 10 MiB 的 CSV。'];
  if (!message && error.status === 422) message = ['Some inputs need correction. Check the highlighted fields or row errors below.','部分输入需要更正，请检查下方字段或行号错误。'];
  if (!message && error.status === 429) message = ['This action is at capacity or its limit has been reached. Check the current run and the server limits before retrying.','当前操作容量已满或已达上限。重试前请检查运行状态和服务器限制。'];
  return (message || ['This service is unavailable. Keep your draft and try reloading its current status.','服务暂不可用。请保留草稿，并尝试重新载入当前状态。'])[chinese ? 1 : 0];
}
