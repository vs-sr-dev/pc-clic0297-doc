# CLIC 02/97 — a cover disc, measured from an image

The CD-ROM bound into the Italian magazine **CLIC!**, mastered on a Macintosh
with Toast 2.5 on **14 February 1997 at 18:54:32 GMT**. It is the thirteenth
disc measured in this collection, the second from this magazine, and the first
that is a **file rather than a disc** — 509,257,728 bytes on a hard drive, with
no drive, no lead-out and no table of contents to read.

Nine separately-assembled bodies of software on one piece of polycarbonate, of
which the magazine made **0.82 %**. Half the object is a mail-order shop's
video trailers for other companies' games. A tenth of it is *Tomb Raider*.

Everything below is measured from the bytes. Each chapter opens with the
measurement it rests on, and every figure in the spec sheet carries the command
that reproduces it.

---

## The short sheet

| | |
|---|---|
| volume identifier | `CLIC` (ISO 9660) / `Clic!` (HFS) — **no issue number in either** |
| what it says it is | *«Clic! Cd-rom di Marzo»* — the March disc, carrying the February website |
| mastered | 1997-02-14 18:54:32 GMT; HFS volume opened 1997-02-07, closed 17:11:37 |
| mastering software | `TOAST ISO 9660 BUILDER … 1993-1995 MILES SOFTWARE ENGINEERING` / `TOAST 2.5 Partition` |
| medium | an **image**: 248,661 sectors against 248,359 declared, the 302 difference all zero and a property of the dumper |
| filesystems | ISO 9660 + HFS, hybrid, Apple partition map at block 0. **No Joliet** |
| files | **2,879** ISO records = 56 directories + 2,823 files, of which 5 are resource forks; **2,820** in the HFS catalogue; **2,818** a PC can open |
| the two catalogues differ by | **five Finder objects** — `Desktop DB`, `Desktop DF`, `Desktop Folder`, `Temporary Items`, `Trash`. No content is on one side only |
| sectors owned by both catalogues | 240,377 = **96.79 %** |
| sectors belonging to nobody | **2** — LBA 136 and 137, both all-zero, and where the disc's two empty files point |
| non-zero padding | **13,850,624 bytes** between the two grids, plus 2,671,402 in last sectors: ~16.5 MB of somebody's uncleared memory |
| copy protection | none: 12 markers over 75 executables, **1 hit, and it is the Italian word *settecento*** |
| absolute paths | **1,281** DOS-shaped, 857 distinct, in 81 files, from four vendors' machines |
| image sha1 | `ee3c2b6f7e16a178d4dd9093cdfe44ae007efca9` |
| leftovers | **4,898,814 bytes, 1.0017 %** |

**What is on it:** a 221-product mail-order games catalogue from Leader with the
trade prices left in (72.43 %), *Ville Venete* in ToolBook 4.0 (10.55 %), the
whole level set of **Tomb Raider** (9.74 %), a *Power F1* demo (2.22 %), the
magazine's own website images fetched by FTP four days earlier (1.18 %),
Internet Explorer 3.01 (1.14 %), a Musée d'Orsay demo (1.07 %), QuickTime for
Windows (0.63 %), and 573 files the magazine actually wrote (**0.82 %**).

**Recorded reality: 73.65 %** — and 92.8 % of that is one shop's advertising.

---

## The chapters

| | |
|---|---|
| [00 — The predictions](docs/00-predictions.md) | sixty-two bets, written before the image was opened, never edited |
| [01 — Provenance](docs/01-provenance.md) | an image of a disc, and nine parcels that never met |
| [02 — The spec sheet](docs/02-spec-sheet.md) | every number, with the command that makes it again |
| [03 — The file count](docs/03-file-count.md) | four answers, and the five Finder objects that explain all of them |
| [04 — The ownership map](docs/04-two-catalogues.md) | two catalogues, 248,359 sectors, and two that belong to nobody |
| [05 — The padding](docs/05-the-padding.md) | 13,850,624 bytes of a hard disk that no longer exists |
| [06 — The five resource forks](docs/06-associated-files.md) | where the cursor was, on a Friday afternoon in 1997 |
| [07 — Five clocks](docs/07-clocks.md) | 99.06 % came through MS-DOS, and 52 records came through nothing |
| [08 — The stratigraphy](docs/08-strata.md) | six suppliers, five runtimes, and nobody in charge |
| [09 — Tomb Raider](docs/09-tombraider.md) | all sixteen levels, half the cut scenes, none of the film |
| [10 — The Leader catalogue](docs/10-leader.md) | a 1997 price list with the trade margin left in |
| [11 — The media](docs/11-media.md) | 1 h 34 m 38 s, read from headers, and a column that does not apply |
| [12 — The producers](docs/12-producers.md) | the magazine made 0.82 % and names itself 1,649 times |
| [13 — Absolute paths](docs/13-paths.md) | three machines, and a heuristic that reads Cinepak as Macintosh |
| [14 — Against CLIC 11](docs/14-against-clic11.md) | two issues share two files and neither is theirs |
| [15 — Leftovers](docs/15-leftovers.md) | 1.0017 %, and twelve logs of the disc making itself |
| [16 — The tools](docs/16-tools.md) | 158 scripts, four written, and 56 that would lie about this disc |
| [17 — Open questions](docs/17-open-questions.md) | six raised, three that need a drive, four closed |
| [18 — The scoring](docs/18-scoring.md) | 62 bets, 75.81 %, and the miss that killed a good story |
| [19 — Corrections](docs/19-corrections.md) | seven in the briefing, eight of mine |

---

## The six things worth knowing

**One — the ownership map closes, and it needed two catalogues to do it.** Every
sector map inherited into this collection assigns each sector to one owner. On a
hybrid that is the wrong shape: **96.79 % of this disc is owned twice**, because
Toast wrote one copy of every file and pointed an ISO tree and an HFS catalogue
at the same bytes. Walked from both, the map runs contiguously from LBA 0 to LBA
248,358 with **two sectors left over**, both zero, sitting in the gap where the
Apple partition map puts the HFS volume at LBA 138.25. The 7,846 sectors the ISO
side alone cannot explain are 86.90 % allocation-block padding — an HFS block is
10,240 bytes and an ISO extent is 2,048, so **every file with a byte in it
starts on a five-sector grid**, 2,821 of 2,823 records.

**Two — the padding is not empty, and 43.6 % of it is on no file of this disc.**
Not one of the 6,763 padding sectors is zero, and none repeats its own file's
tail. Of 39 probes taken from the middle of padding regions and searched against
the whole image, 8 land inside another file, 14 only inside other padding, and
**17 are nowhere at all**. One region holds a fax cover-sheet template that does
not exist on this CD. The inherited `slack.py`, measuring a different region for
a different reason, agrees: **2,820 of 2,821 files have a dirty last sector**.
About 16.5 megabytes of this object is the uncleared working memory of a machine
in Milan in February 1997.

**Three — the two catalogues differ by five Finder objects and nothing else.**
Two files (`Desktop DB` at 40,960 bytes, `Desktop DF` at **zero bytes and seven
allocation blocks**) and three invisible folders, one of which is `Trash`. There
is no Macintosh payload here at all — which closes issue 11's Q6 in the
negative, structurally: the three QuickTime and Sound Manager files it nominated
are not absent because nobody looked, but because this hybrid is a Macintosh
*view* of a PC disc rather than a second disc bolted on.

**Four — five HTML files carry a resource fork, and it is somebody's cursor.**
670 bytes each, creator `R*ch`, one resource of type `BBSR`: **BBEdit**. Inside
is a window rectangle (502 × 346, thirty pixels from the left), a font
(`Monaco`, size 9) and an insertion point — for `CATAL.HTM`, byte 757 of 1,135.
They are not the tree's entry points, which was the guess. They are **the last
five files anybody touched**: `CATAL.HTM` carries the newest directory record on
the whole disc, 1997-02-14 17:03:32, eight minutes before the HFS volume closed.

**Five — the disc kept its own build log, twelve times.** `WS_FTP.LOG` survives
in twelve directories, 884 transfers in all, each line naming a local path, the
host `www1.mondadori.com`, and the publisher's server-side tree. Read in order
they reconstruct the week: back issues on Monday 10 February at 12:05, the
current issue's images at 12:07, the review marks at 12:16, then Tuesday morning
section by section — `TECNICO` at 08:59, 104 letters in `POSTA` at 09:00,
`INTERNET`, `COP`, `EDICOLA` — and the last two files of all, `ville.jpg` and
`orsay.jpg`, at 13:59. Tomb Raider's directory kept a **Watcom linker map**
naming every source file of the game and the machine that built it
(`C:\CCODE\TOMBRAID\GAME\croc.c`), because a developer's own two-line patch
script shipped alongside it and copied it there. And a **Paint Shop Pro
thumbnail cache** records that somebody opened a folder of pictures on a PC in
1996 to choose images.

**Six — the disc closes on itself.** Tomb Raider is product **100742** in
`GAMES.DBF`, published by Eidos, 99,900 lire to the public and 64,500 to the
trade — and it is **the only one of 221 products in the catalogue whose `DEMO`
field is set**. The mail-order catalogue that occupies 72 % of this CD-ROM
advertises exactly one playable demonstration, and that demonstration is sitting
two directories away.

---

## And what is not here

Nobody organised this disc. Nine parcels arrived from nine places and were
copied into nine folders by people with a deadline, and the only coherence on
the object is the coherence of the program that wrote it. Two versions of one
authoring runtime ship in two folders because two suppliers each brought their
own. Every one of the 52 directory records dated before 1993 — one of them 1979
— lives in one of four directories belonging to two strata, and fifty-four other
directories have clean dates.

The magazine names itself **1,649 times** and contributed **0.82 %** of the
bytes. The distributor whose catalogue is 72.43 % names itself 69 times. GLAMM
Interactive, who actually built the object, names itself fourteen.

And 104 files of readers' letters and 24,440 bytes of readers' small ads sit in
`NUMERI/CLIC297/`, holding 45 e-mail addresses and 73 telephone numbers. The
ones belonging to companies are quoted. The ones belonging to people are
**counted and nothing else** — not in the documents, not in `notes/`, not
truncated and not masked. A measurement of a magazine's cover disc that does not
publish its readers is not less rigorous. It is more, because it has separated
the object from the people who ended up inside it.
