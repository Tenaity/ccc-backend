"""
Preferences Adapter for Scheduler Engine

This module provides hooks to integrate staff preferences into the scheduling engine.
Staff preferences influence shift assignments to improve work-life balance.
"""

from datetime import date
from typing import Dict, List, Optional, Set
from collections import defaultdict

from sqlalchemy.orm import Session
from models import Staff, StaffPreferences


class PreferencesAdapter:
    """Adapter to load and apply staff preferences in the scheduler."""

    def __init__(self, session: Session, year: int, month: int):
        self.session = session
        self.year = year
        self.month = month
        self._prefs_cache: Dict[int, StaffPreferences] = {}
        self._load_preferences()

    def _load_preferences(self):
        """Load all staff preferences into cache."""
        stmt = self.session.query(StaffPreferences).all()
        for pref in stmt:
            self._prefs_cache[pref.staff_id] = pref

    def get_preferences(self, staff_id: int) -> Optional[StaffPreferences]:
        """Get preferences for a specific staff member."""
        return self._prefs_cache.get(staff_id)

    def is_preferred_shift(self, staff_id: int, shift_code: str) -> bool:
        """Check if a shift is preferred by the staff member."""
        prefs = self.get_preferences(staff_id)
        if not prefs or not prefs.preferred_shifts:
            return False
        return shift_code in prefs.preferred_shifts

    def is_unavailable(self, staff_id: int, day: date) -> bool:
        """Check if staff member is unavailable on a specific day."""
        prefs = self.get_preferences(staff_id)
        if not prefs or not prefs.unavailable_days:
            return False

        day_str = day.isoformat()
        return day_str in prefs.unavailable_days

    def is_preferred_day_off(self, staff_id: int, day: date) -> bool:
        """Check if a day of week is a preferred day off."""
        prefs = self.get_preferences(staff_id)
        if not prefs or not prefs.preferred_days_off:
            return False

        # 0 = Monday, 6 = Sunday
        day_of_week = day.weekday()
        return day_of_week in prefs.preferred_days_off

    def get_max_consecutive_days(self, staff_id: int) -> int:
        """Get max consecutive working days preference (default 6)."""
        prefs = self.get_preferences(staff_id)
        if not prefs or prefs.max_consecutive_days is None:
            return 6  # Default
        return prefs.max_consecutive_days

    def filter_available_staff(
        self,
        staff_ids: List[int],
        day: date,
        shift_code: str
    ) -> List[int]:
        """
        Filter staff list to remove unavailable staff.

        Args:
            staff_ids: List of candidate staff IDs
            day: Date to check
            shift_code: Shift code being assigned

        Returns:
            Filtered list of available staff IDs
        """
        return [
            sid for sid in staff_ids
            if not self.is_unavailable(sid, day)
        ]

    def calculate_preference_weight(
        self,
        staff_id: int,
        day: date,
        shift_code: str,
        consecutive_days_worked: int = 0
    ) -> float:
        """
        Calculate a preference weight for staff assignment.
        Higher weight = better match with preferences.

        Weight factors:
        - Preferred shift: +10
        - Not on preferred day off: +5
        - Consecutive days below max: +3
        - Unavailable: -1000 (hard constraint)

        Args:
            staff_id: Staff member ID
            day: Date of assignment
            shift_code: Shift code
            consecutive_days_worked: Number of consecutive days already worked

        Returns:
            Float weight score
        """
        prefs = self.get_preferences(staff_id)

        # Hard constraint: unavailable
        if self.is_unavailable(staff_id, day):
            return -1000.0

        weight = 0.0

        if not prefs:
            return weight

        # Preferred shift bonus
        if self.is_preferred_shift(staff_id, shift_code):
            weight += 10.0

        # Preferred day off penalty (working on preferred day off)
        if self.is_preferred_day_off(staff_id, day):
            weight -= 5.0
        else:
            weight += 2.0  # Small bonus for not working on preferred day off

        # Consecutive days constraint
        max_consecutive = self.get_max_consecutive_days(staff_id)
        if consecutive_days_worked < max_consecutive:
            weight += 3.0
        else:
            weight -= 8.0  # Penalty for exceeding max consecutive days

        return weight

    def get_staff_with_shift_preference(
        self,
        staff_ids: List[int],
        shift_code: str
    ) -> List[int]:
        """
        Get list of staff who prefer this shift type.

        Args:
            staff_ids: Candidate staff IDs
            shift_code: Shift code to check

        Returns:
            List of staff IDs who prefer this shift
        """
        return [
            sid for sid in staff_ids
            if self.is_preferred_shift(sid, shift_code)
        ]

    def sort_by_preference(
        self,
        staff_ids: List[int],
        day: date,
        shift_code: str,
        consecutive_tracker: Optional[Dict[int, int]] = None
    ) -> List[int]:
        """
        Sort staff list by preference weight (descending).

        Args:
            staff_ids: List of staff IDs to sort
            day: Date for the assignment
            shift_code: Shift code
            consecutive_tracker: Dict mapping staff_id -> consecutive days worked

        Returns:
            Sorted list of staff IDs (best matches first)
        """
        if not consecutive_tracker:
            consecutive_tracker = {}

        def get_weight(sid: int) -> float:
            consecutive = consecutive_tracker.get(sid, 0)
            return self.calculate_preference_weight(sid, day, shift_code, consecutive)

        return sorted(staff_ids, key=get_weight, reverse=True)

    def get_preference_stats(self, staff_id: int) -> dict:
        """Get summary statistics about staff preferences."""
        prefs = self.get_preferences(staff_id)
        if not prefs:
            return {
                "has_preferences": False,
                "preferred_shift_count": 0,
                "unavailable_days_count": 0,
                "preferred_days_off_count": 0,
                "max_consecutive_days": 6,
            }

        return {
            "has_preferences": True,
            "preferred_shift_count": len(prefs.preferred_shifts or []),
            "unavailable_days_count": len(prefs.unavailable_days or []),
            "preferred_days_off_count": len(prefs.preferred_days_off or []),
            "max_consecutive_days": prefs.max_consecutive_days or 6,
            "notes": prefs.notes,
        }


def create_preferences_adapter(
    session: Session,
    year: int,
    month: int
) -> PreferencesAdapter:
    """Factory function to create a preferences adapter."""
    return PreferencesAdapter(session, year, month)
