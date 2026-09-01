# 04 — The ownership map: two catalogues, 248,359 sectors, and two that belong to nobody

*Measure: every sector of the declared volume space is assigned to the
structures that claim it, walking the ISO 9660 tree **and** the HFS catalogue.
The map closes. Two sectors out of 248,359 belong to neither catalogue, both are
all-zero, and the 7,846 sectors the ISO side alone cannot account for are
explained to the last one.*

```
python tools/twocat.py CLIC.ISO --align --unowned
```

---

## Why the inherited map could not do this

`secmap.py`, `sectormap.py` and `gapmap.py` all assign each sector to at most
one owner, because every disc measured before this one had a single filesystem
that mattered. This disc has two, and **they describe the same bytes**. The ISO
directory record for `/CATAL.HTM;1` and the HFS catalogue record for
`Clic!/catal.htm` point at LBA 1,168 and mean the same 1,135 bytes. A map that
insists on one owner per sector must either count that sector twice or throw one
catalogue away.

So `twocat.py` builds a map of **how many** owners each sector has. That turns
out to be the whole finding.

## The result

```
sectors by number of DISTINCT owner classes:
  0         2    0.0008 %
  1      7980    3.2131 %
  2    240377   96.7861 %

the ten commonest ownership combinations:
  hfsfile+isofile      240377   96.7861 %
  hfsfile                6818    2.7452 %
  hfsbt                  1020    0.4107 %
  isodir                  116    0.0467 %
  sys                      16    0.0064 %
  hfsvol                    6    0.0024 %
  vd                        2    0.0008 %
  ptbl                      2    0.0008 %
  (nobody)                  2    0.0008 %
```

**96.79 % of this disc is owned twice.** That is not an anomaly to be explained
away; it is what a hybrid *is*. Toast wrote one copy of every file and pointed
two catalogues at it. The disc is not an ISO volume with a Macintosh volume
bolted on: it is one body of data with two indexes.

## The map, contiguous

Nothing is scanned for. Every region is addressed from a structure that declared
it, and the regions abut:

| LBA | sectors | owner |
|---|---:|---|
| 0 – 15 | 16 | ISO system area (and, in its first bytes, the Apple partition map) |
| 16 – 17 | 2 | primary and terminator volume descriptors |
| 18 – 19 | 2 | path tables, L and M |
| 20 – 135 | 116 | ISO directory extents, root included |
| **136 – 137** | **2** | **nobody** |
| 138 – 142 | 5 | HFS boot blocks, Master Directory Block, volume bitmap |
| 143 – 652 | 510 | HFS extents-overflow B-tree (allocation blocks 0–101) |
| 653 – 1,162 | 510 | HFS catalogue B-tree (allocation blocks 102–203) |
| 1,163 – 248,357 | 247,195 | file data (allocation blocks 204–49,642) |
| 248,358 | 1 | alternate MDB |

16 + 2 + 2 + 116 + 2 + 5 + 510 + 510 + 247,195 + 1 = **248,359** = the declared
volume space. There is no gap anywhere except the two sectors at 136.

## The two sectors that belong to nobody

LBA 136 and 137. Both contain 2,048 bytes of `00` and nothing else — one
distinct byte value each. They sit in the last gap before the HFS volume starts:
the ISO directory extents run out at 135, and the Apple partition map places the
`Apple_HFS` partition at 512-byte block 553, which is byte 283,136, which is LBA
**138.25**. The HFS volume does not begin on a sector boundary; the ISO side
had already stopped; two sectors fell between.

And then something parked in them. Both zero-byte files on this disc —

```
python tools/twocat.py CLIC.ISO --only-iso

  LBA 136  /LEADER/TOMB/TOMB.LOG;1       0 B
  LBA 136  /MAGDEMO/IMOLA/IMOLA.CD2;1    0 B
```

— carry extent 136 in their directory records. A file of length zero occupies
`ceil(0 / 2048) = 0` sectors, so neither claims anything, and the extent field
is an address that addresses nothing. **Toast pointed its empty files at the
last free sector before the Macintosh volume and moved on.**

Issue 11 left two sectors of 322,926 unowned and both were zero. This disc
leaves two of 248,359 and both are zero. Two hybrids from one publisher,
mastered by two versions of one program eight months apart, both closing to the
same residue.

## The 7,846, explained

Counted from the ISO catalogue alone, 7,846 sectors — 16,068,608 bytes,
3.1591 % — belong to nothing. That number was the reason this chapter exists.
It decomposes exactly:

| | sectors | bytes |
|---|---:|---:|
| HFS allocation-block padding after files | 6,818 | 13,963,264 |
| HFS catalogue and extents B-trees | 1,020 | 2,088,960 |
| HFS volume header, bitmap, alternate MDB | 6 | 12,288 |
| nobody | 2 | 4,096 |
| **total** | **7,846** | **16,068,608** |

**86.90 % of it is a granularity artefact**, and the artefact is arithmetic:

  * an ISO extent covers `ceil(L / 2048)` sectors;
  * an HFS fork covers `ceil(L / 10240) × 5` sectors;
  * the gap between them belongs to HFS and to nothing on the ISO side.

An allocation block of 10,240 bytes is five sectors of 2,048 exactly, so the two
grids nest, and Toast could satisfy both by starting every file on a
10,240-byte boundary. It did:

```
python tools/twocat.py CLIC.ISO --align

alignment of ISO file extents to the 5-sector HFS grid
  first allocation block at LBA 143
    offset 0 :   2821 records  99.9292 %
    offset 3 :      2 records   0.0708 %
```

**2,821 of 2,823 file extents begin on the grid**, and the two that do not are
`TOMB.LOG` and `IMOLA.CD2` parked at LBA 136 — the zero-byte files, which have
no data to align. Of every file on this disc that contains a byte, **100 %
starts on a 10,240-byte boundary.**

## The HFS side closes to the block

The padding argument would be a story if the allocation blocks did not add up.
They do:

```
HFS alloc blocks from extents : 49439
  + catalogue B-tree           102
  + extents overflow B-tree    102
  =                          49643   =  drNmAlBlks,  drFreeBks = 0
```

Every allocation block on the volume is spoken for, the free count is zero, and
the number the MDB declares is the number the catalogue's extents sum to. A
volume that is exactly full is what a mastering program produces and what a
formatted disk never does.

One fork disagrees with the ceiling model, and it is the one from
[chapter 03](03-file-count.md):

```
disagreeing forks: 1
   Clic!/Desktop DF   data len=0  ceil=0  extents=7
```

`Desktop DF` holds seven allocation blocks — 71,680 bytes — for a file that
declares zero. Together with `Desktop DB`'s four blocks, that is the 55-sector
difference between the model (247,140 sectors) and the extents (247,195).

## What this closes

Issue 11 asked for a two-catalogue map and could not build one, because
`hfs.py` existed but nothing joined it to the ISO walker. This is that join, and
it produces the first exact sector accounting of a hybrid in this collection:

  * every sector of the volume space assigned, contiguously;
  * **two** sectors unowned, both zero, and the reason they exist is a partition
    boundary at LBA 138.25;
  * the 3.16 % that looked like unexplained space is a 2,048-versus-10,240
    granularity difference, measured file by file rather than asserted;
  * and **the padding is not empty**, which is [chapter 05](05-the-padding.md)
    and is the strangest thing on the disc.
