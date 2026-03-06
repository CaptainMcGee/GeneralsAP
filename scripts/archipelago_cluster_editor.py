#!/usr/bin/env python3
"""
Cluster definition tool for Archipelago maps.

Define cluster positions on a map bitmap (coordinate-based). Export JSON for
UnlockableCheckSpawner waypoints and slot data.

Usage:
  # Interactive: load bitmap, click to place clusters, save JSON
  python archipelago_cluster_editor.py --bitmap path/to/map.png [--load path/to/clusters.json] [--save path/to/out.json]

  # Non-interactive: convert existing coords file to cluster JSON
  python archipelago_cluster_editor.py --export path/to/coords.txt --save clusters.json

Output format (JSON):
  [
    { "cluster_id": "Cluster_Near_1", "x": 123, "y": 456, "tier": "easy", "waypoint_name": "Waypoint_Near_1" },
    ...
  ]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = REPO_ROOT / "Data" / "Archipelago" / "cluster_definitions"


def load_clusters(path: Path) -> list[dict]:
    """Load cluster list from JSON file."""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("clusters", data.get("points", []))


def save_clusters(path: Path, clusters: list[dict]) -> None:
    """Save cluster list to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clusters, indent=2, sort_keys=False), encoding="utf-8")


def export_from_coords_file(coords_path: Path, default_tier: str = "medium") -> list[dict]:
    """Parse a simple coords file (one 'x,y' or 'x y' or 'id x y tier' per line) into cluster list."""
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
                    cluster_id = f"Cluster_{len(clusters)+1}"
                    tier = default_tier
                elif len(parts) == 3:
                    x, y = int(parts[0]), int(parts[1])
                    cluster_id = f"Cluster_{len(clusters)+1}"
                    tier = parts[2] if parts[2] in ("easy", "medium", "hard") else default_tier
                else:
                    cluster_id = parts[0]
                    x, y = int(parts[1]), int(parts[2])
                    tier = parts[3] if len(parts) > 3 and parts[3] in ("easy", "medium", "hard") else default_tier
            except (ValueError, IndexError):
                continue
            if tier not in ("easy", "medium", "hard"):
                tier = default_tier
            waypoint_name = f"Waypoint_{cluster_id.replace('Cluster_', '')}" if not cluster_id.startswith("Waypoint_") else cluster_id
            clusters.append({
                "cluster_id": cluster_id,
                "x": x,
                "y": y,
                "tier": tier,
                "waypoint_name": waypoint_name,
            })
    return clusters


def run_interactive(bitmap_path: Path, load_path: Path | None, save_path: Path) -> None:
    """Run Tkinter GUI to place clusters on bitmap."""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox, simpledialog
    except ImportError:
        raise SystemExit("Interactive mode requires tkinter (usually bundled with Python).")

    try:
        from PIL import Image
        from PIL import ImageTk
    except ImportError:
        raise SystemExit("Interactive mode requires Pillow: pip install Pillow")

    clusters: list[dict] = load_clusters(load_path) if load_path else []
    next_index = 0
    for c in clusters:
        cid = c.get("cluster_id") or ""
        if not cid:
            continue
        try:
            suffix = cid.split("_")[-1]
            if suffix.isdigit():
                next_index = max(next_index, int(suffix))
        except (ValueError, IndexError):
            pass
    def make_cluster_id() -> str:
        nonlocal next_index
        next_index += 1
        return f"Cluster_{next_index}"

    root = tk.Tk()
    root.title("Archipelago Cluster Editor")
    root.geometry("900x700")

    # Image canvas with scroll
    frame_canvas = ttk.Frame(root)
    frame_canvas.pack(fill=tk.BOTH, expand=True)
    canvas = tk.Canvas(frame_canvas)
    hbar = ttk.Scrollbar(frame_canvas, orient=tk.HORIZONTAL, command=canvas.xview)
    vbar = ttk.Scrollbar(frame_canvas, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
    hbar.pack(side=tk.BOTTOM, fill=tk.X)
    vbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    img = Image.open(bitmap_path)
    photo: ImageTk.PhotoImage | None = None
    scale = 1.0

    def redraw_image() -> None:
        nonlocal photo, scale
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w <= 1:
            w, h = 800, 600
        scale = min(w / img.width, h / img.height, 2.0)
        nw, nh = int(img.width * scale), int(img.height * scale)
        resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(resized)
        canvas.delete("all")
        canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        canvas.config(scrollregion=(0, 0, nw, nh))
        for i, c in enumerate(clusters):
            x, y = c.get("x", 0), c.get("y", 0)
            sx, sy = x * scale, y * scale
            r = 8
            canvas.create_oval(sx - r, sy - r, sx + r, sy + r, outline="lime", width=2, tags=(f"cluster_{i}", "cluster"))
        root.update_idletasks()

    def on_canvas_click(event: tk.Event) -> None:
        item = canvas.find_withtag(tk.CURRENT)
        if item:
            tags = canvas.gettags(item[0])
            for t in tags:
                if t.startswith("cluster_") and t != "cluster":
                    idx = int(t.split("_")[1])
                    if 0 <= idx < len(clusters):
                        action = messagebox.askyesnocancel("Cluster", "Delete this cluster? (No = change tier)")
                        if action is None:
                            return
                        if action:
                            clusters.pop(idx)
                        else:
                            new_tier = simpledialog.askstring("Tier", "Tier (easy/medium/hard):", initialvalue=clusters[idx].get("tier", "medium")) or "medium"
                            if new_tier in ("easy", "medium", "hard"):
                                clusters[idx]["tier"] = new_tier
                        refresh_list()
                        redraw_image()
                    return
        x = int(event.x / scale)
        y = int(event.y / scale)
        cluster_id = make_cluster_id()
        tier = simpledialog.askstring("Tier", "Tier (easy/medium/hard):", initialvalue="medium") or "medium"
        if tier not in ("easy", "medium", "hard"):
            tier = "medium"
        clusters.append({
            "cluster_id": cluster_id,
            "x": x,
            "y": y,
            "tier": tier,
            "waypoint_name": f"Waypoint_{cluster_id.replace('Cluster_', '')}",
        })
        refresh_list()
        redraw_image()

    canvas.bind("<Button-1>", on_canvas_click)

    # Listbox of clusters
    list_frame = ttk.LabelFrame(root, text="Clusters")
    list_frame.pack(fill=tk.X, padx=5, pady=5)
    listbox = tk.Listbox(list_frame, height=4)
    listbox.pack(fill=tk.X)

    def refresh_list() -> None:
        listbox.delete(0, tk.END)
        for c in clusters:
            listbox.insert(tk.END, f"{c.get('cluster_id', '?')} @ ({c.get('x')}, {c.get('y')}) [{c.get('tier', '?')}]")

    refresh_list()

    def do_save() -> None:
        save_clusters(save_path, clusters)
        messagebox.showinfo("Saved", f"Saved {len(clusters)} clusters to {save_path}")

    ttk.Button(root, text="Save JSON", command=do_save).pack(pady=5)
    root.after(100, redraw_image)
    root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description="Archipelago cluster definition tool")
    parser.add_argument("--bitmap", type=Path, help="Path to map bitmap for interactive editing")
    parser.add_argument("--load", type=Path, help="Load existing clusters JSON before editing")
    parser.add_argument("--save", type=Path, default=DEFAULT_OUT_DIR / "clusters.json", help="Output JSON path")
    parser.add_argument("--export", type=Path, help="Non-interactive: export from coords file to cluster JSON")
    parser.add_argument("--default-tier", default="medium", choices=("easy", "medium", "hard"), help="Default tier for --export")
    args = parser.parse_args()

    if args.export is not None:
        clusters = export_from_coords_file(args.export, args.default_tier)
        save_clusters(args.save, clusters)
        print(f"Exported {len(clusters)} clusters to {args.save}")
        return 0

    if args.bitmap is None:
        parser.error("--bitmap required for interactive mode, or use --export for batch export")
    if not args.bitmap.exists():
        parser.error(f"Bitmap not found: {args.bitmap}")
    run_interactive(args.bitmap, args.load, args.save)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
