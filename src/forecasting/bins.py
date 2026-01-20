"""
Bin validation and value-to-bin mapping for binned continuous events.

Provides functions to validate bin specifications and map numeric values
to their corresponding bin IDs for binned_continuous event types.
"""

from typing import Dict, List, Any, Tuple, Optional


def validate_bin_spec(bin_spec: Dict[str, Any]) -> List[str]:
    """
    Validate bin specification.

    Rules:
    1. Bins must not overlap (accounting for include_min/include_max)
    2. Bins must cover entire domain OR have explicit UNDERFLOW/OVERFLOW
    3. Boundary ties resolved by include_min/include_max flags
    4. At least 2 bins required

    Args:
        bin_spec: Bin specification dictionary with 'bins' array

    Returns:
        List of validation errors (empty if valid).
    """
    errors = []

    bins = bin_spec.get("bins", [])
    if not bins:
        errors.append("bin_spec must contain 'bins' array")
        return errors

    if len(bins) < 2:
        errors.append("bin_spec must have at least 2 bins")
        return errors

    # Check for duplicate bin_ids
    bin_ids = [b.get("bin_id") for b in bins]
    seen_ids = set()
    for bid in bin_ids:
        if bid in seen_ids:
            errors.append(f"duplicate bin_id: {bid}")
        seen_ids.add(bid)

    # Check each bin has required fields
    for i, bin_def in enumerate(bins):
        if "bin_id" not in bin_def:
            errors.append(f"bin {i} missing required field 'bin_id'")
        if "label" not in bin_def:
            errors.append(f"bin {i} missing required field 'label'")

    # Check for overlaps
    if bins_have_overlap(bin_spec):
        errors.append("bins have overlapping ranges")

    # Check for gaps
    if bins_have_gaps(bin_spec):
        errors.append("bins have gaps in coverage")

    return errors


def bins_have_overlap(bin_spec: Dict[str, Any]) -> bool:
    """
    Check if any bins overlap.

    Two bins overlap if there exists a value that would match both bins.
    Boundary handling considers include_min/include_max flags.

    Args:
        bin_spec: Bin specification dictionary

    Returns:
        True if bins have overlapping ranges
    """
    bins = bin_spec.get("bins", [])
    if len(bins) < 2:
        return False

    # Extract boundaries with inclusion flags
    ranges = []
    for bin_def in bins:
        min_val = bin_def.get("min")
        max_val = bin_def.get("max")
        include_min = bin_def.get("include_min", True)
        include_max = bin_def.get("include_max", False)
        ranges.append({
            "bin_id": bin_def.get("bin_id"),
            "min": min_val,
            "max": max_val,
            "include_min": include_min,
            "include_max": include_max,
        })

    # Check each pair of bins for overlap
    for i in range(len(ranges)):
        for j in range(i + 1, len(ranges)):
            if _ranges_overlap(ranges[i], ranges[j]):
                return True

    return False


def _ranges_overlap(r1: Dict[str, Any], r2: Dict[str, Any]) -> bool:
    """
    Check if two ranges overlap.

    Args:
        r1, r2: Range dictionaries with min, max, include_min, include_max

    Returns:
        True if ranges overlap
    """
    # Handle unbounded ranges
    r1_min = r1["min"] if r1["min"] is not None else float("-inf")
    r1_max = r1["max"] if r1["max"] is not None else float("inf")
    r2_min = r2["min"] if r2["min"] is not None else float("-inf")
    r2_max = r2["max"] if r2["max"] is not None else float("inf")

    # Check if ranges are disjoint
    # r1 entirely below r2
    if r1_max < r2_min:
        return False
    if r1_max == r2_min:
        # Only overlap if r1 includes max AND r2 includes min
        if not (r1.get("include_max", False) and r2.get("include_min", True)):
            return False

    # r2 entirely below r1
    if r2_max < r1_min:
        return False
    if r2_max == r1_min:
        # Only overlap if r2 includes max AND r1 includes min
        if not (r2.get("include_max", False) and r1.get("include_min", True)):
            return False

    # If we get here, ranges overlap (or touch inclusively)
    # Need more careful check for boundary cases
    if r1_max == r2_min:
        return r1.get("include_max", False) and r2.get("include_min", True)
    if r2_max == r1_min:
        return r2.get("include_max", False) and r1.get("include_min", True)

    return True


def bins_have_gaps(bin_spec: Dict[str, Any]) -> bool:
    """
    Check if bins have gaps in coverage.

    Gaps exist when there are values that wouldn't match any bin.
    This checks for gaps between defined ranges (not unbounded edges).

    Args:
        bin_spec: Bin specification dictionary

    Returns:
        True if bins have gaps in coverage
    """
    bins = bin_spec.get("bins", [])
    if len(bins) < 2:
        return False

    # Extract and sort boundaries
    boundaries = []
    for bin_def in bins:
        min_val = bin_def.get("min")
        max_val = bin_def.get("max")
        include_min = bin_def.get("include_min", True)
        include_max = bin_def.get("include_max", False)

        if min_val is not None:
            boundaries.append({
                "value": min_val,
                "type": "min",
                "inclusive": include_min,
                "bin_id": bin_def.get("bin_id"),
            })
        if max_val is not None:
            boundaries.append({
                "value": max_val,
                "type": "max",
                "inclusive": include_max,
                "bin_id": bin_def.get("bin_id"),
            })

    if not boundaries:
        return False

    # Sort by value
    boundaries.sort(key=lambda x: x["value"])

    # Group boundaries at the same value
    value_groups = {}
    for b in boundaries:
        v = b["value"]
        if v not in value_groups:
            value_groups[v] = []
        value_groups[v].append(b)

    # For each boundary value, check if there's a gap
    # A gap exists at value V if:
    # - There's a max boundary at V that excludes V
    # - AND there's no min boundary at V that includes V
    # OR vice versa
    sorted_values = sorted(value_groups.keys())

    for i, v in enumerate(sorted_values):
        group = value_groups[v]
        has_inclusive_max = any(b["type"] == "max" and b["inclusive"] for b in group)
        has_inclusive_min = any(b["type"] == "min" and b["inclusive"] for b in group)
        has_exclusive_max = any(b["type"] == "max" and not b["inclusive"] for b in group)
        has_exclusive_min = any(b["type"] == "min" and not b["inclusive"] for b in group)

        # Gap at boundary point V if:
        # - One bin ends exclusively at V AND another starts exclusively at V
        # (meaning V itself is not covered)
        if has_exclusive_max and has_exclusive_min and not has_inclusive_max and not has_inclusive_min:
            return True

        # Check for gap between this boundary and the next
        if i < len(sorted_values) - 1:
            next_v = sorted_values[i + 1]
            # Is there coverage between v and next_v?
            # We need at least one bin whose range includes (v, next_v)
            covered = False
            for bin_def in bins:
                b_min = bin_def.get("min")
                b_max = bin_def.get("max")
                inc_min = bin_def.get("include_min", True)
                inc_max = bin_def.get("include_max", False)

                # Check if this bin covers values strictly between v and next_v
                # Bin must start at or before v (or be unbounded below)
                # Bin must end at or after next_v (or be unbounded above)
                bin_covers_below = (b_min is None or b_min < v or
                                   (b_min == v and inc_min))
                bin_covers_above = (b_max is None or b_max > next_v or
                                   (b_max == next_v and inc_max))

                # Actually we need to check if the bin covers the interval (v, next_v)
                # This means: bin_min <= v (with appropriate inclusivity) AND bin_max >= next_v
                effective_min = b_min if b_min is not None else float("-inf")
                effective_max = b_max if b_max is not None else float("inf")

                # The bin covers if effective_min <= v < next_v <= effective_max
                # But we need to be careful about boundary conditions
                if effective_max > v and effective_min < next_v:
                    covered = True
                    break

            if not covered:
                return True

    return False


def value_to_bin(value: Any, bin_spec: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """
    Map numeric value to bin_id.

    Args:
        value: Numeric value to map (can be None)
        bin_spec: Bin specification dictionary

    Returns:
        Tuple of (bin_id, error_reason)
        - If value is None: ("UNKNOWN", "missing_value")
        - If value out of range and no overflow bin: ("UNKNOWN", "out_of_range")
        - If valid: (bin_id, None)

    Boundary handling:
    - If value == boundary, use include_min/include_max to determine bin
    - Deterministic: check bins in order, first match wins
    """
    if value is None:
        return "UNKNOWN", "missing_value"

    try:
        num_value = float(value)
    except (ValueError, TypeError):
        return "UNKNOWN", "invalid_numeric_value"

    bins = bin_spec.get("bins", [])

    # Check bins in order - first match wins
    for bin_def in bins:
        min_val = bin_def.get("min")
        max_val = bin_def.get("max")
        include_min = bin_def.get("include_min", True)
        include_max = bin_def.get("include_max", False)

        # Check minimum boundary
        if min_val is not None:
            if include_min:
                if num_value < min_val:
                    continue
            else:
                if num_value <= min_val:
                    continue

        # Check maximum boundary
        if max_val is not None:
            if include_max:
                if num_value > max_val:
                    continue
            else:
                if num_value >= max_val:
                    continue

        # Value is within this bin
        return bin_def.get("bin_id"), None

    # No bin matched - value is out of range
    return "UNKNOWN", "out_of_range"


def get_bin_by_id(bin_spec: Dict[str, Any], bin_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a bin definition by its ID.

    Args:
        bin_spec: Bin specification dictionary
        bin_id: The bin ID to look up

    Returns:
        Bin definition dictionary, or None if not found
    """
    for bin_def in bin_spec.get("bins", []):
        if bin_def.get("bin_id") == bin_id:
            return bin_def
    return None


def get_bin_ids(bin_spec: Dict[str, Any]) -> List[str]:
    """
    Get list of all bin IDs from a bin specification.

    Args:
        bin_spec: Bin specification dictionary

    Returns:
        List of bin IDs in definition order
    """
    return [b.get("bin_id") for b in bin_spec.get("bins", [])]
