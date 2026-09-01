#!/usr/bin/env python3
"""toolcheck.py -- does an inherited tool actually apply to this material?

P93 predicted how many of the 56 tools carried over from pc-1000miglia-doc
would apply here. Guessing that from the filenames would be worthless, so this
runs each one against this disc and records what happened.

The verdict is one of:

  RUNS      exited 0 and produced output that is about this material
  EMPTY     exited 0 and found nothing here to measure (the tool applies to a
            format this disc does not contain) -- this is NOT the same as
            failing, and it is counted separately
  ERROR     raised, or exited non-zero
  SKIP      needs an argument this harness cannot supply, or is a library

Each tool gets a short timeout, because a few of them walk 577 MB.

    python tools/toolcheck.py E:/ ../pc-1000miglia-doc/tools
"""
import os
import subprocess
import sys

# argument shape per tool, chosen from each tool's own docstring
# tools whose own docstring says to pass a bare drive letter for a real disc
DRIVE_ARG = {"iso9660.py", "rawsect.py", "cdxa.py", "subch.py", "padecho.py"}

ARGS = {
    "census.py": ["{root}/"],
    "headers.py": ["{root}/"],
    "clockwork.py": ["{root}/"],
    "strdump.py": ["{root}/AUTORUN.INF"],
    "hunt.py": ["{root}/", "--tokens", "Epic"],
    "discdiff.py": ["{root}/", "{root}/"],
    "refs.py": ["{root}/"],
    "mzcensus.py": ["{root}/"],
    "pe.py": ["{root}/System/HP.exe"],
    "pecensus.py": ["{root}/"],
    "rsrc.py": ["{root}/AutoRun.exe"],
    "bmp.py": ["{root}/Help/Splash0.bmp"],
    "cab.py": ["{root}/DirectX/bda.cab"],
    "thirdparty.py": ["{root}/"],
    "dates.py": ["{root}/"],
    "timeline.py": ["{root}/"],
    "clocks.py": ["{root}/"],
    "twoclocks.py": ["{root}/"],
    "accounting.py": ["{root}/"],
    "compare.py": ["{root}/"],
    "refcheck.py": ["{root}/"],
    "padecho.py": ["{root}/"],
    "rawsect.py": ["{root}/"],
    "subch.py": ["{root}/"],
    "cdxa.py": ["{root}/"],
    "iso9660.py": ["{root}", "--vd"],
    "collectrefs.py": ["{root}/"],
    "resolve.py": ["{root}/"],
    "mtimes.py": ["{root}/"],
    "stock.py": ["{root}/"],
    "audio.py": ["{root}/Sounds/wavs/scloak1.wav"],
    "jpeg.py": ["{root}/"],
    "tga.py": ["{root}/"],
    "zob.py": ["{root}/"],
    "gamestats.py": ["{root}/"],
    "cabdates.py": ["{root}/DirectX/bda.cab"],
    "inno.py": ["{root}/setup/Setup.exe"],
    "msi.py": ["{root}/setup/data1.cab"],
    "vise.py": ["{root}/setup/Setup.exe"],
    "ne.py": ["{root}/System/HP.exe"],
    "groups.py": ["{root}/"],
    "ptables.py": ["{root}/"],
    "pictures.py": ["{root}/"],
    "iffread.py": ["{root}/"],
    "flread.py": ["{root}/"],
    "ppprobe.py": ["{root}/"],
    "pkgdiff.py": ["{root}/", "{root}/"],
    "sevenzip_tz.py": ["{root}/"],
    "director.py": ["{root}/"],
    "swf.py": ["{root}/"],
    "mov.py": ["{root}/"],
    "mpeg1.py": ["{root}/"],
    "avi.py": ["{root}/"],
    "avibytes.py": ["{root}/"],
    "cast.py": ["{root}/"],
}


def main():
    # "E:" without a slash means "the current directory on drive E" in
    # Windows path semantics, so os.path.join("E:", "DirectX") produces the
    # RELATIVE path "E:DirectX" and every tree-walking tool fails with
    # FileNotFoundError. The first run of this harness stripped the slash for
    # iso9660.py's benefit and broke eleven other tools that way. Tree tools
    # therefore get "E:/" and only the tools that want a bare drive letter
    # get "E:".
    # ARGS templates already carry the separator ("{root}/File"), so `root`
    # here must NOT end in one, or every path comes out with a double slash.
    root = (sys.argv[1] if len(sys.argv) > 1 else "E:").rstrip("/")
    bare = root
    src = sys.argv[2] if len(sys.argv) > 2 else \
        "../pc-1000miglia-doc/tools"
    tools = sorted(f for f in os.listdir(src)
                   if f.endswith(".py") and not f.startswith("_"))
    print("inherited tools: %d" % len(tools))
    print("source         : %s" % src)
    print("target         : %s" % root)
    print()
    verdicts = {}
    for t in tools:
        args = ARGS.get(t)
        if args is None:
            verdicts[t] = ("SKIP", "no argument shape registered")
            continue
        use = bare if t in DRIVE_ARG else root
        cmd = [sys.executable, "-X", "utf8", os.path.join(src, t)] + \
            [a.format(root=use) for a in args]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=180)
        except subprocess.TimeoutExpired:
            verdicts[t] = ("ERROR", "timed out after 180 s")
            continue
        out = (r.stdout or b"").decode("utf-8", "replace")
        err = (r.stderr or b"").decode("utf-8", "replace")
        first = next((l for l in out.splitlines() if l.strip()), "")
        if r.returncode != 0:
            lastl = [l for l in err.splitlines() if l.strip()]
            verdicts[t] = ("ERROR", lastl[-1][:96] if lastl else
                           "exit %d" % r.returncode)
        elif not out.strip():
            verdicts[t] = ("EMPTY", "exited 0, no output")
        else:
            nums = sum(c.isdigit() for c in out)
            verdicts[t] = (("RUNS" if nums > 12 else "EMPTY"),
                           first[:96])
        del out, err

    order = {"RUNS": 0, "EMPTY": 1, "ERROR": 2, "SKIP": 3}
    for v in ("RUNS", "EMPTY", "ERROR", "SKIP"):
        sel = [(t, d) for t, (k, d) in verdicts.items() if k == v]
        print("=" * 70)
        print("%s : %d" % (v, len(sel)))
        print("=" * 70)
        for t, d in sorted(sel):
            print("  %-20s %s" % (t, d))
        print()
    n = {v: sum(1 for k, _ in verdicts.values() if k == v)
         for v in order}
    print("summary: %s" % n)
    print()
    print("applies (RUNS)                 : %d" % n["RUNS"])
    print("does not apply (EMPTY + ERROR) : %d" % (n["EMPTY"] + n["ERROR"]))
    print("not testable by this harness   : %d" % n["SKIP"])


if __name__ == "__main__":
    main()
