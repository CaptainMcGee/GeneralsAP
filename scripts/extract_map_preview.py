"""
extract_map_preview.py
Extract heightmap from C&C Generals ZH .map files and render top-down PNG previews.

Usage:
    python extract_map_preview.py [--big PATH] [--out DIR] [--maps MAP1,MAP2,...]

File format summary (from SAGE engine source DataChunk.cpp):
  Decompressed .map file:
    - "CkMp" magic (4 bytes)
    - count of name-table entries (Int LE)
    - For each entry: 1-byte name length + name bytes + UnsignedInt ID
    - Then chunk stream: ID(u32) + version(u16) + dataSize(i32) + data

  HeightMapData chunk (version 1-4):
    v1: width(i32), height(i32), dataSize(i32), data[dataSize] bytes
    v2: width(i32), height(i32), dataSize(i32), data[dataSize] bytes  (cell=10.0)
    v3: width(i32), height(i32), borderSize(i32), dataSize(i32), data[dataSize] bytes
    v4: width(i32), height(i32), borderSize(i32), numBoundaries(i32),
        boundaries[numBoundaries*{x,y}], dataSize(i32), data[dataSize] bytes

  Height data: dataSize bytes (u8 per cell), cells are (width+2*border)*(height+2*border)
  Cell (x,y) = data[x + y*(width+2*border)]  (row-major, origin bottom-left)
"""

import struct
import os
import sys
import colorsys
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
    if flags & 0x80:       # large-files flag → 4-byte sizes
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

def parse_chunk_file(data: bytes):
    """Parse decompressed SAGE .map chunk file.
    Returns list of (name, version, chunk_bytes)."""

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

    return chunks


# ── HeightMapData parser ──────────────────────────────────────────────────────

def parse_heightmap(version: int, data: bytes):
    """Parse HeightMapData chunk, return (width, height, border, elevations_bytearray)."""
    pos = 0

    width  = struct.unpack_from('<i', data, pos)[0]; pos += 4
    height = struct.unpack_from('<i', data, pos)[0]; pos += 4

    border = 0
    if version >= 3:
        border = struct.unpack_from('<i', data, pos)[0]; pos += 4

    if version >= 4:
        num_boundaries = struct.unpack_from('<i', data, pos)[0]; pos += 4
        pos += num_boundaries * 8   # skip boundary ICoord2D pairs

    data_size = struct.unpack_from('<i', data, pos)[0]; pos += 4
    elevations = data[pos:pos + data_size]

    return width, height, border, elevations


# ── Heightmap renderer ────────────────────────────────────────────────────────

def render_heightmap(width, height, border, elevations, out_path, scale=2):
    """Render heightmap as a color-coded PNG using only stdlib (PPM → PNG via struct)."""

    eff_w = width  + 2 * border
    eff_h = height + 2 * border

    # Build elevation array (u8 per cell, row-major y=0 is bottom in world)
    elev = list(elevations)
    if len(elev) < eff_w * eff_h:
        elev += [0] * (eff_w * eff_h - len(elev))

    # Find min/max for normalisation (ignore border sentinel 0xFF = 255)
    playable = [elev[x + y * eff_w]
                for y in range(border, border + height)
                for x in range(border, border + width)]
    if not playable:
        print("  WARNING: no playable cells found")
        return

    lo = min(playable)
    hi = max(playable)
    rng = max(hi - lo, 1)

    print(f"  elevation range: {lo} - {hi}  ({eff_w}x{eff_h} cells, border={border})")

    # Colour mapping: low=dark-green → mid=tan → high=white with ridge shading
    def cell_colour(h_raw, x, y):
        t = (h_raw - lo) / rng          # 0..1
        # tri-tone: dark green → khaki → light grey
        if t < 0.33:
            tt = t / 0.33
            r = int(30  + tt * (140 - 30))
            g = int(70  + tt * (130 - 70))
            b = int(20  + tt * (80  - 20))
        elif t < 0.66:
            tt = (t - 0.33) / 0.33
            r = int(140 + tt * (180 - 140))
            g = int(130 + tt * (165 - 130))
            b = int(80  + tt * (130 - 80))
        else:
            tt = (t - 0.66) / 0.34
            r = int(180 + tt * (255 - 180))
            g = int(165 + tt * (250 - 165))
            b = int(130 + tt * (255 - 130))

        # Simple directional shading: compare with cell to the right/above
        if x + 1 < eff_w and y + 1 < eff_h:
            n_x = elev[(x+1) + y * eff_w]
            n_y = elev[x + (y+1) * eff_w]
            shade = (int(n_x) + int(n_y) - 2 * int(h_raw)) * 3
            r = max(0, min(255, r + shade))
            g = max(0, min(255, g + shade))
            b = max(0, min(255, b + shade))

        return r, g, b

    # Render (Y flipped: row 0 in image = top = high Y in world)
    img_w = width  * scale
    img_h = height * scale
    pixels = bytearray(img_w * img_h * 3)

    for iy in range(height):
        world_y = (border + height - 1 - iy)   # flip Y
        for ix in range(width):
            world_x = border + ix
            cell_idx = world_x + world_y * eff_w
            h_raw = elev[cell_idx] if cell_idx < len(elev) else 0
            r, g, b = cell_colour(h_raw, world_x, world_y)
            for sy in range(scale):
                for sx in range(scale):
                    px = (ix * scale + sx) + (iy * scale + sy) * img_w
                    pixels[px*3]   = r
                    pixels[px*3+1] = g
                    pixels[px*3+2] = b

    # Write PNG using stdlib zlib
    import zlib, struct as s2

    def png_chunk(tag, data):
        c = s2.pack('>I', len(data)) + tag + data
        c += s2.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c

    # PNG filter type 0 (None) per row
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
    args = parser.parse_args()

    target_maps = CHALLENGE_MAPS
    if args.maps:
        ids = [m.strip() for m in args.maps.split(',')]
        target_maps = {k: v for k, v in CHALLENGE_MAPS.items() if k in ids}

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
        dc = refpack_decompress(raw[8:])      # skip EAR\x00 + 4-byte size header
        print(f"  Decompressed: {len(dc):,} bytes")

        try:
            chunks = parse_chunk_file(dc)
        except Exception as e:
            print(f"  ERROR parsing chunks: {e}")
            continue

        hm_chunk = next(((v, d) for n, v, d in chunks if n == 'HeightMapData'), None)
        if hm_chunk is None:
            print(f"  HeightMapData chunk NOT FOUND")
            continue

        version, hm_data = hm_chunk
        print(f"  HeightMapData version={version}, chunk size={len(hm_data):,}")

        try:
            width, height, border, elevations = parse_heightmap(version, hm_data)
            print(f"  Map size: {width}x{height}, border={border}, cells={len(elevations)}")
        except Exception as e:
            print(f"  ERROR parsing heightmap: {e}")
            continue

        out_path = os.path.join(args.out, f"{map_id}.png")
        try:
            render_heightmap(width, height, border, elevations, out_path, scale=args.scale)
        except Exception as e:
            import traceback
            print(f"  ERROR rendering: {e}")
            traceback.print_exc()


if __name__ == '__main__':
    main()
