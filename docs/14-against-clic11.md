# 14 — Against CLIC 11: two issues of one magazine share two files, and neither is theirs

*Measure: 2,818 files here against 857 on `pc-clic11-doc`, compared by sha1.
**Three hashes match; one is two empty files; the two real crossings are an
Apple installer and a Microsoft runtime.** Not one byte either magazine wrote
appears on both discs. What the two objects do share is a production process,
and five independent measurements agree on it.*

```
python tools/discdiff.py _work/iso ../pc-clic11-doc/_work/iso
python tools/discdiff.py _work/iso ../pc-clic11-doc/_work/iso --by-name
```

---

## Why this comparison is new

Twelve objects in this collection had been compared against each other and the
result was almost always zero. Issue 11 compared 21,870 records against
everything before it and found **two crossings, both Microsoft
redistributables**. That was the state of the art: *two discs share files only
where they share a third party's component.*

This is the first time **two objects of the same publication** have been on the
same machine. If the finding above is a law rather than an accident of sampling,
two issues of one magazine eight months apart should break it. They do not.

## The crossings

```
_work/iso                     2818 files,  2700 distinct,  489,034,354 bytes
../pc-clic11-doc/_work/iso     857 files,   841 distinct,  632,559,963 bytes

files hashing the same on both   3
   QTINSTAL.EXE     ==  QTINSTAL.EXE
   TOMB.LOG         ==  MSCREATE.DIR
   VBRUN300.DLL     ==  VBRUN300.DLL
```

| crossing | bytes | whose |
|---|---:|---|
| `QTINSTAL.EXE` | 1,394,176 | **Apple** — QuickTime for Windows, 16-bit installer |
| `VBRUN300.DLL` | 398,416 | **Microsoft** — Visual Basic 3 runtime |
| `TOMB.LOG` / `MSCREATE.DIR` | **0** | nobody |

**1,792,592 bytes cross, and every one belongs to Apple or Microsoft.**

The third match is a reminder to check. `TOMB.LOG` and `MSCREATE.DIR` are both
zero bytes long, so they have the same sha1 as each other and as every empty
file that has ever existed. It is not a crossing; it is what happens when a
hash-based comparison meets two empty files, and any tool that reports it
without saying so is producing a number that looks like evidence. Counted
honestly, the crossings are **two**.

## Nothing of the magazine's own crosses

By name rather than by hash:

```
basenames on both discs          11
... of which the bytes differ     9
   copertin.jpg  credits.htm  home.htm  intro.wav  lazio.htm
   main.dir  setup.exe  setup.ini  sommario.htm
```

Nine shared names looked at first like the magazine's own template surviving
across issues. It is not. Eight of the nine are coincidence, and the coincidence
is specific:

| basename | CLIC 02/97 | CLIC 11 |
|---|---|---|
| `lazio.htm` | `RETE/LAZIO.HTM` — the **region** of Lazio, in a directory of Italian websites by region | `CalcioHP/lazio.htm` — the **football club**, on a Hewlett-Packard promotional site |
| `credits.htm` | `/CREDITS.HTM` — the magazine's colophon | `CalcioHP/credits.htm` — HP's |
| `home.htm` | `IMG/HOME.HTM` | `CalcioHP/home.htm` |
| `copertin.jpg` | 8,058 B, the magazine's cover | 113,907 B, CalcioHP's |

Six of the nine live in `CalcioHP/` on issue 11 — a third party's website that
happens to use ordinary Italian words for its file names, as does an Italian
magazine. **One** of the nine is genuinely the same feature under the same name:
`sommario.htm`, the table of contents — `NUMERI/CLIC297/EDICOLA/SOMMARIO.HTM`
(7,962 B) here, `HTML/sommario.htm` (1,352 B) there. Different bytes, different
directory, same job.

`GLAMM` occurs **14 times** on this disc and **0 times** on issue 11.

So the honest total is: **zero bytes of CLIC's own work appear on both CLIC
discs.** A monthly magazine ships new content every month, and a cover disc is
made of what other people sent that month. There is nothing to inherit.

## What the two discs do share, and it is measurable

Five independent measurements, taken for other reasons, land on the same
production line:

| | CLIC 02/97 | CLIC 11 |
|---|---|---|
| mastering software | `TOAST ISO 9660 BUILDER … 1993-1995 MILES SOFTWARE ENGINEERING` | `TOAST ISO 9660 BUILDER … 1997 ADAPTEC` |
| HFS partition name | `TOAST 2.5 Partition` | `Toast 3.5.2 PPC HFS Optimizer` |
| filesystems | ISO 9660 + HFS, Apple partition map at block 0 | ISO 9660 + Joliet + HFS, Apple partition map at block 0 |
| **even seconds in directory records** | **99.0622 %** | **99.11 %** |
| **sectors owned by nobody** | **2, both zero** (of 248,359) | **2, both zero** (of 322,926) |
| timezone byte | 0 on all 2,879 records | 0 |
| descriptor implementor payload | zero bytes | zero bytes |

**The same magazine updated its own mastering software between February and
October 1997, and both discs say so in a field designed for something else.**
Toast 2.5, sold by Miles Software Engineering, became Toast 3.5.2, sold by
Adaptec, who had bought them; the partition name changed with it. That is a
stratigraphy of one small company's tooling, readable from two application
identifier strings.

And two numbers that nobody arranged: **99.06 % against 99.11 % even seconds**,
and **two unowned sectors, both zero**, on two discs of different sizes with
different content mastered by different versions of one program. The first says
both trees came off a PC before they reached the Macintosh; the second says
Toast's layout leaves the same residue whatever you feed it.

## This disc carries an archive of "issue 11", and it is not that disc

The readme promises *«le pagelle di tutti i numeri precedenti»* — the review
pages of every previous issue — and it delivers them. `PAG/` holds 288 files
whose names begin with an issue code, and `IMG/` holds one directory per issue:

```
PAG/ issue codes:   4 (42) · 6 (39) · 7 (32) · 9 (26) · 10 (24) · 11 (22)
                    12 (20) · 197 (19) · 297 (35)
IMG/ per issue:     CLIC10 · CLIC11 · CLIC12 · CLIC197 · CLIC297 · VOTI
```

**The magazine numbered its issues sequentially up to 12 and then switched to
month-and-year**: `197` is January 1997 and `297` is February 1997, so issue 12
is December 1996 and **issue 11 is November 1996**.

Which means this disc, mastered in February 1997, carries the back-issue archive
of an issue called 11 — **22 review pages in `PAG/11*.HTM` and 25 images in
`IMG/CLIC11/`**, fetched from
`…/Cliccd/img/clic11` on 1997-02-10 at 12:06 according to that folder's own FTP
log.

And the other object in this collection is a disc whose volume identifier is
`CLIC_11`, mastered **1997-10-20** — eight months later.

```
$ for f in _work/iso/IMG/CLIC11/*.JPG; do  … compare against ../pc-clic11-doc … done
(zero matches)
```

**None of the 25 images of "issue 11" on this disc appears on the disc called
`CLIC_11`.** The two elevens are not the same eleven, or the label means
something other than the issue number — the eleventh CD-ROM rather than the
eleventh magazine, or a second numbering series begun after the month-and-year
experiment ended. Two objects cannot settle it, and it is
[Q3](17-open-questions.md) rather than a conclusion.

What is settled is smaller and firmer: **`CLIC_11` in a volume identifier is not
self-evidently an issue number**, and issue 11's own repository read it as one.
That is the risk of the only field on a disc that names its maker: it says
`CLIC_11` and it does not say what the 11 counts.

## Q6 of issue 11, closed

Issue 11 asked: *does the Macintosh side of any two discs cross?* It named three
candidates to check first on the next hybrid:

```
Metti in Cartella Sistema/QuickTime™            272,096 + 916,587 bytes
Metti in Cartella Sistema/QuickTime™ PowerPlug  152,128 + 490,294 bytes
Metti in Cartella Sistema/Sound Manager               0 +  77,038 bytes
```

**All three are absent, and not because they were looked for and missed.** This
hybrid has no Macintosh side to cross ([chapter 03](03-file-count.md)): its HFS
catalogue holds exactly two files the ISO tree does not, and they are
`Desktop DB` and `Desktop DF`. There is no `Metti in Cartella Sistema` folder,
no Macintosh application, no Macintosh extension, and no resource fork anywhere
except five 670-byte editor states.

So Q6's answer here is **zero, for a structural reason**, and the useful part is
the reason: a Toast hybrid can be built two ways, and these two discs are one of
each. Issue 11 shipped a Macintosh payload of 26,607,777 bytes that no PC could
read. This one shipped a Macintosh *view* of a PC disc — the same 2,818 files
indexed twice — and the entire Macintosh-only content is 44,310 bytes of Finder
bookkeeping.

**That is the more interesting result.** The question "do two hybrids' Mac sides
cross?" assumed both have Mac sides. One of these does not, and the way to tell
is to count the catalogue difference, which is five objects and no content.

## The Saga cell

The index fills its **Saga** column *only when another object in this collection
shares bytes with it*. Four rows have left it empty on that rule, including
issue 11's own, which wrote: *a saga of one is not a saga, and of CLIC there is
exactly one disc here. If CLIC 12 ever arrives the cell fills then.*

A second CLIC has arrived, and the measurement is awkward: **they share
1,792,592 bytes and none of it is theirs.**

Filling the cell on `QTINSTAL.EXE` would be wrong, and it would be wrong in a
way that destroys the rule. Issue 11 established that *any* two discs of the
period share third-party redistributables; if that filled the Saga column, then
every hybrid in this collection carrying QuickTime is in a saga with every
other, and the column stops meaning anything. The *Mega Man* pair — the only
filled cells in the index — filled on **1,855 bytes the studio itself wrote**.

So the rule's operative clause, made explicit here because this is the first
object that forces it: **shared bytes must belong to the objects, not to a third
party both licensed.** By that reading the two CLIC discs share zero and the
cell stays empty.

**And it does not stay empty**, because the rule is a proxy and this object
shows what it is a proxy for. The column exists to distinguish a connection in
fact from a connection in name — to stop *Tomb Raider* filling a cell because
*Tomb Raider* is a famous series. CLIC is not a series title; it is a
**periodical**, and these are two issues of it. What binds them is not a
franchise but a production line, and that production line is measured above in
five places: the same mastering program in two versions, the same hybrid
structure, the same 99.1 % FAT fossil, the same two zero sectors, the same empty
implementor fields.

**The cell fills, on measured shared process rather than on shared payload, and
the cell says which.** That is a change to how the rule is applied and it is
recorded as one, here and in the index row, so that the next object can argue
with it. The four previously empty cells are not disturbed: none of them had a
second object of the same publication sitting on the same machine, and none of
them had five process fingerprints in common.

The thing the cell must not say is that the two discs share content. They do
not. **Zero bytes of CLIC's own work appear on both CLIC discs**, and that is
the most concrete sentence in this chapter.
