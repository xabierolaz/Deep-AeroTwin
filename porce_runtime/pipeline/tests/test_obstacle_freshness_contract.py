import sys
import time
from pathlib import Path

import pytest


PIPELINE_DIR = Path(__file__).resolve().parents[1]
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

import flight_controller as brain  # noqa: E402


def _observation(
    *,
    source_id=7,
    source_timestamp_s=None,
    source_sequence=None,
    confidence=0.8,
    lat=42.2297,
    lon=-1.2351,
    object_type="bike",
    **extra,
):
    item = {
        "source": "vision",
        "source_id": source_id,
        "source_session_id": "test-session",
        "clock_domain": "unix_epoch_s",
        "type": object_type,
        "confidence": confidence,
        "lat": lat,
        "lon": lon,
        "distance": 20.0,
        "information_role": "live_observation",
    }
    if source_timestamp_s is not None:
        item["source_timestamp_s"] = source_timestamp_s
    if source_sequence is not None:
        item["source_sequence"] = source_sequence
    item.update(extra)
    return item


@pytest.fixture(autouse=True)
def clean_obstacle_state():
    with brain.state_lock:
        brain.state["obstacle_tracks"] = {}
        brain.state["obstacles"] = []
        brain.state["next_obstacle_track_id"] = 1
        brain.state["obstacle_observations_rejected_out_of_order"] = 0
        brain.state["obstacle_observations_rejected_expired"] = 0
        brain.state["obstacle_observations_rejected_source"] = 0
        brain.state["obstacle_observations_rejected_malformed"] = 0
        brain.state["obstacle_observations_accepted"] = 0
        brain.state["obstacle_observations_accepted"] = 0
    yield


def test_older_source_timestamp_does_not_rejuvenate_or_move_newer_state():
    now = time.time()
    with brain.state_lock:
        brain._ingest_obstacles_locked(
            [_observation(source_timestamp_s=now - 0.10, source_sequence=10, lat=42.2297)],
            now,
        )
        before = dict(next(iter(brain.state["obstacle_tracks"].values())))
        brain._ingest_obstacles_locked(
            [_observation(source_timestamp_s=now - 2.0, source_sequence=11, lat=42.2397)],
            now + 0.05,
        )
        after = dict(next(iter(brain.state["obstacle_tracks"].values())))

    assert after["source_timestamp_s"] == pytest.approx(before["source_timestamp_s"])
    assert after["lat"] == pytest.approx(before["lat"])
    assert after["brain_receive_timestamp_s"] == pytest.approx(before["brain_receive_timestamp_s"])
    assert brain.state["obstacle_observations_rejected_out_of_order"] == 1


def test_reordered_sequence_is_rejected_and_does_not_displace_new_state():
    now = time.time()
    with brain.state_lock:
        brain._ingest_obstacles_locked(
            [_observation(source_timestamp_s=now - 0.10, source_sequence=20, confidence=0.75)],
            now,
        )
        brain._ingest_obstacles_locked(
            [_observation(source_timestamp_s=now - 0.05, source_sequence=19, confidence=0.99)],
            now + 0.05,
        )
        track = dict(next(iter(brain.state["obstacle_tracks"].values())))

    assert track["source_sequence"] == 20
    assert track["confidence"] == pytest.approx(0.75)
    assert brain.state["obstacle_observations_rejected_out_of_order"] == 1


def test_ui_data_serializes_freshness_uncertainty_and_information_role():
    now = time.time()
    with brain.state_lock:
        brain._ingest_obstacles_locked(
            [
                _observation(
                    source_timestamp_s=now - 0.10,
                    source_sequence=3,
                    uncertainty={"radius_95_m": 2.5, "frame": "local_ned"},
                    information_role="observed_object_state",
                )
            ],
            now,
        )

    response = brain.app.test_client().get("/api/ui/data")
    assert response.status_code == 200
    payload = response.get_json()
    item = payload["obstacles"][0]

    assert item["source_timestamp_s"] == pytest.approx(now - 0.10)
    assert item["brain_receive_timestamp_s"] == pytest.approx(now)
    assert item["measurement_age_s"] >= 0.09
    assert item["brain_receive_age_s"] >= 0.0
    assert item["freshness_known"] is True
    assert item["source_timestamp_valid"] is True
    assert item["stale"] is False
    assert item["uncertainty"] == {"radius_95_m": 2.5, "frame": "local_ned"}
    assert item["information_role"] == "observed_object_state"


def test_confidence_is_current_measurement_not_historical_maximum():
    now = time.time()
    with brain.state_lock:
        brain._ingest_obstacles_locked(
            [_observation(source_timestamp_s=now - 0.20, source_sequence=1, confidence=0.95)],
            now,
        )
        active = brain._ingest_obstacles_locked(
            [_observation(source_timestamp_s=now - 0.10, source_sequence=2, confidence=0.25)],
            now + 0.05,
        )

    assert active[0]["confidence"] == pytest.approx(0.25)
    assert active[0]["max_confidence_seen"] == pytest.approx(0.95)


def test_cow_is_dynamic_and_uses_dynamic_ttl():
    assert brain._obs_is_static("cow") is False
    assert brain._obs_track_ttl_s("cow") == pytest.approx(brain.OBS_TRACK_TTL_DYNAMIC_S)


def test_same_class_objects_outside_association_gate_create_distinct_tracks():
    now = time.time()
    first = _observation(
        source_id=None,
        source_timestamp_s=now - 0.10,
        source_sequence=100,
        lat=42.2297,
        lon=-1.2351,
    )
    second = _observation(
        source_id=None,
        source_timestamp_s=now - 0.05,
        source_sequence=1,
        lat=42.2307,
        lon=-1.2351,
    )
    with brain.state_lock:
        brain._ingest_obstacles_locked([first], now)
        brain._ingest_obstacles_locked([second], now + 0.05)

    assert len(brain.state["obstacle_tracks"]) == 2
    assert brain.state["obstacle_observations_rejected_out_of_order"] == 0


def test_future_timestamp_outside_tolerance_is_unknown_stale_never_fresh():
    now = time.time()
    with brain.state_lock:
        active = brain._ingest_obstacles_locked(
            [_observation(source_timestamp_s=now + brain.OBS_SOURCE_MAX_FUTURE_S + 10.0, source_sequence=1)],
            now,
        )

    assert active[0]["measurement_age_s"] is None
    assert active[0]["freshness_known"] is False
    assert active[0]["source_timestamp_valid"] is False
    assert active[0]["freshness_reason"] == "future_timestamp_out_of_tolerance"
    assert active[0]["stale"] is True


def test_legacy_producer_is_accepted_but_explicitly_marked_stale_unknown():
    now = time.time()
    legacy = _observation(source_timestamp_s=None, source_sequence=None)
    legacy.pop("clock_domain")
    legacy.pop("source_session_id")
    with brain.state_lock:
        active = brain._ingest_obstacles_locked([legacy], now)

    assert len(active) == 1
    assert active[0]["freshness_known"] is False
    assert active[0]["legacy_freshness_fallback"] is True
    assert active[0]["freshness_reason"] == "missing_source_timestamp"
    assert active[0]["stale"] is True


def test_api_batch_metadata_survives_post_to_get(monkeypatch):
    monkeypatch.setattr(brain, "OBSTACLE_TOKEN_REQUIRED", False)
    monkeypatch.setattr(brain, "OBSTACLE_TOKEN", "")
    now = time.time()
    payload = {
        "contract_version": "1.1",
        "source_timestamp_s": now - 0.1,
        "source_sequence": 41,
        "source_session_id": "batch-session",
        "clock_domain": "unix_epoch_s",
        "obstacles": [
            {
                "id": 5,
                "source_id": 5,
                "source": "vision",
                "type": "bike",
                "confidence": 0.72,
                "lat": 42.2297,
                "lon": -1.2351,
                "distance": 20.0,
                "uncertainty": {"radius_95_m": 3.0, "frame": "local_ned"},
                "information_role": "observed_object_state",
                "prior_provenance": {"provider": "test-fixture", "version": "1"},
                "range_clamped": True,
            }
        ],
    }
    client = brain.app.test_client()
    posted = client.post("/api/obstacles", json=payload)
    assert posted.status_code == 200
    assert posted.get_json()["accepted_count"] == 1

    item = client.get("/api/ui/data").get_json()["obstacles"][0]
    assert item["source_timestamp_s"] == pytest.approx(now - 0.1)
    assert item["source_sequence"] == 41
    assert item["source_session_id"] == "batch-session"
    assert item["clock_domain"] == "unix_epoch_s"
    assert item["uncertainty"]["radius_95_m"] == pytest.approx(3.0)
    assert item["information_role"] == "observed_object_state"
    assert item["prior_provenance"] == {"provider": "test-fixture", "version": "1"}
    assert item["range_clamped"] is True


def test_api_entity_metadata_overrides_batch_and_survives_post_to_get(monkeypatch):
    monkeypatch.setattr(brain, "OBSTACLE_TOKEN_REQUIRED", False)
    monkeypatch.setattr(brain, "OBSTACLE_TOKEN", "")
    now = time.time()
    payload = {
        "source_timestamp_s": now - 5.0,
        "source_sequence": 1,
        "source_session_id": "batch-session",
        "clock_domain": "unix_epoch_s",
        "obstacles": [
            {
                "source_id": 9,
                "source": "vision",
                "type": "cow",
                "confidence": 0.61,
                "lat": 42.2297,
                "lon": -1.2351,
                "distance": 12.0,
                "source_timestamp_s": now - 0.05,
                "source_sequence": 8,
                "source_session_id": "entity-session",
                "clock_domain": "utc_unix_s",
                "uncertainty": {"sigma_north_m": 1.0, "sigma_east_m": 2.0},
                "information_role": "sensor_observation",
                "prior_provenance": "not_used_for_object_pose",
                "range_clamped": False,
            }
        ],
    }
    client = brain.app.test_client()
    assert client.post("/api/obstacles", json=payload).status_code == 200
    item = client.get("/api/ui/data").get_json()["obstacles"][0]
    assert item["source_sequence"] == 8
    assert item["source_session_id"] == "entity-session"
    assert item["clock_domain"] == "utc_unix_s"
    assert item["uncertainty"] == {"sigma_north_m": 1.0, "sigma_east_m": 2.0}
    assert item["information_role"] == "sensor_observation"
    assert item["prior_provenance"] == "not_used_for_object_pose"
    assert item["range_clamped"] is False


def test_api_rejects_expired_and_reordered_observations_with_status(monkeypatch):
    monkeypatch.setattr(brain, "OBSTACLE_TOKEN_REQUIRED", False)
    monkeypatch.setattr(brain, "OBSTACLE_TOKEN", "")
    client = brain.app.test_client()
    now = time.time()

    expired = client.post(
        "/api/obstacles",
        json={
            "obstacles": [
                {
                    **_observation(source_timestamp_s=now - 60.0, source_sequence=1),
                }
            ]
        },
    )
    assert expired.status_code == 422
    assert expired.get_json()["status"] == "rejected_expired"
    assert expired.get_json()["accepted_count"] == 0

    first = client.post(
        "/api/obstacles",
        json={"obstacles": [_observation(source_timestamp_s=time.time() - 0.1, source_sequence=10)]},
    )
    assert first.status_code == 200
    reordered = client.post(
        "/api/obstacles",
        json={"obstacles": [_observation(source_timestamp_s=time.time() - 0.05, source_sequence=9)]},
    )
    assert reordered.status_code == 409
    assert reordered.get_json()["status"] == "rejected_out_of_order"
    assert reordered.get_json()["accepted_count"] == 0


def test_api_does_not_report_filtered_or_malformed_batch_as_accepted(monkeypatch):
    monkeypatch.setattr(brain, "OBSTACLE_TOKEN_REQUIRED", False)
    monkeypatch.setattr(brain, "OBSTACLE_TOKEN", "")
    monkeypatch.setattr(brain, "OBS_SOURCE_FILTER_ENABLE", True)
    monkeypatch.setattr(brain, "ALLOWED_OBS_SOURCE_KEYS", {"vision"})
    client = brain.app.test_client()

    filtered = client.post(
        "/api/obstacles",
        json={"obstacles": [{"source": "untrusted", "type": "cow"}]},
    )
    assert filtered.status_code == 422
    assert filtered.get_json()["status"] == "rejected_source"
    assert filtered.get_json()["accepted_count"] == 0
    assert filtered.get_json()["rejected_count"] == 1
    assert filtered.get_json()["rejected_source"] == 1

    malformed = client.post("/api/obstacles", json={"obstacles": ["not-an-object"]})
    assert malformed.status_code == 422
    assert malformed.get_json()["status"] == "rejected_malformed"
    assert malformed.get_json()["accepted_count"] == 0
    assert malformed.get_json()["rejected_count"] == 1
    assert malformed.get_json()["rejected_malformed"] == 1
