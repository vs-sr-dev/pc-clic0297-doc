#!/usr/bin/env python3
"""padecho.py -- what is in the bytes between the end of a file and the end of
its last sector?

A 2,048-byte sector is rarely filled exactly, so every file on an ISO has a
tail of padding. On the three discs before this one that padding was zeros and
nobody looked twice. On this one it is not zeros, it is not random, and it is
not the same thing twice: it is a byte-exact copy of the data **65,536 bytes
earlier in the image**.

The tool takes the file extents out of the ISO itself, so it cannot be accused
of having been pointed at the answer, and for each file it reports:

  * how many padding bytes there are and how many of them are non-zero;
  * whether padding[i] == image[i - 65536] for every byte of the padding;
  * how far that equality extends backwards from the file's end and forwards
    past the sector boundary, which is how the claim "exactly the padding and
    not one byte more" is measured rather than asserted.

Why 65,536 and not something else: it was found, not guessed. The first
32 bytes of the sector past the end of the declared volume were searched for
in the whole image, and came back at four offsets, two pairs, each pair
exactly 65,536 apart.

Usage:
    python tools/padecho.py IMAGE
    python tools/padecho.py IMAGE --distance N
"""
import mmap
import struct
import sys

SECTOR = 2048
DEFAULT_DISTANCE = 65536


def read_tree(m):
    """Walk the primary directory hierarchy and return (name, lba, size)."""
    pvd = m[16 * SECTOR:17 * SECTOR]
    root = pvd[156:156 + 34]
    out = []
    todo = [(struct.unpack("<I", root[2:6])[0],
             struct.unpack("<I", root[10:14])[0], "")]
    while todo:
        lba, size, prefix = todo.pop(0)
        data = m[lba * SECTOR:lba * SECTOR + size]
        off = 0
        while off < len(data) and data[off]:
            rl = data[off]
            ex = struct.unpack("<I", data[off + 2:off + 6])[0]
            ln = struct.unpack("<I", data[off + 10:off + 14])[0]
            flags = data[off + 25]
            nl = data[off + 32]
            name = data[off + 33:off + 33 + nl]
            if nl > 1 or name not in (b"\x00", b"\x01"):
                text = name.decode("ascii", "replace")
                if flags & 2:
                    todo.append((ex, ln, prefix + text + "/"))
                else:
                    out.append((prefix + text.split(";")[0], ex, ln))
            off += rl
    return out


def main():
    path = sys.argv[1]
    dist = DEFAULT_DISTANCE
    if "--distance" in sys.argv:
        dist = int(sys.argv[sys.argv.index("--distance") + 1])
    f = open(path, "rb")
    m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    n = len(m)

    print("image bytes            : %d" % n)
    print("a multiple of %-6d   : %s   (%d whole buffers)"
          % (dist, n % dist == 0, n // dist))
    print("declared volume ends at: %d"
          % (struct.unpack("<I", m[16 * SECTOR + 80:16 * SECTOR + 84])[0] * SECTOR))
    print("echo distance tested   : %d" % dist)
    print()
    print("%-26s %10s %6s %8s %7s %6s %6s"
          % ("file", "end", "pad", "nonzero", "echo", "back", "fwd"))

    files = sorted(read_tree(m), key=lambda r: r[1])
    last_end = 0
    for name, lba, size in files:
        start = lba * SECTOR
        end = start + size
        secend = start + ((size + SECTOR - 1) // SECTOR) * SECTOR
        pad = m[end:secend]
        nz = sum(1 for b in pad if b)
        echo = (len(pad) == 0) or (end >= dist and m[end - dist:secend - dist] == pad)
        back = end
        while back > dist and m[back - 1] == m[back - 1 - dist]:
            back -= 1
        fwd = secend
        while fwd < n and m[fwd] == m[fwd - dist]:
            fwd += 1
        print("%-26s %10d %6d %8d %7s %+6d %+6d"
              % (name.split("/")[-1], end, len(pad), nz, echo,
                 back - end, fwd - secend))
        last_end = max(last_end, end)

    print()
    trail = n - last_end
    print("bytes after the last file's last byte : %d" % trail)
    print("that region is an echo at -%d        : %s"
          % (dist, m[last_end:n] == m[last_end - dist:n - dist]))
    print("rounding the image up to a whole %d  : %d bytes needed"
          % (dist, (-last_end) % dist))
    m.close()
    f.close()


if __name__ == "__main__":
    main()
