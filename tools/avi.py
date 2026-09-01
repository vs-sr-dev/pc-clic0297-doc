#!/usr/bin/env python3
"""avi.py -- RIFF/AVI header reader. Decodes nothing.

Seven files in `/DATA/` are 69.49 % of this disc, so what they are is the
single biggest fact about the product. This reads the RIFF chunk tree, the
`avih` main header and every stream's `strh`/`strf`, and reports duration,
frame rate, resolution, per-stream data rate and the size of the index --
all from headers, without touching a frame. On a 166 MB file that is the
difference between a second and a minute.

It also totals the chunk tree against the file size, which is how you find out
whether an AVI is exactly as long as it says it is.

    python tools/avi.py FILE
    python tools/avi.py DIR --summary
    python tools/avi.py FILE --chunks        # the whole tree, one line each
    python tools/avi.py FILE --index         # idx1 statistics
"""
import os
import struct
import sys
from collections import Counter

AVIF = [(0x00000010, "HASINDEX"), (0x00000020, "MUSTUSEINDEX"),
        (0x00000100, "ISINTERLEAVED"), (0x00000800, "TRUSTCKTYPE"),
        (0x00010000, "WASCAPTUREFILE"), (0x00020000, "COPYRIGHTED")]

WAVEFMT = {0x0001: "PCM", 0x0002: "MS ADPCM", 0x0011: "IMA ADPCM",
           0x0031: "GSM 6.10", 0x0050: "MPEG Layer 1/2",
           0x0055: "MPEG Layer 3", 0x0161: "WMA v2", 0x2000: "AC-3"}


def fourcc(b):
    return b.decode("latin-1", "replace")


def walk(fh, start, end, depth=0, out=None):
    if out is None:
        out = []
    fh.seek(start)
    pos = start
    while pos + 8 <= end:
        fh.seek(pos)
        hdr = fh.read(8)
        if len(hdr) < 8:
            break
        cid = hdr[:4]
        size = struct.unpack("<I", hdr[4:])[0]
        body = pos + 8
        if cid in (b"RIFF", b"LIST"):
            typ = fh.read(4)
            out.append((depth, fourcc(cid), fourcc(typ), pos, size))
            walk(fh, body + 4, min(body + size, end), depth + 1, out)
        else:
            out.append((depth, fourcc(cid), "", pos, size))
        pos = body + size + (size & 1)
    return out


def read_chunk(fh, off, size):
    fh.seek(off + 8)
    return fh.read(size)


class AVI(object):
    def __init__(self, path, fh=None, base=0, length=None):
        self.path = path
        self.own = fh is None
        self.fh = fh or open(path, "rb")
        self.base = base
        self.size = length if length is not None else os.path.getsize(path)
        self.fh.seek(base)
        hdr = self.fh.read(12)
        if hdr[:4] != b"RIFF" or hdr[8:12] != b"AVI ":
            raise ValueError("not a RIFF AVI: %r" % hdr[:12])
        self.riffsize = struct.unpack_from("<I", hdr, 4)[0]
        self.tree = walk(self.fh, base, base + self.size)
        self.avih = None
        self.streams = []
        cur = None
        for depth, cid, typ, off, sz in self.tree:
            if cid == "avih":
                b = read_chunk(self.fh, off, sz)
                (self.us_per_frame, self.max_bytes_sec, self.pad,
                 self.flags, self.total_frames, self.init_frames,
                 self.streams_n, self.suggested_buf, self.width,
                 self.height) = struct.unpack_from("<10I", b)
                self.avih = b
            elif cid == "strh":
                b = read_chunk(self.fh, off, sz)
                cur = dict(
                    type=fourcc(b[0:4]), handler=fourcc(b[4:8]),
                    flags=struct.unpack_from("<I", b, 8)[0],
                    scale=struct.unpack_from("<I", b, 20)[0],
                    rate=struct.unpack_from("<I", b, 24)[0],
                    start=struct.unpack_from("<I", b, 28)[0],
                    length=struct.unpack_from("<I", b, 32)[0],
                    bufsize=struct.unpack_from("<I", b, 36)[0],
                    quality=struct.unpack_from("<i", b, 40)[0],
                    samplesize=struct.unpack_from("<I", b, 44)[0],
                    strf=None)
                self.streams.append(cur)
            elif cid == "strf" and cur is not None:
                cur["strf"] = read_chunk(self.fh, off, sz)
            elif cid == "strn" and cur is not None:
                cur["name"] = read_chunk(self.fh, off, sz).rstrip(b"\x00")

    def close(self):
        if self.own:
            self.fh.close()

    def fps(self, s):
        return s["rate"] / s["scale"] if s["scale"] else 0.0

    def duration(self):
        best = 0.0
        for s in self.streams:
            f = self.fps(s)
            if f:
                best = max(best, s["length"] / f)
        if not best and self.us_per_frame:
            best = self.total_frames * self.us_per_frame / 1e6
        return best

    def video(self):
        for s in self.streams:
            if s["type"] == "vids":
                return s
        return None

    def audio(self):
        for s in self.streams:
            if s["type"] == "auds":
                return s
        return None

    def bmih(self, s):
        b = s["strf"]
        if not b or len(b) < 40:
            return None
        (size, w, h, planes, bits, comp, imgsize, xppm, yppm,
         used, important) = struct.unpack_from("<IiiHHIIiiII", b)
        return dict(w=w, h=h, planes=planes, bits=bits,
                    comp=fourcc(struct.pack("<I", comp)) if comp > 0xFFFF
                    else str(comp),
                    imgsize=imgsize, palette=used,
                    extra=len(b) - size)

    def wfx(self, s):
        b = s["strf"]
        if not b or len(b) < 16:
            return None
        (tag, ch, rate, avg, align, bits) = struct.unpack_from("<HHIIHH", b)
        return dict(tag=tag, name=WAVEFMT.get(tag, "0x%04X" % tag), ch=ch,
                    rate=rate, avg=avg, align=align, bits=bits,
                    extra=len(b) - 16)

    def movi_bytes(self):
        for depth, cid, typ, off, sz in self.tree:
            if cid == "LIST" and typ == "movi":
                return sz
        return 0

    def idx1(self):
        for depth, cid, typ, off, sz in self.tree:
            if cid == "idx1":
                return off, sz
        return None, 0

    def report(self):
        print("file            : %s" % self.path)
        print("size            : %d bytes" % self.size)
        print("RIFF size field : %d  (+8 = %d, file is %d, %s)" % (
            self.riffsize, self.riffsize + 8, self.size,
            "exact" if self.riffsize + 8 == self.size
            else "DIFFERS by %d" % (self.size - self.riffsize - 8)))
        fl = " ".join(n for m, n in AVIF if self.flags & m)
        print("avih flags      : 0x%08X %s" % (self.flags, fl))
        print("microsec/frame  : %d  -> %.3f fps" % (
            self.us_per_frame, 1e6 / self.us_per_frame
            if self.us_per_frame else 0))
        print("total frames    : %d" % self.total_frames)
        print("streams         : %d" % self.streams_n)
        print("frame size      : %d x %d" % (self.width, self.height))
        print("max bytes/sec   : %d  (%.0f kbit/s)" % (
            self.max_bytes_sec, self.max_bytes_sec * 8 / 1000.0))
        print("suggested buffer: %d" % self.suggested_buf)
        d = self.duration()
        print("duration        : %.2f s = %d:%05.2f" % (
            d, int(d // 60), d % 60))
        mv = self.movi_bytes()
        print("movi list bytes : %d  (%.2f %% of file)" % (
            mv, 100.0 * mv / self.size))
        io, isz = self.idx1()
        print("idx1            : %s" % (
            "%d bytes = %d entries" % (isz, isz // 16) if io is not None
            else "ABSENT"))
        print("overall bitrate : %.0f kbit/s" % (
            self.size * 8 / 1000.0 / d) if d else "n/a")
        for i, s in enumerate(self.streams):
            print()
            print("  stream %d      : %s  handler %r  flags 0x%X" % (
                i, s["type"], s["handler"], s["flags"]))
            print("    scale/rate  : %d / %d = %.4f per second" % (
                s["scale"], s["rate"], self.fps(s)))
            print("    length      : %d  -> %.2f s" % (
                s["length"], s["length"] / self.fps(s) if self.fps(s) else 0))
            print("    buffer      : %d   quality %d   sample size %d" % (
                s["bufsize"], s["quality"], s["samplesize"]))
            if "name" in s:
                print("    strn        : %r" % s["name"])
            if s["type"] == "vids":
                b = self.bmih(s)
                if b:
                    print("    bitmap      : %dx%d  %d bpp  planes %d" % (
                        b["w"], b["h"], b["bits"], b["planes"]))
                    print("    compression : %r   image size %d   "
                          "palette %d   extra %d" % (
                              b["comp"], b["imgsize"], b["palette"],
                              b["extra"]))
            elif s["type"] == "auds":
                w = self.wfx(s)
                if w:
                    print("    format      : 0x%04X %s" % (w["tag"], w["name"]))
                    print("    audio       : %d Hz  %d ch  %d bits  "
                          "align %d" % (w["rate"], w["ch"], w["bits"],
                                        w["align"]))
                    print("    avg bytes/s : %d  (%.0f kbit/s)   extra %d" % (
                        w["avg"], w["avg"] * 8 / 1000.0, w["extra"]))

    def chunks(self):
        for depth, cid, typ, off, sz in self.tree:
            print("%s%-6s %-6s at %10d  %12d bytes" % (
                "  " * depth, cid, typ, off, sz))
        print()
        top = [t for t in self.tree if t[0] == 1]
        acct = sum(t[4] + 8 for t in top)
        print("top-level chunks inside RIFF: %d, accounting for %d bytes"
              % (len(top), acct))

    def index(self):
        off, sz = self.idx1()
        if off is None:
            print("no idx1")
            return
        self.fh.seek(off + 8)
        blob = self.fh.read(sz)
        n = sz // 16
        c = Counter()
        key = 0
        sizes = Counter()
        total = 0
        for i in range(n):
            cid, flags, o, l = struct.unpack_from("<4sIII", blob, i * 16)
            c[fourcc(cid)] += 1
            if flags & 0x10:
                key += 1
            total += l
            sizes[fourcc(cid)] += l
        print("idx1 entries      : %d" % n)
        print("keyframe entries  : %d  (%.2f %%)" % (
            key, 100.0 * key / n if n else 0))
        print("bytes indexed     : %d" % total)
        for k, v in c.most_common():
            print("  chunk %-6s %8d entries  %12d bytes  mean %d" % (
                k, v, sizes[k], sizes[k] // v))


def summary(root):
    rows = []
    for dp, _dn, fns in os.walk(root):
        for fn in sorted(fns):
            if not fn.lower().endswith(".avi"):
                continue
            p = os.path.join(dp, fn)
            try:
                a = AVI(p)
            except Exception as ex:
                print("%-16s NOT AN AVI: %s" % (fn, ex))
                continue
            v = a.video()
            au = a.audio()
            b = a.bmih(v) if v else None
            w = a.wfx(au) if au else None
            rows.append((fn, a, v, au, b, w))
            a.close()
    print("%-14s %11s %9s %8s %7s %-6s %11s %11s" % (
        "file", "bytes", "duration", "frames", "fps", "codec", "WxH",
        "kbit/s"))
    tot_b = tot_d = tot_f = 0
    for fn, a, v, au, b, w in rows:
        d = a.duration()
        tot_b += a.size
        tot_d += d
        tot_f += a.total_frames
        print("%-14s %11d %6d:%04.1f %8d %7.2f %-6s %11s %11.0f" % (
            fn, a.size, int(d // 60), d % 60, a.total_frames,
            1e6 / a.us_per_frame if a.us_per_frame else 0,
            b["comp"] if b else "-",
            "%dx%d" % (b["w"], abs(b["h"])) if b else "-",
            a.size * 8 / 1000.0 / d if d else 0))
    print()
    print("files            : %d" % len(rows))
    print("bytes            : %d" % tot_b)
    print("frames           : %d" % tot_f)
    print("runtime          : %.1f s = %d min %04.1f s" % (
        tot_d, int(tot_d // 60), tot_d % 60))
    print("mean bitrate     : %.0f kbit/s" % (tot_b * 8 / 1000.0 / tot_d))
    print()
    print("%-14s %-10s %-22s %s" % ("file", "audio", "format", "video stream"))
    for fn, a, v, au, b, w in rows:
        print("%-14s %-10s %-22s %s" % (
            fn,
            "%dHz" % w["rate"] if w else "none",
            "%s %dch %dbit %dkbit/s" % (w["name"], w["ch"], w["bits"],
                                        w["avg"] * 8 // 1000) if w else "-",
            "%s %dbpp handler %r" % (b["comp"], b["bits"], v["handler"])
            if b else "-"))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    t = sys.argv[1]
    if "--summary" in sys.argv:
        summary(t)
        return
    a = AVI(t)
    if "--chunks" in sys.argv:
        a.chunks()
    elif "--index" in sys.argv:
        a.index()
    else:
        a.report()
    a.close()


if __name__ == "__main__":
    main()
