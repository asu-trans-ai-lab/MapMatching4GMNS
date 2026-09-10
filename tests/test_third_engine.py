"""Integration contract for the mapmatcher4gmns third-engine adapter."""
import csv
from pathlib import Path

import pandas as pd
import pytest

import mapmatching4gmns as mm
from mapmatching4gmns import mapmatcher4gmns_adapter
from mapmatching4gmns.adapters.gps import trace_to_evidence
from mapmatching4gmns.selfdemo import _dataset_root


@pytest.fixture(scope="module")
def i95_fixture():
    root = Path(_dataset_root()) / "i95"
    network = root
    gps = pd.read_csv(root / "gps.csv",
                      dtype={"journey_id": str})
    links = pd.read_csv(network / "link.csv", dtype=str, keep_default_na=False)
    with open(root / "expected_routes.csv", encoding="utf-8", newline="") as source:
        expected = {
            row["journey_id"]: row["link_ids"].split(",")
            for row in csv.DictReader(source)
        }
    return root, network, gps, links, expected


def _assert_known_links(path, links):
    known = set(links["link_id"])
    assert path is not None
    assert path.matched_link_sequence
    assert set(path.matched_link_sequence) <= known


def _assert_connected(path, links):
    lookup = links.set_index("link_id")
    for previous, current in zip(path.matched_link_sequence,
                                 path.matched_link_sequence[1:]):
        assert lookup.loc[previous, "to_node_id"] == lookup.loc[current, "from_node_id"]


@pytest.fixture(scope="module")
def third_paths(i95_fixture):
    _, network, gps, links, _ = i95_fixture
    gp_types = set(links["link_type"])
    paths = {}
    for journey_id, group in gps.groupby("journey_id", sort=True):
        evidence = trace_to_evidence(group, corridor_id=journey_id)
        assert {"local_time", "heading_deg_north", "speed_mph"} <= \
            set(evidence.reference_points.columns)
        paths[journey_id] = mm.match(
            evidence,
            network_dir=str(network),
            gp_types=gp_types,
            engine="mapmatcher4gmns",
        )
    return paths


def test_third_engine_matches_all_five_i95_regression_routes(i95_fixture, third_paths):
    _, _, _, links, expected = i95_fixture
    assert set(third_paths) == set(expected)
    for journey_id, path in third_paths.items():
        assert path.source_engine == "engine_mapmatcher4gmns"
        assert path.matched_link_sequence == expected[journey_id]
        assert path.meta == {"backend": "mapmatcher4gmns", "adapter_notes": []}
        _assert_known_links(path, links)
        _assert_connected(path, links)


def test_one_i95_journey_runs_through_all_three_engines(i95_fixture, third_paths):
    _, network, gps, links, _ = i95_fixture
    journey_id = "39f0065e877ddec9"
    evidence = trace_to_evidence(
        gps.loc[gps["journey_id"] == journey_id], corridor_id=journey_id
    )
    gp_types = set(links["link_type"])
    paths = {
        "native": mm.match(evidence, network_dir=str(network), engine="native"),
        "geometric": mm.match(
            evidence, network_dir=str(network), base_link_df=links,
            gp_types=gp_types, engine="geometric"
        ),
        "mapmatcher4gmns": third_paths[journey_id],
    }
    for path in paths.values():
        _assert_known_links(path, links)
    _assert_connected(paths["native"], links)
    _assert_connected(paths["mapmatcher4gmns"], links)


def test_explicit_third_engine_never_falls_back(monkeypatch):
    monkeypatch.setattr(mapmatcher4gmns_adapter, "available", lambda: False)
    with pytest.raises(RuntimeError, match="not installed"):
        mapmatcher4gmns_adapter.match(
            evidence=None,
            base_link_df=None,
            gp_types=set(),
            engine="mapmatcher4gmns",
            network_dir="unused",
        )
