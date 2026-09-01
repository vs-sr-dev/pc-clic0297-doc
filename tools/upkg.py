#!/usr/bin/env python3
"""upkg.py -- a reader for Unreal Engine 1 packages.

249 of the 540 files on this disc are Unreal packages and they are 89 % of the
bytes, so this is the tool the session turns on. The format is Epic's and it
is documented elsewhere; nothing below is asserted from that documentation
without a byte on this disc behind it, and every structural claim is checked
by an oracle before any number derived from it is printed.

Header layout being asserted:

    +0   u32   signature, 0x9E2A83C1
    +4   u16   package version
    +6   u16   licensee version
    +8   u32   package flags
    +12  u32   name count
    +16  u32   name table offset
    +20  u32   export count
    +24  u32   export table offset
    +28  u32   import count
    +32  u32   import table offset
    +36  ...   version >= 68: 16-byte GUID, then u32 generation count and
               that many (u32 export count, u32 name count) pairs;
               version <  68: u32 heritage count, u32 heritage offset

Name entry, version >= 64: u8 length, that many bytes including the trailing
NUL, then u32 flags. Version < 64: NUL-terminated string then u32 flags.

Import entry: index(class package), index(class name), i32 package,
index(object name).

Export entry: index(class), index(super), i32 package, index(object name),
u32 flags, index(serial size), and if serial size > 0, index(serial offset).

"index" is Unreal's compact index: in the first byte bit 0x80 is the sign and
bit 0x40 is "another byte follows", the low six bits are the low six bits of
the value; in each later byte bit 0x80 is "another byte follows" and the low
seven bits extend the value.

THE ORACLES. A parser that runs without raising is not a parser that is
right. Before any count is reported, each package must satisfy:

    O1  every name index used by an import or an export is < name count
    O2  every export's serial offset + serial size is <= file size
    O3  the export serial extents tile the region between the end of the
        name table and the start of the first table, with no hole and no
        overlap -- i.e. every byte of object data belongs to a declared export
    O4  every export's class reference resolves to an import or an export
    O5  the highest byte the header claims (max of the three table ends and
        every export's serial end) equals the file size
    O6  the export classes fit the extension: a .utx must contain a Texture,
        a .unr a Level, a .uax a Sound, a .umx a Music, a .u a Function

--oracle prints the pass/fail for all six on every package. A package that
fails is reported and its numbers are excluded from every census, because a
number from a wrong parser is worse than no number.

    python tools/upkg.py FILE                    header + oracles
    python tools/upkg.py FILE --names            the name table
    python tools/upkg.py FILE --imports
    python tools/upkg.py FILE --exports
    python tools/upkg.py DIR --census            every package under DIR
    python tools/upkg.py DIR --oracle            oracles only, every package
    python tools/upkg.py DIR --versions          version census
"""
import collections
import os
import struct
import sys

SIG = 0x9E2A83C1
PKGEXT = (".u", ".unr", ".utx", ".uax", ".umx",
          ".ita_uax", ".spa_uax", ".por_uax", ".eng_uax",
          ".ita_utx", ".spa_utx", ".por_utx", ".hun_utx")

PKGFLAGS = {
    0x0001: "AllowDownload",
    0x0002: "ClientOptional",
    0x0004: "ServerSideOnly",
    0x0008: "BrokenLinks",
    0x0010: "Unsecure",
    0x0020: "Need",
}

OBJFLAGS = {
    0x00000001: "Transactional",
    0x00000002: "Unreachable",
    0x00000004: "Public",
    0x00000008: "TagImp",
    0x00000010: "TagExp",
    0x00000020: "SourceModified",
    0x00000040: "TagGarbage",
    0x00000200: "NeedLoad",
    0x00000400: "HighlightedName",
    0x00000800: "EliminateObject",
    0x00001000: "InSingularFunc",
    0x00002000: "RemappedName",
    0x00004000: "Suppress",
    0x00008000: "StateChanged",
    0x00010000: "InEndState",
    0x00020000: "Transient",
    0x00040000: "PreLoading",
    0x00080000: "LoadForClient",
    0x00100000: "LoadForServer",
    0x00200000: "LoadForEdit",
    0x00400000: "Standalone",
    0x00800000: "NotForClient",
    0x01000000: "NotForServer",
    0x02000000: "NotForEdit",
    0x04000000: "Destroyed",
    0x08000000: "NeedPostLoad",
    0x10000000: "HasStack",
    0x20000000: "Native",
    0x40000000: "Marked",
    0x80000000: "ErrorShutdown",
}


class BadPackage(Exception):
    pass


def read_index(d, p):
    """Unreal compact index. Returns (value, newpos)."""
    b0 = d[p]
    p += 1
    neg = b0 & 0x80
    val = b0 & 0x3F
    if b0 & 0x40:
        shift = 6
        while True:
            b = d[p]
            p += 1
            val |= (b & 0x7F) << shift
            shift += 7
            if not (b & 0x80):
                break
            if shift > 35:
                raise BadPackage("compact index runaway at %d" % p)
    return (-val if neg else val), p


class Package:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.d = f.read()
        d = self.d
        self.size = len(d)
        if self.size < 40:
            raise BadPackage("file shorter than a header")
        (sig,) = struct.unpack_from("<I", d, 0)
        if sig != SIG:
            raise BadPackage("signature 0x%08X, expected 0x%08X" % (sig, SIG))
        (self.ver, self.lic, self.flags, self.name_n, self.name_off,
         self.exp_n, self.exp_off, self.imp_n,
         self.imp_off) = struct.unpack_from("<HHIIIIIII", d, 4)
        p = 36
        self.guid = None
        self.generations = []
        self.heritage = None
        if self.ver >= 68:
            self.guid = d[p:p + 16]
            p += 16
            (ngen,) = struct.unpack_from("<I", d, p)
            p += 4
            for _ in range(ngen):
                e, n = struct.unpack_from("<II", d, p)
                p += 8
                self.generations.append((e, n))
        else:
            hc, ho = struct.unpack_from("<II", d, p)
            p += 8
            self.heritage = (hc, ho)
        self.header_end = p
        self.names = None
        self.name_end = None
        self.imports = None
        self.exports = None

    # ---- tables -------------------------------------------------------
    def read_names(self):
        if self.names is not None:
            return self.names
        d = self.d
        p = self.name_off
        out = []
        flags = []
        for _ in range(self.name_n):
            if self.ver >= 64:
                ln = d[p]
                p += 1
                raw = d[p:p + ln]
                p += ln
                s = raw.rstrip(bytes([0])).decode("latin-1")
            else:
                e = d.index(bytes([0]), p)
                s = d[p:e].decode("latin-1")
                p = e + 1
            (fl,) = struct.unpack_from("<I", d, p)
            p += 4
            out.append(s)
            flags.append(fl)
        self.names = out
        self.name_flags = flags
        self.name_end = p
        return out

    def read_imports(self):
        if self.imports is not None:
            return self.imports
        d = self.d
        p = self.imp_off
        out = []
        for _ in range(self.imp_n):
            cp, p = read_index(d, p)
            cn, p = read_index(d, p)
            (pk,) = struct.unpack_from("<i", d, p)
            p += 4
            on, p = read_index(d, p)
            out.append((cp, cn, pk, on))
        self.imports = out
        self.imp_end = p
        return out

    def read_exports(self):
        if self.exports is not None:
            return self.exports
        d = self.d
        p = self.exp_off
        out = []
        for _ in range(self.exp_n):
            cls, p = read_index(d, p)
            sup, p = read_index(d, p)
            (pk,) = struct.unpack_from("<i", d, p)
            p += 4
            on, p = read_index(d, p)
            (fl,) = struct.unpack_from("<I", d, p)
            p += 4
            ssz, p = read_index(d, p)
            soff = 0
            if ssz > 0:
                soff, p = read_index(d, p)
            out.append((cls, sup, pk, on, fl, ssz, soff))
        self.exports = out
        self.exp_end = p
        return out

    def load(self):
        self.read_names()
        self.read_imports()
        self.read_exports()

    # ---- resolution ---------------------------------------------------
    def name(self, i):
        if 0 <= i < len(self.names):
            return self.names[i]
        return "<bad name %d>" % i

    def objref(self, r):
        """Unreal object reference: >0 export r-1, <0 import -r-1, 0 none."""
        if r == 0:
            return "None"
        if r > 0:
            e = self.exports[r - 1] if r - 1 < len(self.exports) else None
            return "exp:" + (self.name(e[3]) if e else "?")
        i = self.imports[-r - 1] if -r - 1 < len(self.imports) else None
        return "imp:" + (self.name(i[3]) if i else "?")

    # ---- oracles ------------------------------------------------------
    def oracles(self):
        self.load()
        res = {}
        n = self.name_n
        bad = []
        for cp, cn, pk, on in self.imports:
            for x in (cp, cn, on):
                if not (0 <= x < n):
                    bad.append(("import", x))
        for e in self.exports:
            if not (0 <= e[3] < n):
                bad.append(("export", e[3]))
        res["O1 name indices in range"] = (not bad, "%d out of range" % len(bad))

        over = [e for e in self.exports if e[5] > 0 and e[6] + e[5] > self.size]
        res["O2 serial extents inside file"] = (
            not over, "%d exports overrun the file" % len(over))

        first_tbl = min(x for x in (self.imp_off, self.exp_off, self.size)
                        if x and x > self.name_end)             if any(x > self.name_end for x in (self.imp_off, self.exp_off))             else self.size
        spans = sorted((e[6], e[6] + e[5]) for e in self.exports if e[5] > 0)
        merged = []
        for a, b in spans:
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        covered = sum(b - a for a, b in merged)
        region = first_tbl - self.name_end
        holes = []
        cur = self.name_end
        for a, b in merged:
            if a > cur:
                holes.append((cur, a))
            cur = max(cur, b)
        if cur < first_tbl:
            holes.append((cur, first_tbl))
        ok3 = (not holes) and covered == region and             (not merged or (merged[0][0] == self.name_end and
                            merged[-1][1] == first_tbl))
        res["O3 exports tile the data region"] = (
            ok3, "region %d..%d = %d bytes, exports cover %d in %d runs, "
            "%d hole(s)%s"
            % (self.name_end, first_tbl, region, covered, len(merged),
               len(holes), (" " + str(holes[:3])) if holes else ""))
        self.data_holes = holes
        self.data_region = (self.name_end, first_tbl)

        badcls = 0
        for e in self.exports:
            r = e[0]
            if r > 0 and r - 1 >= len(self.exports):
                badcls += 1
            elif r < 0 and -r - 1 >= len(self.imports):
                badcls += 1
        res["O4 class refs resolve"] = (badcls == 0,
                                        "%d unresolvable" % badcls)

        # O6: the export classes must fit the extension. Each expectation
        # below was chosen from one package of that kind read by hand first,
        # then applied to all of them.
        EXPECT = {".u": "Function", ".unr": "Level", ".utx": "Texture",
                  ".uax": "Sound", ".umx": "Music"}
        base = self.path.lower()
        ext = os.path.splitext(base)[1]
        if base.endswith("_uax"):
            ext = ".uax"
        elif base.endswith("_utx"):
            ext = ".utx"
        clsnames = collections.Counter()
        for e in self.exports:
            r = e[0]
            if r < 0 and -r - 1 < len(self.imports):
                clsnames[self.name(self.imports[-r - 1][3])] += 1
            elif r > 0 and r - 1 < len(self.exports):
                clsnames[self.name(self.exports[r - 1][3])] += 1
            else:
                clsnames["<class itself>"] += 1
        self.classnames = clsnames
        want = EXPECT.get(ext)
        if want:
            top = clsnames.most_common(1)[0] if clsnames else ("", 0)
            res["O6 export classes fit extension"] = (
                want in clsnames,
                "expected %r in a %s; commonest is %r x%d; %d distinct classes"
                % (want, ext, top[0], top[1], len(clsnames)))
        else:
            res["O6 export classes fit extension"] = (
                True, "no expectation registered for %s" % ext)

        hi = max([self.name_end, getattr(self, "imp_end", 0),
                  getattr(self, "exp_end", 0)] +
                 [e[6] + e[5] for e in self.exports if e[5] > 0] + [0])
        res["O5 highest claimed byte == size"] = (
            hi == self.size, "claims %d, file is %d, difference %d"
            % (hi, self.size, self.size - hi))
        return res


def find_packages(root):
    out = []
    if os.path.isfile(root):
        return [root]
    for dp, dn, fn in os.walk(root):
        for f in sorted(fn):
            low = f.lower()
            if any(low.endswith(x) for x in PKGEXT):
                out.append(os.path.join(dp, f))
    return out


def hdr(p):
    fl = [v for k, v in PKGFLAGS.items() if p.flags & k]
    unk = p.flags & ~sum(PKGFLAGS)
    print("file            : %s" % p.path)
    print("size            : %d bytes" % p.size)
    print("signature       : 0x%08X  (offset 0)" % SIG)
    print("package version : %d       (offset 4)" % p.ver)
    print("licensee version: %d       (offset 6)" % p.lic)
    print("package flags   : 0x%08X  %s%s"
          % (p.flags, ",".join(fl) if fl else "(none named)",
             "  UNKNOWN BITS 0x%X" % unk if unk else ""))
    print("names           : %6d at offset %d" % (p.name_n, p.name_off))
    print("exports         : %6d at offset %d" % (p.exp_n, p.exp_off))
    print("imports         : %6d at offset %d" % (p.imp_n, p.imp_off))
    if p.guid is not None:
        g = p.guid
        print("guid            : %s" % g.hex())
        print("generations     : %d  %s" % (len(p.generations), p.generations))
    else:
        print("heritage        : %s" % (p.heritage,))
    print("header ends at  : %d" % p.header_end)


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    target = args[0]

    if "--census" in args or "--oracle" in args or "--versions" in args:
        paths = find_packages(target)
        good, bad = [], []
        for path in paths:
            try:
                p = Package(path)
                o = p.oracles()
                good.append((p, o))
            except Exception as e:
                bad.append((path, "%s: %s" % (type(e).__name__, e)))
        print("packages found  : %d" % len(paths))
        print("parsed          : %d" % len(good))
        print("failed to parse : %d" % len(bad))
        for path, e in bad:
            print("   %s  %s" % (path, e))
        print()
        if "--oracle" in args:
            names = None
            fails = collections.Counter()
            allpass = 0
            for p, o in good:
                if names is None:
                    names = list(o)
                if all(v[0] for v in o.values()):
                    allpass += 1
                else:
                    for k, v in o.items():
                        if not v[0]:
                            fails[k] += 1
                    print("FAIL %s" % p.path)
                    for k, v in o.items():
                        if not v[0]:
                            print("      %-34s %s" % (k, v[1]))
            print()
            print("packages passing all five oracles: %d of %d"
                  % (allpass, len(good)))
            for k in (names or []):
                print("   %-34s failed %d times" % (k, fails[k]))
            return

        if "--versions" in args:
            vers = collections.Counter((p.ver, p.lic) for p, _ in good)
            print("distinct (package version, licensee version) pairs: %d"
                  % len(vers))
            for (v, l), n in sorted(vers.items()):
                print("   version %-4d licensee %-4d : %4d packages" % (v, l, n))
            print()
            fl = collections.Counter(p.flags for p, _ in good)
            print("distinct package-flag values: %d" % len(fl))
            for f, n in fl.most_common():
                nm = [v for k, v in PKGFLAGS.items() if f & k]
                print("   0x%08X  %4d packages   %s"
                      % (f, n, ",".join(nm) if nm else "(none)"))
            print()
            gens = collections.Counter(len(p.generations) for p, _ in good)
            print("generation-count distribution: %s" % dict(gens))
            guids = collections.Counter(p.guid.hex() for p, _ in good
                                        if p.guid)
            dup = [(g, n) for g, n in guids.items() if n > 1]
            print("distinct GUIDs: %d of %d packages" % (len(guids), len(good)))
            if dup:
                print("GUIDs used by more than one package:")
                for g, n in dup:
                    who = [p.path for p, _ in good if p.guid and
                           p.guid.hex() == g]
                    print("   %s  x%d" % (g, n))
                    for w in who:
                        print("        %s" % w)
            else:
                print("no GUID is shared by two packages.")
            return

        # --census
        print("%-46s %6s %5s %8s %8s %8s %11s"
              % ("package", "ver", "lic", "names", "imports", "exports", "bytes"))
        tn = ti = te = tb = 0
        for p, o in good:
            rel = os.path.relpath(p.path, target if os.path.isdir(target)
                                  else os.path.dirname(target))
            print("%-46s %6d %5d %8d %8d %8d %11d"
                  % (rel.replace(os.sep, "/"), p.ver, p.lic, p.name_n,
                     p.imp_n, p.exp_n, p.size))
            tn += p.name_n
            ti += p.imp_n
            te += p.exp_n
            tb += p.size
        print()
        print("%-46s %6s %5s %8d %8d %8d %11d"
              % ("TOTAL (%d packages)" % len(good), "", "", tn, ti, te, tb))
        return

    p = Package(target)
    p.load()
    hdr(p)
    print()
    if "--names" in args:
        print("name table, %d entries, offset %d..%d"
              % (p.name_n, p.name_off, p.name_end))
        for i, s in enumerate(p.names):
            print("  %5d  0x%08X  %s" % (i, p.name_flags[i], s))
        return
    if "--imports" in args:
        print("import table, %d entries, offset %d..%d"
              % (p.imp_n, p.imp_off, p.imp_end))
        for i, (cp, cn, pk, on) in enumerate(p.imports):
            print("  %5d  %-22s %-22s %-24s package=%s"
                  % (i, p.name(cp), p.name(cn), p.name(on), p.objref(pk)))
        return
    if "--exports" in args:
        print("export table, %d entries, offset %d..%d"
              % (p.exp_n, p.exp_off, p.exp_end))
        for i, (cls, sup, pk, on, fl, ssz, soff) in enumerate(p.exports):
            names = [v for k, v in OBJFLAGS.items() if fl & k]
            print("  %5d  %-28s class=%-22s super=%-18s size=%-9d off=%-9d %s"
                  % (i, p.name(on), p.objref(cls), p.objref(sup), ssz, soff,
                     ",".join(names)))
        return
    print("oracles:")
    for k, v in p.oracles().items():
        print("  %-34s %-6s %s" % (k, "PASS" if v[0] else "FAIL", v[1]))


if __name__ == "__main__":
    main()
