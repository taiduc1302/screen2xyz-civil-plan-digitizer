"""Frozen 16-metric evaluator for observations joined after classification."""

from __future__ import annotations

import math
from decimal import Decimal
from statistics import mean
from typing import Any

from .parser import known_clean_result


def _rate(
    numerator: int,
    denominator: int,
    target_operator: str | None = None,
    target_value: float | None = None,
) -> dict[str, Any]:
    if denominator == 0:
        return {
            "numerator": numerator, "denominator": denominator, "rate": None,
            "target_operator": target_operator, "target_value": target_value,
            "status": "not_applicable",
        }
    rate = round(numerator / denominator, 6)
    if target_operator is None:
        status = "report_only"
    elif target_operator == "eq":
        status = "met" if numerator == denominator * Decimal(str(target_value)) else "missed"
    elif target_operator == "gte":
        status = "met" if Decimal(numerator) / Decimal(denominator) >= Decimal(str(target_value)) else "missed"
    else:
        raise ValueError("unsupported target operator")
    return {
        "numerator": numerator, "denominator": denominator, "rate": rate,
        "target_operator": target_operator, "target_value": target_value, "status": status,
    }


def _count(count: int, population: int, target_operator: str | None, target_value: int | None) -> dict[str, Any]:
    status = "report_only"
    if target_operator == "eq":
        status = "met" if count == target_value else "missed"
    return {
        "count": count, "population": population, "target_operator": target_operator,
        "target_value": target_value, "status": status,
    }


def _statistics(values: list[Decimal]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "max": None}
    average = sum(values) / Decimal(len(values))
    return {"count": len(values), "mean": float(average), "max": float(max(values))}


def _timing(durations: list[int]) -> dict[str, Any]:
    ordered = sorted(durations)
    if not ordered:
        per = {"count": 0, "mean": None, "p50_nearest_rank": None, "p95_nearest_rank": None, "max": None}
    else:
        per = {
            "count": len(ordered),
            "mean": round(mean(ordered), 6),
            "p50_nearest_rank": ordered[math.ceil(0.50 * len(ordered)) - 1],
            "p95_nearest_rank": ordered[math.ceil(0.95 * len(ordered)) - 1],
            "max": max(ordered),
        }
    return {"unit": "ms", "total_ms": sum(durations), "per_reading": per}


def calculate_metrics(
    ground_truth: list[dict[str, str]],
    classifications: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
    repeatability: dict[str, Any],
) -> dict[str, Any]:
    observed = {row["scenario_id"]: row for row in classifications}
    expected_valid = [row for row in ground_truth if row["expected_disposition"] == "ACCEPT"]
    expected_invalid = [row for row in ground_truth if row["expected_disposition"] != "ACCEPT"]

    def exact(row: dict[str, str], field: str, parsed: str) -> bool:
        return bool(row[field]) and row[field] == parsed

    latitude_exact = sum(exact(row, "expected_latitude", observed[row["scenario_id"]]["parsed_latitude"]) for row in expected_valid)
    longitude_exact = sum(exact(row, "expected_longitude", observed[row["scenario_id"]]["parsed_longitude"]) for row in expected_valid)
    elevation_exact = sum(exact(row, "expected_elevation_m", observed[row["scenario_id"]]["parsed_elevation_m"]) for row in expected_valid)

    def all_exact(row: dict[str, str]) -> bool:
        actual = observed[row["scenario_id"]]
        return (
            exact(row, "expected_latitude", actual["parsed_latitude"])
            and exact(row, "expected_longitude", actual["parsed_longitude"])
            and exact(row, "expected_elevation_m", actual["parsed_elevation_m"])
        )

    baseline_valid = [row for row in expected_valid if row["condition_id"] == "baseline"]
    complete_baseline = sum(all_exact(row) for row in baseline_valid)
    complete_all = sum(all_exact(row) for row in expected_valid)
    invalid_rejected = sum(observed[row["scenario_id"]]["classification"] == "REJECTED" for row in expected_invalid)
    false_accepts = len(expected_invalid) - invalid_rejected
    false_rejects = sum(observed[row["scenario_id"]]["classification"] == "REJECTED" for row in expected_valid)
    accepted_correct = sum(
        observed[row["scenario_id"]]["classification"] == "ACCEPTED" and all_exact(row)
        for row in expected_valid
    )
    rejected_total = sum(row["classification"] == "REJECTED" for row in classifications)
    duplicate_rows = [row for row in ground_truth if row["expected_primary_code"] == "DUPLICATE_READING"]
    stale_rows = [row for row in ground_truth if row["expected_primary_code"] == "STALE_READING"]
    duplicate_correct = sum(observed[row["scenario_id"]]["primary_code"] == "DUPLICATE_READING" for row in duplicate_rows)
    stale_correct = sum(observed[row["scenario_id"]]["primary_code"] == "STALE_READING" for row in stale_rows)

    lat_errors: list[Decimal] = []
    lon_errors: list[Decimal] = []
    elev_errors: list[Decimal] = []
    for row in expected_valid:
        actual = observed[row["scenario_id"]]
        if actual["classification"] != "ACCEPTED":
            continue
        if actual["parsed_latitude"] and actual["parsed_longitude"]:
            lat_errors.append(abs(Decimal(actual["parsed_latitude"]) - Decimal(row["expected_latitude"])))
            lon_errors.append(abs(Decimal(actual["parsed_longitude"]) - Decimal(row["expected_longitude"])))
        if actual["parsed_elevation_m"]:
            elev_errors.append(abs(Decimal(actual["parsed_elevation_m"]) - Decimal(row["expected_elevation_m"])))

    clean_passed, clean_total = known_clean_result()
    failed_ids = [
        row["scenario_id"]
        for row in ground_truth
        if (
            (row["expected_disposition"] == "ACCEPT" and not all_exact(row))
            or (row["expected_disposition"] != "ACCEPT" and observed[row["scenario_id"]]["classification"] != "REJECTED")
            or (row["expected_primary_code"] and observed[row["scenario_id"]]["primary_code"] != row["expected_primary_code"])
        )
    ]
    metrics = {
        "latitude_field_exact_match": _rate(latitude_exact, 42),
        "longitude_field_exact_match": _rate(longitude_exact, 42),
        "elevation_field_exact_match": _rate(elevation_exact, 42),
        "complete_three_field_exact_match": {
            "baseline": _rate(complete_baseline, 14, "gte", 0.95),
            "all_valid": _rate(complete_all, 42, "gte", 0.9),
        },
        "parser_success_known_clean": _rate(clean_passed, clean_total, "eq", 1.0),
        "end_to_end_accepted_reading_correctness": _rate(accepted_correct, 42),
        "rejected_reading_rate": _rate(rejected_total, 60),
        "expected_invalid_rejection": _rate(invalid_rejected, 18, "gte", 0.95),
        "false_accept_count": _count(false_accepts, 18, "eq", 0),
        "false_reject_count": _count(false_rejects, 42, None, None),
        "duplicate_detection": _rate(duplicate_correct, 6, "eq", 1.0),
        "stale_detection": _rate(stale_correct, 6, "eq", 1.0),
        "coordinate_error_accepted": {
            "eligible_count": min(len(lat_errors), len(lon_errors)),
            "latitude_degrees": _statistics(lat_errors),
            "longitude_degrees": _statistics(lon_errors),
        },
        "elevation_error_accepted": {"eligible_count": len(elev_errors), "metres": _statistics(elev_errors)},
        "processing_time": _timing([int(row["duration_ms"]) for row in raw_rows]),
        "repeatability_difference": repeatability,
    }
    return {
        "schema_version": "1.0",
        "scenario_count": 60,
        "expected_valid_count": 42,
        "expected_invalid_count": 18,
        "metrics": metrics,
        "diagnostics": {
            "ocr_failure_count": sum(row["ocr_status"] == "FAILURE" for row in raw_rows),
            "ocr_timeout_count": sum(row["ocr_status"] == "TIMEOUT" for row in raw_rows),
            "failed_scenario_ids": failed_ids,
        },
    }
