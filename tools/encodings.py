#!/usr/bin/env python3
"""encodings.py -- which code page the text files on this disc actually use.

Five languages ship here and at least one of them (Hungarian) needs letters no
single Latin code page holds alongside the others. Which encoding a file uses
is therefore a measurement, not an assumption.

The method: collect every byte above 0x7F in every text file, decode it under
each candidate code page, and report the letters that result. A file is
"consistent with" a code page when every high byte decodes to a letter that
belongs to the language the filename claims. A byte that decodes to a box
character or a currency sign in one page and to a vowel in another is the
discriminator, and the discriminators are printed.

    python tools/encodings.py E:/
"""
import collections
import os
import sys

CANDIDATES = ["cp1252", "cp1250", "cp850", "cp437", "latin-1", "utf-8"]

# letters each language needs, over and above plain ASCII
NEEDS = {
    "ita": "àèéìòùÀÈÉÌÒÙ",
    "spa": "áéíóúñüÁÉÍÓÚÑÜ¿¡",
    "por": "ãáàâçéêíóõôúÃÁÀÂÇÉÊÍÓÕÔÚ",
    "pt-st": "ãáàâçéêíóõôúÃÁÀÂÇÉÊÍÓÕÔÚ",
    "de": "äöüßÄÖÜ",
    "fr": "àâçéèêëîïôùûüÀÂÇÉÈÊËÎÏÔÙÛÜ",
    "hun": "áéíóöőúüűÁÉÍÓÖŐÚÜŰ",
    "int": "",
    "en": "",
}

# Two allowances, added after the first run rejected cp1252 for
# System/1/HPcredits.ita. That file has exactly one byte above 0x7F: 0xEB,
# which is a lowercase e-diaeresis in cp1252 and sits in the surname
# "Lenoel" in a credits roll. A language whitelist is the wrong rule for a
# list of people's names, and for typographic punctuation, so both are
# allowed in every language and the allowance is stated rather than hidden.
PROPER = "àáâãäåçèé"          "êëìíîïñòó"          "ôõöøùúûüý"          "ÀÁÂÃÄÅÇÈÉ"          "ÊËÌÍÎÏÑÓÖ"          "Üß"
PUNCT = " ‘’“”–—…«"         "»©®°´·ªº™"

TEXTEXT = (".txt", ".int", ".ita", ".spa", ".por", ".ini", ".csv", ".cfg",
           ".inf", ".lay")


def lang_of(path):
    b = os.path.basename(path).lower()
    stem, ext = os.path.splitext(b)
    e = ext.lstrip(".")
    if e in NEEDS:
        return e
    for k in ("ita", "spa", "por", "pt-st", "de", "fr", "en"):
        if ("_" + k) in stem or stem.endswith(k):
            return k
    return None


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "E:/"
    files = []
    for dp, dn, fn in os.walk(root):
        for f in sorted(fn):
            if os.path.splitext(f)[1].lower() in TEXTEXT:
                files.append(os.path.join(dp, f))

    print("text files examined: %d" % len(files))
    print()
    print("%-40s %8s %6s  %s" % ("file", "bytes", "high", "high bytes seen"))
    hi_all = collections.Counter()
    rows = []
    for p in files:
        d = open(p, "rb").read()
        high = sorted({c for c in d if c > 0x7F})
        hi_all.update(c for c in d if c > 0x7F)
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        rows.append((rel, d, high))
        if high:
            print("%-40s %8d %6d  %s"
                  % (rel[:40], len(d), len(high),
                     " ".join("%02X" % c for c in high[:18])
                     + (" ..." if len(high) > 18 else "")))
    print()
    nohigh = [r for r in rows if not r[2]]
    print("files that are pure 7-bit ASCII: %d of %d" % (len(nohigh), len(rows)))
    print()

    print("the distinct high bytes on the whole disc's text files, and what")
    print("each candidate code page makes of them:")
    print()
    print("  %-5s %s" % ("byte", "  ".join("%-8s" % c for c in CANDIDATES[:5])))
    for c in sorted(hi_all):
        cells = []
        for enc in CANDIDATES[:5]:
            try:
                cells.append("%-8s" % bytes([c]).decode(enc))
            except UnicodeDecodeError:
                cells.append("%-8s" % "--")
        print("  0x%02X  %s   x%d" % (c, "  ".join(cells), hi_all[c]))
    print()

    print("per language file, which code pages are consistent:")
    print()
    for rel, d, high in rows:
        lang = lang_of(rel)
        if not high or lang is None:
            continue
        need = NEEDS.get(lang, "") + PROPER + PUNCT
        ok = []
        for enc in CANDIDATES:
            try:
                txt = d.decode(enc)
            except UnicodeDecodeError:
                continue
            bad = [ch for ch in txt if ord(ch) > 0x7F and ch not in need]
            if not bad:
                ok.append(enc)
        print("  %-40s (%s) consistent with: %s"
              % (rel[:40], lang, ", ".join(ok) if ok else "NONE of the five"))
        if not ok:
            for enc in ("cp1252", "cp1250"):
                try:
                    txt = d.decode(enc)
                except UnicodeDecodeError:
                    continue
                bad = sorted({ch for ch in txt
                              if ord(ch) > 0x7F and ch not in need})
                print("        under %s the unexpected characters are %s"
                      % (enc, "".join(bad[:24])))
    print()
    print("the Hungarian test: does any file on this disc contain a letter")
    print("that cp1252 cannot represent?")
    need_hu = "őűŐŰ"
    found = []
    for rel, d, high in rows:
        for enc in ("cp1250", "utf-8"):
            try:
                txt = d.decode(enc)
            except UnicodeDecodeError:
                continue
            if any(ch in need_hu for ch in txt):
                found.append((rel, enc))
                break
    print("   files decoding to a Hungarian long umlaut under cp1250 or"
          " utf-8: %d %s" % (len(found), found[:6]))
    print("   (MenuArt.hun_utx is a texture package, so Hungarian text on this")
    print("    disc is pixels, not characters -- which is what makes the")
    print("    question answerable at all.)")


if __name__ == "__main__":
    main()
