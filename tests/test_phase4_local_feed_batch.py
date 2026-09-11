"""Local feed batching keeps the incumbent batch as the minimum."""

from scripts.phase4_local_feed_batch import build


def test_local_feed_batch_compiles_with_bounded_public_task_cluster():
    source = build()
    assert "distance(other_target, target) <= 3" in source
    assert "min(6, max(3, nearby_feed))" in source
    namespace = {}
    exec(source, namespace)
    assert callable(namespace["agent"])
