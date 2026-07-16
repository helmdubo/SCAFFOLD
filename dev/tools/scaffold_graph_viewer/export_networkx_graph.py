"""
Layer: dev tooling

Rules:
- Export ScaffoldGraph as a networkx-compatible node-link JSON payload.
- Import scaffold_core as a consumer; do not define Scaffold relations here.
- JSON export is pure stdlib; --draw needs optional networkx + matplotlib.
- Do not import Blender.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scaffold_core.pipeline.inspection import scaffold_graph_to_node_link_dict
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_one_seam_source,
    make_cylinder_tube_without_caps_with_two_seams_source,
)
from scaffold_core.tests.fixtures.extruded_cross import make_extruded_cross_source
from scaffold_core.tests.fixtures.l_corridor_tunnel import make_l_corridor_tunnel_seamed_folds_source
from scaffold_core.tests.fixtures.tube_with_cap import make_tube_with_cap_source


FIXTURES = {
    "cylinder_one_seam": make_cylinder_tube_without_caps_with_one_seam_source,
    "cylinder_two_seam": make_cylinder_tube_without_caps_with_two_seams_source,
    "extruded_cross": make_extruded_cross_source,
    "l_corridor": make_l_corridor_tunnel_seamed_folds_source,
    "tube_with_cap": make_tube_with_cap_source,
}

JUNCTION_NODE_COLORS = {
    "SELF_SEAM": "#d62728",
    "CROSS_PATCH": "#1f77b4",
    None: "#7f7f7f",
}

COMPONENT_EDGE_PALETTE = (
    "#2ca02c",
    "#ff7f0e",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#17becf",
    "#bcbd22",
    "#1f77b4",
)


def _component_edge_color(component_id: str | None, ordered_component_ids: list[str]) -> str:
    if component_id is None:
        return "#999999"
    index = ordered_component_ids.index(component_id)
    return COMPONENT_EDGE_PALETTE[index % len(COMPONENT_EDGE_PALETTE)]


def _planar_positions(data: dict) -> dict[str, tuple[float, float]] | None:
    positions = {node["id"]: node.get("position") for node in data["nodes"]}
    if not positions or any(position is None for position in positions.values()):
        return None
    spreads = []
    for axis in range(3):
        values = [position[axis] for position in positions.values()]
        spreads.append((max(values) - min(values), axis))
    (_, first_axis), (_, second_axis) = sorted(spreads, reverse=True)[:2]
    return {
        node_id: (position[first_axis], position[second_axis])
        for node_id, position in positions.items()
    }


def _draw(data: dict, out_path: Path) -> Path | None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import networkx as nx
    except ImportError as error:
        print(f"--draw skipped ({error}); install with: pip install networkx matplotlib")
        return None

    try:
        graph = nx.node_link_graph(data, edges="links")
    except TypeError:  # older networkx without the edges= keyword
        graph = nx.node_link_graph(data)

    positions = _planar_positions(data) or nx.spring_layout(graph, seed=1)
    ordered_component_ids = sorted(
        {
            link["continuity_component_id"]
            for link in data["links"]
            if link["continuity_component_id"] is not None
        }
    )

    fig, ax = plt.subplots(figsize=(10.0, 8.0))
    node_colors = [
        JUNCTION_NODE_COLORS.get(attrs.get("junction_kind"), "#7f7f7f")
        for _, attrs in graph.nodes(data=True)
    ]
    nx.draw_networkx_nodes(graph, positions, ax=ax, node_color=node_colors, node_size=700)
    nx.draw_networkx_labels(
        graph,
        positions,
        ax=ax,
        labels={node_id: node_id.rsplit(":", 1)[-1] for node_id in graph.nodes},
        font_size=8,
        font_color="white",
    )

    pair_totals: dict[tuple[str, str], int] = {}
    for source, target in graph.edges(keys=False):
        pair = (source, target) if source <= target else (target, source)
        pair_totals[pair] = pair_totals.get(pair, 0) + 1
    pair_progress: dict[tuple[str, str], int] = {}
    for source, target, key, attrs in graph.edges(keys=True, data=True):
        pair = (source, target) if source <= target else (target, source)
        index = pair_progress.get(pair, 0)
        pair_progress[pair] = index + 1
        total = pair_totals[pair]
        if source == target:
            rad = 0.25 + 0.2 * index
        else:
            rad = 0.25 * (index - (total - 1) / 2.0)
        nx.draw_networkx_edges(
            graph,
            positions,
            ax=ax,
            edgelist=[(source, target)],
            connectionstyle=f"arc3,rad={rad}",
            edge_color=_component_edge_color(
                attrs.get("continuity_component_id"), ordered_component_ids
            ),
            width=2.0,
        )

    legend_lines = [
        f"nodes: {graph.number_of_nodes()}  edges: {graph.number_of_edges()}",
        "node color: junction kind (red SELF_SEAM, blue CROSS_PATCH, grey none)",
        "edge color: continuity component id",
    ]
    ax.set_title(f"{data['graph']['id']}\n" + "\n".join(legend_lines), fontsize=9)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a Scaffold fixture ScaffoldGraph as networkx node-link JSON.",
    )
    parser.add_argument("fixture", choices=sorted(FIXTURES))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--draw", action="store_true", help="also render a PNG next to the JSON")
    args = parser.parse_args()

    source = FIXTURES[args.fixture]()
    context = run_pass_1_relations(run_pass_0(source))
    node_link = scaffold_graph_to_node_link_dict(
        context.relation_snapshot,
        context.geometry_facts,
    )
    if node_link is None:
        print(f"fixture {args.fixture} produced no ScaffoldGraph")
        return 1

    payload = {
        "format": "scaffold_graph_node_link_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {"id": str(source.id), "name": args.fixture},
        **node_link,
    }
    out = args.out or Path(__file__).with_name("reports") / f"{args.fixture}.nxgraph.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(out)
    if args.draw:
        image_path = _draw(node_link, out.with_suffix(".png"))
        if image_path is not None:
            print(image_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
