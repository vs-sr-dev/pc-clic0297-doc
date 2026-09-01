#!/usr/bin/env python3
"""leadout.py -- can the 150 sectors past the volume be read?

The briefing reported that the volume device stops at the size the primary
volume descriptor declares (292,173) and returns nothing beyond it. Running
the inherited iso9660.py against E:/ printed a size of 598,677,504 bytes =
292,323 sectors -- the LEAD-OUT address, not the volume size -- which says the
device is 150 sectors longer than the filesystem on it.

So the question §02 left open is testable after all. This reads the last
sectors of the volume and every sector from there to the lead-out, one at a
time, reporting for each whether it came back, how long it took, and what is
in it.

It reads each sector once. It does not retry.

    python tools/leadout.py E
    python tools/leadout.py E --dump
"""
import collections
import hashlib
import math
import sys
import time

BS = chr(92)
SECTOR = 2048
VOLSIZE = 292173      # from the primary volume descriptor, tools/vds.py
LEADOUT = 292323      # from the TOC, tools/toc.py


def ent(b):
    c = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def main():
    letter = (sys.argv[1] if len(sys.argv) > 1 else "E").upper()
    path = BS + BS + "." + BS + letter + ":"
    dump = "--dump" in sys.argv

    import os
    try:
        f = open(path, "rb")
    except OSError as e:
        raise SystemExit("cannot open %s: %s" % (path, e))
    # seeking to the end of a volume device raises errno 22 here, so the
    # size is asked for with the ioctl that answers it instead.
    # Seeking to the end of a volume device raises errno 22 here, and
    # kernel32 has no _get_osfhandle, so the length is asked for on a handle
    # of our own, the way pc-1000miglia-doc/tools/iso9660.py's RawDisc does.
    size = None
    try:
        import ctypes
        import ctypes.wintypes as wt
        k = ctypes.windll.kernel32
        k.CreateFileW.restype = ctypes.c_void_p
        h = k.CreateFileW(path, 0x80000000, 3, None, 3, 0, None)
        if h not in (None, 0, 0xFFFFFFFFFFFFFFFF):
            out = ctypes.c_longlong(0)
            ret = wt.DWORD()
            ok = k.DeviceIoControl(ctypes.c_void_p(h), 0x0007405C, None, 0,
                                   ctypes.byref(out), 8, ctypes.byref(ret),
                                   None)
            if ok:
                size = int(out.value)
            k.CloseHandle(ctypes.c_void_p(h))
    except Exception as e:
        print("  (length ioctl failed: %r)" % (e,))
    print("device            : %s" % path)
    if size:
        print("device size       : %d bytes = %.3f sectors"
              % (size, size / SECTOR))
        print("  IOCTL_DISK_GET_LENGTH_INFO says %d sectors" % (size // SECTOR))
        print("  the pvd says %d, the toc lead-out is %d" % (VOLSIZE, LEADOUT))
        print("  device sectors - volume sectors = %d"
              % (size // SECTOR - VOLSIZE))
        print("  device sectors - lead-out       = %d"
              % (size // SECTOR - LEADOUT))
    else:
        print("device size       : the length ioctl did not answer")
    print("pvd volume size   : %d sectors = %d bytes"
          % (VOLSIZE, VOLSIZE * SECTOR))
    print("toc lead-out LBA  : %d" % LEADOUT)
    print()

    lo = VOLSIZE - 3
    hi = LEADOUT + 3
    print("reading LBA %d .. %d, one sector each, no retries" % (lo, hi))
    print()
    print("  %8s %-6s %8s  %-10s %s"
          % ("LBA", "result", "seconds", "entropy", "note"))
    got = {}
    for lba in range(lo, hi + 1):
        t0 = time.perf_counter()
        try:
            f.seek(lba * SECTOR)
            b = f.read(SECTOR)
            dt = time.perf_counter() - t0
            if len(b) == SECTOR:
                got[lba] = b
                z = (set(b) == {0})
                mark = ""
                if lba == VOLSIZE:
                    mark = "  <- first sector past the volume"
                if lba == LEADOUT:
                    mark = "  <- lead-out address"
                print("  %8d %-6s %8.3f  %-10.4f %s%s"
                      % (lba, "OK", dt, ent(b),
                         "all zero" if z else b[:12].hex(" "), mark))
            else:
                print("  %8d %-6s %8.3f  %-10s short read, %d bytes"
                      % (lba, "SHORT", dt, "-", len(b)))
        except OSError as e:
            dt = time.perf_counter() - t0
            print("  %8d %-6s %8.3f  %-10s errno %s"
                  % (lba, "FAIL", dt, "-", e.errno))
    f.close()
    print()

    past = {k: v for k, v in got.items() if k >= VOLSIZE}
    print("sectors at or past the declared volume end that read: %d of %d"
          % (len(past), LEADOUT + 3 - VOLSIZE + 1))
    if not past:
        print("=> the volume device stops at the filesystem, as the briefing said.")
        return
    print("=> the volume device exposes %d sectors the filesystem does not claim."
          % len(past))
    print()
    zero = [k for k, v in past.items() if set(v) == {0}]
    print("all-zero among them : %d of %d" % (len(zero), len(past)))
    digs = collections.Counter(hashlib.sha1(v).hexdigest() for v in past.values())
    print("distinct contents   : %d" % len(digs))
    for d, c in digs.most_common(5):
        ex = sorted(k for k, v in past.items()
                    if hashlib.sha1(v).hexdigest() == d)
        print("   %s x%-4d first at LBA %d" % (d[:16], c, ex[0]))
    print()
    if dump:
        for k in sorted(past)[:4]:
            print("LBA %d, first 128 bytes:" % k)
            b = past[k]
            for a in range(0, 128, 16):
                ch = b[a:a + 16]
                print("   %4d  %-47s  %s"
                      % (a, ch.hex(" "),
                         "".join(chr(c) if 32 <= c < 127 else "." for c in ch)))
            print()


if __name__ == "__main__":
    main()
