""" dataset

Dataset response serializers.
"""

from typing import Optional, Dict, Any

from app.modules.dataset.domain.models import Dataset, DatasetDocument, DatasetIndex
from app.modules.dataset.application.schemas import (
    DatasetResponse,
    DocumentResponse,
    IndexResponse,
)


def serialize_dataset(dataset: Dataset) -> Dict[str, Any]:
    """Serialize dataset model to dictionary.
    
    Args:
        dataset: Dataset model instance.
        
    Returns:
        Serialized dataset dictionary.
    """
    return DatasetResponse.model_validate(dataset).model_dump()


def serialize_document(document: DatasetDocument) -> Dict[str, Any]:
    """Serialize document model to dictionary.
    
    Args:
        document: DatasetDocument model instance.
        
    Returns:
        Serialized document dictionary.
    """
    return DocumentResponse.model_validate(document).model_dump()


def serialize_index(index: DatasetIndex) -> Dict[str, Any]:
    """Serialize index model to dictionary.
    
    Args:
        index: DatasetIndex model instance.
        
    Returns:
        Serialized index dictionary.
    """
    return IndexResponse.model_validate(index).model_dump()

