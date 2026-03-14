#!/usr/bin/env python3
"""
Archipelago Cluster Placement Editor — Web-based interactive tool.

Serves a local web UI for placing spawned-unit clusters on challenge mission maps.
Clusters define positions, tiers, and radii that the Archipelago seed system uses
to randomly select which clusters activate per run.

Usage:
  python archipelago_cluster_editor.py [--port 8742] [--no-browser]

The editor opens in your default browser at http://localhost:8742
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[1]
EDITOR_DIR = Path(__file__).resolve().parent / "cluster_editor"
CLUSTER_DEF_DIR = REPO_ROOT / "Data" / "Archipelago" / "cluster_definitions"
CLUSTER_CONFIG = REPO_ROOT / "Data" / "Archipelago" / "cluster_config.json"
REGISTRY_PATH = EDITOR_DIR / "maps" / "registry.json"

# Ensure mimetypes are set for JS modules
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")


def load_json(path: Path) -> dict | list:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_registry() -> dict:
    return load_json(REGISTRY_PATH)


def load_clusters_for_map(map_id: str) -> dict:
    path = CLUSTER_DEF_DIR / f"{map_id}.json"
    if path.exists():
        return load_json(path)
    return {"version": 2, "map_id": map_id, "clusters": []}


def save_clusters_for_map(map_id: str, data: dict) -> None:
    data["modified"] = datetime.now(timezone.utc).isoformat()
    if "version" not in data:
        data["version"] = 2
    if "map_id" not in data:
        data["map_id"] = map_id
    save_json(CLUSTER_DEF_DIR / f"{map_id}.json", data)


def build_export_bundle(maps_to_export: list[str] | None = None) -> dict:
    registry = load_registry()
    all_ids = [m["id"] for m in registry.get("maps", [])]
    export_ids = maps_to_export if maps_to_export else all_ids
    bundle = {
        "format": "archipelago_cluster_bundle",
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "maps": {},
    }
    for mid in export_ids:
        if mid in all_ids:
            bundle["maps"][mid] = load_clusters_for_map(mid)
    return bundle


def generate_ini_preview(map_id: str, clusters: list[dict], registry: dict) -> str:
    if not clusters:
        return f"; No clusters defined for {map_id}\n"
    map_meta = None
    for m in registry.get("maps", []):
        if m["id"] == map_id:
            map_meta = m
            break
    lines = [f"[{map_id}]"]
    ids = []
    tiers = []
    waypoints = []
    angles = []
    radii = []
    spreads = []
    reserved = []
    for c in clusters:
        ids.append(c.get("cluster_id", "Cluster_?"))
        tiers.append(c.get("tier", "medium"))
        wp = c.get("waypoint_name", "Player_1_Start")
        waypoints.append(wp)
        cx, cy = c.get("x", 0), c.get("y", 0)
        wpx, wpy = 0, 0
        if map_meta:
            wp_coords = map_meta.get("known_waypoints", {}).get(wp)
            if wp_coords:
                wpx, wpy = wp_coords
        import math
        dx = cx - wpx
        dy = cy - wpy
        angle = math.atan2(dy, dx)
        dist = math.sqrt(dx * dx + dy * dy)
        angles.append(f"{angle:.6f}")
        radii.append(f"{dist:.0f}")
        spreads.append(str(c.get("spread", 100)))
        reserved.append(str(c.get("center_reserved_radius", 0)))
    lines.append(f"ClusterIds = {','.join(ids)}")
    lines.append(f"ClusterTiers = {','.join(tiers)}")
    lines.append(f"ClusterWaypoints = {','.join(waypoints)}")
    lines.append(f"ClusterAngles = {','.join(angles)}")
    lines.append(f"ClusterRadii = {','.join(radii)}")
    lines.append(f"ClusterSpreads = {','.join(spreads)}")
    lines.append(f"ClusterCenterReservedRadii = {','.join(reserved)}")
    return "\n".join(lines) + "\n"


class EditorHandler(SimpleHTTPRequestHandler):
    """Serves static files from cluster_editor/ and handles API routes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(EDITOR_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/maps":
            self._json_response(load_registry())
        elif path == "/api/config":
            self._json_response(load_json(CLUSTER_CONFIG))
        elif path.startswith("/api/clusters/"):
            map_id = path.split("/api/clusters/")[1].strip("/")
            self._json_response(load_clusters_for_map(map_id))
        elif path == "/api/export":
            self._json_response(build_export_bundle())
        elif path.startswith("/api/ini-preview/"):
            map_id = path.split("/api/ini-preview/")[1].strip("/")
            data = load_clusters_for_map(map_id)
            registry = load_registry()
            ini = generate_ini_preview(map_id, data.get("clusters", []), registry)
            self._text_response(ini)
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"

        if path.startswith("/api/clusters/"):
            map_id = path.split("/api/clusters/")[1].strip("/")
            try:
                data = json.loads(body)
                save_clusters_for_map(map_id, data)
                self._json_response({"status": "ok", "map_id": map_id})
            except json.JSONDecodeError as e:
                self._json_response({"status": "error", "message": str(e)}, code=400)
        elif path == "/api/import":
            try:
                bundle = json.loads(body)
                imported = []
                for mid, mdata in bundle.get("maps", {}).items():
                    save_clusters_for_map(mid, mdata)
                    imported.append(mid)
                self._json_response({"status": "ok", "imported": imported})
            except json.JSONDecodeError as e:
                self._json_response({"status": "error", "message": str(e)}, code=400)
        elif path == "/api/export":
            try:
                opts = json.loads(body) if body.strip() else {}
                maps_list = opts.get("maps")
                self._json_response(build_export_bundle(maps_list))
            except json.JSONDecodeError as e:
                self._json_response({"status": "error", "message": str(e)}, code=400)
        else:
            self._json_response({"status": "error", "message": "Unknown endpoint"}, code=404)

    def _json_response(self, data, code=200):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _text_response(self, text, code=200):
        body = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        if "/api/" in str(args[0]) if args else False:
            sys.stderr.write(f"[cluster-editor] {format % args}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Archipelago Cluster Placement Editor")
    parser.add_argument("--port", type=int, default=8742, help="HTTP server port (default: 8742)")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")

    # Legacy args for backward compatibility (ignored)
    parser.add_argument("--bitmap", type=Path, help="(Legacy) Ignored — use web UI instead")
    parser.add_argument("--load", type=Path, help="(Legacy) Ignored")
    parser.add_argument("--save", type=Path, help="(Legacy) Ignored")
    parser.add_argument("--export", type=Path, help="(Legacy) Batch export from coords file")
    parser.add_argument("--default-tier", default="medium", choices=("easy", "medium", "hard"))

    args = parser.parse_args()

    # Legacy batch export mode
    if args.export is not None:
        from pathlib import Path as P
        clusters = _legacy_export_from_coords(args.export, args.default_tier)
        save_path = args.save or (CLUSTER_DEF_DIR / "clusters.json")
        save_json(save_path, clusters)
        print(f"Exported {len(clusters)} clusters to {save_path}")
        return 0

    # Ensure directories exist
    CLUSTER_DEF_DIR.mkdir(parents=True, exist_ok=True)
    (CLUSTER_DEF_DIR / "_shared_exports").mkdir(exist_ok=True)

    url = f"http://localhost:{args.port}"
    print(f"Archipelago Cluster Editor starting at {url}")
    print(f"  Editor files: {EDITOR_DIR}")
    print(f"  Cluster data: {CLUSTER_DEF_DIR}")
    print(f"  Map images:   {EDITOR_DIR / 'maps'}")
    print(f"  Press Ctrl+C to stop.\n")

    server = HTTPServer(("localhost", args.port), EditorHandler)

    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEditor stopped.")
        server.server_close()

    return 0


def _legacy_export_from_coords(coords_path: Path, default_tier: str = "medium") -> list[dict]:
    """Parse simple coords file for backward compatibility."""
    clusters = []
    for line in coords_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.replace(",", " ").split()
        if len(parts) >= 2:
            try:
                if len(parts) == 2:
                    x, y = int(parts[0]), int(parts[1])
                    cid = f"Cluster_{len(clusters)+1}"
                    tier = default_tier
                else:
                    cid = parts[0]
                    x, y = int(parts[1]), int(parts[2])
                    tier = parts[3] if len(parts) > 3 and parts[3] in ("easy", "medium", "hard") else default_tier
            except (ValueError, IndexError):
                continue
            clusters.append({"cluster_id": cid, "x": x, "y": y, "tier": tier, "waypoint_name": f"Waypoint_{len(clusters)}"})
    return clusters


if __name__ == "__main__":
    raise SystemExit(main())
