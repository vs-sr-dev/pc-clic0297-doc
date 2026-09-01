#!/usr/bin/env python3
"""threeclocks.py -- date every file three times and print the disagreements.

The whole method of this session in one tool. A file on a CD-ROM carries up to
three independent statements about when it existed:

  clock A   the ISO 9660 directory record's recording date. Written by the
            mastering software when the image was built, and inherited from
            whatever the file's timestamp was on the machine that fed it in.
            The weakest clock: a copy destroys it, and every tool rewrites it.

  clock B   a timestamp *inside* the file's own format, written by whatever
            produced the file. A COFF TimeDateStamp, a QuickTime mvhd creation
            date, the DOS stamps on the members of a cabinet, a WinHelp
            GenDate, a RIFF ICRD. Copying does not touch it. Nothing but a
            rebuild changes it.

  clock C   not a date but a *version*: the linker that emitted the PE, the
            NE header's linker revision, the Director imap version, the RIFF
            ISFT software string. It bounds the date from below -- a file
            linked by version 5.12 cannot predate version 5.12.

Where all three agree you have a stratum. Where they disagree you have a
history, and the direction of the disagreement says which. This tool never
decides which clock is right; it prints all three and the signed difference.

    python tools/threeclocks.py _work/iso --image _work/clic11.img \n        --tsv notes/threeclocks.tsv
    python tools/threeclocks.py _work/iso --summary
    python tools/threeclocks.py _work/iso --disagreements --days 180

EPOCHS, WHICH IS WHERE THIS KIND OF TOOL GOES WRONG
---------------------------------------------------
  ISO 9660 record      seven bytes, the last of which is an offset from GMT in
                       fifteen-minute units. **Every record on this disc says
                       zero**, so the recorded value is GMT and is used as
                       such.
  COFF TimeDateStamp   seconds since 1970-01-01 UTC
  QuickTime mvhd       seconds since 1904-01-01, no zone, local by convention
  MS-DOS date/time     a packed local date with two-second resolution
  WinHelp GenDate      seconds since 1970-01-01

Clock A is read from the directory record itself and NOT from the filesystem
mtime. That distinction is worth two hours: Windows reads a record whose GMT
offset is zero, converts it to the machine's local time, and hands back a
timestamp two hours later than the bytes say during Italian summer time. The
first run of this tool compared that shifted value against a COFF stamp in GMT
and reported eleven files as "written before they were linked". They were not;
the tool was.
"""
import argparse
import datetime
import os
import struct
import sys
from collections import Counter

QT_EPOCH = datetime.datetime(1904, 1, 1)


def rd(fh, off, n):
    fh.seek(off)
    return fh.read(n)


# ---------------------------------------------------------------- PE / NE

def pe_ne(fh, size):
    head = rd(fh, 0, 2)
    if head != b"MZ":
        return None
    if size < 0x40:
        return None
    e_lfanew = struct.unpack("<I", rd(fh, 0x3c, 4))[0]
    if e_lfanew + 4 > size or e_lfanew < 2:
        return ("MZ", None, "DOS executable, no extended header")
    sig = rd(fh, e_lfanew, 4)
    if sig[:2] == b"NE":
        h = rd(fh, e_lfanew, 64)
        ver = "%d.%d" % (h[2], h[3])
        tgt = {1: "OS/2", 2: "Windows", 3: "European MS-DOS 4.x",
               4: "Windows 386", 5: "BOSS"}.get(h[0x36], "target %d" % h[0x36])
        exever = struct.unpack("<H", h[0x3e:0x40])[0] if len(h) >= 64 else 0
        return ("NE", None,
                "NE %s, linker %s, expected Windows %d.%d"
                % (tgt, ver, exever >> 8, exever & 0xff))
    if sig == b"PE\x00\x00":
        coff = rd(fh, e_lfanew + 4, 20)
        mach, nsec, tds = struct.unpack("<HHI", coff[:8])
        # PE optional header: +0 magic (0x010B / 0x020B), +2 linker major,
        # +3 linker minor. The first version of this read +0 and +1 and
        # reported every image on the disc as "linker 11.01", which is the
        # magic 0x010B little-endian read as two decimal bytes.
        opt = rd(fh, e_lfanew + 24, 4)
        magic = struct.unpack("<H", opt[:2])[0] if len(opt) >= 2 else 0
        lnk = "%d.%02d" % (opt[2], opt[3]) if len(opt) == 4 else "?"
        machn = {0x14c: "i386", 0x8664: "amd64", 0x1c0: "arm",
                 0x184: "alpha", 0x1f0: "ppc", 0x162: "mips"}.get(
                     mach, "0x%04x" % mach)
        when = None
        if 0 < tds < 0x7fffffff:
            try:
                when = datetime.datetime.fromtimestamp(
                    tds, datetime.timezone.utc).replace(tzinfo=None)
            except (OverflowError, OSError, ValueError):
                when = None
        return ("PE", when, "PE %s, linker %s, %d sections" % (machn, lnk, nsec))
    if sig[:2] == b"LE" or sig[:2] == b"LX":
        return ("LE", None, "linear executable")
    return ("MZ", None, "DOS executable, extended header %r" % sig[:2])


# ---------------------------------------------------------------- QuickTime

def quicktime(fh, size):
    """walk top-level atoms for moov, then moov's mvhd."""
    def atoms(base, end, depth=0):
        off = base
        while off + 8 <= end and depth < 4:
            fh.seek(off)
            hdr = fh.read(8)
            if len(hdr) < 8:
                return
            ln = struct.unpack(">I", hdr[:4])[0]
            typ = hdr[4:8]
            if ln == 1:
                ext = fh.read(8)
                if len(ext) < 8:
                    return
                ln = struct.unpack(">Q", ext)[0]
                body = off + 16
            elif ln == 0:
                ln = end - off
                body = off + 8
            else:
                body = off + 8
            if ln < 8:
                return
            yield typ, body, off + ln
            off += ln

    seen = set()
    for typ, body, end in atoms(0, size):
        seen.add(typ)
        if typ == b"moov":
            for t2, b2, e2 in atoms(body, end, 1):
                if t2 == b"mvhd":
                    d = rd(fh, b2, 20)
                    if len(d) < 20:
                        return None
                    ver = d[0]
                    if ver == 0:
                        cre, mod, ts, dur = struct.unpack(">IIII", d[4:20])
                    else:
                        d = rd(fh, b2, 32)
                        cre, mod = struct.unpack(">QQ", d[4:20])
                        ts, dur = struct.unpack(">II", d[20:28])
                    try:
                        when = QT_EPOCH + datetime.timedelta(seconds=cre)
                    except OverflowError:
                        when = None
                    secs = (dur / ts) if ts else 0
                    return ("MooV", when,
                            "QuickTime, mvhd v%d, %.1f s, atoms %s"
                            % (ver, secs,
                               "+".join(sorted(t.decode("latin-1", "replace")
                                               for t in seen))))
            return ("MooV", None, "QuickTime, moov without mvhd")
    if b"mdat" in seen or b"ftyp" in seen:
        return ("MooV", None, "QuickTime, no moov at top level")
    return None


# ---------------------------------------------------------------- RIFF

def riff(fh, size):
    hdr = rd(fh, 0, 12)
    if hdr[:4] not in (b"RIFF", b"RIFX"):
        return None
    form = hdr[8:12].decode("latin-1")
    info = {}
    idit = None
    end = min(size, struct.unpack("<I", hdr[4:8])[0] + 8)
    off = 12
    guard = 0
    while off + 8 <= end and guard < 4000:
        guard += 1
        d = rd(fh, off, 8)
        if len(d) < 8:
            break
        ck = d[:4]
        ln = struct.unpack("<I", d[4:8])[0]
        if ck == b"LIST":
            sub = rd(fh, off + 8, 4)
            if sub == b"INFO":
                p = off + 12
                lend = off + 8 + ln
                while p + 8 <= min(lend, end):
                    dd = rd(fh, p, 8)
                    if len(dd) < 8:
                        break
                    k = dd[:4].decode("latin-1")
                    l2 = struct.unpack("<I", dd[4:8])[0]
                    v = rd(fh, p + 8, min(l2, 200)).split(b"\x00")[0]
                    info[k] = v.decode("latin-1", "replace").strip()
                    p += 8 + l2 + (l2 & 1)
            off += 8 + ln + (ln & 1)
            continue
        if ck == b"IDIT":
            idit = rd(fh, off + 8, min(ln, 64)).split(b"\x00")[0]
            idit = idit.decode("latin-1", "replace").strip()
        off += 8 + ln + (ln & 1)
    bits = []
    if info.get("ISFT"):
        bits.append("ISFT %r" % info["ISFT"])
    if idit:
        bits.append("IDIT %r" % idit)
    for k in ("ICRD", "IART", "INAM", "ICOP", "ICMT", "IENG", "ITCH"):
        if info.get(k):
            bits.append("%s %r" % (k, info[k]))
    when = None
    for cand in (info.get("ICRD"), idit):
        if not cand:
            continue
        for f in ("%Y-%m-%d", "%Y/%m/%d", "%a %b %d %H:%M:%S %Y",
                  "%b %d %Y", "%Y"):
            try:
                when = datetime.datetime.strptime(cand.strip(), f)
                break
            except ValueError:
                pass
        if when:
            break
    return ("RIFF/" + form.strip(), when, "; ".join(bits) or "no INFO chunk")


def aiff(fh, size):
    hdr = rd(fh, 0, 12)
    if hdr[:4] != b"FORM" or hdr[8:12] not in (b"AIFF", b"AIFC"):
        return None
    off = 12
    bits = []
    guard = 0
    while off + 8 <= size and guard < 400:
        guard += 1
        d = rd(fh, off, 8)
        if len(d) < 8:
            break
        ck = d[:4]
        ln = struct.unpack(">I", d[4:8])[0]
        if ck in (b"ANNO", b"NAME", b"AUTH", b"(c) ", b"APPL"):
            v = rd(fh, off + 8, min(ln, 200))
            bits.append("%s %r" % (ck.decode("latin-1"),
                                   v.decode("latin-1", "replace").strip()))
        if ck == b"COMM":
            v = rd(fh, off + 8, min(ln, 22))
            if len(v) >= 8:
                ch, nf = struct.unpack(">HI", v[:6])
                bits.append("%d ch, %d frames" % (ch, nf))
            if ln >= 22 and len(v) >= 22:
                bits.append("codec %r" % v[18:22].decode("latin-1", "replace"))
        off += 8 + ln + (ln & 1)
    return (hdr[8:12].decode("latin-1"), None, "; ".join(bits) or "no text chunk")


# ---------------------------------------------------------------- CAB

def cab(fh, size):
    h = rd(fh, 0, 36)
    if h[:4] != b"MSCF":
        return None
    (sig, res1, csize, res2, coff, res3, vmin, vmaj, nfold, nfiles,
     flags, setid, icab) = struct.unpack("<4sIIIIIBBHHHHH", h)
    hoff = 36
    if flags & 4:
        r = rd(fh, 36, 4)
        cbh, cbf, cbd = struct.unpack("<HBB", r)
        hoff = 36 + 4 + cbh
    fh.seek(coff)
    dates = []
    names = []
    for _ in range(nfiles):
        d = fh.read(16)
        if len(d) < 16:
            break
        usz, uoff, ifold, dt, tm, attr = struct.unpack("<IIHHHH", d)
        nm = b""
        while True:
            c = fh.read(1)
            if not c or c == b"\x00":
                break
            nm += c
        y = ((dt >> 9) & 0x7f) + 1980
        mo = (dt >> 5) & 0xf
        dy = dt & 0x1f
        hh = (tm >> 11) & 0x1f
        mi = (tm >> 5) & 0x3f
        ss = (tm & 0x1f) * 2
        try:
            dates.append(datetime.datetime(y, mo, dy, hh, mi, min(ss, 59)))
        except ValueError:
            pass
        names.append(nm.decode("latin-1", "replace"))
    when = min(dates) if dates else None
    det = ("CAB v%d.%d, %d folders, %d files, setid %d, index %d"
           % (vmaj, vmin, nfold, nfiles, setid, icab))
    if dates:
        det += ", member dates %s .. %s" % (min(dates).strftime("%Y-%m-%d"),
                                            max(dates).strftime("%Y-%m-%d"))
    if flags & 1:
        det += ", cont-prev"
    if flags & 2:
        det += ", cont-next"
    if flags & 4:
        det += ", reserved area"
    return ("MSCF", when, det)


# ---------------------------------------------------------------- WinHelp

def winhelp(fh, size):
    h = rd(fh, 0, 16)
    if h[:4] != b"\x3f\x5f\x03\x00":
        return None
    dirstart = struct.unpack("<i", h[4:8])[0]
    # the |SYSTEM internal file holds GenDate; find it via the b-tree the
    # cheap way: the directory is a b+tree whose leaf entries are name\0 + off
    d = rd(fh, dirstart, 9)
    if len(d) < 9:
        return ("HLP", None, "WinHelp 3.x/4.x, unreadable directory")
    used = struct.unpack("<i", d[0:4])[0]
    fh.seek(dirstart)
    blob = fh.read(min(used + 9, 65536))
    idx = blob.find(b"|SYSTEM\x00")
    if idx < 0:
        return ("HLP", None, "WinHelp, no |SYSTEM entry in the first block")
    off = struct.unpack("<i", blob[idx + 8:idx + 12])[0]
    s = rd(fh, off, 9 + 12)
    if len(s) < 21:
        return ("HLP", None, "WinHelp, |SYSTEM unreadable")
    body = s[9:]
    magic, minor, major, gendate, flags = struct.unpack("<HHHIH", body[:12])
    when = None
    if 0 < gendate < 0x7fffffff:
        try:
            when = datetime.datetime.fromtimestamp(
                gendate, datetime.timezone.utc).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            when = None
    return ("HLP", when,
            "WinHelp, |SYSTEM magic 0x%04x, version %d.%d, flags %d"
            % (magic, major, minor, flags))


# ---------------------------------------------------------------- Director

def director(fh, size):
    h = rd(fh, 0, 12)
    if h[:4] == b"RIFX":
        order = ">"
    elif h[:4] == b"XFIR":
        order = "<"
    else:
        return None
    codec = h[8:12].decode("latin-1", "replace")
    d = rd(fh, 12, 24)
    imapver = None
    if d[:4] in (b"imap", b"pami"):
        n = struct.unpack(order + "I", d[8:12])[0]
        imapver = struct.unpack(order + "I", d[20:24])[0] if len(d) >= 24 else None
    return ("RIFX" if order == ">" else "XFIR", None,
            "Director %s, codec %s, imap version %s"
            % ("big-endian (Motorola)" if order == ">" else
               "little-endian (Intel)", codec,
               "?" if imapver is None else imapver))


# ---------------------------------------------------------------- others

def gif(fh, size):
    h = rd(fh, 0, 13)
    if h[:3] != b"GIF":
        return None
    w, ht = struct.unpack("<HH", h[6:10])
    return ("GIF", None, "GIF%s, %dx%d"
            % (h[3:6].decode("latin-1"), w, ht))


def jpeg(fh, size):
    if rd(fh, 0, 2) != b"\xff\xd8":
        return None
    off = 2
    bits = []
    when = None
    guard = 0
    while off + 4 <= size and guard < 60:
        guard += 1
        m = rd(fh, off, 4)
        if m[0] != 0xff:
            break
        mk = m[1]
        ln = struct.unpack(">H", m[2:4])[0]
        if mk == 0xd9 or mk == 0xda:
            break
        seg = rd(fh, off + 4, min(ln - 2, 512))
        if mk == 0xe0 and seg[:5] == b"JFIF\x00":
            bits.append("JFIF %d.%02d" % (seg[5], seg[6]))
        if mk == 0xe1 and seg[:6] == b"Exif\x00\x00":
            bits.append("Exif")
            i = seg.find(b"20")
            for pat in (b"19", b"20"):
                j = seg.find(pat)
                while j >= 0 and j + 19 <= len(seg):
                    cand = seg[j:j + 19]
                    try:
                        when = datetime.datetime.strptime(
                            cand.decode("ascii"), "%Y:%m:%d %H:%M:%S")
                        break
                    except (ValueError, UnicodeDecodeError):
                        j = seg.find(pat, j + 1)
                if when:
                    break
        if mk == 0xee and seg[:5] == b"Adobe":
            bits.append("Adobe APP14")
        if mk == 0xfe:
            bits.append("comment %r" % seg[:60].decode("latin-1", "replace"))
        off += 2 + ln
    return ("JPEG", when, "; ".join(bits) or "bare JFIF stream")


def szdd(fh, size):
    h = rd(fh, 0, 14)
    if h[:8] == b"SZDD\x88\xf0\x27\x33":
        return ("SZDD", None, "compress.exe container, declares %d bytes"
                % struct.unpack("<I", h[10:14])[0])
    if h[:8] == b"KWAJ\x88\xf0\x27\xd1":
        meth = struct.unpack("<H", h[8:10])[0]
        return ("KWAJ", None, "KWAJ container, method %d" % meth)
    return None


def generic(fh, size):
    h = rd(fh, 0, 16)
    for sig, name in ((b"\x89PNG", "PNG"), (b"BM", "BMP"),
                      (b"PK\x03\x04", "ZIP"), (b"MThd", "MIDI"),
                      (b"%PDF", "PDF"), (b"\x00\x00\x01\x00", "ICO"),
                      (b"ITSF", "CHM"), (b"\xd0\xcf\x11\xe0", "OLE2"),
                      (b"ISc(", "InstallShield"),
                      (b"\x13\x5d\x65\x8c", "InstallShield Z")):
        if h.startswith(sig):
            return (name, None, "")
    return (None, None, "")


PROBES = [pe_ne, cab, director, quicktime, riff, aiff, winhelp, gif, jpeg,
          szdd, generic]


def classify(path, size):
    if size == 0:
        return ("(empty)", None, "zero bytes on the ISO side")
    with open(path, "rb") as fh:
        for p in PROBES:
            try:
                r = p(fh, size)
            except Exception as e:              # a probe must never kill a run
                r = (p.__name__ + "!", None, "probe raised %s" % e.__class__.__name__)
            if r and r[0]:
                return r
    return ("(unknown)", None, "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--image", default="_work/clic11.img")
    ap.add_argument("--tsv")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--disagreements", action="store_true")
    ap.add_argument("--days", type=float, default=1.0,
                    help="threshold in days for calling A and B different")
    a = ap.parse_args()

    recorded = {}
    if a.image:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import assoc
        img = assoc.Img(a.image)
        vd = None
        for n in range(16, 32):
            s = img.sector(n)
            if s is None or s[1:6] != b"CD001":
                continue
            if s[0] == 2:
                vd = s
                break
            if s[0] == 255:
                break
        if vd is not None:
            root = vd[156:190]
            for path, lba, ln, flags, when in assoc.walk(
                    img, struct.unpack("<I", root[2:6])[0],
                    struct.unpack("<I", root[10:14])[0], True):
                if flags & 2 or flags & 4 or not when:
                    continue
                recorded[path.upper()] = datetime.datetime.strptime(
                    when.split(" tz")[0], "%Y-%m-%d %H:%M:%S")

    rows = []
    nofile = 0
    for dp, dn, fn in os.walk(a.root):
        for f in sorted(fn):
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, a.root).replace(os.sep, "/")
            st = os.stat(p)
            A = recorded.get(rel.upper())
            if A is None:
                A = datetime.datetime.fromtimestamp(st.st_mtime)
                nofile += 1
            kind, B, C = classify(p, st.st_size)
            rows.append((rel, st.st_size, A, kind, B, C))
    print("clock A source : %s"
          % ("ISO 9660 directory records out of %s" % a.image
             if recorded else "filesystem mtime (no image given)"))
    if recorded:
        print("records matched: %d of %d; %d fell back to the filesystem mtime"
              % (len(rows) - nofile, len(rows), nofile))
    print()

    have_b = [r for r in rows if r[4] is not None]
    print("files                       : %d" % len(rows))
    print("files with an internal clock: %d  (%.1f %%)"
          % (len(have_b), 100.0 * len(have_b) / max(len(rows), 1)))
    if have_b:
        bs = sorted(r[4] for r in have_b)
        print("internal clock spans        : %s .. %s"
              % (bs[0].strftime("%Y-%m-%d %H:%M:%S"),
                 bs[-1].strftime("%Y-%m-%d %H:%M:%S")))
        print("                              %d days"
              % (bs[-1] - bs[0]).days)
    dirs = sorted(r[2] for r in rows)
    print("directory clock spans       : %s .. %s   %d days"
          % (dirs[0].strftime("%Y-%m-%d %H:%M:%S"),
             dirs[-1].strftime("%Y-%m-%d %H:%M:%S"),
             (dirs[-1] - dirs[0]).days))
    print()

    print("by container kind:")
    kc = Counter(r[3] for r in rows)
    kb = Counter()
    kwb = Counter()
    for r in rows:
        kb[r[3]] += r[1]
        if r[4] is not None:
            kwb[r[3]] += 1
    print("  %-12s %6s %14s %10s" % ("kind", "files", "bytes", "with B"))
    for k, n in kc.most_common():
        print("  %-12s %6d %14d %10d" % (k, n, kb[k], kwb[k]))
    print()

    thr = datetime.timedelta(days=a.days)
    ahead = [r for r in have_b if r[4] - r[2] > thr]
    behind = [r for r in have_b if r[2] - r[4] > thr]
    same = len(have_b) - len(ahead) - len(behind)
    print("comparing clock A (directory) with clock B (internal), threshold %g days:"
          % a.days)
    print("  agree within threshold          : %d" % same)
    print("  internal NEWER than directory   : %d   <- impossible by copying" % len(ahead))
    print("  internal OLDER than directory   : %d   <- ordinary: a copied file" % len(behind))
    print()

    if a.disagreements or ahead:
        print("files whose internal clock is NEWER than their directory record:")
        for r in sorted(ahead, key=lambda r: r[4] - r[2], reverse=True):
            print("  %-52s  A %s   B %s   +%s"
                  % (r[0][:52], r[2].strftime("%Y-%m-%d %H:%M"),
                     r[4].strftime("%Y-%m-%d %H:%M"), r[4] - r[2]))
        print()

    if a.summary:
        print("the widest gaps, internal older than directory:")
        for r in sorted(behind, key=lambda r: r[2] - r[4], reverse=True)[:25]:
            print("  %-52s  A %s   B %s   -%s"
                  % (r[0][:52], r[2].strftime("%Y-%m-%d"),
                     r[4].strftime("%Y-%m-%d"), (r[2] - r[4])))
        print()

    if a.tsv:
        with open(a.tsv, "w", encoding="utf-8", newline="") as fh:
            fh.write("path\tsize\tclockA\tkind\tclockB\tclockC\tdelta_days\n")
            for rel, sz, A, kind, B, C in rows:
                fh.write("%s\t%d\t%s\t%s\t%s\t%s\t%s\n"
                         % (rel, sz, A.strftime("%Y-%m-%d %H:%M:%S"), kind,
                            B.strftime("%Y-%m-%d %H:%M:%S") if B else "",
                            C.replace("\t", " "),
                            "%.3f" % ((B - A).total_seconds() / 86400.0)
                            if B else ""))
        print("wrote %s" % a.tsv)


if __name__ == "__main__":
    main()
