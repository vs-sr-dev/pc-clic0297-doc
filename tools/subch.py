#!/usr/bin/env python3
"""subch.py - read a CloneCD .sub subchannel file.

96 bytes accompany every 2,352-byte sector on a CD. They carry eight
channels, P through W, 96 bits each. On a data disc only two of them are
used: P marks the pause before a track, and Q carries the running address,
the track and index numbers, and the control nibble that says what kind of
track this is. R through W are for CD+G and are zero on everything else.

A .sub file can hold those 96 bytes in either of two arrangements:

  interleaved     as the drive delivers them. Byte i holds bit i of all
                  eight channels at once: bit 7 is P, bit 6 is Q, down to
                  bit 0 for W.
  deinterleaved   bytes 0..11 are the whole P channel, 12..23 the whole Q
                  channel, and so on.

This tool detects which by trying both and seeing which one produces Q
entries whose CRC-16 checks out, because guessing is how you end up
documenting noise.

Q, mode 1 (ADR = 1), the only mode present inside a track:

  byte 0     control (high nibble) | ADR (low nibble)
  byte 1     track number, BCD
  byte 2     index, BCD
  bytes 3-5  running time within the track, MIN SEC FRAME, BCD
  byte 6     zero
  bytes 7-9  absolute time on the disc, MIN SEC FRAME, BCD
  bytes 10-11 CRC-16 CCITT over bytes 0..9, big-endian, complemented

Usage:
    python tools/subch.py SUB --layout
    python tools/subch.py SUB --scan
    python tools/subch.py SUB --dump LBA [--count N]
    python tools/subch.py SUB --vs-headers HEADERS.txt
    python tools/subch.py SUB --entropy
    python tools/subch.py SUB --errors
    python tools/subch.py SUB --pruns
"""

import argparse
import os
import sys

SUBSIZE = 96


# ------------------------------------------------------------------ CRC-16
def _crc16_table():
    tbl = []
    for i in range(256):
        v = i << 8
        for _ in range(8):
            v = ((v << 1) ^ 0x1021) & 0xFFFF if v & 0x8000 else (v << 1) & 0xFFFF
        tbl.append(v)
    return tbl


CRC_TBL = _crc16_table()


def crc16(data):
    c = 0
    for b in data:
        c = ((c << 8) & 0xFFFF) ^ CRC_TBL[((c >> 8) ^ b) & 0xFF]
    return c


# ------------------------------------------------------------------ layout
def deinterleave(block):
    """96 interleaved bytes -> 96 deinterleaved bytes (P..W, 12 each)."""
    out = bytearray(96)
    for ch in range(8):
        shift = 7 - ch
        for byte in range(12):
            acc = 0
            for bit in range(8):
                acc = (acc << 1) | ((block[byte * 8 + bit] >> shift) & 1)
            out[ch * 12 + byte] = acc
    return bytes(out)


def bcd(b):
    hi, lo = b >> 4, b & 0x0F
    if hi > 9 or lo > 9:
        return None
    return hi * 10 + lo


def lba_to_msf(lba):
    v = lba + 150
    return v // 4500, (v // 75) % 60, v % 75


def msf_to_lba(m, s, f):
    return (m * 60 + s) * 75 + f - 150


def q_of(block, layout):
    if layout == "deinterleaved":
        return block[12:24]
    return deinterleave(block)[12:24]


def p_of(block, layout):
    if layout == "deinterleaved":
        return block[0:12]
    return deinterleave(block)[0:12]


def rw_of(block, layout):
    if layout == "deinterleaved":
        return block[24:96]
    return deinterleave(block)[24:96]


def iter_blocks(path, start=0, count=None, chunk=4096):
    total = os.path.getsize(path) // SUBSIZE
    if count is None:
        count = total - start
    end = min(start + count, total)
    with open(path, "rb") as fh:
        fh.seek(start * SUBSIZE)
        lba = start
        while lba < end:
            n = min(chunk, end - lba)
            buf = fh.read(n * SUBSIZE)
            if len(buf) < n * SUBSIZE:
                n = len(buf) // SUBSIZE
                if n == 0:
                    return
            for i in range(n):
                yield lba + i, buf[i * SUBSIZE:(i + 1) * SUBSIZE]
            lba += n


def detect_layout(path, sample=2000):
    """Try both arrangements on a sample and report the CRC pass rate."""
    scores = {}
    for layout in ("deinterleaved", "interleaved"):
        ok = 0
        n = 0
        for lba, blk in iter_blocks(path, 0, sample):
            q = q_of(blk, layout)
            stored = (q[10] << 8) | q[11]
            if crc16(q[0:10]) ^ 0xFFFF == stored:
                ok += 1
            n += 1
        scores[layout] = (ok, n)
    return scores


# ------------------------------------------------------------------ commands
def cmd_layout(path, sample):
    total = os.path.getsize(path) // SUBSIZE
    rem = os.path.getsize(path) % SUBSIZE
    print("file        %s" % path)
    print("bytes       %d" % os.path.getsize(path))
    print("/ 96        %d blocks, remainder %d" % (total, rem))
    print()
    print("-- which arrangement, tested on the first %d blocks --" % sample)
    scores = detect_layout(path, sample)
    for layout, (ok, n) in scores.items():
        print("  %-15s Q CRC-16 valid on %d / %d  (%.2f %%)"
              % (layout, ok, n, 100.0 * ok / n if n else 0))
    best = max(scores, key=lambda k: scores[k][0])
    print()
    print("  -> %s" % best)
    return best


def cmd_scan(path, layout, verbose_limit=16):
    total = os.path.getsize(path) // SUBSIZE

    crc_bad = []
    adr = {}
    control = {}
    tno = {}
    index = {}
    abs_break = []
    rel_mismatch = []
    zero_nonzero = []
    p_values = {}
    rw_nonzero = []
    bad_bcd = []
    prev_abs = None

    for lba, blk in iter_blocks(path):
        q = q_of(blk, layout)
        stored = (q[10] << 8) | q[11]
        if crc16(q[0:10]) ^ 0xFFFF != stored:
            if len(crc_bad) < 2000:
                crc_bad.append(lba)

        a = q[0] & 0x0F
        c = (q[0] >> 4) & 0x0F
        adr[a] = adr.get(a, 0) + 1
        control[c] = control.get(c, 0) + 1
        tno[q[1]] = tno.get(q[1], 0) + 1
        index[q[2]] = index.get(q[2], 0) + 1

        if q[6] != 0:
            if len(zero_nonzero) < 2000:
                zero_nonzero.append(lba)

        am, asec, af = bcd(q[7]), bcd(q[8]), bcd(q[9])
        rm, rs, rf = bcd(q[3]), bcd(q[4]), bcd(q[5])
        if None in (am, asec, af, rm, rs, rf):
            if len(bad_bcd) < 2000:
                bad_bcd.append(lba)
        else:
            cur = msf_to_lba(am, asec, af)
            if prev_abs is not None and cur != prev_abs + 1:
                if len(abs_break) < 2000:
                    abs_break.append((lba, prev_abs, cur))
            prev_abs = cur
            # running time within a track that starts at LBA 0
            if msf_to_lba(rm, rs, rf) + 150 != cur:
                if len(rel_mismatch) < 2000:
                    rel_mismatch.append((lba, (rm, rs, rf), (am, asec, af)))

        p = p_of(blk, layout)
        p_values[p] = p_values.get(p, 0) + 1

        if any(rw_of(blk, layout)):
            if len(rw_nonzero) < 2000:
                rw_nonzero.append(lba)

    print("=" * 72)
    print("SUBCHANNEL SCAN  %s   (%s)" % (path, layout))
    print("=" * 72)
    print("blocks                          %d" % total)
    print()
    print("-- Q, CRC-16 ---------------------------------------------------")
    print("  valid                         %d" % (total - len(crc_bad)))
    print("  invalid                       %d" % len(crc_bad))
    if crc_bad:
        print("    first: %s" % crc_bad[:verbose_limit])
    print()
    print("-- Q, ADR ------------------------------------------------------")
    names = {1: "position", 2: "media catalogue number", 3: "ISRC"}
    for a in sorted(adr):
        print("  ADR %d (%-22s)      %d" % (a, names.get(a, "?"), adr[a]))
    print()
    print("-- Q, CONTROL --------------------------------------------------")
    for c in sorted(control):
        bits = []
        bits.append("data" if c & 0x4 else "audio")
        bits.append("4ch" if c & 0x8 else "2ch")
        bits.append("copy permitted" if c & 0x2 else "copy prohibited")
        bits.append(("incremental" if c & 0x1 else "uninterrupted")
                    if c & 0x4 else
                    ("pre-emphasis" if c & 0x1 else "no pre-emphasis"))
        print("  0x%x  %-8d  %s" % (c, control[c], ", ".join(bits)))
    print()
    print("-- Q, track and index ------------------------------------------")
    for t in sorted(tno):
        print("  TNO   0x%02X (%s)   %d" % (t, bcd(t), tno[t]))
    for i in sorted(index):
        print("  INDEX 0x%02X (%s)   %d" % (i, bcd(i), index[i]))
    print()
    print("-- Q, addresses ------------------------------------------------")
    print("  non-BCD address bytes         %d" % len(bad_bcd))
    print("  byte 6 (ZERO) non-zero        %d" % len(zero_nonzero))
    print("  breaks in absolute address    %d" % len(abs_break))
    for lba, prev, cur in abs_break[:verbose_limit]:
        print("    at block %d: %d -> %d" % (lba, prev, cur))
    print("  relative != absolute - 150    %d" % len(rel_mismatch))
    for lba, r, a in rel_mismatch[:verbose_limit]:
        print("    block %d: rel %02d:%02d:%02d abs %02d:%02d:%02d"
              % (lba, r[0], r[1], r[2], a[0], a[1], a[2]))
    print()
    print("-- P channel ---------------------------------------------------")
    for v, n in sorted(p_values.items(), key=lambda kv: -kv[1])[:8]:
        print("  %s   %d  (%.4f %%)" % (v.hex(), n, 100.0 * n / total))
    print()
    print("-- R..W channels -----------------------------------------------")
    print("  blocks with any non-zero R-W  %d" % len(rw_nonzero))
    if rw_nonzero:
        print("    first: %s" % rw_nonzero[:verbose_limit])
    print()
    ok = not (crc_bad or abs_break or bad_bcd or zero_nonzero
              or rel_mismatch or rw_nonzero)
    print("VERDICT: %s" % ("Q is internally consistent on every block"
                           if ok else "ANOMALIES PRESENT, see above"))


def cmd_dump(path, layout, lba, count):
    for l, blk in iter_blocks(path, lba, count):
        q = q_of(blk, layout)
        stored = (q[10] << 8) | q[11]
        good = crc16(q[0:10]) ^ 0xFFFF == stored
        print("block %-8d Q %s  ctl=%x adr=%x tno=%s idx=%s "
              "rel=%02d:%02d:%02d abs=%02d:%02d:%02d crc=%04x %s"
              % (l, q.hex(" "), q[0] >> 4, q[0] & 0xF,
                 bcd(q[1]), bcd(q[2]),
                 bcd(q[3]) or 0, bcd(q[4]) or 0, bcd(q[5]) or 0,
                 bcd(q[7]) or 0, bcd(q[8]) or 0, bcd(q[9]) or 0,
                 stored, "OK" if good else "BAD"))
        print("           P %s" % p_of(blk, layout).hex(" "))
        print("        R..W %s" % rw_of(blk, layout).hex())


def cmd_vs_headers(path, layout, headers):
    """Compare Q absolute addresses against the sector headers in the .img."""
    hdr = {}
    with open(headers) as fh:
        for line in fh:
            parts = line.split()
            if len(parts) < 2 or parts[1].startswith("BAD"):
                continue
            m, s, f = (int(x) for x in parts[1].split(":"))
            hdr[int(parts[0])] = (m, s, f)

    total = os.path.getsize(path) // SUBSIZE
    checked = agree = 0
    disagree = []
    missing = 0
    for lba, blk in iter_blocks(path):
        if lba not in hdr:
            missing += 1
            continue
        q = q_of(blk, layout)
        a = (bcd(q[7]), bcd(q[8]), bcd(q[9]))
        checked += 1
        if a == hdr[lba]:
            agree += 1
        elif len(disagree) < 2000:
            # a byte that is not valid BCD decodes to None; show the raw byte
            shown = tuple("%02d" % v if v is not None else "<%02X>" % q[7 + i]
                          for i, v in enumerate(a))
            disagree.append((lba, shown, hdr[lba]))

    print("subchannel blocks               %d" % total)
    print("sector headers supplied         %d" % len(hdr))
    print("compared                        %d" % checked)
    print("Q absolute == sector header     %d" % agree)
    print("disagree                        %d" % len(disagree))
    for lba, a, h in disagree[:32]:
        print("  LBA %d: Q %s:%s:%s, header %02d:%02d:%02d"
              % (lba, a[0], a[1], a[2], h[0], h[1], h[2]))
    print()
    if checked and agree == checked:
        print("Two structures written in two different places on the disc, and")
        print("recorded here in two separate files, agree on all %d addresses."
              % checked)


def expected_q(lba, control=0x4, adr=1, tno=1, index=1):
    """The Q entry this block must hold if the disc is what the TOC says it
    is: one data track, one index, addresses counting by one. Everything in a
    Q entry on a single-track data disc is a function of the block number,
    which is exactly what makes a damaged one identifiable."""
    def tobcd(v):
        return ((v // 10) << 4) | (v % 10)
    am, asec, af = lba_to_msf(lba)
    rm, rs, rf = lba // 4500, (lba // 75) % 60, lba % 75
    q = bytearray(12)
    q[0] = (control << 4) | adr
    q[1] = tobcd(tno)
    q[2] = tobcd(index)
    q[3], q[4], q[5] = tobcd(rm), tobcd(rs), tobcd(rf)
    q[6] = 0
    q[7], q[8], q[9] = tobcd(am), tobcd(asec), tobcd(af)
    c = crc16(bytes(q[0:10])) ^ 0xFFFF
    q[10], q[11] = c >> 8, c & 0xFF
    return bytes(q)


def cmd_errors(path, layout, verbose_limit=64):
    """Compare every Q entry against the one the TOC predicts, and measure
    how far the damaged ones are from it in bits."""
    total = os.path.getsize(path) // SUBSIZE
    diffs = []
    hist = {}
    crcbad = set()
    for lba, blk in iter_blocks(path):
        q = q_of(blk, layout)
        want = expected_q(lba)
        if q == want:
            continue
        stored = (q[10] << 8) | q[11]
        if crc16(q[0:10]) ^ 0xFFFF != stored:
            crcbad.add(lba)
        bits = sum(bin(a ^ b).count("1") for a, b in zip(q, want))
        hist[bits] = hist.get(bits, 0) + 1
        diffs.append((lba, q, want, bits))

    print("=" * 72)
    print("Q ENTRIES vs THE ENTRY THE TOC PREDICTS  %s" % path)
    print("=" * 72)
    print("blocks                              %d" % total)
    print("Q entries byte-identical to predicted %d  (%.4f %%)"
          % (total - len(diffs), 100.0 * (total - len(diffs)) / total))
    print("Q entries that differ                 %d" % len(diffs))
    print("  of which CRC-16 also fails          %d" % len(crcbad))
    print()
    print("-- how many bits wrong, per damaged entry ----------------------")
    for bits in sorted(hist):
        print("  %2d bit(s) wrong    %d entr%s"
              % (bits, hist[bits], "y" if hist[bits] == 1 else "ies"))
    print()
    if diffs:
        nbits = sum(b for _, _, _, b in diffs)
        print("  total wrong bits                  %d" % nbits)
        print("  Q bits on the disc                %d  (%d blocks x 96)"
              % (total * 96, total))
        print("  subchannel Q bit error rate       %.3e" % (nbits / (total * 96.0)))
        print()
    print("-- the damaged entries -----------------------------------------")
    print("  %-9s %-36s %-36s %s" % ("LBA", "read", "predicted", "bits"))
    for lba, q, want, bits in diffs[:verbose_limit]:
        xor = bytes(a ^ b for a, b in zip(q, want))
        marks = "".join("^" if x else " " for x in xor)
        print("  %-9d %s  %s  %d" % (lba, q.hex(" "), want.hex(" "), bits))
        print("  %-9s %s" % ("", " ".join(" ^" if x else "  " for x in xor).strip()))
    if len(diffs) > verbose_limit:
        print("  ... %d more" % (len(diffs) - verbose_limit))


def cmd_pruns(path, layout):
    """Where does the P channel go high, and for how long?"""
    total = os.path.getsize(path) // SUBSIZE
    runs = []
    cur = None
    for lba, blk in iter_blocks(path):
        p = p_of(blk, layout)
        # a block is "flagged" if the majority of P bits are set; a single
        # stray bit from a read error must not open a run
        ones = sum(bin(b).count("1") for b in p)
        hi = ones >= 48
        if cur is None or cur[2] != hi:
            if cur is not None:
                runs.append(cur)
            cur = [lba, lba, hi]
        else:
            cur[1] = lba
    if cur is not None:
        runs.append(cur)

    print("P channel runs (a block counts as high when >= 48 of its 96 bits are 1)")
    print()
    print("  %-10s %-10s %-9s %s" % ("from LBA", "to LBA", "blocks", "P"))
    for a, b, hi in runs:
        print("  %-10d %-10d %-9d %s" % (a, b, b - a + 1, "HIGH" if hi else "low"))
    print()
    print("total blocks %d" % total)


def cmd_entropy(path, layout):
    """How much unique information is actually in these 12 megabytes?"""
    total = os.path.getsize(path) // SUBSIZE
    seen_q = set()
    seen_full = set()
    for lba, blk in iter_blocks(path):
        seen_full.add(blk)
        seen_q.add(q_of(blk, layout))
    print("blocks                          %d" % total)
    print("distinct 96-byte blocks         %d" % len(seen_full))
    print("distinct 12-byte Q entries      %d" % len(seen_q))
    print()
    print("The file is %d bytes. Everything in it that is not the Q address"
          % os.path.getsize(path))
    print("counter is %d distinct values." % len(seen_q))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sub")
    ap.add_argument("--layout", action="store_true")
    ap.add_argument("--sample", type=int, default=2000)
    ap.add_argument("--force-layout", choices=("deinterleaved", "interleaved"))
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--dump", type=int)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--vs-headers")
    ap.add_argument("--entropy", action="store_true")
    ap.add_argument("--errors", action="store_true")
    ap.add_argument("--pruns", action="store_true")
    a = ap.parse_args()

    layout = a.force_layout
    if a.layout or layout is None:
        detected = cmd_layout(a.sub, a.sample)
        layout = layout or detected
        print()

    if a.scan:
        cmd_scan(a.sub, layout)
    if a.dump is not None:
        cmd_dump(a.sub, layout, a.dump, a.count)
    if a.vs_headers:
        cmd_vs_headers(a.sub, layout, a.vs_headers)
    if a.entropy:
        cmd_entropy(a.sub, layout)
    if a.errors:
        cmd_errors(a.sub, layout)
    if a.pruns:
        cmd_pruns(a.sub, layout)


if __name__ == "__main__":
    main()
