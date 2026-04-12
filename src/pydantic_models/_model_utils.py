"""
Helpers and abstract models.
"""

from typing import Optional, List, Any, TypeVar
from pydantic import BaseModel, ValidationError
from ..utils.openai_utils import ConversationRetryError


# ============================================================================
# Mixin for List Deduplication
# ============================================================================


T = TypeVar('T')

def _dedupe_list(items: List[T]) -> List[T]:
    """
    Deduplicate list while preserving order.

    Uses dict.fromkeys() for hashable items (O(n) performance).
    Falls back to manual comparison for unhashable items.

    Args:
        items: List to deduplicate

    Returns:
        Deduplicated list with order preserved
    """
    if not items:
        return items
    try:
        # Fast path for hashable items
        return list(dict.fromkeys(items))
    except TypeError:
        # Fallback for unhashable items
        result = []
        for item in items:
            if item not in result:
                result.append(item)
        return result

def _recursive_list_dedupe_helper(obj: Any) -> Any:
    """
    Recursively deduplicate all lists in a nested object structure.

    Handles:
    - Pydantic models (recurses into all fields)
    - Lists (deduplicates and recurses into elements)
    - Dicts (recurses into values)
    - Other objects (returned as-is)

    Args:
        obj: Object to recursively deduplicate

    Returns:
        The same object with all nested lists deduplicated
    """
    if obj is None:
        return obj

    # Handle Pydantic BaseModel instances
    if isinstance(obj, BaseModel):
        # Recursively process all model fields
        for field_name in obj.__class__.model_fields.keys():
            field_value = getattr(obj, field_name)
            if field_value is not None:
                # Recursively process the field value
                processed_value = _recursive_list_dedupe_helper(field_value)
                # Only update if the value changed (for immutables this is a no-op)
                if processed_value is not field_value:
                    object.__setattr__(obj, field_name, processed_value)

        return obj

    # Handle lists
    elif isinstance(obj, list):
        # First deduplicate the list itself
        deduped = _dedupe_list(obj)
        # Then recursively process each element
        return [_recursive_list_dedupe_helper(item) for item in deduped]

    # Handle dicts
    elif isinstance(obj, dict):
        # Recursively process all values
        return {key: _recursive_list_dedupe_helper(value) for key, value in obj.items()}

    # For all other types (str, int, float, None, etc.), return as-is
    else:
        return obj

class ListDedupeMixin:
    """
    Mixin providing list deduplication functionality for Pydantic models.

    Adds a `list_dedupe()` method that can operate in two modes:
    - Shallow (recursive=False): Only deduplicates direct List fields
    - Deep (recursive=True): Recursively deduplicates all lists at all nesting levels
    """

    def list_dedupe(self, recursive: bool = False):
        """
        Deduplicate all List fields in this model.

        Args:
            recursive: If True, recursively deduplicates all nested lists.
                      If False (default), only deduplicates direct List fields.

        Returns:
            self (for method chaining)

        Examples:
            # Shallow deduplication (only direct lists)
            metadata.list_dedupe()

            # Deep deduplication (all nested lists)
            doc.list_dedupe(recursive=True)
        """
        if recursive:
            # Use the recursive helper function
            _recursive_list_dedupe_helper(self)
        else:
            # Shallow deduplication: only process direct List fields
            for field_name, field_info in self.__class__.model_fields.items():
                field_value = getattr(self, field_name)

                # Check if the field is a List type
                if field_value is not None and isinstance(field_value, list):
                    # Deduplicate and update
                    deduped = _dedupe_list(field_value)
                    object.__setattr__(self, field_name, deduped)

        return self


# ============================================================================
# Constants and helper functions
# ============================================================================


# Placeholder values that should be treated as None/empty
EMPTY_PLACEHOLDER_VALUES = {
    "",
    "无",
    "null",
    "NULL",
    "None",
    "NONE",
    "无信息",
    "不适用",
    "N/A",
    "n/a",
    "NA",
    "na",
    "NaN",
    "nan"
}

def clean_string_value(value: Any) -> Optional[str]:
    """
    Clean a string value by removing placeholder values that should be None.

    Args:
        value: The value to clean (can be str, None, or other types)

    Returns:
        None if the value is a placeholder, otherwise the original value
    """
    if value is None:
        return None

    if not isinstance(value, str):
        return value

    # Strip whitespace
    cleaned = value.strip()

    # Check if it's a placeholder value
    if cleaned in EMPTY_PLACEHOLDER_VALUES:
        return None

    # Check if it's an empty string after stripping
    if not cleaned:
        return None

    return cleaned


# ============================================================================
# Constants and helper functions
# ============================================================================


class DuplicateCategoryError(ConversationRetryError):
    """Custom error for duplicate requirement categories in Style B policies"""
    def __init__(self, message: str, raw_input: str = None):
        """Initialize with message and optional raw input."""
        ConversationRetryError.__init__(self, message, raw_input)
        Exception.__init__(self, message)

    
class ResidenceConditionConflictError(ConversationRetryError):
    """Custom error for conflicting residence conditions in cross-check policies"""
    def __init__(self, message: str, raw_input: str = None):
        """Initialize with message and optional raw input."""
        ConversationRetryError.__init__(self, message, raw_input)
        Exception.__init__(self, message)
