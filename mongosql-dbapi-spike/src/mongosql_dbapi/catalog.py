"""Pure-Python catalog derivation: sample documents via PyMongo, infer $jsonSchema.

Stands in for py_schema_builder_library (which embeds the Rust MongoDB driver).
Output matches its contract: {"$jsonSchema": {...}} per collection.

Typing rules (documented in README limitations): bool/int/float/str/bytes map to
bool/long/double/string/binData; datetime and date to "date"; dict/list to
object/array; ObjectId/Decimal128 to objectId/decimal; anything unrecognized
(including exotic BSON like Timestamp or Regex) degrades to "string", matching
the bindings' stringification.
"""

_NAMED_TYPES = {
    "ObjectId": "objectId",
    "Decimal128": "decimal",
    "datetime": "date",
    "date": "date",
}

_PRIMITIVES = {
    bool: "bool",
    int: "long",
    float: "double",
    str: "string",
    bytes: "binData",
}


def _bson_type_of(value):
    if value is None:
        return "null"
    t = type(value)
    if t in _PRIMITIVES:
        return _PRIMITIVES[t]
    if t is list:
        return "array"
    if t is dict:
        return "object"
    return _NAMED_TYPES.get(t.__name__, "string")


def _dedupe(schemas):
    seen, out = set(), []
    for schema in schemas:
        key = repr(schema)
        if key not in seen:
            seen.add(key)
            out.append(schema)
    return out


def _field_schema(values):
    schemas = []
    for value in values:
        bson_type = _bson_type_of(value)
        if bson_type == "object" and value:
            schemas.append(_bare_object_schema([value]))
        elif bson_type == "array":
            items = _field_schema(list(value)) if value else {"bsonType": "string"}
            schemas.append({"bsonType": "array", "items": items})
        else:
            schemas.append({"bsonType": bson_type})
    uniq = _dedupe(schemas)
    if len(uniq) == 1:
        return uniq[0]
    return {"anyOf": uniq}


def _bare_object_schema(documents):
    """Return a bare (unwrapped) object schema for one or more documents."""
    present, total = {}, 0
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        total += 1
        for key, value in doc.items():
            present.setdefault(key, []).append(value)
    required = sorted(
        key for key, vals in present.items() if total and len(vals) == total)
    props = {key: _field_schema(vals) for key, vals in present.items()}
    return {"bsonType": "object", "properties": props, "required": required}


def infer_schema(documents):
    """Return a $jsonSchema-wrapped schema inferred from the given documents."""
    return {"$jsonSchema": _bare_object_schema(documents)}


def build_catalog(client, database, sample_size=100, collections=None):
    """Sample every collection in `database` and return {db: {coll: schema}}."""
    names = (collections if collections is not None
             else client[database].list_collection_names())
    catalog = {}
    for name in names:
        docs = list(client[database][name].find({}, limit=sample_size))
        catalog[name] = infer_schema(docs)
    return {database: catalog}
