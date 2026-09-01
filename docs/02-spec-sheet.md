# 02 — The spec sheet: every number, with the command that makes it again

*Measure: each row is a figure and the command that reproduces it. Commands are
run from the repository root with `CLIC.ISO` in place. Nothing here is copied
from the session briefing; where a figure disagrees with the briefing the
disagreement is recorded in [chapter 19](19-corrections.md).*

---

## The image

| | | command |
|---|---|---|
| size | 509,257,728 bytes = 248,661 sectors of 2,048, exact | `python tools/iso9660.py CLIC.ISO --vd` |
| sha1 | `ee3c2b6f7e16a178d4dd9093cdfe44ae007efca9` | `sha1sum CLIC.ISO` |
| declared volume space | 248,359 sectors = 508,639,232 bytes | `--vd` |
| tail beyond the volume space | 302 sectors, 618,496 bytes, **all zero** | `python tools/twocat.py CLIC.ISO` |
| sector size | 2,048, cooked; no 2,352-byte raw framing | `--vd` (`looks_raw` returns false) |

**The 302 is not a lead-out.** It is the difference between a file's length and a
number inside that file. See [chapter 01](01-provenance.md).

## The ISO 9660 side

| | | command |
|---|---|---|
| descriptors | 2: primary at sector 16, terminator at 17 | `--vd` |
| Joliet | **none** — no type-2 descriptor exists | `--vd`; `--compare` refuses with *no volume descriptor of type 2* |
| El Torito / boot record | none | `--vd` |
| CD-XA | none | `--vd` |
| system identifier | `APPLE COMPUTER, INC., TYPE: 0002` | `--vd` |
| volume identifier | `CLIC` | `--vd` |
| application identifier | `TOAST ISO 9660 BUILDER COPYRIGHT (C) 1993-1995 MILES SOFTWARE ENGINEERING - HAVE A NICE DAY` | `--vd` |
| publisher / preparer / copyright / abstract / bibliographic | all blank | `--vd` |
| volume set size / sequence | 1 / 1 | `--vd` |
| path table | 798 bytes, L at sector 18, M at 19 | `--vd` |
| creation = modification | 1997-02-14 18:54:32.00 GMT+0, raw `1997021418543200` | `--vd` |
| expiration / effective | **not set**, sixteen zero bytes each | `--vd` |
| file structure version | 1 | `--vd` |
| root directory record | extent 20, 2,048 bytes, 1997-02-14 18:53:35, raw `61 02 0E 12 35 23 00` | `--vd` |
| application-use field | 512 bytes, **all zero** | `--vd` |
| directory records | **2,879** = 56 directories + 2,823 file records | `python tools/iso9660.py CLIC.ISO --tree` |
| Associated-File records | **5**, 670 bytes each | `python tools/twocat.py CLIC.ISO` |
| files a PC can see | **2,818** | 2,823 − 5; confirmed by extraction, below |
| file bytes | 489,037,704 (2,818 data files: 489,034,354) | `--tree` |
| file extent sectors | 240,377 | `python tools/twocat.py CLIC.ISO` |

The 2,330 bytes of implementor-defined space that carried a payload on four
non-Toast discs in this collection are zero here, as they were on issue 11 —
the second Toast disc to say nothing in them.

## The Macintosh side

| | | command |
|---|---|---|
| driver descriptor | `ER` at block 0, block size 512, 993,436 blocks | `python tools/hfs.py --image CLIC.ISO --map` |
| partition 1 | `MRKS`, `Apple_partition_map`, start block 1, 2 blocks | `--map` |
| partition 2 | `TOAST 2.5 Partition`, `Apple_HFS`, start block 553, 992,881 blocks | `--map` |
| MDB | at byte 284,160 (LBA 138, offset 1,536), signature `BD` | `python tools/hfs.py --image CLIC.ISO --mdb` |
| volume name | `Clic!` | `--mdb` |
| created | 1997-02-07 13:16:32 | `--mdb` |
| last modified | 1997-02-14 17:11:37 | `--mdb` |
| files / directories | 2,820 / 59 (`drDirCnt` excludes the root; the catalogue holds 60) | `--mdb`, `--catalog` |
| allocation block | 10,240 bytes = **5 sectors of 2,048, exactly** | `--mdb` |
| allocation blocks | 49,643, **0 free** | `--mdb` |
| first allocation block | LBA 143.0000 | `--mdb` |
| catalogue file | 1,044,480 bytes at allocation block 102, length 102 | `--mdb` |
| extents overflow file | 1,044,480 bytes at allocation block 0, length 102 | `--mdb` |
| next CNID / write count | 3,047 / 5,031 | `--mdb` |
| blessed system folder | CNID 0 — **the volume is not bootable** | `--mdb` |
| catalogue B-tree | 2,040 nodes of 512, depth 4, root node 120, first leaf 4, 1,046 free nodes, key length 37 | `python tools/hfs.py --image CLIC.ISO --catalog` |
| catalogue records | 2,940 = 2,820 files + 60 directories + 60 threads, over 882 leaves | `--catalog` |
| forks with a resource fork | **5**, 670 bytes each, 3,350 bytes in total | `python tools/twocat.py CLIC.ISO` |
| forks using all three extent slots | **0** — nothing on this volume is fragmented | `python tools/twocat.py CLIC.ISO` |

`hfs.parse_catalog()` reads this volume correctly with no change. The briefing
reported it returning two records; it returns 2,940. See
[chapter 19](19-corrections.md).

## The ownership map

Full derivation in [chapter 04](04-two-catalogues.md).

| | | command |
|---|---|---|
| sectors owned by both catalogues | 240,377 = 96.7861 % | `python tools/twocat.py CLIC.ISO` |
| sectors owned by HFS alone | 6,818 = 2.7452 % | same |
| sectors owned by nobody | **2** — LBA 136 and 137, both all-zero | `--unowned` |
| ISO extents on the 10,240-byte grid | 2,821 of 2,823 = 99.9292 % | `--align` |
| the two exceptions | `/LEADER/TOMB/TOMB.LOG` and `/MAGDEMO/IMOLA/IMOLA.CD2`, both **zero bytes** | `--align`, `--only-iso` |
| HFS allocation blocks, from extents | 49,439 files + 102 catalogue + 102 extents = **49,643 = `drNmAlBlks`** | see chapter 04 |

The complete map is contiguous and leaves no gap other than those two sectors:

```
      0 –     15   ISO system area (16)          16 –     17   descriptors (2)
     18 –     19   path tables (2)               20 –    135   ISO directories (116)
    136 –    137   nobody (2)                   138 –    142   HFS volume header (5)
    143 –    652   HFS extents B-tree (510)     653 –   1162   HFS catalogue B-tree (510)
   1163 – 248357   file data (247,195)        248358          alternate MDB (1)
```

16 + 2 + 2 + 116 + 2 + 5 + 510 + 510 + 247,195 + 1 = **248,359**.

## The file count depends on the walker

Four answers, all correct, all of different questions
([chapter 03](03-file-count.md)):

| | |
|---|---|
| 2,879 | ISO directory records including directories |
| 2,823 | ISO file records including the five resource forks |
| 2,820 | HFS catalogue files |
| **2,818** | files a Windows machine can open |

Extraction is its own proof: `--extract` writes 2,823 records and leaves
**2,818 files**, because each Associated File collides with the data file of the
same name and is overwritten.

## Content

| | | command |
|---|---|---|
| recorded reality (`.MOV .AVI .WAV .SND .SMK`) | 360,192,268 bytes = **73.6533 %** | see chapter 11 |
| still images (`.TIF .JPG .GIF .LBM .PCX .BBM .BMP`) | 30,096,122 bytes = 6.1542 % | same |
| declared media duration | **1 h 34 m 38 s** (MOV 27 m 16 s, WAV 59 m 38 s, AVI 5 m 19 s, SMK 2 m 25 s) | `mov.py`, `audio.py`, `avi.py` |
| largest stratum | `LEADER/CATALOGO`, 354,228,172 bytes = 72.4342 % | `python tools/census.py _work/iso` |
| the magazine's own share | 0.8205 %, or 1.9970 % counting `IMG/` | chapter 12 |
| executables | 75 scanned; **2 PE32**, ~38 NE16, the rest MZ/DOS | `python tools/pecensus.py _work/iso` |
| copy protection | **none**: 12 markers, 1 hit, and the hit is the Italian word *settecento* | `python tools/protscan.py _work/iso` |
| absolute paths | 1,281 DOS-shaped, 857 distinct, 81 files; 248 "Mac-shaped" are noise | `python tools/buildpaths.py _work/iso` |
| internal duplicates | 118 redundant copies, 4,296,305 bytes = 0.8785 % | chapter 15 |
| files shared with CLIC 11 | **3 hashes, 2 real** | `python tools/discdiff.py _work/iso ../pc-clic11-doc/_work/iso` |

## Engine — what runs what

There is no engine. There are five, and they do not know about each other.

| runtime | version | shipped by | drives |
|---|---|---|---|
| Asymetrix Multimedia ToolBook | **3.0** (`MTB30RUN.EXE`, 620,864 B) | Leader | `LEADER/CATALOGO/CATAL.TBK` |
| Asymetrix Multimedia ToolBook | **4.0** (`MTB40RUN.EXE`, 807,296 B) | the *Ville Venete* supplier | `VILLE/VILLE.EXE`, itself a compiled ToolBook application |
| Macromedia Director | Projector for Windows Release 5.0 | Leader, and the Orsay supplier | `LEADER/CATALOGO/LCAT.EXE`, `MUSEO/ORSAY.EXE` + `MAIN.DIR` |
| Rational Systems DOS/4GW | bound, 16-bit MZ stub | Core Design; Team17-era F1 demo | `LEADER/TOMB/TOMB.EXE`, `MAGDEMO/F1.EXE` |
| Apple QuickTime for Windows | 16-bit and 32-bit installers | Apple, via Leader | the 32 `.MOV` files |

Plus **HMI Sound Operating System** (Human Machine Interfaces Inc., 1995) as the
audio layer under Tomb Raider — three `.386` drivers and a setup utility that
enumerates eighteen sound cards — and the **Q+E / Pioneer Software ODBC** stack
under ToolBook 3.0, fourteen DLLs deep, for a catalogue that queries a dBase
file.

Two ToolBook runtimes on one disc is not redundancy the publisher chose. It is
two suppliers who each shipped their own, and nobody reconciled them.
