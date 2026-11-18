# Pricing Engine 数据调查：微软原例与 Kaggle

状态：个人非商业学习/展示的选型记录；未开始模型训练。核查日：2026-11-17。

## 建议

先用微软仓库附带的 Orange Juice 原始资料，完成价格、促销、跨门店信息共享与定价审核闭环；再用 Kaggle M5 检验数千商品与长尾批处理。两套数据分别建模，不把不同商家的字段拼接成虚假的完整记录。

## 微软确实附带数据

原仓库的 [assets/oj_raw.csv](https://github.com/Azure/cortana-intelligence-price-analytics/blob/master/assets/oj_raw.csv) 可直接读取。本轮对实际文件做的统计：

- 28,947 条数据、17 列；4,772,840 字节。
- 83 家门店、3 个品牌：dominicks、minute.maid、tropicana。
- 121 个周编号（40–160），249 条门店×品牌序列；不是 249 个不同商品。
- 店×品牌×周主键无重复；完整 249×121 面板应有 30,129 行，实际少 1,182 行，缺失周不能直接当零需求。
- `feat=1` 有 6,868 行，`feat=0` 有 22,079 行。
- SHA-256：`3fc53cf6b14df1d69aba1977a27953400e53df5483c23493a38d6031b27b2c54`。

字段包括 `store`, `brand`, `week`, `logmove`, `feat`, `price`，以及 AGE60、EDUC、INCOME 等门店区域特征。销量由 `exp(logmove)` 还原，需考虑原始 log 精度。`feat` 对应推广/广告特征，不能声称包含所有促销类型或推广成本。

仓库还提供 `OJ_Demo_beta_clean.xlsx`、Power BI `.pbix` 文件，以及 `forecasts.csv`、`elasticities.csv`、`cross_elasticities.csv`、`suggestion_runs.csv`、`underover.csv`。后五类是预计算结果，不能当作自己的训练成果，也不作为训练目标回灌。

特别核查 [post_bcp_actions.sql](https://github.com/Azure/cortana-intelligence-price-analytics/blob/master/assets/post_bcp_actions.sql)：其 `UnitCost` 用品牌基准成本、月份、趋势和随机噪声生成；属于演示假设。日期由周编号加到 2015-01-01 上，且用户指南明确演示日期会平移。不要据此连接真实历史节假日、天气和宏观数据。原始周历确定前，只使用可说明的时间序列特征。

同一 SQL 简化后的 `pricingdata` 表不保留 `feat`；我们的模型应该保留原始促销字段。来源保留微软说明及 bayesm/原研究引用；仓库 MIT 不应被扩大解释为所有上游数据一律无条件许可。[微软指南](https://github.com/Azure/cortana-intelligence-price-analytics/blob/master/User%20Guide/UserGuide.md)；[bayesm 官方说明，orangeJuice 部分](https://cran.r-project.org/web/packages/bayesm/bayesm.pdf)。

## Kaggle 与其他资料比较

| 数据 | 有实际商品售价吗 | 有实际促销信息吗 | 适合本项目哪部分 |
|---|---|---|---|
| [M5 / Walmart](https://www.kaggle.com/competitions/m5-forecasting-accuracy/data) | 有：周平均 `sell_price` | 官方字段没有明确促销标记；节日/SNAP 不能冒充促销 | 最适合大量商品、长尾和日历效果；价格响应扩展需要另做识别检查 |
| [Favorita Grocery Sales](https://www.kaggle.com/competitions/favorita-grocery-sales-forecasting/data) | 没有商品售价 | `onpromotion` 布尔值，约 16% 缺失 | 真实商品销量与促销预测；不是完整定价核心数据 |
| [Favorita Store Sales](https://www.kaggle.com/competitions/store-sales-time-series-forecasting/data) | 没有 | `onpromotion` 是商品大类里促销商品数量 | 简洁的季节/促销预测教学；不是单 SKU 定价 |
| [Rossmann](https://www.kaggle.com/competitions/rossmann-store-sales/data) | 没有 SKU 售价；`Sales` 是门店营业额 | 有 Promo/Promo2 | 门店收入和业务因素分析；对商品定价适配较弱 |
| [dunnhumby Breakfast at the Frat](https://www.dunnhumby.com/source-files/) | 官方介绍有 base/shelf price | 有促销支持、陈列等 | 小规模价格与促销研究备选；下载文件和实际字段还需核验 |
| [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail) | 有成交单价 | 没有显式促销 | 已有公开管线与商品目录基线；CC BY 4.0 |

**M5**：官方参与指南确认 3,049 个商品、10 家门店、3 个州，形成 30,490 条商品×门店序列；最多 1,941 天，2011-01-29 至 2016-06-19。销量表有商品/部门/品类/门店和各日销量；价格表为 `store_id,item_id,wm_yr_wk,sell_price`；calendar 有日历事件和 SNAP。数据页显示五个文件约 450.47 MB。缺价格不证明库存为零，也没有真实成本和库存余额。[官方参与指南，3–5 页](https://storage.googleapis.com/kaggle-forum-message-attachments/772349/15032/M5-Competitors-Guide-Final-10-March-2020.pdf)。

**Favorita Grocery**：`unit_sales` 可为小数，负值代表退货；零销量商品/门店/日期的行省略，官方明确没有库存状态。油价是宏观变量，不是商品售价/成本；未来实际交易笔数不能泄漏到预测中。文件约 479.88 MB 压缩后，行数和具体覆盖期留待文件审计。

**Favorita Store Sales**：`sales` 是商品大类销量，不是美元销售额；`onpromotion` 是促销项数量，不是布尔值。文件约 124.76 MB。

**Rossmann**：1,115 店，有节假日、营业状态、门店类型、促销和竞争门店距离。竞争距离不是竞争商品报价；未来实际 Customers 也不能作为已知输入。文件约 39.85 MB。

**Breakfast at the Frat**：官方介绍 156 周，有商品/门店/周销量、支出、base/shelf price、推广支持。下载表单要求基本信息、用途和条款；本轮未提交。提供方把系列描述为受真实业务启发的表示，具体版本是否原样真实记录需看随附指南。

上述四个 Kaggle 比赛数据页均需登录并接受对应竞赛规则后下载；本轮仅查看官方页面，没有登录/接受/下载。Kaggle 是托管平台，数据能否解决问题仍看字段与来源，而不是标题写了 pricing 就足够。

## 容易选错的样例

[Retail Store Inventory Forecasting Dataset](https://www.kaggle.com/datasets/anirudhchauhan/retail-store-inventory-forecasting-dataset) 的发布者明确写为 synthetic，虽有 73,000 多行及库存、价格、竞争/天气等丰富字段，也只能用于接口/边界测试。不能据此声称模型学到真实商业价格效果。

## 下一步数据审计（讨论后执行）

1. 微软原始文件建立真实价格/推广/销量面板；保留缺失周、恢复单位与周历、检查价格支持。
2. 在同一份真实面板上比较简单基线、含促销/时间特征的模型，以及有条件的信息共享；独立保存模型与验证结果。
3. 成本与库存仍为单独、有来源状态的输入。可重现微软演示成本作为测试，但 UI 标注为情景。
4. 获取 M5 后先做可控范围的运行测量，再扩展目录；结果分别报告，不把三品牌实验称为已验证数万 SKU。
5. 数据包放私人 Drive 备份；GitHub 保留下载路径、版本、哈希、字段字典、处理脚本和恢复说明。受来源条件限制的原始资料不随公共代码自动镜像。
