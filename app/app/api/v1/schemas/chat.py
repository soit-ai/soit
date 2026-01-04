"""chat

Chat response serializers.
"""

from typing import Any, Dict

from app.modules.chat.application.schemas import (
    ConversationResponse,
    MessageResponse,
)


def serialize_conversation(conversation: Any) -> Dict[str, Any]:
    """Serialize conversation model to dictionary.

    Args:
        conversation: Conversation model instance.

    Returns:
        Serialized conversation dictionary.
    """
    return ConversationResponse.model_validate(conversation).model_dump()


def serialize_message(message: Any) -> Dict[str, Any]:
    """Serialize message model to dictionary.

    Args:
        message: Message model instance.

    Returns:
        Serialized message dictionary.
    """
    return MessageResponse.model_validate(message).model_dump()
