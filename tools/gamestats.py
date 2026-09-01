#!/usr/bin/env python3
"""gamestats.py -- census of the game's own data, all of which is plain text.

Everything this game does is described in XML files with private extensions
(`.sgi`, `.ssd`) or public ones (`.xml`), plus one flat text file with one
field per line (`levels.db`). Nothing is compressed, encoded or obfuscated, so
the whole of the game's structure can be counted with `xml.etree` and no
format work at all.

Sections:
    --dialogue   sentence.ssd: chains, lines, words, speakers, and how many
                 lines have a voice recording named after their id
    --sequences  seq.sgi: steps, verbs, chain terminators, dangling links
    --actors     actors.xml, characters.ssd, overlays.xml
    --scenes     gdata: the 48 scene directories against levels.db
    --audio      duplicate audio files, and music tracks named by no level
    --images     every image, checked magic-against-extension, inside the
                 resource archives as well as outside them
    --all        all of the above

Usage:
    python tools/gamestats.py GAMEDIR [--all|--dialogue|...]
"""
import collections
import glob
import hashlib
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

BS = chr(92)


def load(path):
    with open(path, "rb") as f:
        return ET.fromstring(f.read().decode("utf-8", "replace"))


def dialogue(base):
    root = load(os.path.join(base, "media", "Sentence", "sentence.ssd"))
    chains = root.findall("sentenceChain")
    sents = root.findall(".//sentence")
    print("=== dialogue ===")
    print("  sentenceChains        : %d" % len(chains))
    print("  sentences             : %d" % len(sents))
    print("  words                 : %d"
          % sum(len(s.get("content", "").split()) for s in sents))
    print("  characters of text    : %d"
          % sum(len(s.get("content", "")) for s in sents))
    who = collections.Counter(s.get("character", "") for s in sents)
    print("  distinct speakers     : %d" % len(who))
    for k, v in who.most_common(8):
        print("      %-18s %5d   %5.2f %%" % (k, v, 100.0 * v / len(sents)))
    sfx = os.path.join(base, "media", "Sound", "SFX")
    have = {f[:-4].lower() for f in os.listdir(sfx) if f.lower().endswith(".ogg")}
    ids = [s.get("id") for s in sents]
    voiced = [i for i in ids if i and i.lower() in have]
    print("  lines with a recording: %d = %.1f %%"
          % (len(voiced), 100.0 * len(voiced) / len(ids)))
    print("  lines without         : %d" % (len(ids) - len(voiced)))
    print("  recordings in SFX     : %d" % len(have))
    print("  recordings matching no line: %d"
          % len(have - {i.lower() for i in ids if i}))


def sequences(base):
    root = load(os.path.join(base, "media", "Interface", "seq.sgi"))
    sq = root.findall("sequence")
    ids = [s.get("id") for s in sq]
    print("=== sequences ===")
    print("  steps                 : %d" % len(sq))
    print("  distinct ids          : %d" % len(set(ids)))
    dup = [k for k, v in collections.Counter(ids).items() if v > 1]
    print("  ids defined twice     : %d  %s" % (len(dup), sorted(dup)))
    nxt = [s.get("next") for s in sq]
    print("  terminators (NULL)    : %d" % sum(1 for n in nxt if n == "NULL"))
    dangling = sorted({n for n in nxt if n not in set(ids) and n != "NULL"})
    print("  links to a missing id : %d  %s" % (len(dangling), dangling))
    fn = collections.Counter(s.get("function") for s in sq)
    print("  distinct verbs        : %d" % len(fn))
    for k, v in fn.most_common():
        print("      %-26s %5d" % (k, v))


def actors(base):
    a = load(os.path.join(base, "gdata", "actors.xml"))
    names = [x.get("name") for x in a.findall("actor")]
    ch = load(os.path.join(base, "media", "Sentence", "characters.ssd"))
    cn = [c.get("name") for c in ch.findall("character")]
    s = load(os.path.join(base, "media", "Sentence", "sentence.ssd"))
    sp = {x.get("character") for x in s.findall(".//sentence")}
    ov = load(os.path.join(base, "gdata", "overlays.xml"))
    print("=== actors and overlays ===")
    print("  actor entries         : %d  (distinct names %d)"
          % (len(names), len(set(names))))
    print("  states                : %d" % len(a.findall(".//state")))
    print("  script calls          : %d" % len(a.findall(".//script")))
    print("  mesh mappings         : %d over %d display names"
          % (len(cn), len(set(cn))))
    print("  dialogue speakers     : %d" % len(sp))
    print("      with a mesh       : %d" % len(sp & set(cn)))
    print("      without           : %d" % len(sp - set(cn)))
    print("  overlays.xml bytes    : %d"
          % os.path.getsize(os.path.join(base, "gdata", "overlays.xml")))
    print("  levels in it          : %d" % len(ov.findall("level")))
    print("  overlay elements      : %d" % len(ov.findall(".//overlayElement")))


def scenes(base):
    db = open(os.path.join(base, "bin", "release", "levels.db")).read().split()
    names, music, term = db[0:-1:2], db[1:-1:2], db[-1]
    g = os.path.join(base, "gdata")
    have = sorted(d for d in os.listdir(g) if os.path.isdir(os.path.join(g, d)))
    print("=== scenes ===")
    print("  levels.db pairs       : %d, terminator %r" % (len(names), term))
    print("  gdata directories     : %d" % len(have))
    print("  in levels.db, not on disc : %s" % [n for n in names if n not in have])
    print("  on disc, not in levels.db : %s" % [h for h in have if h not in names])
    print("  distinct music tracks named: %d  %s"
          % (len(set(music)), sorted(set(music))))
    odd = []
    for d in have:
        fs = sorted(os.listdir(os.path.join(g, d)))
        if [os.path.splitext(x)[1].lower() for x in fs] != [".osm", ".zip", ".xml"]:
            odd.append((d, fs))
    print("  directories that are not osm+zip+sceneini : %s" % odd)
    ext = collections.Counter()
    n = 0
    for r, _, fs in os.walk(g):
        for f in fs:
            ext[os.path.splitext(f)[1].lower()] += 1
            n += 1
    print("  gdata files           : %d  %s" % (n, dict(ext)))


def audio(base):
    snd = os.path.join(base, "media", "Sound")
    db = open(os.path.join(base, "bin", "release", "levels.db")).read().split()
    music = set(db[1:-1:2])
    bg = sorted(os.listdir(os.path.join(snd, "BG")))
    print("=== audio ===")
    print("  tracks in Sound/BG    : %d" % len(bg))
    print("  tracks named by levels.db: %d" % len(music))
    print("  shipped and never named : %s"
          % sorted(f for f in bg if f[:-4] not in music))
    seen = {}
    for r, _, fs in os.walk(snd):
        for f in fs:
            p = os.path.join(r, f)
            with open(p, "rb") as fh:
                h = hashlib.md5(fh.read()).hexdigest()
            seen.setdefault(h, []).append(os.path.relpath(p, snd))
    dup = [v for v in seen.values() if len(v) > 1]
    print("  byte-identical groups : %d covering %d files"
          % (len(dup), sum(len(v) for v in dup)))
    for v in dup:
        print("      %s" % v)


MAGIC = {".dds": b"DDS ", ".png": b"\x89PNG", ".jpg": b"\xff\xd8\xff",
         ".jpeg": b"\xff\xd8\xff"}


def images(base):
    ok = collections.Counter()
    bad = []
    n = 0

    def check(name, head):
        nonlocal n
        e = os.path.splitext(name)[1].lower()
        if e == ".tga":
            ok[".tga ok"] += 1
            n += 1
            return
        if e not in MAGIC:
            return
        n += 1
        good = head.startswith(MAGIC[e])
        ok[e + (" ok" if good else " BAD")] += 1
        if not good:
            bad.append((name, head[:8].hex()))

    for r, _, fs in os.walk(base):
        for f in fs:
            if os.path.splitext(f)[1].lower() in (
                    ".dds", ".png", ".jpg", ".jpeg", ".tga"):
                with open(os.path.join(r, f), "rb") as fh:
                    check(f, fh.read(8))
    for z in glob.glob(os.path.join(base, "gdata", "*", "*.zip")) + \
            glob.glob(os.path.join(base, "media", "packs", "*.zip")):
        with zipfile.ZipFile(z) as zf:
            for i in zf.infolist():
                if os.path.splitext(i.filename)[1].lower() in (
                        ".dds", ".png", ".jpg", ".jpeg", ".tga"):
                    check(i.filename, zf.open(i).read(8))
    print("=== images ===")
    print("  checked               : %d" % n)
    for k, v in sorted(ok.items()):
        print("      %-12s %5d" % (k, v))
    print("  magic disagreeing with the extension : %d" % len(bad))
    for b in bad[:20]:
        print("      %s" % (b,))


def main():
    base = sys.argv[1]
    what = [a for a in sys.argv[2:] if a.startswith("--")] or ["--all"]
    order = [("--dialogue", dialogue), ("--sequences", sequences),
             ("--actors", actors), ("--scenes", scenes),
             ("--audio", audio), ("--images", images)]
    for flag, fn in order:
        if "--all" in what or flag in what:
            fn(base)
            print()


if __name__ == "__main__":
    main()
