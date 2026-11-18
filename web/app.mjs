import { priceDecision, sharedElasticity } from "./engine.mjs";
const $ = (id) => document.getElementById(id);
let language = "en",
  catalog,
  selected,
  lastResult = null;
const t = (en, zh) => (language === "zh" ? zh : en);
const money = (value) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(
    value,
  );
const num = (value) => Number(value).toFixed(2);
const segmentName = (key) =>
  ({
    sparse: t("Sparse recorded sales", "低频销售"),
    regular: t("Regular recorded sales", "经常有销售"),
    no_recent_sales: t("No recent recorded sales", "最近没有销售记录"),
    occasional: t("Occasional recorded sales", "偶尔有销售"),
  })[key];

function translate() {
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  document
    .querySelectorAll("[data-en]")
    .forEach((el) => (el.textContent = el.dataset[language]));
  $("language").textContent = language === "zh" ? "English" : "中文讲解";
  if (catalog) {
    renderOptions();
    renderRecord();
    poolNote();
    if (lastResult) renderResult(lastResult);
    else clearDecision();
  }
}

function renderOptions() {
  $("product").replaceChildren(
    ...catalog.products.map((p, i) => {
      const option = document.createElement("option");
      option.value = String(i);
      option.textContent = `${p.sku} · ${segmentName(p.segment)}`;
      return option;
    }),
  );
  $("product").value = String(catalog.products.indexOf(selected));
}

function renderRecord() {
  $("product-name").textContent = selected.description;
  $("segment").textContent = segmentName(selected.segment);
  $("base-price").textContent = money(selected.last_observed_price);
  $("active-weeks").textContent = `${selected.active_weeks_last_8} / 8`;
  const max = Math.max(1, ...selected.history.map((row) => row.units));
  $("history").replaceChildren(
    ...selected.history.map((row) => {
      const bar = document.createElement("span");
      bar.style.height = `${(row.units / max) * 100}%`;
      bar.title = `${row.week}: ${row.units} ${t("recorded units", "件")}`;
      return bar;
    }),
  );
  $("history").setAttribute(
    "aria-label",
    t("Weekly recorded unit sales, 26 weeks", "26 周的每周记录销量"),
  );
  $("record-note").textContent = t(
    `Last sale: ${selected.last_sale_date}. Eight-week mean: ${num(selected.recorded_units_per_week)} units/week. ${selected.unique_transaction_prices_last_26} distinct transaction prices in 26 weeks; discounts and customer mix may differ.`,
    `最后成交日期：${selected.last_sale_date}。最近 8 周平均每周 ${num(selected.recorded_units_per_week)} 件。26 周有 ${selected.unique_transaction_prices_last_26} 个不同成交价；价格差异也可能来自折扣和客户结构。`,
  );
}

function poolNote() {
  try {
    const shared = sharedElasticity(
      Number($("sku-e").value),
      Number($("family-e").value),
      selected.active_weeks_last_8,
    );
    $("pool-note").textContent = t(
      `Teaching weight: ${selected.active_weeks_last_8}/(${selected.active_weeks_last_8}+8). Item ${Math.round(shared.weight * 100)}%, family ${Math.round((1 - shared.weight) * 100)}%; combined assumption ${num(shared.elasticity)}.`,
      `教学权重：${selected.active_weeks_last_8}/(${selected.active_weeks_last_8}+8)。单品占 ${Math.round(shared.weight * 100)}%，同类占 ${Math.round((1 - shared.weight) * 100)}%；合并弹性假设为 ${num(shared.elasticity)}。`,
    );
  } catch {
    $("pool-note").textContent = t(
      "Enter valid negative sensitivity assumptions.",
      "请填写有效的负数弹性假设。",
    );
  }
}

function clearDecision() {
  lastResult = null;
  window.__pricingResult = null;
  $("decision").replaceChildren();
  const p = document.createElement("p");
  p.className = "empty";
  p.textContent = t(
    "Inputs changed. Compare prices to calculate a new proposal.",
    "条件已变化，请点击比较价格，重新计算。",
  );
  $("decision").append(p);
  $("review").hidden = true;
  $("review-status").textContent = "";
}

function chooseProduct() {
  selected = catalog.products[Number($("product").value)];
  $("cost").value = (selected.last_observed_price * 0.6).toFixed(2);
  $("market").value = (selected.last_observed_price * 1.05).toFixed(2);
  $("review-note").value = "";
  renderRecord();
  poolNote();
  clearDecision();
}

function readInputs() {
  return {
    basePrice: selected.last_observed_price,
    baseUnits: selected.recorded_units_per_week,
    cost: Number($("cost").value),
    minMargin: Number($("margin").value) / 100,
    maxChange: Number($("change").value) / 100,
    skuElasticity: Number($("sku-e").value),
    familyElasticity: Number($("family-e").value),
    activeWeeks: selected.active_weeks_last_8,
    competitorCeiling: $("use-market").checked
      ? Number($("market").value)
      : null,
  };
}

function renderResult(result) {
  const labels = {
    margin: t("Cost / margin floor", "成本与毛利底线"),
    change: t("Change limit", "涨跌幅限制"),
    market: t("Market ceiling", "市场上限"),
  };
  const rules = `<ul class="rules">${result.floors.map((row) => `<li><span>${labels[row.name]} ≥</span><strong>${money(row.value)}</strong></li>`).join("")}${result.ceilings.map((row) => `<li><span>${labels[row.name]} ≤</span><strong>${money(row.value)}</strong></li>`).join("")}</ul>`;
  if (result.status === "infeasible") {
    $("decision").innerHTML =
      `<div class="decision-state">${t("CONFLICT · NO PRICE PROPOSED", "规则冲突 · 不输出价格")}</div><div class="notice">${t(`The floor ${money(result.lower)} exceeds the ceiling ${money(result.upper)}. Review the cost or one of the rules before proceeding.`, `最低需要 ${money(result.lower)}，但最多只允许 ${money(result.upper)}。需要人工核实成本或调整某条规则。`)}</div>${rules}`;
  } else if (result.status === "insufficient_sales") {
    $("decision").innerHTML =
      `<div class="decision-state">${t("NO RECENT SALES · REVIEW NEEDED", "近期无销售 · 需要人工查看")}</div><div class="notice">${t("There are no positive sales in the recent eight weeks. Check availability and product lifecycle. The engine does not invent a sale to calculate a profit opportunity.", "最近 8 周没有记录到正向销售。请先检查库存与商品生命周期；系统不会凭空补一件销量来计算利润机会。")}</div>${rules}`;
  } else {
    const best = result.candidate,
      middle = best.values[1];
    const worstDelta = best.worstProfit - result.baseline.worstProfit;
    $("decision").innerHTML =
      `<div class="decision-state">${t("SCENARIO CANDIDATE · HUMAN REVIEW", "情景候选价 · 待人工审核")}</div><div class="price">${money(best.price)}</div><div class="price-subtitle">${t(`Compared with the last observed ${money(result.input.basePrice)}. Not a live quote.`, `对照最后成交价 ${money(result.input.basePrice)}；这不是对外报价。`)}</div><div class="range"><div class="rail"></div><div class="rail-labels"><span>${t("Allowed floor", "允许底价")} ${money(result.lower)}</span><span>${t("Ceiling", "上限")} ${money(result.upper)}</span></div></div>${rules}<p class="small">${t(`Compared ${result.candidates.length} feasible candidates. This candidate has the highest lowest-scenario profit among the tested prices.`, `比较了 ${result.candidates.length} 个可行候选价。在测试的价格里，它的“三种情景中最差毛利”最高。`)}</p><div class="numbers"><div><strong>${num(middle.quantity)}</strong><span>${t("units/week · central scenario", "件/周 · 中间情景")}</span></div><div><strong>${money(worstDelta)}</strong><span>${t("change in worst-scenario weekly profit", "最差情景的周毛利变化")}</span></div></div><table class="scenario-table"><thead><tr><th>${t("Assumed elasticity", "弹性假设")}</th><th>${t("Units/week", "件/周")}</th><th>${t("Gross profit/week", "毛利/周")}</th></tr></thead><tbody>${best.values.map((row) => `<tr><td>${num(row.elasticity)}</td><td>${num(row.quantity)}</td><td>${money(row.profit)}</td></tr>`).join("")}</tbody></table><p class="hint">${t("Three sensitivity scenarios (combined assumption ±0.6), not a confidence interval or a guarantee. Profit excludes overhead and other unprovided costs.", "三种敏感度情景（合并假设 ±0.6），并非置信区间或收益保证。毛利没有扣除数据中未提供的管理等其他成本。")}</p>${result.baselineFeasible ? "" : `<div class="notice">${t("The old price does not satisfy the current assumptions.", "原成交价不满足当前设置的限制。")}</div>`}`;
  }
  $("review").hidden = false;
  if (result.reviewStatus === "noted_locally")
    $("review-status").textContent = t(
      "Review saved in this browser. No price was published.",
      "审核意见已保存在本浏览器，没有对外发布价格。",
    );
}

function calculate(event) {
  event?.preventDefault();
  clearDecision();
  try {
    const result = priceDecision(readInputs());
    lastResult = {
      ...result,
      product: { sku: selected.sku, description: selected.description },
      snapshot: catalog.as_of,
      calculatedAt: new Date().toISOString(),
      engineVersion: "scenario-v1",
      reviewStatus: "pending",
      provenance:
        "UCI historical sales; cost, elasticities and market ceiling are assumptions; no fitted elasticity model.",
    };
    window.__pricingResult = lastResult;
    renderResult(lastResult);
  } catch (error) {
    const p = document.createElement("p");
    p.className = "notice";
    p.textContent =
      t(
        "Check the entered numbers. No proposal was calculated. ",
        "请检查输入的数值，本次没有生成报价。 ",
      ) + error.message;
    $("decision").append(p);
  }
}

$("language").addEventListener("click", () => {
  language = language === "en" ? "zh" : "en";
  translate();
});
$("product").addEventListener("change", chooseProduct);
$("pricing-form").addEventListener("submit", calculate);
$("pricing-form").addEventListener("input", () => {
  clearDecision();
  poolNote();
});
$("use-market").addEventListener("change", () => {
  $("market-field").hidden = !$("use-market").checked;
  $("market").required = $("use-market").checked;
  clearDecision();
});
$("try-conflict").addEventListener("click", () => {
  $("cost").value = (selected.last_observed_price * 1.5).toFixed(2);
  calculate();
});
$("save-review").addEventListener("click", () => {
  if (!lastResult) return;
  const note = $("review-note").value.trim();
  if (!note) {
    $("review-status").textContent = t(
      "Write a review note first.",
      "请先填写审核意见。",
    );
    return;
  }
  try {
    const entry = {
      ...lastResult,
      reviewStatus: "noted_locally",
      reviewNote: note,
      reviewedAt: new Date().toISOString(),
    };
    const stored = JSON.parse(localStorage.getItem("pricing-reviews") || "[]");
    const previous = Array.isArray(stored) ? stored : [];
    localStorage.setItem(
      "pricing-reviews",
      JSON.stringify([entry, ...previous].slice(0, 25)),
    );
    lastResult = entry;
    window.__pricingResult = entry;
    $("review-status").textContent = t(
      "Review saved in this browser. No price was published.",
      "审核意见已保存在本浏览器，没有对外发布价格。",
    );
  } catch {
    $("review-status").textContent = t(
      "Browser storage is unavailable. Download the calculation instead.",
      "浏览器存储不可用，可下载计算记录保存。",
    );
  }
});
$("download").addEventListener("click", () => {
  if (!lastResult) return;
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(lastResult, null, 2)], {
      type: "application/json",
    }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `pricing-${selected.sku}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

try {
  const response = await fetch("catalog.json");
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  catalog = await response.json();
  window.__catalog = catalog;
  if (!catalog.products?.length) throw new Error("No public examples");
  selected = catalog.products[0];
  renderOptions();
  chooseProduct();
  $("loading").hidden = true;
  $("workbench").hidden = false;
} catch (error) {
  $("loading").textContent =
    t(
      "Could not load the public snapshot. Reload this page. ",
      "数据快照未加载，请刷新页面。 ",
    ) + error.message;
}
