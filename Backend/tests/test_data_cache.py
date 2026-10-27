import pandas as pd

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.data_cache import DataReferenceCache


def _fdf():
    schema = DataSchema(columns=[Column(name="x", type=DataType.NUMBER)])
    return FluxDataFrame(schema=schema, df=pd.DataFrame({"x": [1, 2, 3]}), total_row_count=3)


def test_put_returns_a_reference_id_and_get_resolves_it():
    cache = DataReferenceCache()
    fdf = _fdf()
    reference_id = cache.put(fdf)
    assert isinstance(reference_id, str) and reference_id
    assert cache.get(reference_id) is fdf


def test_get_unknown_reference_id_returns_none():
    cache = DataReferenceCache()
    assert cache.get("does-not-exist") is None


def test_put_generates_distinct_ids_for_repeated_calls():
    cache = DataReferenceCache()
    id1 = cache.put(_fdf())
    id2 = cache.put(_fdf())
    assert id1 != id2


def test_expired_entry_is_evicted_and_get_returns_none():
    cache = DataReferenceCache(ttl_seconds=-1)  # already expired the instant it's inserted
    reference_id = cache.put(_fdf())
    assert cache.get(reference_id) is None


def test_expired_entries_evicted_on_put_not_just_get():
    cache = DataReferenceCache(ttl_seconds=-1)
    stale_id = cache.put(_fdf())
    cache.put(_fdf())  # triggers eviction pass
    assert stale_id not in cache._entries


def test_non_expired_entry_survives_eviction_pass():
    cache = DataReferenceCache(ttl_seconds=3600)
    fdf = _fdf()
    reference_id = cache.put(fdf)
    cache.put(_fdf())  # another put triggers an eviction pass; this one shouldn't be swept
    assert cache.get(reference_id) is fdf
