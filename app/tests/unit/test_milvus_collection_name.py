"""test_milvus_collection_name

Unit tests for Milvus collection name normalization.
"""

from app.adapters.vector.milvus import MilvusVectorPort


def test_normalize_collection_name_strips_invalid_chars():
    name = "ds:ds_id_abcd:idx_id_1234"
    normalized = MilvusVectorPort._normalize_collection_name(name)
    assert normalized == "ds_ds_id_abcd_idx_id_1234"


def test_normalize_collection_name_prefixes_digit_start():
    name = "123_invalid"
    normalized = MilvusVectorPort._normalize_collection_name(name)
    assert normalized.startswith("c_")


def test_normalize_collection_name_limits_length():
    name = "a" * 300
    normalized = MilvusVectorPort._normalize_collection_name(name)
    assert len(normalized) <= 255
