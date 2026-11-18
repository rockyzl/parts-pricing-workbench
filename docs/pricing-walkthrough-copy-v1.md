# Pricing walkthrough copy v1

Future interface copy only; V2 is not claimed live. English is the default; Chinese is the learning toggle. Bind result-dependent copy to actual verified artifacts and permissions. References: [design](design-v2.md), [backend contract](backend-contract-v1.md), [pricing contract](pricing-contract-v1.md). These contracts govern when each action and message may appear.

## Opening and access

| Placement | English | 中文讲解 |
|---|---|---|
| Title | Plan prices for the next 4 weeks | 制定未来 4 周的价格方案 |
| Introduction | Prepare a catalog price plan: check the records, compare allowed prices, and send your decisions for review. | 为整个商品目录制定价格方案：检查记录，比较允许的价格，再提交审核。 |
| Example context | Orange juice example · 3 brands · 83 stores · 249 store–brand entries | 橙汁示例 · 3 个品牌 · 83 家门店 · 249 个门店与品牌组合 |
| Period | History through source week 160 · Plan for source weeks 161–164 | 历史截至原始周编号 160 · 计划覆盖周编号 161–164 |
| Guest context | Viewing the example · Read only | 正在查看示例 · 只读 |
| Access explanation | Explore the prepared example without an account. An invited account lets you upload data, run models, and save your own plans. Your workspace stays private. | 无需账号即可查看准备好的示例。受邀账号可上传数据、运行模型并保存自己的方案，工作区内容保持私密。 |
| Guest action | Explore the example | 查看示例 |
| Analyst actions | Create my plan · Import my data | 创建我的方案 · 导入我的数据 |
| Sign-in title | Sign in to your pricing workspace | 登录定价工作区 |
| Uninvited account | This account has no workspace access. You can still explore the example. | 此账号尚无工作区权限，仍可查看公开示例。 |

The visible sequence is **Import → Check data & model → Plan prices → Review → Publish** / **导入 → 检查数据与模型 → 制定价格 → 审核 → 发布**. The example starts loaded at step 2. Guest actions inspect saved sample stages; they never create reviews, training runs, or ledger entries.

## 1. Import — begin with the records

| Placement | English | 中文讲解 |
|---|---|---|
| Heading | Start with weekly sales | 从每周销售记录开始 |
| Loaded example | The orange juice example is ready to inspect. Each entry follows one brand at one store. | 橙汁示例已载入。每条目录记录对应一个品牌在一家门店的历史。 |
| Upload explanation | Import a weekly sales CSV with price and recorded sales. Add store IDs if your data covers several stores. | 导入包含价格和记录销量的每周销售 CSV；涉及多家门店时，需要门店编号。 |
| Actions | Download CSV template · Save dataset and check data | 下载 CSV 模板 · 保存数据并检查 |
| Privacy | Your uploaded records and results stay in this workspace. | 上传的记录及结果仅保存在此工作区。 |

## 2. Check data & model — inspect before deciding

| Placement | English | 中文讲解 |
|---|---|---|
| Heading | See the sales behind this plan | 查看这份方案依据的销售记录 |
| Record summary | 28,947 recorded observations across 249 store–brand entries | 249 个门店与品牌组合，共有 28,947 条观测记录 |
| Chart titles | Recorded sales by week · Observed price by week | 每周记录销量 · 每周记录价格 |
| Table labels | Store / brand · Reference price · Observed weeks · Price changes | 门店／品牌 · 参考价 · 有记录的周数 · 价格变化次数 |
| Reference price | Last observed price, with its recorded week | 最近一次记录的价格，并显示对应周编号 |
| Missing record | No record for this week. Sales and stock availability are unknown. | 本周缺少记录，销量和是否有货均未知。 |
| Business inputs | Unit cost: missing · Stock: missing | 单位成本：缺失 · 库存：缺失 |
| Units | Prices and sales use the source's units. | 价格与销量保留原始数据的计量尺度。 |
| Model heading | Check predictions against past sales | 用历史销量检查预测 |
| Baseline explanation | Compare the model with a simple estimate based on recent recorded sales. Lower error means predictions were closer to the records. | 把模型与按近期记录销量计算的简单预测比较。误差越小，表示越接近记录值。 |
| Historical test label | Historical check · Recorded prices and feature advertising | 历史检验 · 使用记录中的价格与广告状态 |
| Essential model explanation | This check uses the prices and advertising that were later recorded. It does not show that changing a price will cause a sales or profit increase. | 此检验使用后来实际记录的价格与广告状态，不能据此认定调价会带来销量或利润增长。 |
| Next actions | View model evidence · View example price plan | 查看模型依据 · 查看示例价格方案 |

**Learn disclosure — sharing information when one entry has little history**

EN: “The model can learn a shared price–sales relationship from the same brand across stores, while using each store's recent sales to describe that entry. This can help when one entry has little history. It does not supply missing observations or make that entry safe to reprice. If its evidence is too limited, keep the reference price or use an explicit business rule.”

中文：“模型可以合并同品牌在不同门店的历史，学习价格与销量共同变化的关系，同时使用各门店近期销量描述各自情况。这有助于处理记录较少的组合，但不会补出缺失事实，也不代表它已有足够依据调价。证据不足时，保持参考价，或使用明确的业务规则。”

## 3. Plan prices — compare the whole catalog

| Placement | English | 中文讲解 |
|---|---|---|
| Heading | Choose a four-week price plan | 制定四周价格方案 |
| Explanation | Every catalog entry gets a decision and a reason. Some prices may change; others may stay. | 每条目录记录都要有处理结果和理由。有些价格可能调整，有些保持。 |
| Schedule | One price per entry for all 4 weeks | 每个组合在 4 周内使用同一个价格 |
| Assumption action | Use example business assumptions | 使用示例经营假设 |
| Cost assumption | Scenario cost: 60% of the reference price. This cost is invented for the exercise. | 情景成本：参考价的 60%。该成本是为练习设置的假设。 |
| Unit assumption | For this exercise, treat the price as the amount received per source sales unit. This is a hypothetical mapping, not a verified currency or package size. | 本练习假设每个原始销量单位收到对应价格的金额。这是情景映射，未核实币种或包装规格。 |
| Example rules | Scenario limits: 20% minimum margin · ±5% price change · At most 20 changed entries · 0.01 source-unit price steps | 情景限制：最低毛利率 20% · 调价幅度 ±5% · 最多调整 20 个组合 · 价格步长为 0.01 个原始价格单位 |
| Advertising assumption | Keep the last recorded feature-advertising state for all 4 weeks; unknown stays unknown. Assume zero additional advertising spend each week. | 4 周沿用最近记录的广告状态，未知仍为未知；假设每周新增广告费用为零。 |
| Stock | Stock is unknown. Stock feasibility has not been checked. | 库存未知，尚未检查供货能否支持计划。 |
| Calculation action | Compare prices | 比较价格 |
| Candidate explanation | Compare the reference price with allowed alternatives. Prices that break a rule cannot be selected. | 将参考价与符合条件的候选价比较。违反规则的价格不能选入方案。 |
| Future label | Future plan scenario · Entered prices and advertising | 未来计划情景 · 使用设定的价格与广告状态 |
| Scenario output | Scenario margin % · Estimated contribution · scenario · source-scale units | 情景毛利率 % · 预计贡献额 · 情景估计 · 原始尺度单位 |
| Output explanation | These estimates depend on the entered assumptions. They are not realized profit. | 这些估计取决于输入的假设，不是已经实现的利润。 |
| Next action | Send for review | 提交审核 |

Apply all example assumptions only after the explicit action, as one named scenario version. Preserve the actual reference prices; never replace them with illustrative numbers. A margin is the share of price left after the assumed unit cost. Do not show a contribution estimate when the required cost, receipt mapping, weekly spend, or supported model response is missing.

| Decision / strategy | English explanation | 中文讲解 |
|---|---|---|
| Hold / 保持 | Keep the reference price if it meets the rules. A change needs enough evidence or an explicit business decision. | 参考价满足规则时可保持；调价需要足够依据，或明确的业务决定。 |
| Rule / 规则 | Use the stated cost and price limits to propose an allowed price. This does not establish a sales or profit gain. | 按声明的成本和价格限制提出合规候选价，不据此认定销量或利润会增长。 |
| Model / 模型 | Compare allowed prices using a reviewed price model where this entry has enough supporting history. | 该组合有足够历史支持时，用经过检验的价格模型比较允许的候选价。 |
| Needs data / 缺少数据 | Add the missing input before this comparison can be used. | 补齐缺失输入后，才能使用这项比较。 |
| Rule conflict / 规则冲突 | No tested price meets all the rules. Revise the inputs or record an exclusion. | 没有测试价格同时满足全部规则；需修改输入或记录排除理由。 |
| All hold / 全部保持 | This plan keeps all eligible reference prices. Review the reasons before approving. | 本方案保持所有符合条件的参考价。批准前请检查理由。 |

## 4. Review — another person checks the plan

| Placement | English | 中文讲解 |
|---|---|---|
| Heading | Review the proposed prices | 审核拟定价格 |
| Pending status | Awaiting review · This plan is not in the Demo ledger yet. | 待审核 · 此方案尚未进入演示价格台账。 |
| Reviewer explanation | Check the prices, assumptions, and reasons. Approval must come from someone who did not create or edit this version. | 检查价格、假设和理由；批准人不能是本版本的创建人或修改人。 |
| Actions | Approve · Request revision · Reject · Exclude with a reason | 批准 · 要求修改 · 拒绝 · 填写理由并排除 |
| Revision message | The plan changed. Recalculate and submit the new version for review. | 方案已修改，需要重新计算并提交新版本审核。 |
| Coverage | Every entry needs an outcome: approved change, approved hold, rejected, or excluded with a reason. | 每条记录都需有结果：批准调价、批准保持、拒绝，或说明理由后排除。 |
| Saved message | Review saved for this version. | 此版本的审核记录已保存。 |

Use “saved” only after server acknowledgement. A suggested price in a review comment does not change the plan. A new executable revision requires a new approval. Guests see **“View example review” / “查看示例审核”**, not approval controls.

## 5. Publish — record the approved version

| Placement | English | 中文讲解 |
|---|---|---|
| Heading | Record the approved pricebook | 保存已批准的价格表 |
| Authorized action | Publish to Demo ledger | 发布到演示价格台账 |
| Destination explanation | Save the approved four-week prices in this private workspace and make them available to download. Store prices are not updated. | 将批准的四周价格保存在此私密工作区，供下载使用；门店价格不会随之更新。 |
| Before publication | Resolve the remaining entries before publishing. | 发布前需处理剩余记录。 |
| Success, after confirmation | Published to Demo ledger · Version {version} | 已发布到演示价格台账 · 版本 {version} |
| Downloads | Download pricebook · Download coverage report | 下载价格表 · 下载全目录处理报告 |
| Export explanation | The pricebook includes approved changes and allowed holds. The coverage report also records rejected and excluded entries. | 价格表包含批准的调价和符合规则的保持项；全目录处理报告还记录拒绝及排除项。 |
| Privacy | Publication keeps your records private. | 发布后，工作区记录仍保持私密。 |
| Later outcomes | No later sales records loaded. | 尚未载入后续销售记录。 |

## One guided example, from start to finish

EN: “You manage the orange juice catalog. Start with all 249 store–brand entries through week 160. Inspect a real row's sales and price history, then check the historical predictions. For weeks 161–164, explicitly apply the example cost and rule assumptions above. Compare all entries, keeping holds and conflicts visible. Inspect one returned decision and its reason; no price increase or gain is promised. Save any revision and send the plan to a different reviewer. After every entry is resolved, an authorized reviewer or owner records the approved version in the private Demo ledger. A guest follows this same story through the saved sample.”

中文：“你负责橙汁目录定价。从截至周编号 160 的全部 249 个门店与品牌组合开始，查看一条真实记录的销量与价格历史，再检查历史预测。为周编号 161–164 明确采用上面的示例成本与规则假设，比较整个目录，并保留保持项和冲突项。查看实际返回的一项决定及理由，不预设一定涨价或增加收益。修改后保存并交给另一人审核。全部记录处理完毕后，由有权限的审核人或负责人将批准版本写入私密演示价格台账。访客通过保存好的示例了解同一流程。”

## Details only

Place **“How this was built / 实现方式”** and **“Source details / 数据出处”** in disclosures. Populate them with the actual source/version, sales transformation, fitted method, shared brand relationship, validation periods, and saved run/review references. Keep API names, storage, authentication mechanics, formulas, and model coefficients out of primary task copy. Do not invent scores, causal gains, confidence intervals, source calendar dates, live V2 status, or completed sample actions.
