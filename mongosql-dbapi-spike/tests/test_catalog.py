from conftest import DB
from mongosql_dbapi.catalog import build_catalog, infer_schema


def test_infer_schema_primitives():
    wrapped = infer_schema([{"a": 1, "b": "x", "c": 1.5, "d": True}])
    schema = wrapped["$jsonSchema"]
    assert schema["bsonType"] == "object"
    assert schema["properties"]["a"] == {"bsonType": "long"}
    assert schema["properties"]["b"] == {"bsonType": "string"}
    assert schema["properties"]["c"] == {"bsonType": "double"}
    assert schema["properties"]["d"] == {"bsonType": "bool"}
    assert schema["required"] == ["a", "b", "c", "d"]


def test_infer_schema_widens_mixed_types():
    schema = infer_schema([{"a": 1}, {"a": "x"}])["$jsonSchema"]
    assert "anyOf" in schema["properties"]["a"]


def test_infer_schema_nested_object():
    schema = infer_schema([{"o": {"x": 1, "y": "s"}}])["$jsonSchema"]
    inner = schema["properties"]["o"]
    if "$jsonSchema" in inner:  # nested objects reuse the wrapped form
        inner = inner["$jsonSchema"]
    assert inner["bsonType"] == "object"
    assert inner["properties"]["x"] == {"bsonType": "long"}


def test_infer_schema_null_and_missing_fields_not_required():
    schema = infer_schema([{"a": None}, {"b": 1}])["$jsonSchema"]
    assert schema["required"] == []
    assert _types(schema["properties"]["a"]) == {"null"}


def test_build_catalog_from_seeded(seeded_client):
    catalog = build_catalog(seeded_client, DB)
    schema = catalog[DB]["test"]["$jsonSchema"]
    assert set(schema["properties"]) == {"_id", "id", "name", "income", "unique_test"}
    assert _types(schema["properties"]["_id"]) == {"objectId"}
    assert _types(schema["properties"]["id"]) == {"long"}


def _types(field_schema):
    if "anyOf" in field_schema:
        return {v["bsonType"] for v in field_schema["anyOf"] if "bsonType" in v}
    return {field_schema["bsonType"]}
