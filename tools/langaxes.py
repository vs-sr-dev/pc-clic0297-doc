#!/usr/bin/env python3
"""langaxes.py -- every list of languages on this disc, side by side.

`langtable.py` was written for pc-harrypotter1-doc's fifteen axes and its axis
definitions are that disc's directory layout. The method is the one worth
keeping -- build the table, then look at the holes -- so this is the same tool
with this disc's axes.

The axes here:

  help      Support/European Help Files/<lang>/          folder names
  readme    Support/<lang>/<localised name>.txt          folder names
  splash    AutoRun/<lang>_AutoRun.bmp                   filename prefixes
  ereg      Support/ereg-dict-<lang>.xml                 filename suffixes
  cdkey     Support/Localization.ini  [CDKEY]            keys (UTF-16 file)
  readmeini Support/Localization.ini  [README]           keys
  title     Support/Localization.ini  [TITLE]            keys
  autorun   AutoRun/autorun.cfg language flags           names, value 1 = on
  game      language folders inside the .big archives    from notes/big-list.txt

Codes are normalised to lower case with '_' and '-' folded, because the disc
spells the same language four different ways.

    python tools/langaxes.py _work/nozip
    python tools/langaxes.py _work/nozip --big notes/big-list.txt
"""
import argparse
import collections
import os
import re
import sys

NAME2CODE = {
    "english us": "en-us", "english uk": "en-uk", "french": "fr", "german": "de",
    "italian": "it", "spanish": "es", "swedish": "sv", "finnish": "fi",
    "dutch": "nl", "danish": "da", "portbrzl": "pt-br", "czech": "cs",
    "hebrew": "he", "greek": "el", "japanese": "ja", "korean": "ko",
    "russian": "ru", "chinese (simplified)": "zh-cn",
    "chinese (traditional)": "zh-tw", "polish": "pl", "thai": "th",
    "norwegian": "no", "portuguese": "pt-pt", "hungarian": "hu",
    "portuguese_portugal": "pt-pt", "portuguese_brazil": "pt-br",
    "portuguese-portugal": "pt-pt", "portuguese-brazil": "pt-br",
    "english": "en",
}


def norm(c):
    c = c.strip().lower().replace("_", "-")
    if c in NAME2CODE:
        return NAME2CODE[c]
    c = {"fr-fr": "fr", "pt": "pt-pt", "en_uk": "en-uk", "en-us": "en-us",
         "en_us": "en-us", "pt_pt": "pt-pt", "pt_br": "pt-br",
         "fr_fr": "fr", "zh_cn": "zh-cn", "zh_tw": "zh-tw"}.get(c, c)
    return c


def read_utf16(p):
    b = open(p, "rb").read()
    if b[:2] == b"\xff\xfe":
        return b[2:].decode("utf-16-le", "replace")
    return b.decode("latin-1")


def ini_sections(text):
    out = collections.defaultdict(list)
    sec = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("//") or not line:
            continue
        m = re.match(r"^\[(.+?)\]$", line)
        if m:
            sec = m.group(1).upper()
            continue
        if sec and "=" in line:
            out[sec].append(line.split("=", 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--big")
    a = ap.parse_args()
    R = a.root

    axes = collections.OrderedDict()

    hp = os.path.join(R, "Support", "European Help Files")
    axes["help"] = sorted(norm(d) for d in os.listdir(hp)
                          if os.path.isdir(os.path.join(hp, d)))

    sp = os.path.join(R, "Support")
    axes["readme"] = sorted(norm(d) for d in os.listdir(sp)
                            if os.path.isdir(os.path.join(sp, d))
                            and d != "European Help Files")

    ar = os.path.join(R, "AutoRun")
    sl = []
    for f in os.listdir(ar):
        if f.endswith("_AutoRun.bmp"):
            sl.append(norm(f[:-len("_AutoRun.bmp")]))
        elif f == "AutoRun.bmp":
            sl.append("(default)")
    axes["splash"] = sorted(sl)

    axes["ereg"] = sorted(norm(f[len("ereg-dict-"):-4]) for f in os.listdir(sp)
                          if f.startswith("ereg-dict-") and f.endswith(".xml"))

    loc = ini_sections(read_utf16(os.path.join(sp, "Localization.ini")))
    axes["cdkey"] = sorted(norm(k) for k, v in loc.get("CDKEY", []))
    axes["readmeini"] = sorted(norm(k) for k, v in loc.get("README", []))
    axes["title"] = sorted(norm(k) for k, v in loc.get("TITLE", []))

    cfg = open(os.path.join(ar, "autorun.cfg"), "rb").read().decode("cp1252")
    on, named = [], []
    for line in cfg.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip().lower() in NAME2CODE:
            named.append(norm(k))
            if v.strip() == "1":
                on.append(norm(k))
    axes["autorun-named"] = sorted(named)
    axes["autorun-on"] = sorted(on)

    if a.big:
        langs = set()
        for line in open(a.big, encoding="utf-8", errors="replace"):
            m = re.match(r"^\s+\d+\s+\d+\s\s(.+?)\s*$", line)
            if m:
                parts = m.group(1).replace(chr(92), "/").split("/")
                if len(parts) > 2:
                    c = parts[1]
                    if c.lower() in NAME2CODE or c in ("English",):
                        langs.add(norm(c) if c != "English" else "en")
        axes["game"] = sorted(langs)

    allc = sorted({c for v in axes.values() for c in v})
    print("axes  : %d" % len(axes))
    print("codes : %d distinct" % len(allc))
    print()
    hdr = "%-10s" % "code"
    for k in axes:
        hdr += " %-14s" % k
    print(hdr)
    print("-" * len(hdr))
    for c in allc:
        row = "%-10s" % c
        for k in axes:
            row += " %-14s" % ("yes" if c in axes[k] else ".")
        print(row)
    print("-" * len(hdr))
    row = "%-10s" % "count"
    for k in axes:
        row += " %-14d" % len(axes[k])
    print(row)
    print()

    n = len(axes)
    everywhere = [c for c in allc if all(c in v for v in axes.values())]
    print("languages present on ALL %d axes : %d  %s"
          % (n, len(everywhere), ", ".join(everywhere) or "(none)"))
    counts = collections.Counter()
    for c in allc:
        counts[sum(1 for v in axes.values() if c in v)] += 1
    print("languages by number of axes they appear on:")
    for k in sorted(counts, reverse=True):
        who = [c for c in allc if sum(1 for v in axes.values() if c in v) == k]
        print("  on %2d of %d axes : %2d   %s" % (k, n, counts[k], ", ".join(who)))


if __name__ == "__main__":
    main()
