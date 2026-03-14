"""
extract_map_preview.py
Extract heightmap and waypoints from C&C Generals ZH .map files,
render top-down PNG previews, and update maps/registry.json.

Usage:
    python extract_map_preview.py [--big PATH] [--out DIR] [--maps MAP1,MAP2,...]

File format summary (from SAGE engine source DataChunk.cpp):
  Decompressed .map file:
    - "CkMp" magic (4 bytes)
    - count of name-table entries (Int LE)
    - For each entry: 1-byte name length + name bytes + UnsignedInt ID
    - Then chunk stream: ID(u32) + version(u16) + dataSize(i32) + data
    - Chunks may be nested (sub-chunks inside parent chunk data)

  HeightMapData chunk (version 1-4):
    v1/v2: width(i32), height(i32), dataSize(i32), data[dataSize] bytes
    v3: width(i32), height(i32), borderSize(i32), dataSize(i32), data[dataSize] bytes
    v4: width(i32), height(i32), borderSize(i32), numBoundaries(i32),
        boundaries[numBoundaries*2*i32], dataSize(i32), data[dataSize] bytes

  Height data: dataSize = width*height bytes (u8 per cell, NO border cells stored).
  Cell (ix, iy) = data[ix + iy*width], where iy=0 is the BOTTOM row (south edge).
  Game world coords: wx = ix*10, wy = iy*10  (10 world-units per tile).

  ObjectsList chunk (version 3): contains nested Object sub-chunks.
  Each Object sub-chunk:
    x (f32 LE), y (f32 LE), z (f32 LE), angle (f32 LE), flags (i32 LE),
    name (AsciiString: u16 len + chars),
    properties (Dict: u16 pair_count, then pairs of i32 keyAndType + value).
  Dict key type encoding: keyAndType low 8 bits = DataType (0=bool,1=int,2=real,
    3=asciistring,4=unicodestring), high 24 bits = name-table ID for key name.
  Waypoints are identified by having a "waypointName" key in their properties dict.

  Coordinate system: image pixel (px, py) <-> game world (wx, wy):
    px = wx * scale / 10       (scale pixels per tile, 10 world-units per tile)
    py = img_h - wy * scale / 10    (Y flipped: image row 0 = north = high game Y)
"""

import struct
import os
import json
from pathlib import Path


# ── RefPack decompressor (Frank Barchard / Niotso spec) ──────────────────────

def refpack_decompress(data: bytes) -> bytes:
    pos = 0
    flags = data[pos]; pos += 1
    if data[pos] != 0xFB:
        raise ValueError(f"Not RefPack: magic byte = {data[pos]:#x}")
    pos += 1
    if flags & 0x01:       # compressed-size-present flag
        pos += 3
    if flags & 0x80:       # large-files flag -> 4-byte sizes
        uncmp_size = int.from_bytes(data[pos:pos+4], 'big'); pos += 4
    else:
        uncmp_size = int.from_bytes(data[pos:pos+3], 'big'); pos += 3

    dst = bytearray(uncmp_size)
    d = 0

    while pos < len(data):
        b0 = data[pos]; pos += 1

        if not (b0 & 0x80):              # 2-byte: 0DDRRRPP DDDDDDDD
            b1 = data[pos]; pos += 1
            proc_len = b0 & 0x03
            for _ in range(proc_len): dst[d] = data[pos]; pos += 1; d += 1
            ref_dis = ((b0 & 0x60) << 3) + b1 + 1
            ref_len = ((b0 & 0x1C) >> 2) + 3
            src = d - ref_dis
            for i in range(ref_len): dst[d] = dst[src + i]; d += 1

        elif not (b0 & 0x40):            # 3-byte: 10RRRRRR PPDDDDDD DDDDDDDD
            b1 = data[pos]; pos += 1
            b2 = data[pos]; pos += 1
            proc_len = b1 >> 6
            for _ in range(proc_len): dst[d] = data[pos]; pos += 1; d += 1
            ref_dis = ((b1 & 0x3F) << 8) + b2 + 1
            ref_len = (b0 & 0x3F) + 4
            src = d - ref_dis
            for i in range(ref_len): dst[d] = dst[src + i]; d += 1

        elif not (b0 & 0x20):            # 4-byte: 110DRRPP DDDDDDDD DDDDDDDD RRRRRRRR
            b1 = data[pos]; pos += 1
            b2 = data[pos]; pos += 1
            b3 = data[pos]; pos += 1
            proc_len = b0 & 0x03
            for _ in range(proc_len): dst[d] = data[pos]; pos += 1; d += 1
            ref_dis = ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1
            ref_len = ((b0 & 0x0C) << 6) + b3 + 5
            src = d - ref_dis
            for i in range(ref_len): dst[d] = dst[src + i]; d += 1

        else:                            # 1-byte: 111PPPPP
            proc_len = (b0 & 0x1F) * 4 + 4
            if proc_len <= 0x70:         # ordinary literal run
                for _ in range(proc_len): dst[d] = data[pos]; pos += 1; d += 1
            else:                        # stop command
                proc_len = b0 & 0x03
                for _ in range(proc_len): dst[d] = data[pos]; pos += 1; d += 1
                break

    return bytes(dst[:d])


# ── BIG archive reader ────────────────────────────────────────────────────────

def read_big(big_path: str) -> dict:
    """Returns dict of {path_str: raw_bytes} for all files in the BIG archive."""
    files = {}
    with open(big_path, 'rb') as f:
        magic = f.read(4)
        if magic not in (b'BIG4', b'BIGF'):
            raise ValueError(f"Not a BIG file: {magic}")
        f.read(4)  # archive size
        count = struct.unpack('>I', f.read(4))[0]
        f.read(4)  # first file offset
        entries = []
        for _ in range(count):
            off  = struct.unpack('>I', f.read(4))[0]
            size = struct.unpack('>I', f.read(4))[0]
            name = b''
            while True:
                c = f.read(1)
                if c == b'\x00': break
                name += c
            entries.append((name.decode('latin-1'), off, size))
        for name, off, size in entries:
            f.seek(off)
            files[name] = f.read(size)
    return files


# ── SAGE DataChunk parser ─────────────────────────────────────────────────────

def _read_ascii_string(data: bytes, pos: int):
    """Read a SAGE AsciiString (u16 length + chars). Returns (string, new_pos)."""
    length = struct.unpack_from('<H', data, pos)[0]; pos += 2
    s = data[pos:pos+length].decode('latin-1'); pos += length
    return s, pos


def _read_dict(data: bytes, pos: int, id_to_name: dict):
    """Read a SAGE Dict. Returns (dict of {key_name: value}, new_pos)."""
    pair_count = struct.unpack_from('<H', data, pos)[0]; pos += 2
    result = {}
    for _ in range(pair_count):
        key_and_type = struct.unpack_from('<i', data, pos)[0]; pos += 4
        dtype = key_and_type & 0xFF
        name_id = (key_and_type >> 8) & 0xFFFFFF
        key_name = id_to_name.get(name_id, f'<id:{name_id}>')
        if dtype == 0:    # DICT_BOOL
            val = data[pos] != 0; pos += 1
        elif dtype == 1:  # DICT_INT
            val = struct.unpack_from('<i', data, pos)[0]; pos += 4
        elif dtype == 2:  # DICT_REAL
            val = struct.unpack_from('<f', data, pos)[0]; pos += 4
        elif dtype == 3:  # DICT_ASCIISTRING
            val, pos = _read_ascii_string(data, pos)
        elif dtype == 4:  # DICT_UNICODESTRING
            length = struct.unpack_from('<H', data, pos)[0]; pos += 2
            val = data[pos:pos+length*2].decode('utf-16-le', errors='replace'); pos += length * 2
        else:
            break  # unknown type, stop parsing this dict
        result[key_name] = val
    return result, pos


def parse_chunk_file(data: bytes):
    """Parse decompressed SAGE .map chunk file.
    Returns (id_to_name, list of (name, version, chunk_bytes)).
    id_to_name is needed for Dict key decoding in sub-chunks."""

    pos = 0

    # Name table: "CkMp" + count + entries
    if data[pos:pos+4] != b'CkMp':
        raise ValueError(f"Expected CkMp, got {data[pos:pos+4]}")
    pos += 4

    count = struct.unpack_from('<i', data, pos)[0]; pos += 4
    id_to_name = {}
    for _ in range(count):
        name_len = data[pos]; pos += 1
        name = data[pos:pos+name_len].decode('latin-1'); pos += name_len
        chunk_id = struct.unpack_from('<I', data, pos)[0]; pos += 4
        id_to_name[chunk_id] = name

    # Build reverse lookup: name -> id (for finding known key IDs)
    # Not needed here but returned with id_to_name

    # Chunk stream
    chunks = []
    while pos < len(data):
        if pos + 10 > len(data):
            break
        chunk_id   = struct.unpack_from('<I', data, pos)[0]; pos += 4
        version    = struct.unpack_from('<H', data, pos)[0]; pos += 2
        data_size  = struct.unpack_from('<i', data, pos)[0]; pos += 4
        if data_size < 0 or pos + data_size > len(data):
            break
        chunk_data = data[pos:pos+data_size]; pos += data_size
        name = id_to_name.get(chunk_id, f'<unknown:{chunk_id}>')
        chunks.append((name, version, chunk_data))

    return id_to_name, chunks


def parse_sub_chunks(data: bytes, id_to_name: dict):
    """Parse a chunk's data as a stream of nested sub-chunks.
    Returns list of (name, version, chunk_bytes)."""
    pos = 0
    chunks = []
    while pos + 10 <= len(data):
        chunk_id  = struct.unpack_from('<I', data, pos)[0]; pos += 4
        version   = struct.unpack_from('<H', data, pos)[0]; pos += 2
        data_size = struct.unpack_from('<i', data, pos)[0]; pos += 4
        if data_size < 0 or pos + data_size > len(data):
            break
        chunk_data = data[pos:pos+data_size]; pos += data_size
        name = id_to_name.get(chunk_id, f'<unknown:{chunk_id}>')
        chunks.append((name, version, chunk_data))
    return chunks


# ── Object / Waypoint parser ──────────────────────────────────────────────────

import re as _re
_SKIP_WP = _re.compile(
    r'^Waypoint\s+\d+$'          # "Waypoint 123" - generic AI path nodes
    r'|^(Camera|Cine|CINE|cam\d|cm_|WP_CIN_|WP_Spawn_Radiation)',
    _re.IGNORECASE
)

def _is_useful_waypoint(name: str) -> bool:
    """Return True for waypoints worth showing in the cluster editor dropdown."""
    return not bool(_SKIP_WP.match(name))


def parse_objects_from_list(objects_chunk_data: bytes, id_to_name: dict):
    """Parse ObjectsList chunk.

    Returns:
        waypoints  — dict {waypoint_name: (world_x, world_y)}
        draw_list  — list of (world_x, world_y, fill_rgb, outline_rgb, radius)
                     for non-waypoint objects worth drawing on the preview image.

    All coordinates are in game world units (10 units per tile).
    """
    waypoints = {}
    draw_list = []
    sub_chunks = parse_sub_chunks(objects_chunk_data, id_to_name)
    for name, version, obj_data in sub_chunks:
        if name != 'Object':
            continue
        try:
            pos = 0
            wx = struct.unpack_from('<f', obj_data, pos)[0]; pos += 4
            wy = struct.unpack_from('<f', obj_data, pos)[0]; pos += 4
            pos += 4  # wz
            pos += 4  # angle
            pos += 4  # flags
            obj_name, pos = _read_ascii_string(obj_data, pos)
            props, _ = _read_dict(obj_data, pos, id_to_name)
            wp_name = props.get('waypointName')
            if wp_name:
                if _is_useful_waypoint(wp_name):
                    waypoints[wp_name] = (wx, wy)
            else:
                vis = _classify_object(obj_name)
                if vis is not None:
                    fill, outline, radius = vis
                    draw_list.append((wx, wy, fill, outline, radius))
        except Exception:
            continue  # skip malformed objects
    return waypoints, draw_list


# Keep old name as alias for any existing callers
def parse_waypoints_from_objects(objects_chunk_data: bytes, id_to_name: dict):
    waypoints, _ = parse_objects_from_list(objects_chunk_data, id_to_name)
    return waypoints


# ── HeightMapData parser ──────────────────────────────────────────────────────

def parse_heightmap(version: int, data: bytes):
    """Parse HeightMapData chunk.
    Returns (width, height, border, elevations_bytes).
    elevations has exactly width*height bytes (no border cells stored)."""
    pos = 0

    width  = struct.unpack_from('<i', data, pos)[0]; pos += 4
    height = struct.unpack_from('<i', data, pos)[0]; pos += 4

    border = 0
    if version >= 3:
        border = struct.unpack_from('<i', data, pos)[0]; pos += 4

    if version >= 4:
        num_boundaries = struct.unpack_from('<i', data, pos)[0]; pos += 4
        pos += num_boundaries * 8   # skip boundary ICoord2D pairs (2 * i32 each)

    data_size = struct.unpack_from('<i', data, pos)[0]; pos += 4
    elevations = data[pos:pos + data_size]

    return width, height, border, elevations


# ── Heightmap renderer ────────────────────────────────────────────────────────

# ── Object classifier & renderer helpers ─────────────────────────────────────

# Each entry: (match_fn, fill_rgb, outline_rgb, dot_radius)
# Evaluated in order; first match wins.  Return None to skip an object entirely.

def _classify_object(obj_name: str):
    """Classify a non-waypoint map object into a (fill, outline, radius) tuple
    or None if the object should not be drawn.

    Returns: (fill_rgb, outline_rgb, radius_pixels) or None.
    """
    n = obj_name.lower()

    # Skip purely decorative / terrain objects
    _skip = (
        'tree', 'shrub', 'grass', 'bush', 'rock', 'cliff', 'fence',
        'road', 'rubble', 'water', 'bridge', 'patch', 'debris',
        'ambient', 'invisible', 'waypoint', 'camera', 'cine',
        'floatingsmall', 'cloud', 'rift', 'smoke', 'fire', 'crater',
        'propane', 'barrel', 'cart', 'crate', 'pallet', 'pile',
        'lamppost', 'lamp', 'sign', 'flag', 'sand', 'dust',
        'trail', 'flare', 'light', 'halos',
    )
    if any(kw in n for kw in _skip):
        return None

    # Supply sources (yellow-gold) — player resources
    if any(kw in n for kw in ('supply', 'warehouse', 'supplybox', 'supplydock')):
        return (220, 185, 30), (50, 40, 0), 5

    # Tech / neutral capturable buildings (bright cyan)
    if obj_name.startswith('Tech'):
        return (20, 210, 225), (0, 60, 70), 5

    # Command centers (bright red, larger dot)
    if 'commandcenter' in n:
        return (220, 40, 40), (80, 0, 0), 7

    # Faction structures — subdivide by color so maps read clearly
    if obj_name.startswith('America'):
        return (60, 120, 220), (10, 30, 80), 3   # blue
    if obj_name.startswith('China') and not obj_name.startswith('ChinaBoss'):
        return (220, 50, 50), (80, 0, 0), 3       # red
    if obj_name.startswith('ChinaBoss'):
        return (200, 20, 20), (60, 0, 0), 3
    if obj_name.startswith('GLA'):
        return (50, 200, 70), (0, 60, 10), 3      # green

    # Civilian buildings (muted blue-grey)
    if 'civilian' in n or 'building' in n:
        return (140, 145, 175), (40, 40, 60), 3

    return None  # skip anything else unrecognized


def _draw_circle(pixels: bytearray, img_w: int, img_h: int,
                 cx: int, cy: int, radius: int, color: tuple):
    """Fill a solid circle onto the pixel buffer (RGB flat array)."""
    r, g, b = color
    r2 = radius * radius
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy <= r2:
                px, py = cx + dx, cy + dy
                if 0 <= px < img_w and 0 <= py < img_h:
                    idx = (py * img_w + px) * 3
                    pixels[idx]     = r
                    pixels[idx + 1] = g
                    pixels[idx + 2] = b


def render_heightmap(width, height, elevations, out_path, scale=2, draw_objects=None):
    """Render heightmap as a color-coded PNG with optional object overlays.

    elevations: exactly width*height bytes, cell (ix,iy) = elev[ix + iy*width],
    iy=0 is the SOUTH (bottom) row.  Image row 0 is NORTH (top).

    draw_objects: list of (world_x, world_y, fill_rgb, outline_rgb, radius)
    in game-world coordinates (10 world-units per tile).
    """
    elev = list(elevations)
    expected = width * height
    if len(elev) < expected:
        elev += [0] * (expected - len(elev))

    lo = min(elev)
    hi = max(elev)
    rng = max(hi - lo, 1)

    print(f"  elevation range: {lo} - {hi}  ({width}x{height} playable cells)")

    # Desert colour palette matching C&C Generals ZH's sandy Middle-East terrain.
    # 4-stop gradient: dark lowland sand -> bright sandy flat -> brown hills -> dark rocky peak
    # No whites: peak colour is a dark brownish-grey to keep terrain readable at all scales.
    def cell_colour(h_raw, ix, iy):
        t = (h_raw - lo) / rng          # 0..1

        if t < 0.25:                    # deep lowlands: dark tan
            tt = t / 0.25
            r = int(108 + tt * (185 - 108))
            g = int(88  + tt * (155 - 88))
            b = int(55  + tt * (90  - 55))
        elif t < 0.55:                  # sandy flats (main floor): bright desert sand
            tt = (t - 0.25) / 0.30
            r = int(185 + tt * (170 - 185))
            g = int(155 + tt * (130 - 155))
            b = int(90  + tt * (75  - 90))
        elif t < 0.78:                  # hills/ridges: warm brown
            tt = (t - 0.55) / 0.23
            r = int(170 + tt * (120 - 170))
            g = int(130 + tt * (95  - 130))
            b = int(75  + tt * (58  - 75))
        else:                           # rocky peaks: dark earth, no white
            tt = (t - 0.78) / 0.22
            r = int(120 + tt * (72  - 120))
            g = int(95  + tt * (58  - 95))
            b = int(58  + tt * (40  - 58))

        # Hillshade: light from NE (east+north neighbors raised = brighter face).
        # Keep intensity modest (-40..+40) so peaks never blow out to white.
        east_idx  = (ix + 1) + iy * width  if ix + 1 < width  else None
        north_idx = ix + (iy + 1) * width  if iy + 1 < height else None
        if east_idx is not None and north_idx is not None:
            shade = (int(elev[east_idx]) + int(elev[north_idx]) - 2 * int(h_raw)) * 2
            shade = max(-40, min(40, shade))
            r = max(0, min(255, r + shade))
            g = max(0, min(255, g + shade))
            b = max(0, min(255, b + shade))

        return r, g, b

    img_w = width  * scale
    img_h = height * scale
    pixels = bytearray(img_w * img_h * 3)

    for img_row in range(height):
        # img_row=0 is top of image (north), img_row=height-1 is bottom (south)
        world_iy = height - 1 - img_row   # iy=height-1 is north row in data
        for ix in range(width):
            cell_idx = ix + world_iy * width
            h_raw = elev[cell_idx]
            r, g, b = cell_colour(h_raw, ix, world_iy)
            for sy in range(scale):
                for sx in range(scale):
                    px = (ix * scale + sx) + (img_row * scale + sy) * img_w
                    pixels[px*3]   = r
                    pixels[px*3+1] = g
                    pixels[px*3+2] = b

    # ── Object overlay ──────────────────────────────────────────────────────
    if draw_objects:
        for wx, wy, fill, outline, dot_r in draw_objects:
            # Convert game-world coords to image pixel coords
            cx = int(round(wx * scale / 10.0))
            cy = int(round(img_h - wy * scale / 10.0))
            # Draw outline ring first, then fill
            _draw_circle(pixels, img_w, img_h, cx, cy, dot_r + 1, outline)
            _draw_circle(pixels, img_w, img_h, cx, cy, dot_r, fill)

    # Write PNG (stdlib zlib, filter-type 0 per row)
    import zlib, struct as s2

    def png_chunk(tag, data):
        c = s2.pack('>I', len(data)) + tag + data
        c += s2.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c

    raw_rows = bytearray()
    row_bytes = img_w * 3
    for row in range(img_h):
        raw_rows += b'\x00'
        raw_rows += pixels[row * row_bytes:(row+1) * row_bytes]

    png = (
        b'\x89PNG\r\n\x1a\n'
        + png_chunk(b'IHDR', s2.pack('>IIBBBBB', img_w, img_h, 8, 2, 0, 0, 0))
        + png_chunk(b'IDAT', zlib.compress(bytes(raw_rows), 6))
        + png_chunk(b'IEND', b'')
    )

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'wb') as f:
        f.write(png)

    print(f"  Saved {img_w}x{img_h} PNG -> {out_path}")
    return img_w, img_h


# ── Registry updater ──────────────────────────────────────────────────────────

def world_to_pixel(wx, wy, img_h, scale):
    """Convert game world coords (10 units/tile) to image pixel coords.
    Image row 0 = north (high wy), row img_h-1 = south (low wy)."""
    px = wx * scale / 10.0
    py = img_h - wy * scale / 10.0
    return round(px), round(py)


def update_registry(registry_path: str, map_id: str, img_w: int, img_h: int,
                    waypoints: dict, scale: int):
    """Update a single map entry in registry.json with correct dimensions
    and extracted waypoint pixel positions."""
    registry_path = Path(registry_path)
    if registry_path.exists():
        with open(registry_path, encoding='utf-8') as f:
            registry = json.load(f)
    else:
        registry = {"maps": []}

    # Find existing entry
    entry = next((m for m in registry.get('maps', []) if m['id'] == map_id), None)
    if entry is None:
        print(f"  WARNING: {map_id} not in registry.json, skipping registry update")
        return

    # Update map world size to image pixel dimensions
    entry['map_world_size'] = [img_w, img_h]

    # Convert all waypoints to pixel space and update known_waypoints
    pixel_waypoints = {}
    for wp_name, (wx, wy) in waypoints.items():
        px, py = world_to_pixel(wx, wy, img_h, scale)
        # Clamp to image bounds
        px = max(0, min(img_w, px))
        py = max(0, min(img_h, py))
        pixel_waypoints[wp_name] = [px, py]
    if pixel_waypoints:
        entry['known_waypoints'] = pixel_waypoints
        print(f"  Waypoints extracted: {list(pixel_waypoints.keys())}")
    else:
        print(f"  WARNING: No waypoints found in map file")

    with open(registry_path, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=2)


# ── Main ──────────────────────────────────────────────────────────────────────

CHALLENGE_MAPS = {
    "GC_TankGeneral":        "Maps\\GC_TankGeneral\\GC_TankGeneral.map",
    "GC_AirForceGeneral":    "Maps\\GC_AirGeneral\\GC_AirGeneral.map",
    "GC_LaserGeneral":       "Maps\\GC_LaserGeneral\\GC_LaserGeneral.map",
    "GC_SuperweaponGeneral": "Maps\\GC_SuperWeaponsGeneral\\GC_SuperWeaponsGeneral.map",
    "GC_NukeGeneral":        "Maps\\GC_NukeGeneral\\GC_NukeGeneral.map",
    "GC_StealthGeneral":     "Maps\\GC_Stealth\\GC_Stealth.map",
    "GC_ToxinGeneral":       "Maps\\GC_ChemGeneral\\GC_ChemGeneral.map",
    "GC_BossGeneral":        "Maps\\GC_ChinaBoss\\GC_ChinaBoss.map",
}

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract map previews from MapsZH.big")
    parser.add_argument('--big',  default=r'C:\Users\Matt\Desktop\GeneralsAP\build\probe-runtime\MapsZH.big')
    parser.add_argument('--out',  default=r'C:\Users\Matt\Desktop\GeneralsAP\scripts\cluster_editor\maps')
    parser.add_argument('--maps', default=None, help='Comma-separated map IDs (default: all 8)')
    parser.add_argument('--scale', type=int, default=2, help='Pixels per tile (default: 2)')
    parser.add_argument('--no-registry', action='store_true', help='Skip updating registry.json')
    args = parser.parse_args()

    target_maps = CHALLENGE_MAPS
    if args.maps:
        ids = [m.strip() for m in args.maps.split(',')]
        target_maps = {k: v for k, v in CHALLENGE_MAPS.items() if k in ids}

    registry_path = os.path.join(args.out, 'registry.json')

    print(f"Reading {args.big} ...")
    big = read_big(args.big)
    print(f"  {len(big)} files in archive")

    for map_id, big_path in target_maps.items():
        print(f"\n[{map_id}]")
        raw = big.get(big_path)
        if raw is None:
            print(f"  NOT FOUND in BIG: {big_path}")
            continue

        print(f"  Compressed: {len(raw):,} bytes")
        # .map files start with EAR\x00 + 4-byte uncompressed size, then RefPack stream
        dc = refpack_decompress(raw[8:])
        print(f"  Decompressed: {len(dc):,} bytes")

        try:
            id_to_name, chunks = parse_chunk_file(dc)
        except Exception as e:
            print(f"  ERROR parsing chunks: {e}")
            continue

        # --- HeightMapData ---
        hm_chunk = next(((v, d) for n, v, d in chunks if n == 'HeightMapData'), None)
        if hm_chunk is None:
            print(f"  HeightMapData chunk NOT FOUND")
            continue

        version, hm_data = hm_chunk
        print(f"  HeightMapData version={version}, chunk size={len(hm_data):,}")

        try:
            width, height, border, elevations = parse_heightmap(version, hm_data)
            print(f"  Map: {width}x{height} tiles, border={border}, data={len(elevations)} bytes")
        except Exception as e:
            print(f"  ERROR parsing heightmap: {e}")
            continue

        # --- Waypoints & objects (from ObjectsList) — parse BEFORE rendering ---
        waypoints = {}
        draw_objects = []
        objects_chunk = next((d for n, v, d in chunks if n == 'ObjectsList'), None)
        if objects_chunk is not None:
            try:
                waypoints, draw_objects = parse_objects_from_list(objects_chunk, id_to_name)
                print(f"  Objects to draw: {len(draw_objects)}")
            except Exception as e:
                print(f"  WARNING: object extraction failed: {e}")
        else:
            print(f"  WARNING: ObjectsList chunk not found")

        out_path = os.path.join(args.out, f"{map_id}.png")
        try:
            img_w, img_h = render_heightmap(width, height, elevations, out_path,
                                            scale=args.scale, draw_objects=draw_objects)
        except Exception as e:
            import traceback
            print(f"  ERROR rendering: {e}")
            traceback.print_exc()
            continue

        # --- Update registry.json ---
        if not args.no_registry:
            update_registry(registry_path, map_id, img_w, img_h, waypoints, args.scale)


if __name__ == '__main__':
    main()
