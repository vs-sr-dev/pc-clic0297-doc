#!/usr/bin/env python3
"""rawsect.py - read a 2352-byte-per-sector CD image and audit its scaffolding.

A CloneCD .img holds whole physical sectors: sync, header, mode byte,
subheader, user data, EDC, ECC. Everything outside the user data is the
scaffolding a burner writes and a cooked ISO throws away, and it is the only
place where a disc can be examined as a disc.

Sector layouts (ECMA-130 / Yellow Book / Green Book):

  all modes    0..11    sync   00 FF FF FF FF FF FF FF FF FF FF 00
               12..14   header MMSSFF, BCD, MSF of this sector
               15       mode: 0 (empty), 1, or 2

  mode 1       16..2063   2048 user data
               2064..2067 EDC over bytes 0..2063
               2068..2075 eight zero bytes
               2076..2351 ECC (P 172 + Q 104)

  mode 2 f1    16..23     subheader, 4 bytes written twice
               24..2071   2048 user data
               2072..2075 EDC over bytes 16..2071
               2076..2351 ECC (P 172 + Q 104)
               -- no reserved field: unlike Mode 1, Form 1 has none, because
                  the subheader stands in for the header in the ECC and the
                  four bytes Mode 1 spends on a header are not spent here.

  mode 2 f2    16..23     subheader, 4 bytes written twice
               24..2347   2324 user data
               2348..2351 EDC over bytes 16..2347, or zero if unused

Form is bit 5 (0x20) of the submode byte at offset 18: clear = Form 1.

Usage:
    python tools/rawsect.py IMG --summary
    python tools/rawsect.py IMG --scan          # sync, mode, form, header, ECC
    python tools/rawsect.py IMG --edc           # add full EDC verification
    python tools/rawsect.py IMG --tail          # trailing all-zero user data
    python tools/rawsect.py IMG --headers-out F # LBA -> header MSF, for subch.py
    python tools/rawsect.py IMG --cook OUT.iso  # 2048 bytes/sector
    python tools/rawsect.py IMG --dump LBA [N]  # hexdump raw sectors
"""

import argparse
import os
import sys

SECTOR = 2352
SYNC = b"\x00" + b"\xff" * 10 + b"\x00"

# CD EDC: CRC-32, generator (x^16+x^15+x^2+1)(x^16+x^2+x+1)
#   = x^32 + x^31 + x^16 + x^15 + x^4 + x^3 + x + 1  = 0x8001801B normal form.
# The loop below is LSB-first (reflected), so it needs the bit-reversed
# constant, 0xD8018001. Using the normal form in a reflected loop mismatches
# every sector, which is exactly what it did the first time this ran.
EDC_POLY = 0xD8018001


def _edc_table():
    tbl = []
    for i in range(256):
        v = i
        for _ in range(8):
            v = (v >> 1) ^ (EDC_POLY if v & 1 else 0)
        tbl.append(v)
    return tbl


EDC_TBL = _edc_table()


def edc(data, tbl=EDC_TBL):
    crc = 0
    for b in data:
        crc = tbl[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc


def bcd(b):
    """Decode one BCD byte; return None if either nibble is not a digit."""
    hi, lo = b >> 4, b & 0x0F
    if hi > 9 or lo > 9:
        return None
    return hi * 10 + lo


def lba_to_msf(lba):
    v = lba + 150
    return v // 4500, (v // 75) % 60, v % 75


def open_image(path):
    size = os.path.getsize(path)
    sectors, rem = divmod(size, SECTOR)
    return size, sectors, rem


def iter_sectors(path, start=0, count=None, chunk=512):
    """Yield (lba, bytes) in blocks, reading `chunk` sectors at a time."""
    size, sectors, _ = open_image(path)
    if count is None:
        count = sectors - start
    end = min(start + count, sectors)
    with open(path, "rb") as fh:
        fh.seek(start * SECTOR)
        lba = start
        while lba < end:
            n = min(chunk, end - lba)
            buf = fh.read(n * SECTOR)
            if len(buf) < n * SECTOR:
                n = len(buf) // SECTOR
                if n == 0:
                    return
            for i in range(n):
                yield lba + i, buf[i * SECTOR:(i + 1) * SECTOR]
            lba += n


def cmd_summary(path):
    size, sectors, rem = open_image(path)
    print("image            %s" % path)
    print("bytes            %d" % size)
    print("/ 2352           %d sectors, remainder %d" % (sectors, rem))
    if rem:
        print("  ** not a whole number of 2352-byte sectors **")
    m, s, f = lba_to_msf(sectors)
    print("lead-out would be at LBA %d = %02d:%02d:%02d" % (sectors, m, s, f))
    print("user bytes @2048 %d" % (sectors * 2048))
    print("subchannel @96   %d" % (sectors * 96))


def cmd_scan(path, do_edc, verbose_limit=24):
    size, sectors, rem = open_image(path)

    bad_sync = []
    modes = {}
    forms = {}
    subhdr_mismatch = []
    hdr_bad_bcd = []
    hdr_wrong = []
    subheaders = {}
    ecc_zero = []
    edc_bad = []
    edc_checked = 0

    for lba, sec in iter_sectors(path):
        if sec[0:12] != SYNC:
            if len(bad_sync) < 1000:
                bad_sync.append(lba)

        mode = sec[15]
        modes[mode] = modes.get(mode, 0) + 1

        mm, ss, ff = bcd(sec[12]), bcd(sec[13]), bcd(sec[14])
        if mm is None or ss is None or ff is None:
            if len(hdr_bad_bcd) < 1000:
                hdr_bad_bcd.append(lba)
        else:
            em, es, ef = lba_to_msf(lba)
            if (mm, ss, ff) != (em, es, ef):
                if len(hdr_wrong) < 1000:
                    hdr_wrong.append((lba, (mm, ss, ff), (em, es, ef)))

        if mode == 2:
            sh1, sh2 = sec[16:20], sec[20:24]
            if sh1 != sh2:
                if len(subhdr_mismatch) < 1000:
                    subhdr_mismatch.append(lba)
            subheaders[sh1] = subheaders.get(sh1, 0) + 1
            form = 2 if (sh1[2] & 0x20) else 1
            forms[form] = forms.get(form, 0) + 1

            if form == 1:
                if sec[2076:2352] == b"\x00" * 276:
                    if len(ecc_zero) < 1000:
                        ecc_zero.append(lba)
                if do_edc:
                    want = int.from_bytes(sec[2072:2076], "little")
                    if edc(sec[16:2072]) != want:
                        if len(edc_bad) < 1000:
                            edc_bad.append(lba)
                    edc_checked += 1
        elif mode == 1:
            if sec[2076:2352] == b"\x00" * 276:
                if len(ecc_zero) < 1000:
                    ecc_zero.append(lba)
            if do_edc:
                want = int.from_bytes(sec[2064:2068], "little")
                if edc(sec[0:2064]) != want:
                    if len(edc_bad) < 1000:
                        edc_bad.append(lba)
                edc_checked += 1

    print("=" * 72)
    print("RAW SECTOR SCAN  %s" % path)
    print("=" * 72)
    print("sectors                  %d" % sectors)
    print("trailing bytes           %d" % rem)
    print()
    print("-- sync ---------------------------------------------------------")
    print("  sectors with correct 00 FF*10 00     %d" % (sectors - len(bad_sync)))
    print("  sectors with bad sync                %d" % len(bad_sync))
    if bad_sync:
        print("    first: %s" % bad_sync[:verbose_limit])
    print()
    print("-- mode byte ----------------------------------------------------")
    for m in sorted(modes):
        print("  mode %d                               %d  (%.4f %%)"
              % (m, modes[m], 100.0 * modes[m] / sectors))
    print()
    if forms:
        print("-- form (submode bit 0x20) --------------------------------------")
        for f in sorted(forms):
            print("  Mode 2 Form %d                        %d  (%.4f %%)"
                  % (f, forms[f], 100.0 * forms[f] / sectors))
        print()
        print("-- subheader (file, channel, submode, coding) -------------------")
        for sh, n in sorted(subheaders.items(), key=lambda kv: -kv[1]):
            sm = sh[2]
            bits = []
            if sm & 0x80: bits.append("EOF")
            if sm & 0x40: bits.append("RT")
            if sm & 0x20: bits.append("form2")
            if sm & 0x10: bits.append("trigger")
            if sm & 0x08: bits.append("data")
            if sm & 0x04: bits.append("audio")
            if sm & 0x02: bits.append("video")
            if sm & 0x01: bits.append("EOR")
            print("  %02X %02X %02X %02X   %10d  (%.4f %%)   %s"
                  % (sh[0], sh[1], sh[2], sh[3], n, 100.0 * n / sectors,
                     "|".join(bits) if bits else "-"))
        print()
        print("  subheader copies disagree            %d" % len(subhdr_mismatch))
        if subhdr_mismatch:
            print("    first: %s" % subhdr_mismatch[:verbose_limit])
        print()
    print("-- header MSF ---------------------------------------------------")
    print("  non-BCD header bytes                 %d" % len(hdr_bad_bcd))
    if hdr_bad_bcd:
        print("    first: %s" % hdr_bad_bcd[:verbose_limit])
    print("  header != LBA+150 in MSF             %d" % len(hdr_wrong))
    for lba, got, want in hdr_wrong[:verbose_limit]:
        print("    LBA %d: header %02d:%02d:%02d, expected %02d:%02d:%02d"
              % (lba, got[0], got[1], got[2], want[0], want[1], want[2]))
    print()
    print("-- parity -------------------------------------------------------")
    print("  sectors with all-zero ECC            %d" % len(ecc_zero))
    if ecc_zero:
        print("    first: %s" % ecc_zero[:verbose_limit])
        print("    last:  %s" % ecc_zero[-verbose_limit:])
    print()
    if do_edc:
        print("-- EDC ----------------------------------------------------------")
        print("  sectors EDC-checked                  %d" % edc_checked)
        print("  EDC mismatches                       %d" % len(edc_bad))
        if edc_bad:
            print("    first: %s" % edc_bad[:verbose_limit])
        print()
    verdict = (not bad_sync and not hdr_bad_bcd and not hdr_wrong
               and not subhdr_mismatch and not edc_bad)
    print("VERDICT: %s" % ("every checked structure is internally consistent"
                           if verdict else "ANOMALIES PRESENT, see above"))


def cmd_tail(path, verify):
    """Find the run of trailing sectors whose user data is all zero."""
    size, sectors, _ = open_image(path)
    zeros = b"\x00" * 2048
    last_nonzero = -1
    run = 0
    with open(path, "rb") as fh:
        # walk backwards in blocks
        lba = sectors - 1
        block = 512
        found = False
        while lba >= 0 and not found:
            start = max(0, lba - block + 1)
            n = lba - start + 1
            fh.seek(start * SECTOR)
            buf = fh.read(n * SECTOR)
            for i in range(n - 1, -1, -1):
                sec = buf[i * SECTOR:(i + 1) * SECTOR]
                mode = sec[15]
                off = 24 if mode == 2 else 16
                if sec[off:off + 2048] != zeros:
                    last_nonzero = start + i
                    found = True
                    break
                run += 1
            lba = start - 1

    print("sectors                        %d" % sectors)
    print("last sector with non-zero user data   LBA %d" % last_nonzero)
    print("trailing all-zero sectors             %d  (LBA %d .. %d)"
          % (run, last_nonzero + 1, sectors - 1))
    print("content sectors                       %d" % (last_nonzero + 1))
    print()
    print("  %d - 150 (Red Book post-gap) = %d" % (run, run - 150))

    if verify and run:
        print()
        print("-- are the trailing sectors real, formatted sectors? -----------")
        bad = {"sync": 0, "hdr": 0, "edc": 0, "eccz": 0, "mode": {}, "form": {}}
        for lba, sec in iter_sectors(path, last_nonzero + 1, run):
            if sec[0:12] != SYNC:
                bad["sync"] += 1
            mm, ss, ff = bcd(sec[12]), bcd(sec[13]), bcd(sec[14])
            if (mm, ss, ff) != lba_to_msf(lba):
                bad["hdr"] += 1
            m = sec[15]
            bad["mode"][m] = bad["mode"].get(m, 0) + 1
            if m == 2:
                f = 2 if sec[18] & 0x20 else 1
                bad["form"][f] = bad["form"].get(f, 0) + 1
                if f == 1:
                    if edc(sec[16:2072]) != int.from_bytes(sec[2072:2076], "little"):
                        bad["edc"] += 1
                    if sec[2076:2352] == b"\x00" * 276:
                        bad["eccz"] += 1
        print("  bad sync              %d / %d" % (bad["sync"], run))
        print("  bad header MSF        %d / %d" % (bad["hdr"], run))
        print("  bad EDC               %d / %d" % (bad["edc"], run))
        print("  all-zero ECC          %d / %d" % (bad["eccz"], run))
        print("  modes                 %s" % bad["mode"])
        print("  forms                 %s" % bad["form"])
        ok = not (bad["sync"] or bad["hdr"] or bad["edc"] or bad["eccz"])
        print()
        print("  -> %s" % ("fully formed sectors carrying 2048 zero bytes each: "
                           "written by the recorder, not left blank"
                           if ok else "not uniformly well-formed, see counts"))


def cmd_headers_out(path, out):
    with open(out, "w") as fh:
        for lba, sec in iter_sectors(path):
            mm, ss, ff = bcd(sec[12]), bcd(sec[13]), bcd(sec[14])
            fh.write("%d %s %s\n" % (
                lba,
                "%02d:%02d:%02d" % (mm, ss, ff) if None not in (mm, ss, ff)
                else "BAD-%02X%02X%02X" % (sec[12], sec[13], sec[14]),
                "%d" % sec[15]))
    print("wrote %s" % out)


def cmd_cook(path, out):
    size, sectors, _ = open_image(path)
    written = 0
    skipped = {}
    with open(out, "wb") as fo:
        buf = []
        for lba, sec in iter_sectors(path):
            mode = sec[15]
            if mode == 2:
                form = 2 if sec[18] & 0x20 else 1
                if form == 1:
                    buf.append(sec[24:2072])
                else:
                    skipped["mode2form2"] = skipped.get("mode2form2", 0) + 1
                    buf.append(b"\x00" * 2048)
            elif mode == 1:
                buf.append(sec[16:2064])
            else:
                skipped["mode%d" % mode] = skipped.get("mode%d" % mode, 0) + 1
                buf.append(b"\x00" * 2048)
            written += 1
            if len(buf) >= 1024:
                fo.write(b"".join(buf))
                buf = []
        if buf:
            fo.write(b"".join(buf))
    print("cooked %s" % out)
    print("  sectors  %d" % written)
    print("  bytes    %d" % (written * 2048))
    if skipped:
        print("  substituted zeros for: %s" % skipped)


def cmd_dump(path, lba, n):
    for l, sec in iter_sectors(path, lba, n):
        mm, ss, ff = bcd(sec[12]), bcd(sec[13]), bcd(sec[14])
        print("=" * 72)
        hdr = ("%02d:%02d:%02d" % (mm, ss, ff) if None not in (mm, ss, ff)
               else "BAD-" + sec[12:15].hex())
        print("LBA %d   header %s   mode %d   subheader %s"
              % (l, hdr, sec[15], sec[16:24].hex(" ")))
        print("=" * 72)
        for off in range(0, SECTOR, 16):
            row = sec[off:off + 16]
            txt = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
            print("  %04X  %-47s  %s" % (off, row.hex(" "), txt))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("img")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--edc", action="store_true", help="with --scan, verify EDC")
    ap.add_argument("--tail", action="store_true")
    ap.add_argument("--verify", action="store_true", help="with --tail")
    ap.add_argument("--headers-out")
    ap.add_argument("--cook")
    ap.add_argument("--dump", type=int)
    ap.add_argument("--count", type=int, default=1)
    a = ap.parse_args()

    if a.summary:
        cmd_summary(a.img)
    if a.scan:
        cmd_scan(a.img, a.edc)
    if a.tail:
        cmd_tail(a.img, a.verify)
    if a.headers_out:
        cmd_headers_out(a.img, a.headers_out)
    if a.cook:
        cmd_cook(a.img, a.cook)
    if a.dump is not None:
        cmd_dump(a.img, a.dump, a.count)


if __name__ == "__main__":
    main()
