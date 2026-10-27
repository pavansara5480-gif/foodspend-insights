"""Scalar formulas. Every aggregate in the project is built from these."""
from __future__ import annotations

from .constants import NUTRIENTS, STATUS_ABOVE, STATUS_BELOW, STATUS_INSUFFICIENT, STATUS_WITHIN


class UnitMismatch(ValueError):
    pass


def nutrient_amounts(amount: float, unit: str, basis_quantity: float, basis_unit: str,
                     values: dict) -> dict:
    """Scale nutrient values given per `basis_quantity` `basis_unit` to `amount` `unit`.

    nutrient = (amount / basis_quantity) x value_per_basis
    e.g. per 100 g: 150 g of curd -> 1.5 x value per 100 g.
    Unknown values (None) stay None; they are never treated as zero.
    """
    if unit != basis_unit:
        raise UnitMismatch(f"cannot scale {unit} against a {basis_unit} basis")
    factor = amount / basis_quantity
    return {n: None if values.get(n) is None else round(values[n] * factor, 2) for n in NUTRIENTS}


def order_final_total(subtotal: float, discount: float, tax: float, delivery_fee: float, other: float) -> float:
    """Final total = items subtotal - order discount + tax + delivery fee + other charges."""
    return round(subtotal - discount + tax + delivery_fee + other, 2)


def line_total(quantity: float, unit_price: float, item_discount: float = 0.0) -> float:
    return round(quantity * unit_price - item_discount, 2)


def budget_metrics(cost: float, budget: float | None) -> dict:
    """Remaining budget = budget - cost; utilisation % = cost / budget x 100 (None when budget <= 0)."""
    if budget is None:
        return {"budget": None, "cost": round(cost, 2), "remaining": None, "utilization_pct": None,
                "within_budget": None}
    return {
        "budget": round(budget, 2),
        "cost": round(cost, 2),
        "remaining": round(budget - cost, 2),
        "utilization_pct": round(cost / budget * 100, 1) if budget > 0 else None,
        "within_budget": cost <= budget,
    }


def goal_status(value: float | None, direction: str, target: float | None = None,
                lower: float | None = None, upper: float | None = None) -> str:
    """Status label against a documented target.

    at_least: below target -> "Below target", otherwise "Within range" (exceeding a minimum is not scored higher)
    at_most:  above target -> "Above target", otherwise "Within range"
    range:    compares with [lower, upper]
    Missing value or missing reference -> "Insufficient data".
    """
    if value is None:
        return STATUS_INSUFFICIENT
    if direction == "at_least":
        if target is None:
            return STATUS_INSUFFICIENT
        return STATUS_BELOW if value < target else STATUS_WITHIN
    if direction == "at_most":
        if target is None:
            return STATUS_INSUFFICIENT
        return STATUS_ABOVE if value > target else STATUS_WITHIN
    if direction == "range":
        if lower is None and upper is None:
            return STATUS_INSUFFICIENT
        if lower is not None and value < lower:
            return STATUS_BELOW
        if upper is not None and value > upper:
            return STATUS_ABOVE
        return STATUS_WITHIN
    raise ValueError(f"unknown direction {direction}")


def pct(part: float | None, whole: float | None) -> float | None:
    if part is None or not whole:
        return None
    return round(part / whole * 100, 1)
