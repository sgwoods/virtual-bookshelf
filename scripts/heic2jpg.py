#!/usr/bin/env python3
"""Decode an iPhone HEIC (HEVC tile grid) to JPEG using only ffmpeg + Pillow.
Usage: heic2jpg.py in.heic out.jpg
"""
import struct, subprocess, sys, tempfile, os
from PIL import Image

def boxes(buf, start=0, end=None):
    end = len(buf) if end is None else end
    p = start
    while p + 8 <= end:
        size, typ = struct.unpack('>I4s', buf[p:p+8]); hdr = 8
        if size == 1:
            size = struct.unpack('>Q', buf[p+8:p+16])[0]; hdr = 16
        elif size == 0:
            size = end - p
        yield typ.decode('latin1'), p + hdr, p + size
        p += size

def find(buf, path, start=0, end=None):
    cur = [(start, end if end is not None else len(buf))]
    for name in path:
        nxt = []
        for s, e in cur:
            for t, bs, be in boxes(buf, s, e):
                if t == name:
                    nxt.append((bs, be))
        cur = nxt
    return cur

FULL = {'meta', 'pitm', 'iinf', 'iloc', 'iref', 'ipma', 'ispe', 'irot', 'infe', 'hvcC'}

def parse(buf):
    (ms, me), = find(buf, ['meta'])
    ms += 4  # fullbox
    # item infos
    items = {}
    for s, e in find(buf, ['iinf'], ms, me):
        for t, bs, be in boxes(buf, s + 4 + 2, e):
            if t == 'infe':
                v = buf[bs]
                if v >= 2:
                    iid, prot, ityp = struct.unpack('>HH4s', buf[bs+4:bs+12])
                    items[iid] = ityp.decode('latin1')
    # primary
    (ps, pe), = find(buf, ['pitm'], ms, me)
    pitm = struct.unpack('>H', buf[ps+4:ps+6])[0]
    # iloc
    (ls, le), = find(buf, ['iloc'], ms, me)
    ver = buf[ls]; p = ls + 4
    b = buf[p]; os_, ls_ = b >> 4, b & 15; b = buf[p+1]; bs_, is_ = b >> 4, b & 15; p += 2
    n = struct.unpack('>H', buf[p:p+2])[0] if ver < 2 else struct.unpack('>I', buf[p:p+4])[0]
    p += 2 if ver < 2 else 4
    def rd(nb):
        nonlocal p
        v = {0: 0, 4: struct.unpack('>I', buf[p:p+4])[0] if nb == 4 else 0, 8: 0}
        if nb == 4: v = struct.unpack('>I', buf[p:p+4])[0]
        elif nb == 8: v = struct.unpack('>Q', buf[p:p+8])[0]
        else: v = 0
        p += nb; return v
    loc = {}
    for _ in range(n):
        iid = struct.unpack('>H', buf[p:p+2])[0]; p += 2
        if ver in (1, 2):
            p += 2  # construction method
        p += 2  # data ref idx
        base = rd(bs_)
        cnt = struct.unpack('>H', buf[p:p+2])[0]; p += 2
        ext = []
        for _ in range(cnt):
            if ver in (1, 2) and is_ > 0: rd(is_)
            off = rd(os_); ln = rd(ls_)
            ext.append((base + off, ln))
        loc[iid] = ext
    # iref dimg: grid -> tiles
    tiles = []
    for s, e in find(buf, ['iref'], ms, me):
        for t, bs, be in boxes(buf, s + 4, e):
            if t == 'dimg':
                fr, cnt = struct.unpack('>HH', buf[bs:bs+4])
                if fr == pitm:
                    tiles = list(struct.unpack('>%dH' % cnt, buf[bs+4:bs+4+2*cnt]))
    # properties: hvcC, ispe, irot
    props = []
    for s, e in find(buf, ['iprp', 'ipco'], ms, me):
        for t, bs, be in boxes(buf, s, e):
            props.append((t, buf[bs:be]))
    assoc = {}
    for s, e in find(buf, ['iprp', 'ipma'], ms, me):
        ver = buf[s]; flags = buf[s+3]; p = s + 4
        cnt = struct.unpack('>I', buf[p:p+4])[0]; p += 4
        for _ in range(cnt):
            iid = struct.unpack('>H', buf[p:p+2])[0]; p += 2
            ac = buf[p]; p += 1
            lst = []
            for _ in range(ac):
                if flags & 1:
                    v = struct.unpack('>H', buf[p:p+2])[0]; p += 2; idx = v & 0x7fff
                else:
                    idx = buf[p] & 0x7f; p += 1
                lst.append(idx - 1)
            assoc[iid] = lst
    return items, pitm, loc, tiles, props, assoc

def hvcc_to_annexb(h):
    p = 22; n = h[p]; p += 1; out = b''
    for _ in range(n):
        p += 1
        cnt = struct.unpack('>H', h[p:p+2])[0]; p += 2
        for _ in range(cnt):
            ln = struct.unpack('>H', h[p:p+2])[0]; p += 2
            out += b'\x00\x00\x00\x01' + h[p:p+ln]; p += ln
    return out, (h[21] & 3) + 1

def item_annexb(buf, loc, iid, nal_len):
    data = b''.join(buf[o:o+l] for o, l in loc[iid])
    out = b''; p = 0
    while p < len(data):
        ln = int.from_bytes(data[p:p+nal_len], 'big'); p += nal_len
        out += b'\x00\x00\x00\x01' + data[p:p+ln]; p += ln
    return out

def decode(buf, loc, iid, props, assoc, tmp):
    hv = next(d for t, d in [props[i] for i in assoc[iid]] if t == 'hvcC')
    hdr, nal_len = hvcc_to_annexb(hv)
    raw = os.path.join(tmp, f'{iid}.hevc'); png = os.path.join(tmp, f'{iid}.png')
    open(raw, 'wb').write(hdr + item_annexb(buf, loc, iid, nal_len))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw, '-frames:v', '1', png], check=True)
    return Image.open(png).convert('RGB')

def main(src, dst):
    buf = open(src, 'rb').read()
    items, pitm, loc, tiles, props, assoc = parse(buf)
    pr = [props[i] for i in assoc.get(pitm, [])]
    W = H = None; rot = 0
    for t, d in pr:
        if t == 'ispe': W, H = struct.unpack('>II', d[4:12])
        if t == 'irot': rot = d[0] & 3
    with tempfile.TemporaryDirectory() as tmp:
        if items[pitm] == 'grid':
            ow, oh = W, H
            first = decode(buf, loc, tiles[0], props, assoc, tmp)
            tw, th = first.size
            cols, rows = -(-ow // tw), -(-oh // th)
            assert rows * cols == len(tiles), (rows, cols, len(tiles))
            canvas = Image.new('RGB', (cols * tw, rows * th))
            for i, tid in enumerate(tiles):
                im = first if i == 0 else decode(buf, loc, tid, props, assoc, tmp)
                canvas.paste(im, ((i % cols) * tw, (i // cols) * th))
            img = canvas.crop((0, 0, ow, oh))
        else:
            img = decode(buf, loc, pitm, props, assoc, tmp)
    if rot:
        img = img.rotate(90 * rot, expand=True)
    img.save(dst, quality=92)
    print(dst, img.size)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
