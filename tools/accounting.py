#!/usr/bin/env python3
"""accounting.py -- the headline figures, all of them, from one command.

Every proportion quoted in the documents comes out of here, so that a reader
who distrusts a percentage can re-derive it without reading the chapter that
uses it. Nothing is hard-coded except the four paths.

The three sizes this disc has, and they are not the same size:

  * the IMAGE, 1,114,767,360 bytes, which is what a copy of the file weighs;
  * the INSTALL, the 2,440 files the installer writes, 1.41 GB;
  * the EXPANDED tree, the install with its 55 OGRE resource archives opened,
    which is what the engine actually reads and is 2.14 GB.

Quoting a proportion without saying which of the three it is over is the
easiest way to be accidentally wrong by a factor of two, so every line below
names its denominator.

Usage:
    python tools/accounting.py IMAGE ISODIR GAMEDIR
"""
import glob
import os
import sys
import zipfile


def tree(root):
    n = b = 0
    for r, _, fs in os.walk(root):
        for f in fs:
            n += 1
            b += os.path.getsize(os.path.join(r, f))
    return n, b


def pct(a, b):
    return 100.0 * a / b


def main():
    image, isodir, gamedir = sys.argv[1], sys.argv[2], sys.argv[3]
    img = os.path.getsize(image)
    iso_n, iso_b = tree(isodir)
    ins_n, ins_b = tree(gamedir)

    zips = sorted(glob.glob(os.path.join(gamedir, "gdata", "*", "*.zip"))) + \
        sorted(glob.glob(os.path.join(gamedir, "media", "packs", "*.zip")))
    zip_file_bytes = sum(os.path.getsize(z) for z in zips)
    zin = zub = 0
    dds_n = dds_b = 0
    for z in zips:
        with zipfile.ZipFile(z) as f:
            for i in f.infolist():
                zin += 1
                zub += i.file_size
                if i.filename.lower().endswith(".dds"):
                    dds_n += 1
                    dds_b += i.file_size
    expanded = ins_b - zip_file_bytes + zub

    print("=== the image ===")
    print("image bytes                    %14d" % img)
    print("sectors of 2048                %14d   remainder %d"
          % (img // 2048, img % 2048))
    print("multiple of 65,536             %14s   %d x 64 KiB"
          % (img % 65536 == 0, img // 65536))
    print("files in the ISO               %14d" % iso_n)
    print("bytes in those files           %14d   %.4f %% of the image"
          % (iso_b, pct(iso_b, img)))
    print()
    named = {}
    for r, _, fs in os.walk(isodir):
        for f in fs:
            named[f] = os.path.getsize(os.path.join(r, f))
    for f in sorted(named, key=lambda k: -named[k]):
        print("  %-26s %14d   %8.4f %% of the image"
              % (f, named[f], pct(named[f], img)))
    print()

    print("=== the install ===")
    print("files written                  %14d" % ins_n)
    print("bytes written                  %14d" % ins_b)
    print("expansion over the image        %13.4fx" % (ins_b / float(img)))
    big = named.get("Lucignolo.exe", 0)
    print("installer payload compressed   %14d" % (big - 54272 - 99977 - 229090))
    print("compression ratio               %13.4fx"
          % (ins_b / float(big - 54272 - 99977 - 229090)))
    print()

    print("=== the expanded tree ===")
    print("resource archives              %14d" % len(zips))
    print("their size as files            %14d   %.3f %% of the install"
          % (zip_file_bytes, pct(zip_file_bytes, ins_b)))
    print("members inside them            %14d" % zin)
    print("their uncompressed size        %14d" % zub)
    print("archive ratio                   %13.4fx" % (zub / float(zip_file_bytes)))
    print("EXPANDED TREE                  %14d" % expanded)
    print("expansion over the image        %13.4fx" % (expanded / float(img)))
    print()

    print("=== what the expanded tree is made of ===")
    print("DDS textures inside archives   %14d   %.3f %% of the expanded tree"
          % (dds_b, pct(dds_b, expanded)))
    print("   as a count                  %14d" % dds_n)
    video = 0
    vdir = os.path.join(gamedir, "media", "video")
    if os.path.isdir(vdir):
        video = sum(os.path.getsize(os.path.join(vdir, f))
                    for f in os.listdir(vdir))
    print("video                          %14d   %.3f %% of the expanded tree"
          % (video, pct(video, expanded)))
    sound = 0
    sdir = os.path.join(gamedir, "media", "Sound")
    for r, _, fs in os.walk(sdir):
        for f in fs:
            sound += os.path.getsize(os.path.join(r, f))
    print("Ogg Vorbis audio               %14d   %.3f %% of the expanded tree"
          % (sound, pct(sound, expanded)))
    exe = os.path.join(gamedir, "bin", "release", "Lucignolo.exe")
    if os.path.exists(exe):
        g = os.path.getsize(exe)
        print("the game executable            %14d   %.5f %% of the expanded tree"
              % (g, pct(g, expanded)))
        print("                                              %.5f %% of the install"
              % pct(g, ins_b))
    bn, bb = tree(os.path.join(gamedir, "bin"))
    print("everything in bin/             %14d   %.3f %% of the expanded tree"
          % (bb, pct(bb, expanded)))


if __name__ == "__main__":
    main()
