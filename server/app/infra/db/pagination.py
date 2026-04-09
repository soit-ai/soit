""" pagination

Cursor pagination helpers with support for both offset-based and cursor-based (timestamp+id) pagination.
"""

from typing import Generic, TypeVar, Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel
import json
import base64

T = TypeVar("T")


class PageToken(BaseModel):
    """Cursor-based pagination token."""
    
    offset: int
    """Offset for pagination."""
    
    limit: int
    """Page size."""
    
    @classmethod
    def from_string(cls, token_str: str) -> "PageToken":
        """Parse page token from string.
        
        Args:
            token_str: Base64 or JSON encoded token string.
            
        Returns:
            PageToken instance.
        """
        # Simple implementation: assume JSON format
        import json
        import base64
        try:
            decoded = base64.b64decode(token_str).decode("utf-8")
            data = json.loads(decoded)
            return cls(**data)
        except Exception:
            # Fallback: try direct JSON
            try:
                data = json.loads(token_str)
                return cls(**data)
            except Exception:
                raise ValueError("Invalid page token")
    
    def to_string(self) -> str:
        """Encode page token to string.
        
        Returns:
            Base64 encoded token string.
        """
        import json
        import base64
        data = self.model_dump()
        json_str = json.dumps(data)
        return base64.b64encode(json_str.encode("utf-8")).decode("utf-8")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response with cursor-based pagination."""
    
    items: List[T]
    """Items in current page."""
    
    next_page_token: Optional[str] = None
    """Token for next page, None if last page."""
    
    page_size: int
    """Page size (number of items returned)."""
    
    @classmethod
    def create(
        cls,
        items: List[T],
        page_size: int,
        has_next: bool = False,
        next_offset: Optional[int] = None,
    ) -> "PaginatedResponse[T]":
        """Create paginated response.
        
        Args:
            items: Items in current page.
            page_size: Page size.
            has_next: Whether there is a next page.
            next_offset: Next page offset (if has_next is True).
            
        Returns:
            PaginatedResponse instance.
        """
        next_token = None
        if has_next and next_offset is not None:
            next_token = PageToken(offset=next_offset, limit=page_size).to_string()
        
        return cls(
            items=items,
            next_page_token=next_token,
            page_size=len(items),
        )


def parse_page_params(
    page_token: Optional[str] = None,
    page_size: int = 20,
    max_page_size: int = 100,
) -> tuple[int, Optional[PageToken]]:
    """Parse pagination parameters.
    
    Args:
        page_token: Optional page token string.
        page_size: Requested page size.
        max_page_size: Maximum allowed page size.
        
    Returns:
        Tuple of (limit, page_token_obj).
    """
    # Clamp page size
    limit = min(max(1, page_size), max_page_size)
    
    # Parse page token
    token_obj = None
    if page_token:
        try:
            token_obj = PageToken.from_string(page_token)
            limit = token_obj.limit
        except ValueError:
            # Invalid token, ignore
            pass
    
    return limit, token_obj


class PaginatedResult(BaseModel, Generic[T]):
    """Paginated result for repository-level helpers."""

    items: List[T]
    next_page_token: Optional[str] = None
    page_size: int


def paginate_query(
    query: Any,
    page_size: int,
    page_token: Optional[str] = None,
    exec_fn: Optional[Any] = None,
) -> PaginatedResult[T]:
    """Paginate a SQLAlchemy/SQLModel query with PageToken support."""
    limit, token_obj = parse_page_params(page_token, page_size)
    offset = token_obj.offset if token_obj else 0

    paged = query.offset(offset).limit(limit + 1)
    if exec_fn:
        results = list(exec_fn(paged).all())
    else:
        results = list(paged.all())
    if results and hasattr(results[0], "_mapping"):
        results = [row[0] for row in results]
    has_next = len(results) > limit
    items = results[:limit]
    next_offset = offset + len(items) if has_next else None

    next_token = None
    if has_next and next_offset is not None:
        next_token = PageToken(offset=next_offset, limit=limit).to_string()

    return PaginatedResult(items=items, next_page_token=next_token, page_size=len(items))


# ============================================================================
# Cursor-based pagination (timestamp + ID for time-ordered data)
# ============================================================================


class CursorToken(BaseModel):
    """Cursor-based pagination token using timestamp + ID."""

    scope: str
    """Scope identifier to prevent token reuse across different lists."""

    limit: int
    """Page size."""

    cursor_at: Optional[str] = None
    """ISO timestamp of cursor position."""

    cursor_id: Optional[str] = None
    """ID at cursor position (for tie-breaking)."""

    @classmethod
    def from_string(cls, token_str: str) -> "CursorToken":
        """Parse cursor token from base64-encoded JSON string.

        Args:
            token_str: Base64-encoded token string.

        Returns:
            CursorToken instance.

        Raises:
            ValueError: If token is invalid.
        """
        try:
            decoded = base64.b64decode(token_str).decode("utf-8")
            data = json.loads(decoded)
            return cls(**data)
        except Exception as e:
            raise ValueError(f"Invalid cursor token: {e}")

    def to_string(self) -> str:
        """Encode cursor token to base64 JSON string.

        Returns:
            Base64-encoded token string.
        """
        data = self.model_dump(exclude_none=True)
        json_str = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
        return base64.b64encode(json_str.encode("utf-8")).decode("utf-8")


def encode_cursor_token(
    scope: str,
    limit: int,
    cursor_at: Optional[datetime] = None,
    cursor_id: Optional[str] = None,
) -> Optional[str]:
    """Encode cursor pagination token.

    Args:
        scope: Scope identifier (e.g., "messages", "conversations").
        limit: Page size.
        cursor_at: Cursor timestamp (for time-ordered pagination).
        cursor_id: Cursor ID (for tie-breaking).

    Returns:
        Base64-encoded token, or None if no cursor data.
    """
    if not cursor_at and not cursor_id:
        return None

    token = CursorToken(
        scope=scope,
        limit=limit,
        cursor_at=cursor_at.isoformat() if cursor_at else None,
        cursor_id=cursor_id,
    )
    return token.to_string()


def decode_cursor_token(
    token_str: str,
    expected_scope: str,
    default_limit: int = 20,
    max_limit: int = 100,
) -> tuple[int, Optional[datetime], Optional[str]]:
    """Decode cursor pagination token.

    Args:
        token_str: Base64-encoded token string.
        expected_scope: Expected scope identifier.
        default_limit: Default page size if not in token.
        max_limit: Maximum allowed page size.

    Returns:
        Tuple of (limit, cursor_at, cursor_id).
        - limit: Clamped page size.
        - cursor_at: Cursor timestamp (None if not present).
        - cursor_id: Cursor ID (None if not present).
    """
    if not token_str:
        return clamp_page_size(default_limit, max_limit), None, None

    try:
        token = CursorToken.from_string(token_str)

        # Verify scope matches
        if token.scope != expected_scope:
            return clamp_page_size(default_limit, max_limit), None, None

        # Parse limit
        limit = clamp_page_size(token.limit, max_limit)

        # Parse cursor_at
        cursor_at = None
        if token.cursor_at:
            try:
                cursor_at = datetime.fromisoformat(token.cursor_at)
            except (TypeError, ValueError):
                pass

        # Parse cursor_id
        cursor_id = token.cursor_id

        if cursor_at is None and cursor_id is None:
            return clamp_page_size(default_limit, max_limit), None, None

        return limit, cursor_at, cursor_id

    except (ValueError, TypeError):
        # Invalid token, return defaults
        return clamp_page_size(default_limit, max_limit), None, None


def clamp_page_size(size: int, max_size: int = 100, min_size: int = 1) -> int:
    """Clamp page size to valid range.

    Args:
        size: Requested page size.
        max_size: Maximum allowed size.
        min_size: Minimum allowed size.

    Returns:
        Clamped page size.
    """
    return min(max(min_size, size), max_size)
