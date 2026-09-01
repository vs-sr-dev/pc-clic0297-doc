#!/usr/bin/env python3
"""pe.py -- a PE/COFF reader, standard library only.

pc-mystictowers-doc had `mzinfo.py` for 16-bit MZ executables. This disc is
Win32, so none of that applies and this is a new tool. It reports, in order of
how much it tells you about who built the file:

  * the **Rich header** -- the undocumented block Microsoft's linker writes
    between the DOS stub and `PE\\0\\0`, XOR-masked with a key stored in the
    block itself. It lists every tool that contributed object code, by
    product ID and build number, with a count of objects per tool. It is the
    single most specific compiler fingerprint a Windows binary carries, and
    it survives in files whose version resource is empty.
  * the **COFF timestamp**, seconds since the Unix epoch, written by the
    linker at link time. On this disc it is a real date and not a
    reproducible-build constant, which makes it the only trustworthy clock in
    the whole image.
  * **VS_VERSIONINFO**, if present: company, product, file version, and the
    free-text fields nobody remembers to clear.
  * imports, exports, sections, per-section entropy, and where the entry
    point lands -- which together answer "is this packed" without trusting a
    signature scan.

    python tools/pe.py FILE
    python tools/pe.py FILE --imports
    python tools/pe.py FILE --sections
    python tools/pe.py DIR --summary
"""
import datetime
import math
import os
import struct
import sys
from collections import Counter

# Rich header product IDs. Only the ones that turn up in 1999-2003 binaries
# are named; anything else prints as its raw number, which is honest.
PRODID = {
    0x00: "unknown / linker padding",
    0x01: "Import (linker-generated)",
    0x02: "Linker 5.10 (VC++ 5.0)",
    0x03: "Cvtomf 5.10",
    0x04: "Linker 5.10 (VC++ 5.0)",
    0x05: "Cvtomf 5.10",
    0x06: "Cvtres 5.00",
    0x07: "Utc11_Basic",
    0x08: "Utc11_C",
    0x09: "Utc12_Basic",
    0x0A: "Utc12_C (VC++ 6.0 C)",
    0x0B: "Utc12_CPP (VC++ 6.0 C++)",
    0x0C: "AliasObj60",
    0x0D: "VisualBasic 6.0",
    0x0E: "Masm613",
    0x0F: "Masm710",
    0x10: "Linker 5.11",
    0x11: "Cvtomf 5.11",
    0x12: "Masm614",
    0x13: "Linker 5.12",
    0x14: "Cvtomf 5.12",
    0x15: "Masm615",
    0x16: "Utc12_C_Std",
    0x17: "Utc12_CPP_Std",
    0x18: "Utc12_C_Book",
    0x19: "Utc12_CPP_Book",
    0x1A: "Implib 6.00",
    0x1B: "Cvtomf 6.00",
    0x1C: "Cvtres 6.00",
    0x1D: "Utc12_C_Pgo / Linker 6.00",
    0x1E: "Utc12_CPP_Pgo",
    0x1F: "Masm620",
    0x20: "AliasObj70",
    0x21: "Linker 6.10",
    0x22: "Cvtomf 6.10",
    0x23: "Cvtres 6.10",
    0x24: "Utc13_Basic",
    0x25: "Utc13_C",
    0x26: "Utc13_CPP",
    0x27: "Linker 6.20",
    0x28: "Cvtomf 6.20",
    0x29: "Cvtres 6.20",
    0x2A: "Masm700",
    0x3D: "Linker 7.10 (VC++ .NET 2003)",
    0x5D: "Linker 8.00",
}

MACHINE = {0x014C: "i386", 0x8664: "x86-64", 0x01C0: "ARM",
           0x0166: "MIPS R4000", 0x01F0: "PowerPC"}

SUBSYS = {1: "native", 2: "Windows GUI", 3: "Windows console",
          5: "OS/2 console", 7: "POSIX console", 9: "Windows CE GUI"}

DLLCHAR = [(0x0040, "DYNAMIC_BASE"), (0x0080, "FORCE_INTEGRITY"),
           (0x0100, "NX_COMPAT"), (0x0200, "NO_ISOLATION"),
           (0x0400, "NO_SEH"), (0x0800, "NO_BIND"),
           (0x2000, "WDM_DRIVER"), (0x8000, "TERMINAL_SERVER_AWARE")]

SECCHAR = [(0x00000020, "CODE"), (0x00000040, "INITIALIZED_DATA"),
           (0x00000080, "UNINITIALIZED_DATA"), (0x02000000, "DISCARDABLE"),
           (0x04000000, "NOT_CACHED"), (0x08000000, "NOT_PAGED"),
           (0x10000000, "SHARED"), (0x20000000, "EXECUTE"),
           (0x40000000, "READ"), (0x80000000, "WRITE")]

PACKER_MAGIC = [
    (b"UPX0", "UPX section name"), (b"UPX1", "UPX section name"),
    (b"UPX!", "UPX identifier"),
    (b".aspack", "ASPack section"), (b".adata", "ASPack section"),
    (b"ASPack", "ASPack string"),
    (b"PECompact", "PECompact"), (b"PEC2", "PECompact 2"),
    (b".petite", "Petite"), (b"petite", "Petite"),
    (b"NEOLITE", "Neolite"), (b".neolit", "Neolite"),
    (b"WWPACK", "WWPack32"), (b".WWP32", "WWPack32"),
    (b"SafeDisc", "SafeDisc"), (b"BoG_", "SafeDisc BoG_ marker"),
    (b"LaserLock", "LaserLock"), (b"SecuROM", "SecuROM"),
    (b".cms_t", "SecuROM section"), (b".cms_d", "SecuROM section"),
    (b"StarForce", "StarForce"), (b".sforce", "StarForce section"),
    (b"VOB ProtectCD", "VOB ProtectCD"),
    (b".shrink", "Shrinker"), (b"Themida", "Themida"),
    (b".vmp0", "VMProtect"),
]


def entropy(b):
    if not b:
        return 0.0
    c = Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def ts(v):
    if v == 0:
        return "0 (unset)"
    try:
        d = datetime.datetime.fromtimestamp(v, datetime.timezone.utc)
        return "%d  %s UTC" % (v, d.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception:
        return "%d (out of range)" % v


class PE(object):
    def __init__(self, path):
        self.path = path
        self.data = open(path, "rb").read()
        d = self.data
        if d[:2] != b"MZ":
            raise ValueError("not an MZ image")
        self.e_lfanew = struct.unpack_from("<I", d, 0x3C)[0]
        if d[self.e_lfanew:self.e_lfanew + 4] != b"PE\x00\x00":
            raise ValueError("no PE signature at e_lfanew=%d" % self.e_lfanew)
        o = self.e_lfanew + 4
        (self.machine, self.nsec, self.timestamp, self.symtab, self.nsym,
         self.optsize, self.characteristics) = struct.unpack_from(
            "<HHIIIHH", d, o)
        oo = o + 20
        self.magic = struct.unpack_from("<H", d, oo)[0]
        self.pe32plus = (self.magic == 0x20B)
        self.linker = (d[oo + 2], d[oo + 3])
        (self.sizecode, self.sizeinit, self.sizeuninit, self.entry,
         self.basecode) = struct.unpack_from("<IIIII", d, oo + 4)
        if self.pe32plus:
            self.imagebase = struct.unpack_from("<Q", d, oo + 24)[0]
            nrva_off = oo + 108
        else:
            self.basedata = struct.unpack_from("<I", d, oo + 24)[0]
            self.imagebase = struct.unpack_from("<I", d, oo + 28)[0]
            nrva_off = oo + 92
        self.secalign, self.filealign = struct.unpack_from("<II", d, oo + 32)
        self.osver = struct.unpack_from("<HH", d, oo + 40)
        self.imgver = struct.unpack_from("<HH", d, oo + 44)
        self.subsysver = struct.unpack_from("<HH", d, oo + 48)
        self.sizeimage, self.sizehdr = struct.unpack_from("<II", d, oo + 56)
        self.checksum = struct.unpack_from("<I", d, oo + 64)[0]
        self.subsystem, self.dllchar = struct.unpack_from("<HH", d, oo + 68)
        self.nrva = struct.unpack_from("<I", d, nrva_off)[0]
        self.dirs = []
        for i in range(min(self.nrva, 16)):
            self.dirs.append(struct.unpack_from("<II", d, nrva_off + 4 + i * 8))
        self.sections = []
        so = oo + self.optsize
        for i in range(self.nsec):
            b = d[so + i * 40:so + i * 40 + 40]
            if len(b) < 40:
                break
            name = b[:8].rstrip(b"\x00").decode("latin-1", "replace")
            vsize, vaddr, rsize, roff = struct.unpack_from("<IIII", b, 8)
            ch = struct.unpack_from("<I", b, 36)[0]
            self.sections.append(dict(name=name, vsize=vsize, vaddr=vaddr,
                                      rsize=rsize, roff=roff, ch=ch))

    # -------------------------------------------------------------- helpers
    def rva2off(self, rva):
        for s in self.sections:
            if s["vaddr"] <= rva < s["vaddr"] + max(s["vsize"], s["rsize"]):
                off = rva - s["vaddr"] + s["roff"]
                if off < len(self.data):
                    return off
        return None

    def cstr(self, off, limit=512):
        if off is None or off >= len(self.data):
            return ""
        end = self.data.find(b"\x00", off, off + limit)
        if end < 0:
            end = off + limit
        return self.data[off:end].decode("latin-1", "replace")

    def section_of(self, rva):
        for s in self.sections:
            if s["vaddr"] <= rva < s["vaddr"] + max(s["vsize"], s["rsize"]):
                return s["name"]
        return "(outside every section)"

    # ----------------------------------------------------------- rich header
    def rich(self):
        d = self.data[:self.e_lfanew]
        i = d.rfind(b"Rich")
        if i < 0 or i + 8 > len(d):
            return None
        key = struct.unpack_from("<I", d, i + 4)[0]
        j = i
        start = None
        while j >= 4:
            j -= 4
            if struct.unpack_from("<I", d, j)[0] ^ key == 0x536E6144:  # 'DanS'
                start = j
                break
        if start is None:
            return None
        out = []
        p = start + 16
        while p + 8 <= i:
            v = struct.unpack_from("<I", d, p)[0] ^ key
            c = struct.unpack_from("<I", d, p + 4)[0] ^ key
            out.append((v >> 16, v & 0xFFFF, c))
            p += 8
        return dict(key=key, start=start, end=i + 8, entries=out)

    # --------------------------------------------------------------- imports
    def imports(self):
        if len(self.dirs) < 2:
            return []
        rva, size = self.dirs[1]
        if not rva:
            return []
        off = self.rva2off(rva)
        if off is None:
            return []
        out = []
        while True:
            b = self.data[off:off + 20]
            if len(b) < 20 or not any(b):
                break
            oft, tds, fc, namerva, fthunk = struct.unpack("<IIIII", b)
            dll = self.cstr(self.rva2off(namerva), 128)
            funcs = []
            t = oft or fthunk
            if t:
                to = self.rva2off(t)
                if to is not None:
                    while True:
                        v = struct.unpack_from("<I", self.data, to)[0]
                        if not v:
                            break
                        if v & 0x80000000:
                            funcs.append("#%d" % (v & 0xFFFF))
                        else:
                            funcs.append(self.cstr(self.rva2off(v) + 2
                                                   if self.rva2off(v) is not None
                                                   else None, 128))
                        to += 4
                        if len(funcs) > 4000:
                            break
            out.append((dll, funcs, tds))
            off += 20
        return out

    def exports(self):
        if len(self.dirs) < 1:
            return None
        rva, size = self.dirs[0]
        if not rva:
            return None
        off = self.rva2off(rva)
        if off is None:
            return None
        (flags, tstamp, mj, mn, namerva, ordbase, naddr, nnames,
         addrrva, namesrva, ordsrva) = struct.unpack_from("<IIHHIIIIIII",
                                                          self.data, off)
        name = self.cstr(self.rva2off(namerva), 128)
        names = []
        no = self.rva2off(namesrva)
        if no is not None:
            for i in range(min(nnames, 4000)):
                r = struct.unpack_from("<I", self.data, no + i * 4)[0]
                names.append(self.cstr(self.rva2off(r), 128))
        return dict(name=name, tstamp=tstamp, nfunc=naddr, nnames=nnames,
                    ordbase=ordbase, names=names)

    # -------------------------------------------------------- version resource
    def versioninfo(self):
        """Find VS_VERSIONINFO without walking the resource tree: the literal
        UTF-16 'VS_VERSION_INFO' is unique enough, and a hand-rolled tree
        walker is more code than it is worth for one string block."""
        needle = "VS_VERSION_INFO".encode("utf-16-le")
        i = self.data.find(needle)
        if i < 0:
            return None
        # The fixed file info follows, dword-aligned, starting with 0xFEEF04BD
        j = self.data.find(struct.pack("<I", 0xFEEF04BD), i, i + 128)
        fixed = None
        if j > 0:
            (sig, sver, fvms, fvls, pvms, pvls, fflagsmask, fflags, os_,
             ftype, fsubtype, fdms, fdls) = struct.unpack_from(
                "<IIIIIIIIIIIII", self.data, j)
            fixed = dict(
                fileversion="%d.%d.%d.%d" % (fvms >> 16, fvms & 0xFFFF,
                                             fvls >> 16, fvls & 0xFFFF),
                productversion="%d.%d.%d.%d" % (pvms >> 16, pvms & 0xFFFF,
                                                pvls >> 16, pvls & 0xFFFF),
                flags=fflags & fflagsmask, os=os_, type=ftype)
        # Harvest the UTF-16 key/value pairs in the block that follows.
        blob = self.data[i:i + 8192]
        strs = []
        cur = []
        for k in range(0, len(blob) - 1, 2):
            ch = blob[k] | (blob[k + 1] << 8)
            if 32 <= ch < 0xFFFE and ch != 0:
                cur.append(chr(ch))
            else:
                if len(cur) >= 2:
                    strs.append("".join(cur))
                cur = []
        return dict(fixed=fixed, strings=strs, at=i)

    # ------------------------------------------------------------- reporting
    def report(self, show_imports=True, show_sections=True):
        d = self.data
        print("file                : %s" % self.path)
        print("size                : %d bytes" % len(d))
        print("e_lfanew            : 0x%X" % self.e_lfanew)
        print("machine             : 0x%04X %s" % (
            self.machine, MACHINE.get(self.machine, "?")))
        print("characteristics     : 0x%04X%s" % (
            self.characteristics,
            "  DLL" if self.characteristics & 0x2000 else "  EXE"))
        print("COFF timestamp      : %s" % ts(self.timestamp))
        print("linker version      : %d.%d" % self.linker)
        print("optional header     : 0x%X (%s)" % (
            self.magic, "PE32+" if self.pe32plus else "PE32"))
        print("image base          : 0x%08X" % self.imagebase)
        print("entry point RVA     : 0x%08X  in section %s" % (
            self.entry, self.section_of(self.entry)))
        print("section alignment   : %d / file alignment %d" % (
            self.secalign, self.filealign))
        print("subsystem           : %d %s  (version %d.%d)" % (
            self.subsystem, SUBSYS.get(self.subsystem, "?"),
            self.subsysver[0], self.subsysver[1]))
        print("OS version required : %d.%d" % self.osver)
        print("size of image       : %d" % self.sizeimage)
        print("checksum in header  : 0x%08X" % self.checksum)
        flags = [n for m, n in DLLCHAR if self.dllchar & m]
        print("dll characteristics : 0x%04X %s" % (
            self.dllchar, " ".join(flags) if flags else "(none)"))
        print("data directories    : %d" % self.nrva)

        r = self.rich()
        print()
        if r is None:
            print("Rich header         : ABSENT")
            print("  (absent means either a non-Microsoft linker, or a tool")
            print("   that stripped it -- both are findings, and they differ)")
        else:
            print("Rich header         : present, XOR key 0x%08X, "
                  "file offset %d..%d" % (r["key"], r["start"], r["end"]))
            print("  %-8s %-8s %-7s  %s" % ("prodID", "build", "count",
                                            "tool"))
            for prod, build, count in r["entries"]:
                print("  0x%04X   %-8d %-7d  %s" % (
                    prod, build, count, PRODID.get(prod, "(unlisted id)")))

        v = self.versioninfo()
        print()
        if v is None:
            print("VS_VERSIONINFO      : ABSENT")
        else:
            print("VS_VERSIONINFO      : at file offset %d" % v["at"])
            if v["fixed"]:
                print("  file version      : %s" % v["fixed"]["fileversion"])
                print("  product version   : %s" % v["fixed"]["productversion"])
            print("  strings in block  : %d" % len(v["strings"]))
            for s in v["strings"]:
                print("      %s" % s)

        if show_sections:
            print()
            print("%-10s %10s %10s %10s %10s %8s  %s" % (
                "section", "vaddr", "vsize", "rawoff", "rawsize", "entropy",
                "flags"))
            for s in self.sections:
                blob = d[s["roff"]:s["roff"] + s["rsize"]]
                fl = ",".join(n for m, n in SECCHAR if s["ch"] & m)
                print("%-10s 0x%08X %10d 0x%08X %10d %8.3f  %s" % (
                    s["name"], s["vaddr"], s["vsize"], s["roff"], s["rsize"],
                    entropy(blob), fl))
            raw = sum(s["rsize"] for s in self.sections)
            print("sum of raw section sizes: %d of %d file bytes (%.2f %%)" % (
                raw, len(d), 100.0 * raw / len(d)))
            tail = len(d) - max((s["roff"] + s["rsize"]) for s in self.sections)
            print("bytes after the last section: %d" % tail)

        if show_imports:
            imps = self.imports()
            print()
            print("imports: %d DLLs" % len(imps))
            total = 0
            for dll, funcs, tds in imps:
                total += len(funcs)
                print("  %-20s %4d functions%s" % (
                    dll, len(funcs),
                    "   bound (%s)" % ts(tds) if tds not in (0, 0xFFFFFFFF)
                    else ""))
            print("  total imported functions: %d" % total)
            if len(imps) <= 5 or "--imports" in sys.argv:
                for dll, funcs, tds in imps:
                    print("  --- %s" % dll)
                    for f in funcs:
                        print("        %s" % f)
            ex = self.exports()
            if ex:
                print()
                print("exports: name %r, %d functions, %d named, "
                      "timestamp %s" % (ex["name"], ex["nfunc"],
                                        ex["nnames"], ts(ex["tstamp"])))
                for n in ex["names"]:
                    print("      %s" % n)

        print()
        hits = []
        for magic, label in PACKER_MAGIC:
            k = d.find(magic)
            if k >= 0:
                hits.append((label, k))
        print("packer / protection magic scan: %s" % (
            "no hit" if not hits else ""))
        for label, k in hits:
            print("   %-28s at file offset %d" % (label, k))
        code = [s for s in self.sections if s["ch"] & 0x20]
        if code:
            e = entropy(d[code[0]["roff"]:code[0]["roff"] + code[0]["rsize"]])
            print("first code section entropy: %.3f  (%s)" % (
                e, "plain compiled code" if e < 6.8 else
                "HIGH -- compressed or encrypted"))
        print("entry point is in       : %s" % self.section_of(self.entry))


def summary(root):
    rows = []
    for dirpath, _dn, fns in os.walk(root):
        for fn in sorted(fns):
            if os.path.splitext(fn)[1].lower() not in (
                    ".exe", ".dll", ".ocx", ".ax", ".sys"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            try:
                pe = PE(p)
            except Exception as ex:
                rows.append((rel, os.path.getsize(p), None, str(ex)))
                continue
            r = pe.rich()
            v = pe.versioninfo()
            comp = ""
            if v and v["strings"]:
                for s in v["strings"]:
                    if len(s) > 3 and s not in ("StringFileInfo",
                                                "VarFileInfo", "Translation",
                                                "VS_VERSION_INFO"):
                        comp = s
                        break
            rows.append((rel, os.path.getsize(p), pe, dict(
                rich=r, ver=v, first=comp)))
    print("%-30s %11s %-30s %-6s %-5s %s" % (
        "file", "bytes", "COFF timestamp (UTC)", "linker", "sects", "imports"))
    for rel, size, pe, extra in rows:
        if pe is None:
            print("%-30s %11d  NOT A PE: %s" % (rel, size, extra))
            continue
        d = datetime.datetime.fromtimestamp(pe.timestamp,
                                            datetime.timezone.utc)
        print("%-30s %11d %-30s %d.%-4d %-5d %d" % (
            rel, size, d.strftime("%Y-%m-%d %H:%M:%S"),
            pe.linker[0], pe.linker[1], len(pe.sections),
            len(pe.imports())))
    print()
    print("%-30s %s" % ("file", "Rich header toolchain"))
    for rel, size, pe, extra in rows:
        if pe is None:
            continue
        r = extra["rich"]
        if not r:
            print("%-30s (no Rich header)" % rel)
            continue
        names = ", ".join("%s x%d" % (PRODID.get(p, "id 0x%02X" % p), c)
                          for p, b, c in r["entries"] if p)
        print("%-30s %s" % (rel, names))
    print()
    print("%-30s %s" % ("file", "version resource"))
    for rel, size, pe, extra in rows:
        if pe is None:
            continue
        v = extra["ver"]
        if not v:
            print("%-30s (none)" % rel)
        else:
            fv = v["fixed"]["fileversion"] if v["fixed"] else "?"
            print("%-30s %s   %s" % (rel, fv, " | ".join(
                s for s in v["strings"] if len(s) > 2)[:150]))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    target = sys.argv[1]
    if "--summary" in sys.argv:
        summary(target)
        return
    pe = PE(target)
    pe.report(show_imports="--sections" not in sys.argv,
              show_sections="--imports" not in sys.argv)


if __name__ == "__main__":
    main()
