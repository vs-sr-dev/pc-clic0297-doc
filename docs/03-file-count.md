# 03 — The file count: four answers, and the five objects that explain all of them

*Measure: four walkers over the same 509,257,728 bytes return 2,879, 2,823,
2,820 and 2,818. Every one is right. This chapter says what each is counting
and settles the difference between the two catalogues completely — it is five
objects, and none of them is content.*

---

## The four numbers

```
python tools/iso9660.py CLIC.ISO --tree | tail -5
python tools/hfs.py --image CLIC.ISO --catalog
python tools/twocat.py CLIC.ISO
python tools/iso9660.py CLIC.ISO --extract _work/iso && find _work/iso -type f | wc -l
```

| count | what it counts |
|---|---|
| **2,879** | every ISO 9660 directory record: 56 directories and 2,823 file records |
| **2,823** | ISO file records, including five that carry the Associated-File flag |
| **2,820** | files in the HFS catalogue |
| **2,818** | files a Windows machine opens, and files left on disk after extraction |

Issue 11 had the same problem with a bigger population: 875 records, 857 files,
eighteen resource forks. Here the forks are five and the spread is smaller, so
the difference can be closed exactly rather than characterised.

## Why 2,823 and not 2,818: the Associated-File bit

Five paths appear twice in the ISO tree. The second record of each pair has bit
2 of the file-flags byte set — ECMA-119 §9.1.6, *Associated File* — and is 670
bytes long:

| path | fork LBA | data LBA | data bytes |
|---|---:|---:|---:|
| `/CATAL.HTM;1` | 1,163 | 1,168 | 1,135 |
| `/DEMO.HTM;1` | 1,173 | 1,178 | 1,429 |
| `/NUMERI/CLIC297/EDICOLA/SOMMARIO.HTM;1` | 1,183 | 1,188 | 7,962 |
| `/PROD.HTM;1` | 1,193 | 1,198 | 1,896 |
| `/PAG/PAGELLE.HTM;1` | 1,203 | 1,208 | 3,558 |

They are Macintosh resource forks, and what is in them is
[chapter 06](06-associated-files.md). What matters here is that a walker which
keeps them counts 2,823 and a filesystem driver which drops them shows 2,818 —
and **the extraction proves it without being asked to**:

```
extracted 2823 files, 489037704 bytes, to _work/iso
$ find _work/iso -type f | wc -l
2818
```

Each fork is written to the same name as its data file and then overwritten by
it. Five records in, five files fewer out, 3,350 bytes gone. Any hash list of
this disc built from a mounted volume is short by exactly that.

Note also the LBAs: 1,163, 1,173, 1,183, 1,193, 1,203 — **ten sectors apart,
without exception**, each fork five sectors ahead of its own data. These five
files are the first file data on the whole volume, laid out in pairs at the
head of the disc immediately after the HFS catalogue B-tree ends at LBA 1,162.
That spacing is the 10,240-byte allocation block of
[chapter 04](04-two-catalogues.md), visible with no tool at all.

## Why 2,820 and not 2,818: two Finder files

```
python tools/twocat.py CLIC.ISO --only-hfs
```

```
HFS forks whose LBA no ISO record points at:
  LBA 248303  Clic!/Desktop DB    data  40960 B  type 'BTFL' creator 'DMGR'
  LBA 248323  Clic!/Desktop DF    data      0 B  type 'DTFL' creator 'DMGR'
```

`Desktop DB` and `Desktop DF` are the Macintosh Desktop Manager's database —
the index the Finder keeps of every file's icon and creator on a volume.
Creator `DMGR`, types `BTFL` and `DTFL`. They are bookkeeping, not content,
and no Windows machine has ever needed them.

`Desktop DF` is the better of the two. It declares **zero bytes of data and
holds seven allocation blocks**, 71,680 bytes reserved for a file with nothing
in it:

```
Clic!/Desktop DF   data len=0  ceil=0  extents=7
```

That is the only fork on the volume whose physical size disagrees with its
logical size, and it is 35 of the 55 sectors by which the HFS extent total
exceeds the ceiling model in [chapter 04](04-two-catalogues.md).

## And three directories nobody put there

```
python tools/hfs.py --image CLIC.ISO --tsv notes/hfs-files.tsv
```

The ISO tree holds 56 directories plus the root. The HFS catalogue holds 60.
The three extra are:

```
Desktop Folder
Temporary Items
Trash
```

The invisible folders the Macintosh Finder creates on any volume it mounts
with write access. `Trash` on a CD-ROM is the Finder's habit pressed into
polycarbonate.

## The difference, complete

**Everything the two catalogues disagree about is five Finder objects.**

| | HFS | ISO |
|---|---|---|
| files | 2,820 | 2,818 |
| `Desktop DB`, `Desktop DF` | present | absent |
| directories (incl. root) | 60 | 57 |
| `Desktop Folder`, `Temporary Items`, `Trash` | present | absent |
| resource forks | 5, as fork records | 5, as Associated-File records |
| `TOMB.LOG`, `IMOLA.CD2` (0 bytes) | present, zero extents | present, extent 136, zero sectors |

Not one file of content exists on one side and not the other. **There is no
Macintosh payload on this disc.** Issue 11 had 28 HFS-only files and 47 forks
totalling 26,607,777 bytes that no PC could read; this disc has 40,960 bytes of
Finder database and 3,350 bytes of text-editor state.

That is a structural fact and it settles an inherited question in the negative —
see [chapter 14](14-against-clic11.md), Q6.

## Which number this repository uses

**2,818**, and it says so on every line where it matters. It is the count of
things on this disc that are files in the ordinary sense: they have a name, they
have contents, and something can open them. The other three numbers are
properties of a format, a catalogue and a flag, and they are quoted with their
walker attached.

The one place the choice bites is byte totals. 2,823 records hold 489,037,704
bytes; 2,818 files hold **489,034,354**. The difference is 3,350 — five
resource forks — and the HFS catalogue agrees with the second number exactly:
its data forks total 489,075,314 bytes, of which `Desktop DB` is 40,960, and
489,075,314 − 40,960 = **489,034,354**. Two catalogues written by one program,
agreeing to the byte about the same 2,818 files.
