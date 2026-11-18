import test from "node:test";
import assert from "node:assert/strict";
import { priceDecision, sharedElasticity } from "../web/engine.mjs";
const base = {
  basePrice: 100,
  baseUnits: 10,
  cost: 60,
  minMargin: 0.2,
  maxChange: 0.12,
  skuElasticity: -2.2,
  familyElasticity: -1.5,
  activeWeeks: 2,
  competitorCeiling: null,
};

test("contradictory cost and maximum price returns no quote", () => {
  const result = priceDecision({ ...base, cost: 120 });
  assert.equal(result.status, "infeasible");
  assert.equal(result.candidate, null);
});
test("all candidates obey rounded margin, change and optional market bounds", () => {
  const result = priceDecision({
    ...base,
    cost: 71.23,
    minMargin: 0.23,
    competitorCeiling: 103.333,
  });
  for (const row of result.candidates) {
    assert.ok(row.price >= result.lower && row.price <= result.upper);
    assert.ok((row.price - 71.23) / row.price >= 0.23 - 1e-10);
    assert.ok(row.price <= 103.333);
  }
});
test("no observed sales does not become a fabricated unit", () => {
  assert.equal(
    priceDecision({ ...base, baseUnits: 0 }).status,
    "insufficient_sales",
  );
});
test("teaching pooling retains family estimate when there is no evidence", () => {
  assert.equal(sharedElasticity(-3, -1.5, 0).elasticity, -1.5);
  assert.ok(
    sharedElasticity(-3, -1.5, 1).weight < sharedElasticity(-3, -1.5, 8).weight,
  );
});
test("optimizer matches independent exhaustive-cent maximization", () => {
  const result = priceDecision(base);
  const profits = [];
  for (
    let cents = Math.ceil(result.lower * 100);
    cents <= Math.floor(result.upper * 100);
    cents++
  ) {
    const p = cents / 100;
    profits.push(
      Math.min(
        ...result.elasticities.map(
          (e) => (p - base.cost) * base.baseUnits * (p / base.basePrice) ** e,
        ),
      ),
    );
  }
  // Narrow a case to exercise cent enumeration, rather than the documented wider grid.
  const small = priceDecision({ ...base, maxChange: 0.02 });
  const exact = [];
  for (
    let cents = Math.round(small.lower * 100);
    cents <= Math.round(small.upper * 100);
    cents++
  ) {
    const p = cents / 100;
    exact.push(
      Math.min(
        ...small.elasticities.map(
          (e) => (p - base.cost) * base.baseUnits * (p / base.basePrice) ** e,
        ),
      ),
    );
  }
  assert.ok(Math.abs(small.candidate.worstProfit - Math.max(...exact)) < 1e-9);
  assert.ok(result.candidate.worstProfit >= result.baseline.worstProfit - 1e-9);
});
test("invalid and nonfinite inputs cannot leak a price", () => {
  for (const patch of [
    { basePrice: 0 },
    { cost: -1 },
    { minMargin: 1 },
    { maxChange: NaN },
    { activeWeeks: 9 },
    { competitorCeiling: Infinity },
  ])
    assert.throws(() => priceDecision({ ...base, ...patch }));
});
test("zero allowed change preserves the original feasible price", () => {
  assert.equal(priceDecision({ ...base, maxChange: 0 }).candidate.price, 100);
});
test("infeasible penny interval rejects unsafe rounding", () => {
  assert.equal(
    priceDecision({
      ...base,
      basePrice: 1,
      cost: 0.999,
      minMargin: 0,
      maxChange: 0,
      competitorCeiling: 0.999,
    }).status,
    "infeasible",
  );
});
