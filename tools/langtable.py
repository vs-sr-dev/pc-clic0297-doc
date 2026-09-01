#!/usr/bin/env python3
"""langtable.py -- how many languages are on this disc, counted seven ways.

The answer depends on what you count, and the seven counts do not agree. This
builds the table instead of picking one number: for each axis it lists the
language tags present, derived from filenames, directory names, Windows
locale identifiers and one configuration file, and then prints the union and
the holes.

The axes, and where each is read from:

  audio        Sounds/AllDialog.*            and Sounds/AllEmote.*
  game text    System/*.int and System/{0,1,2}/*.{spa,ita,por}
  menu art     Textures/MenuArt.* and Textures/{0,1,2}/MenuArt.*
  readme       ReadMe/*.txt
  help         Support/*_eahelp.hlp
  eula         Support/*_eula.txt
  finished     Support/Finished Version/*.txt
  autorun cfg  autorun/autorun.cfg          (a list with a flag per language)
  autorun art  autorun/*.bmp                (a filename prefix per language)
  autorun str  autorun/autorun.csv          (one column per language)
  installer    setup/setupdir/*             (a Windows LCID per directory)
  protection   System/*.016 and *.256       (a Windows LCID per file)

    python tools/langtable.py E:/
"""
import collections
import os
import re
import sys

# Windows primary language identifiers seen on this disc, and the full LCIDs
LCID = {
    0x000A: "Spanish", 0x0010: "Italian", 0x0016: "Portuguese",
    0x040A: "Spanish", 0x0410: "Italian",
    0x0816: "Portuguese", 0x0409: "English (US)",
    0x0809: "English (UK)", 0x0407: "German", 0x040C: "French",
    0x0416: "Portuguese (Brazil)", 0x0415: "Polish", 0x040E: "Hungarian",
}

TAG = {
    "eng": "English", "int": "English", "en": "English",
    "en-us": "English (US)", "en-uk": "English (UK)",
    "ita": "Italian", "it": "Italian",
    "spa": "Spanish", "es": "Spanish",
    "por": "Portuguese", "pt-st": "Portuguese", "pt": "Portuguese",
    "hun": "Hungarian", "de": "German", "fr-fr": "French", "fr": "French",
    "bra": "Portuguese (Brazil)", "pol": "Polish", "kor": "Korean",
    "ko": "Korean", "sim": "Chinese (Simplified)",
    "tra": "Chinese (Traditional)", "tha": "Thai", "th": "Thai",
    "el": "Greek", "he": "Hebrew", "ja": "Japanese",
    "zh-cn": "Chinese (Simplified)", "zh-tw": "Chinese (Traditional)",
}


def L(t):
    return TAG.get(t.lower(), t)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "E:/"
    j = lambda *a: os.path.join(root, *a)
    axes = collections.OrderedDict()
    detail = {}

    def add(axis, langs, note):
        axes[axis] = sorted(set(langs))
        detail[axis] = note

    # audio
    a = []
    for f in os.listdir(j("Sounds")):
        m = re.match(r"AllDialog\.(?:(\w+)_)?uax$", f, re.I)
        if m:
            a.append(L(m.group(1)) if m.group(1) else "English")
    for d in ("0", "1", "2"):
        p = j("Sounds", d)
        if os.path.isdir(p):
            for f in os.listdir(p):
                m = re.match(r"AllDialog\.(\w+)_uax$", f, re.I)
                if m:
                    a.append(L(m.group(1)))
    add("audio (AllDialog)", a, "Sounds/ and Sounds/{0,1,2}/")

    # emote audio
    e = []
    for f in os.listdir(j("Sounds")):
        m = re.match(r"AllEmote\.(?:(\w+)_)?uax$", f, re.I)
        if m:
            e.append(L(m.group(1)) if m.group(1) else "English")
    add("audio (AllEmote)", e, "Sounds/")

    # game text
    t = ["English"] if any(f.lower().endswith(".int")
                           for f in os.listdir(j("System"))) else []
    for d in ("0", "1", "2"):
        p = j("System", d)
        if os.path.isdir(p):
            for f in os.listdir(p):
                ext = f.rsplit(".", 1)[-1].lower()
                if ext in ("spa", "ita", "por"):
                    t.append(L(ext))
    add("game text", t, "System/*.int and System/{0,1,2}/")

    # menu art
    mt = []
    for f in os.listdir(j("Textures")):
        m = re.match(r"MenuArt\.(?:(\w+)_)?utx$", f, re.I)
        if m:
            mt.append(L(m.group(1)) if m.group(1) else "English")
    for d in ("0", "1", "2"):
        p = j("Textures", d)
        if os.path.isdir(p):
            for f in os.listdir(p):
                m = re.match(r"MenuArt\.(\w+)_utx$", f, re.I)
                if m:
                    mt.append(L(m.group(1)))
    add("menu art", mt, "Textures/ and Textures/{0,1,2}/")

    # readme
    r = []
    for f in os.listdir(j("ReadMe")):
        m = re.match(r"readme_([\w-]+)\.txt$", f, re.I)
        if m:
            r.append(L(m.group(1)))
    add("readme", r, "ReadMe/")

    # help, eula, finished version
    h, u = [], []
    for f in os.listdir(j("Support")):
        m = re.match(r"([\w-]+)_eahelp\.hlp$", f, re.I)
        if m:
            h.append(L(m.group(1)))
        m = re.match(r"([\w-]+)_eula\.txt$", f, re.I)
        if m:
            u.append(L(m.group(1)))
    add("help", h, "Support/*_eahelp.hlp")
    add("eula", u, "Support/*_eula.txt")

    fv = {"readme.txt": "English", "leeme.txt": "Spanish",
          "liesmich.txt": "German", "lisezmoi.txt": "French"}
    f2 = []
    p = j("Support", "Finished Version")
    if os.path.isdir(p):
        for f in os.listdir(p):
            f2.append(fv.get(f.lower(), f))
    add("Finished Version readmes", f2,
        "Support/Finished Version/ (named by the word for 'read me')")

    # autorun.cfg
    cfg = {}
    for line in open(j("autorun", "autorun.cfg"), encoding="latin-1"):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            cfg[k] = v
    RENAME = {"PortStd": "Portuguese", "PortBrzl": "Portuguese (Brazil)",
              "Brazilian Portuguese": "Portuguese (Brazil)"}
    known = [k for k, v in cfg.items() if v in ("0", "1")
             and k not in ("Demo", "EReg", "TechSupport", "AutoSort")]
    on = [k for k in known if cfg[k] == "1"]
    add("autorun.cfg, enabled", [RENAME.get(k, k) for k in on],
        "autorun/autorun.cfg, NumLanguages=%s ; the flags are %s"
        % (cfg.get("NumLanguages"), ", ".join("%s=%s" % (k, cfg[k])
                                              for k in on)))
    axes["autorun.cfg, listed"] = sorted(RENAME.get(k, k) for k in known)
    detail["autorun.cfg, listed"] = "every language the shell knows about"

    # autorun art prefixes
    pre = collections.Counter()
    b2 = collections.Counter()
    for f in os.listdir(j("autorun")):
        m = re.match(r"back2_(\w+)\.bmp$", f, re.I)
        if m:
            b2[L(m.group(1))] += 1
            continue
        m = re.match(r"([a-z]{2}(?:-[a-z]{2})?)_(?:up|down|layout)", f, re.I)
        if m:
            pre[L(m.group(1))] += 1
    add("autorun UI art (filename prefix)", list(pre) + ["English"],
        "autorun/*.bmp, %d prefixed files" % sum(pre.values()))
    add("autorun language banners", list(b2) + ["English"],
        "autorun/back2_*.bmp")

    # autorun.csv columns
    hdr = open(j("autorun", "autorun.csv"), encoding="latin-1").readline()
    cols = [c.strip() for c in hdr.split(",")][2:]
    add("autorun.csv columns", [RENAME.get(c, c) for c in cols],
        "autorun/autorun.csv, header row, %d columns" % len(cols))

    # installer LCIDs
    inst = []
    p = j("setup", "setupdir")
    if os.path.isdir(p):
        for d in sorted(os.listdir(p)):
            try:
                inst.append(LCID.get(int(d, 16), "LCID 0x%s" % d))
            except ValueError:
                inst.append(d)
    add("installer (setupdir LCIDs)", inst,
        "setup/setupdir/ = %s, hex Windows LCIDs"
        % ", ".join(sorted(os.listdir(p))) if os.path.isdir(p) else "-")

    prot = []
    for f in os.listdir(j("System")):
        m = re.match(r"([0-9a-f]{8})\.(016|256)$", f, re.I)
        if m:
            prot.append(LCID.get(int(m.group(1), 16), "LCID 0x" + m.group(1)))
    add("protection dialogs (LCID files)", prot,
        "System/0000040a, 00000410, 00000816 .016 and .256")

    print("LANGUAGES ON THIS DISC, COUNTED %d WAYS" % len(axes))
    print()
    for k in axes:
        print("  %-34s %2d   %s" % (k, len(axes[k]), ", ".join(axes[k])))
        print("  %-34s      source: %s" % ("", detail[k]))
    print()

    allangs = sorted({x for v in axes.values() for x in v})
    print("union over every axis: %d tags" % len(allangs))
    print("   %s" % ", ".join(allangs))
    print()
    print("presence matrix (axis x language):")
    print()
    hdr = ["%-34s" % "axis"] + ["%-3s" % a[:3] for a in allangs]
    print("  " + " ".join(hdr))
    for k in axes:
        row = ["%-34s" % k[:34]]
        for a in allangs:
            row.append("%-3s" % ("X" if a in axes[k] else "."))
        print("  " + " ".join(row))
    print()
    print("languages present on every axis  : %s"
          % ([a for a in allangs
              if all(a in v for v in axes.values())] or "none"))
    print("languages present on exactly one : ")
    for a in allangs:
        n = sum(1 for v in axes.values() if a in v)
        if n == 1:
            who = [k for k in axes if a in axes[k]][0]
            print("     %-26s only on: %s" % (a, who))


if __name__ == "__main__":
    main()
