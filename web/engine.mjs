/* Independent implementation of bounded contribution-profit scenarios.
 * Constant elasticity and candidate grids are mathematical methods, not a trained model.
 * See THIRD_PARTY.md for inspected references and why their code was not copied.
 */
function finite(value, name) {
  if (typeof value !== "number" || !Number.isFinite(value))
    throw new Error(`Invalid ${name}`);
  return value;
}

export function sharedElasticity(skuAssumption, familyAssumption, activeWeeks) {
  finite(skuAssumption, "SKU elasticity");
  finite(familyAssumption, "family elasticity");
  finite(activeWeeks, "active weeks");
  if (
    skuAssumption >= 0 ||
    familyAssumption >= 0 ||
    activeWeeks < 0 ||
    activeWeeks > 8
  )
    throw new Error("Invalid pooling scenario");
  // Teaching policy, NOT a fitted empirical-Bayes posterior or uncertainty estimate.
  const weight = activeWeeks / (activeWeeks + 8);
  return {
    weight,
    elasticity: weight * skuAssumption + (1 - weight) * familyAssumption,
  };
}

export function evaluatePrice(price, input, elasticities) {
  const values = elasticities.map((e) => {
    const quantity = input.baseUnits * (price / input.basePrice) ** e;
    return {
      elasticity: e,
      quantity,
      revenue: price * quantity,
      profit: (price - input.cost) * quantity,
    };
  });
  if (!values.every((v) => Object.values(v).every(Number.isFinite)))
    throw new Error("Non-finite scenario");
  return {
    price,
    values,
    worstProfit: Math.min(...values.map((v) => v.profit)),
  };
}

export function priceDecision(input) {
  for (const name of [
    "basePrice",
    "baseUnits",
    "cost",
    "minMargin",
    "maxChange",
    "skuElasticity",
    "familyElasticity",
    "activeWeeks",
  ])
    finite(input[name], name);
  if (
    input.basePrice <= 0 ||
    input.basePrice > 1000000 ||
    input.baseUnits < 0 ||
    input.cost < 0 ||
    input.minMargin < 0 ||
    input.minMargin >= 1 ||
    input.maxChange < 0 ||
    input.maxChange > 0.5
  )
    throw new Error("Inputs outside supported range");
  if (
    input.competitorCeiling !== null &&
    input.competitorCeiling !== undefined
  ) {
    finite(input.competitorCeiling, "market ceiling");
    if (input.competitorCeiling <= 0)
      throw new Error("Market ceiling must be positive");
  }
  const shared = sharedElasticity(
    input.skuElasticity,
    input.familyElasticity,
    input.activeWeeks,
  );
  const elasticities = [
    shared.elasticity - 0.6,
    shared.elasticity,
    Math.min(-0.05, shared.elasticity + 0.6),
  ];
  const floors = [
    { name: "margin", value: input.cost / (1 - input.minMargin) },
    { name: "change", value: input.basePrice * (1 - input.maxChange) },
  ];
  const ceilings = [
    { name: "change", value: input.basePrice * (1 + input.maxChange) },
  ];
  if (input.competitorCeiling != null)
    ceilings.push({ name: "market", value: input.competitorCeiling });
  const lowerCents = Math.max(
    1,
    Math.ceil(Math.max(...floors.map((r) => r.value)) * 100 - 1e-8),
  );
  const upperCents = Math.floor(
    Math.min(...ceilings.map((r) => r.value)) * 100 + 1e-8,
  );
  const common = {
    shared,
    elasticities,
    floors,
    ceilings,
    lower: lowerCents / 100,
    upper: upperCents / 100,
    input: { ...input },
    trainedModel: false,
  };
  if (lowerCents > upperCents)
    return { ...common, status: "infeasible", candidate: null, candidates: [] };
  if (input.baseUnits === 0)
    return {
      ...common,
      status: "insufficient_sales",
      candidate: null,
      candidates: [],
    };
  const step = Math.max(1, Math.ceil((upperCents - lowerCents) / 1000));
  const cents = new Set([lowerCents, upperCents]);
  for (let p = lowerCents; p <= upperCents; p += step) cents.add(p);
  const reference = Math.round(input.basePrice * 100);
  if (reference >= lowerCents && reference <= upperCents) cents.add(reference);
  const candidates = [...cents]
    .sort((a, b) => a - b)
    .map((p) => evaluatePrice(p / 100, input, elasticities));
  let best = candidates[0];
  for (const candidate of candidates.slice(1)) {
    if (
      candidate.worstProfit > best.worstProfit + 1e-9 ||
      (Math.abs(candidate.worstProfit - best.worstProfit) <= 1e-9 &&
        Math.abs(candidate.price - input.basePrice) <
          Math.abs(best.price - input.basePrice))
    )
      best = candidate;
  }
  return {
    ...common,
    status: "review_required",
    candidate: best,
    candidates,
    baseline: evaluatePrice(input.basePrice, input, elasticities),
    baselineFeasible: reference >= lowerCents && reference <= upperCents,
  };
}
