#!/usr/bin/env python3
"""stock.py -- how much of the shipped media is OGRE SDK sample content?

The game is built on OGRE 1.2.4 and CEGUI, and the `media/` tree it installs
contains files that are not its own: the demo material scripts, the sample
meshes, the CEGUI look-and-feel, and the OGRE demo resource packs. This
counts them.

The definition matters more than the number, so it is written down here and
nowhere else, and it is deliberately conservative -- a file is counted as
stock only if one of these is true:

  1. it lives in `media/packs/`, whose seven archives are the OGRE demo packs
     named by the shipped `resources.cfg`;
  2. it lives in `media/DeferredShadingMedia/`, which is the OGRE deferred
     shading demo, shipped whole;
  3. its base name is one of the seven sample meshes named -- and commented
     out -- in the shipped `media.cfg`;
  4. its base name starts with one of the demo prefixes below, all of which
     are OGRE or CEGUI sample asset names.

Anything else counts as the game's own, including files that merely *look*
generic. That biases the number downwards, which is the right direction: an
undercount that is defensible beats an overcount that needs an argument.

What this does NOT claim is that the game fails to use these files. Some of
them it certainly does load -- `resources.cfg` mounts the demo packs at
startup and `Ogre.log` shows the demo material scripts being parsed. The
measurement is "how much of what ships came from the SDK", not "how much is
wasted", and the second question needs the game running, which is out of
scope for this repository.

Usage:
    python tools/stock.py MEDIADIR
"""
import os
import sys

PACK_DIRS = ("packs", "DeferredShadingMedia")

MEDIA_CFG_MESHES = {
    "ogrehead.mesh", "geosphere4500.mesh", "razor.mesh", "knot.mesh",
    "rzr-002.mesh", "geosphere8000.mesh", "sphere.mesh",
}

PREFIXES = (
    "example", "examples", "ocean", "ocean2", "compositordemo", "oceandemo",
    "taharezlook", "deferred", "falagard", "guilayout", "guischeme",
    "imageset", "font.xsd", "ogrecore", "ogredebugpanel", "ogreloadingpanel",
    "ogreprofiler", "ogre.fontdef", "ogre.material", "new_ogre_",
    "bluehighway", "cubemap", "cubescene", "early_morning", "cloudy_noon",
    "stevecube", "stormy", "morning", "evening", "dragon", "fresnel",
    "ogretestmap", "skybox", "testgui", "cegui", "shaders.program",
    "smoke", "spot_shadow_fade", "flare", "nm_", "notex_",
)


def is_stock(relpath, name):
    parts = relpath.replace(chr(92), "/").split("/")
    if parts and parts[0] in PACK_DIRS:
        return "sdk directory"
    low = name.lower()
    if low in MEDIA_CFG_MESHES:
        return "media.cfg mesh"
    for p in PREFIXES:
        if low.startswith(p):
            return "demo name"
    return None


def main():
    base = sys.argv[1]
    stock_n = stock_b = own_n = own_b = 0
    reasons = {}
    for root, _, files in os.walk(base):
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, base)
            size = os.path.getsize(p)
            why = is_stock(rel, f)
            if why:
                stock_n += 1
                stock_b += size
                reasons.setdefault(why, [0, 0])
                reasons[why][0] += 1
                reasons[why][1] += size
            else:
                own_n += 1
                own_b += size
    tot_n, tot_b = stock_n + own_n, stock_b + own_b
    print("media tree            : %s" % base)
    print("files                 : %d" % tot_n)
    print("bytes                 : %d" % tot_b)
    print()
    print("%-22s %7s %14s %9s %9s" % ("", "files", "bytes", "% files", "% bytes"))
    print("%-22s %7d %14d %8.3f%% %8.3f%%"
          % ("SDK sample content", stock_n, stock_b,
             100.0 * stock_n / tot_n, 100.0 * stock_b / tot_b))
    for why in sorted(reasons):
        n, b = reasons[why]
        print("   %-19s %7d %14d" % (why, n, b))
    print("%-22s %7d %14d %8.3f%% %8.3f%%"
          % ("the game's own", own_n, own_b,
             100.0 * own_n / tot_n, 100.0 * own_b / tot_b))


if __name__ == "__main__":
    main()
