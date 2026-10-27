from conftest import DB, COLL


def test_mongod_fixture_reachable_and_seeded(seeded_client):
    assert seeded_client.admin.command("ping")["ok"]
    docs = list(seeded_client[DB][COLL].find({}))
    assert [d["name"] for d in sorted(docs, key=lambda d: d["id"])] == [
        "foo", "bar", "baz"]
