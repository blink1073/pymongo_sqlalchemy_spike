"""Test fixtures: session mongod lifecycle + seeded collections."""
import subprocess
import time
from datetime import datetime

import pytest
from pymongo import MongoClient

MONGO_PORT = 27217
MONGO_URI = f"mongodb://127.0.0.1:{MONGO_PORT}"
DB = "sqltest"
COLL = "test"


def _mongod_running():
    try:
        MongoClient(MONGO_URI, serverSelectionTimeoutMS=300).admin.command("ping")
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def mongo_uri(tmp_path_factory):
    """Start a scratch mongod on 127.0.0.1:27217 (reuse one already running)."""
    if _mongod_running():
        yield MONGO_URI
        return
    dbpath = tmp_path_factory.mktemp("mongodata")
    proc = subprocess.Popen(
        ["mongod", "--dbpath", str(dbpath), "--port", str(MONGO_PORT),
         "--bind_ip", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    client = None
    try:
        for _ in range(120):
            try:
                client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=300)
                client.admin.command("ping")
                break
            except Exception:
                client = None
                time.sleep(0.25)
        if client is None:
            proc.terminate()
            raise RuntimeError("mongod did not become ready")
        yield MONGO_URI
    finally:
        if client is not None:
            client.close()
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="session")
def seeded_client(mongo_uri):
    """Seed sqltest.test (mirrors the sqlite fixture table) and sqltest.types."""
    client = MongoClient(mongo_uri)
    db = client[DB]
    db[COLL].insert_many([
        {"id": 1, "name": "foo", "income": 2500.32, "unique_test": "u1"},
        {"id": 2, "name": "bar", "income": 100.5, "unique_test": "u2"},
        {"id": 3, "name": "baz", "income": 7.25, "unique_test": "u3"},
    ])
    db["types"].insert_one({
        "i": 42, "f": 1.5, "s": "text", "b": True, "n": None,
        "d": datetime(2024, 5, 6, 7, 8, 9),
    })
    yield client
    client.drop_database(DB)
    client.close()


@pytest.fixture()
def conn(seeded_client):
    """An open mongosql_dbapi connection against the seeded database."""
    import mongosql_dbapi
    connection = mongosql_dbapi.connect(uri=MONGO_URI, database=DB)
    yield connection
    connection.close()
