"""
Preferences Helper for Scheduler Engine

Helper functions to apply staff preferences when selecting candidates for shifts.
"""

from datetime import date
from typing import List, Optional
from collections import deque

from .core import Context


def filter_by_preferences(
    ctx: Context,
    candidates: List,
    day: date,
    shift_code: str,
    consecutive_tracker: Optional[dict] = None
) -> List:
    """
    Filter and sort candidates based on preferences.

    Args:
        ctx: Scheduler context
        candidates: List of staff objects to filter
        day: Date for the shift
        shift_code: Shift code being assigned
        consecutive_tracker: Optional dict tracking consecutive days worked

    Returns:
        Filtered and sorted list of candidates (best matches first)
    """
    if not ctx.preferences or not candidates:
        return candidates

    # Get staff IDs
    staff_ids = [s.id for s in candidates]

    # Filter out unavailable staff
    available_ids = ctx.preferences.filter_available_staff(
        staff_ids, day, shift_code
    )

    # If no one is available, return original list (fallback)
    if not available_ids:
        return candidates

    # Sort by preference weight
    sorted_ids = ctx.preferences.sort_by_preference(
        available_ids,
        day,
        shift_code,
        consecutive_tracker
    )

    # Map back to staff objects in sorted order
    id_to_staff = {s.id: s for s in candidates}
    return [id_to_staff[sid] for sid in sorted_ids if sid in id_to_staff]


def filter_queue_by_preferences(
    ctx: Context,
    queue: deque,
    day: date,
    shift_code: str,
    locked: set,
    used: set,
    max_results: int = None
) -> List:
    """
    Filter a queue of staff based on preferences and constraints.

    Args:
        ctx: Scheduler context
        queue: Deque of staff to check
        day: Date for assignment
        shift_code: Shift code
        locked: Set of locked staff IDs
        used: Set of already used staff IDs today
        max_results: Maximum number of results to return

    Returns:
        List of suitable staff objects
    """
    candidates = []
    checked = set()

    # Create a temporary list from queue to avoid modifying it
    queue_list = list(queue)

    for staff in queue_list:
        if staff.id in checked:
            continue
        checked.add(staff.id)

        # Skip if locked or already used
        if staff.id in locked or staff.id in used:
            continue

        # Check if staff is unavailable due to preferences
        if ctx.preferences and ctx.preferences.is_unavailable(staff.id, day):
            continue

        # Check quota
        if not ctx.can_take(staff.id, shift_code):
            continue

        candidates.append(staff)

        # Stop if we have enough
        if max_results and len(candidates) >= max_results:
            break

    # Apply preference sorting if we have candidates
    if candidates and ctx.preferences:
        candidates = filter_by_preferences(ctx, candidates, day, shift_code)

    return candidates


def get_preferred_staff_for_shift(
    ctx: Context,
    all_staff: List,
    shift_code: str,
    day: date,
    locked: set,
    used: set
) -> List:
    """
    Get staff who prefer this specific shift type.

    Args:
        ctx: Scheduler context
        all_staff: List of all available staff
        shift_code: Shift code to check preferences for
        day: Date of shift
        locked: Locked staff IDs
        used: Already used staff IDs

    Returns:
        List of staff who prefer this shift and are available
    """
    if not ctx.preferences:
        return []

    # Filter available staff
    available = [
        s for s in all_staff
        if s.id not in locked
        and s.id not in used
        and ctx.can_take(s.id, shift_code)
        and not ctx.preferences.is_unavailable(s.id, day)
    ]

    # Get those who prefer this shift
    preferred_ids = ctx.preferences.get_staff_with_shift_preference(
        [s.id for s in available],
        shift_code
    )

    # Map back to staff objects
    id_to_staff = {s.id: s for s in available}
    return [id_to_staff[sid] for sid in preferred_ids if sid in id_to_staff]


def should_skip_due_to_preferences(
    ctx: Context,
    staff_id: int,
    day: date
) -> bool:
    """
    Check if staff should be skipped due to hard preference constraints.

    Args:
        ctx: Scheduler context
        staff_id: Staff ID to check
        day: Date to check

    Returns:
        True if staff should be skipped (unavailable)
    """
    if not ctx.preferences:
        return False

    return ctx.preferences.is_unavailable(staff_id, day)
