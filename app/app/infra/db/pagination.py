""" pagination

Cursor pagination helpers.
"""

from typing import Generic, TypeVar, Optional, List, Dict, Any
from pydantic import BaseModel

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
