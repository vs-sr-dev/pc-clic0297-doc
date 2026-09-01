# 00 — The predictions: sixty-two bets, written before the image was opened

*Measure: this file was written before any tool was pointed at `CLIC.ISO`, and
it is not edited afterwards. Section §A repeats what the briefing measured for
me and is worth no points. Section §B states inferences I am making from §A —
they are reasoning, not bets, and they are named so that the scoring chapter can
tell them apart from the clauses. The clauses are `C01`..`C62`, each marked
**method** (how the measurement will behave) or **content** (what the object
will turn out to contain).*

Scoring lives in [22 — The scoring](22-prediction-scoring.md) and is produced by
`python tools/checkscore.py docs/22-prediction-scoring.md`, not by adding up
here.

---

## §A — What I was given, and what it is worth (nothing)

The briefing measured the following before the session began. It is repeated
here so that the scoring chapter can prove no clause below merely restates it.

| | |
|---|---|
| image | `CLIC.ISO`, 509,257,728 bytes = 248,661 sectors of 2,048 exactly |
| sha1 | `ee3c2b6f7e16a178d4dd9093cdfe44ae007efca9` |
| descriptors | 2 — primary at sector 16, terminator at 17. No Joliet, no boot record, no CD-XA |
| volume identifier | `CLIC` |
| system identifier | `APPLE COMPUTER, INC., TYPE: 0002` |
| application identifier | `TOAST ISO 9660 BUILDER COPYRIGHT (C) 1993-1995 MILES SOFTWARE ENGINEERING - HAVE A NICE DAY` |
| publisher / preparer / copyright / abstract / bibliographic | all empty |
| volume space | 248,359 sectors = 508,639,232 bytes |
| created = modified | 1997-02-14 18:54:32.00 GMT+0 |
| expiration | not set |
| root directory | extent 20, 1997-02-14 18:53:35 |
| Apple partition map | block 0 `ER`, block size 512, 993,436 blocks; `MRKS` (Apple_partition_map, start 1, 2 blocks); `TOAST 2.5 Partition` (Apple_HFS, start 553, 992,881 blocks) |
| HFS MDB | `drVN` = `Clic!`; 2,820 files, 59 directories; 49,643 allocation blocks of 10,240 bytes; created 1997-02-07 13:16:32, modified 1997-02-14 17:11:37 |
| ISO tree | 2,879 records = 2,823 files + 56 directories; 5 carry the Associated-File bit at 670 bytes each; 2,818 files visible to a PC; 489,037,704 bytes of file data in 240,377 sectors |
| record dates | 1,590 distinct, 1979-06-05 01:42:28 → 1997-02-14 17:03:32; 1979:15 · 1980:32 · 1981:4 · 1984:1 · 1993:4 · 1994:65 · 1995:174 · 1996:1,410 · 1997:1,118 |
| unowned sectors | 7,846 (16,068,608 bytes, 3.16 %), of which 7,075 are not all-zero |
| image tail | 302 sectors, 618,496 bytes, all zero — a property of the dumper, not the disc |
| the five duplicated paths | `/CATAL.HTM`, `/DEMO.HTM`, `/PROD.HTM`, `/PAG/PAGELLE.HTM`, `/NUMERI/CLIC297/EDICOLA/SOMMARIO.HTM` |
| `.BZP` and `.LZP` | eight files, all beginning `42 5A 49 50` |
| nine bodies of software | LEADER/CATALOGO 354,228,172 · LEADER/DATA+TOMB 47,619,223 · VILLE 51,595,303 · MAGDEMO 10,839,135 · DOWN/MSIE301.EXE 5,585,256 · MUSEO 5,212,705 · LEADER/QTW 3,102,720 · the magazine 9,769,426 |
| personal data | 45 distinct e-mail addresses in 60 occurrences over 18 files; 74 `tel:`/`fax:` occurrences over 11 files |

Three questions inherited from `pc-clic11-doc/docs/21-open-questions.md` are
**not applicable** here and the briefing says so: Q1 and Q2 (the 152 sectors —
there is no drive and no TOC) and Q3 (the drive's maximum transfer — there is no
drive). They are closed as such in [21](21-open-questions.md), not re-asked.

---

## §B — What I infer from §A before measuring (reasoning, not bets)

**B1 — the arithmetic of the unowned sectors is already almost solved, and it is
a granularity artefact.** The HFS volume declares 49,643 allocation blocks of
10,240 bytes = 508,344,320 bytes = **248,215 sectors of 2,048 exactly**. The ISO
side declares 240,377 sectors of file extents. The difference is **7,838**, and
the briefing counts **7,846** sectors owned by nobody on the ISO side. Those two
numbers are eight apart. An allocation block of 10,240 bytes is five sectors of
2,048; an ISO extent is one sector of 2,048. A hybrid built by one pass of one
program has to satisfy both, so every file must start on a 10,240-byte boundary
and the bytes between the end of its ISO extent and that boundary belong to HFS
and to nobody on the ISO side. That is where the 3.16 % goes. The clauses below
bet on this in a form that can fail.

**B2 — this hybrid has almost no Macintosh side.** 2,820 HFS files against 2,818
PC-visible ones is a difference of **two**. CLIC 11's difference was 28 files and
47 forks and 26,607,777 bytes. A difference of two means the HFS catalogue is a
*re-presentation of the same tree*, not a second payload — which in turn means
Q6 of CLIC 11, the Macintosh-side crossing, is answerable here and the structural
answer is likely to be *nothing to cross*.

**B3 — nobody organised this disc.** Nine bodies of software in nine folders is
what a deadline looks like, not a design. Any sentence of the form "the disc is
organised into nine sections" is false and I am pre-committing not to write one.

**B4 — half of this object is a mail-order catalogue's trailers.** The six
largest files are all in `/LEADER/CATALOGO/TRYOUT/`. Whatever the recorded-
reality column ends up saying, it is measuring a retailer's advertising, not the
content of a work.

---

## The clauses

### The two-catalogue ownership map

| # | kind | clause |
|---|---|---|
| C01 | method | An ownership map that walks the ISO **and** the HFS catalogue cannot assign each sector to exactly one owner, because ISO file extents and HFS file extents describe **the same bytes**. The honest map is a map of *how many* owners each sector has, and the dominant class will be **two**. |
| C02 | content | Of the 7,846 ISO-unowned sectors, **more than 85 %** are accounted for by HFS allocation-block rounding — the gap between the end of a file's ISO extent and the next 10,240-byte boundary. |
| C03 | content | The residual after both catalogues are walked is **fewer than 400 sectors**, and it is **not zero**. |
| C04 | content | Every file's data begins on a **10,240-byte boundary** — i.e. every ISO extent LBA, minus the LBA at which the HFS allocation area starts, is a multiple of 5. This will hold for at least 99 % of the 2,823 file records. |
| C05 | content | The 7,075 non-zero unowned sectors are non-zero because Toast did **not** zero the padding: their content will be recognisable as **a repeat of the tail of the file that precedes them**, not random and not a hidden payload. |
| C06 | method | `hfs.parse_catalog()` returning 2 records is a node-size bug, not an empty catalogue: the B-tree node size will read **512** from the header node but the catalogue file will be large enough (from `drCTFlSize`) to hold hundreds of nodes. Fixing it is a change to how the leaf chain is followed, not a rewrite. |
| C07 | content | `drCTFlSize` is between **150,000 and 700,000 bytes**. |
| C08 | content | The HFS bitmap accounts for 49,643 bits = 6,206 bytes = **4 sectors**, and the number of allocation blocks it marks used will agree with the catalogue's file sizes to within 0.1 %. |

### The two files of difference

| # | kind | clause |
|---|---|---|
| C09 | content | The two files in the HFS catalogue that no PC sees are **Finder bookkeeping, not content** — the `Desktop DB` / `Desktop DF` pair, or a `Desktop` file, or an invisible Toast/Finder artefact of the same kind. |
| C10 | content | Their combined data-fork size is **under 1 MB**. |
| C11 | content | **Zero** files on this disc are Macintosh applications or Macintosh-only payload. There is no `Metti in Cartella Sistema` folder and no Mac QuickTime. |
| C12 | content | Consequently CLIC 11's **Q6 is answered and the answer is zero crossings**, and the reason is structural (nothing to cross) rather than evidential (looked and did not find). The three named candidates — `QuickTime™`, `QuickTime™ PowerPlug`, `Sound Manager` — are **absent from this disc**. |
| C13 | content | Resource forks: **fewer than 20** files on the whole volume have a non-empty resource fork, and five of them are the five Associated Files. |

### The five Associated Files

| # | kind | clause |
|---|---|---|
| C14 | content | The five 670-byte forks are **byte-identical to each other** — one template resource fork written five times. |
| C15 | content | Their content is a Macintosh **resource fork** with a valid 16-byte resource header whose offsets close against 670. |
| C16 | content | The resource they carry is Finder/appearance metadata rather than document content — a window position, an icon, or a `STR ` — and **no readable prose**. |
| C17 | content | Why those five of 549 HTML files: they are the five that a Macintosh application **opened or saved**, and they will share a property the other 544 lack — I bet on **all five being top-of-tree entry points** (four are at the root or one level down, and `SOMMARIO.HTM` is a section index). |
| C18 | method | Windows' own file count over the mounted ISO agrees with 2,818, and the count of 2,823 is reachable only by a walker that keeps the Associated-File records. Every file count in this repository will name which of the two it uses. |

### The media, which is 73.65 % of the disc

| # | kind | clause |
|---|---|---|
| C19 | content | The 32 `.MOV` files total between **45 and 100 minutes** of declared duration. |
| C20 | content | The dominant `.MOV` video codec is **Cinepak** (`cvid`), by file count and by bytes. |
| C21 | content | The three `.AVI` files total between **10 and 30 minutes**, and their codec is **not** the same as the `.MOV` codec — Indeo or Cinepak, decided by the `strf` chunk. |
| C22 | content | Not one `.MOV` or `.AVI` on this disc is 320×240 or larger for its whole population: the **median frame width is 240 or less**. |
| C23 | content | The 195 `.WAV` files total between **20 and 70 minutes**, and the most common sample rate is **22,050 Hz**. |
| C24 | content | At least one `.WAV` on the disc is **8-bit**, and at least one is mono at 11,025 Hz. |
| C25 | content | Total declared media duration — MOV + AVI + WAV + SMK — is between **1 h 30 m and 3 h 00 m**. |
| C26 | method | All of the above is read from declared headers with **zero frames decoded**, as in `pc-teslaeffect-doc`, and the tools that do it (`mov.py`, `avi.py`, `audio.py`) are validated against one known specimen each before being run on the population. |

### Tomb Raider

| # | kind | clause |
|---|---|---|
| C27 | content | The 20 `.PHD` files are the **complete retail level set of Tomb Raider (1996)**: 16 game levels including `GYM`, plus 4 cut-scene levels. |
| C28 | content | The disc therefore carries the **whole playable game data** and is not a one-level demo. |
| C29 | content | What is **missing** is the streamed media: **no `.RPL` FMV files** and **no CD audio track** — this image has one data track, so the game's Red Book music cannot be here. |
| C30 | content | The absence of FMV and music is **larger than what is present**: the missing material, had it shipped, would exceed 45,553,852 bytes. |
| C31 | content | `DEMO.DAT` at 628 bytes is a recorded **input stream for attract mode**, not a level and not a licence file. |
| C32 | content | `TOMB.LOG` is zero bytes and is a **leftover**, and it goes in the leftovers chapter. |
| C33 | content | `SETUP.INI` / `TOMB.MAP` / `INSTALL.BAT` are plain enough to read, and **at least one of them names a path or a drive letter** from the machine the build was made or packed on. |
| C34 | method | The `.PHD` format is proprietary and **no third-party implementation is consulted**. What is stated about it comes from the first bytes of the files themselves and from their names; everything else is declared **not derived**. |

### The nine strata

| # | kind | clause |
|---|---|---|
| C35 | content | The nine bodies of software were assembled by **at least six different organisations**, and no two of them share a build toolchain. |
| C36 | content | Two ToolBook runtimes ship on one disc — `MTB30RUN.EXE` (3.0) and `MTB40RUN.EXE` (4.0) — and they are **not** two copies of one file: they differ in size and in version resource. |
| C37 | content | The Leader catalogue (`LEADER/CATALOGO`, 354,228,172 bytes) is **72.4 % ± 2 % of all file bytes** and is the largest single stratum by a wide margin. |
| C38 | content | The magazine's own share, counted as `NUMERI` + `PAG` + `RETE` + `PRE` + root, is **under 1 %** of file bytes; including `IMG` it is **under 2.1 %**. Both figures are below CLIC 11's 3.37 %. |
| C39 | content | `MSIE301.EXE` is a single self-extracting archive and its internal version string says **3.01**; CLIC 11 shipped the same product as 121 signed cabinets eight months later. Same vendor, same product line, **two completely different delivery mechanisms**. |
| C40 | content | The oldest stratum by directory-record date is **not** the oldest by content: the 1979/1980 dates are constants, not history. |

### The clocks

| # | kind | clause |
|---|---|---|
| C41 | content | The 52 records dated before 1993 resolve to **fewer than 12 distinct timestamps** — the same handful of values repeated, which is the signature of a constant. |
| C42 | content | The 15 records from 1979 hold **at most 3** distinct timestamps. |
| C43 | content | The pre-1993 dates cluster **by directory**, not by extension: whole folders carry one impossible date. |
| C44 | content | The seconds field of the ISO directory records is **even in more than 90 %** of the 2,879 records, because the tree came off a FAT filesystem with a two-second grid — reproducing CLIC 11's 99.11 %. |
| C45 | content | The odd-seconds exceptions are **fewer than 200 records** and they concentrate in the same folders as the impossible dates. |
| C46 | content | The 1 h 42 m 55 s between the HFS modification time and the ISO creation time is **the mastering run itself**, and no directory record falls inside that window. |

### Absolute paths, protection, and the inherited measurements

| # | kind | clause |
|---|---|---|
| C47 | content | `paths.py` run intact over the 22 `.EXE`, 47 `.DLL`, 3 `.386` and any `.VBX` finds **between 30 and 400** absolute paths. |
| C48 | content | Those paths come from **at least four distinct vendors** — the most heterogeneous population this measurement has had — and no single build machine accounts for more than half. |
| C49 | content | At least one absolute path names a **drive letter other than `C:`**. |
| C50 | content | The protection scan finds **zero** hits over all 22 executables, and the positive control fires on at least 21 of them. |
| C51 | content | All 22 `.EXE` are `MZ`; **at least two** are 16-bit NE with no PE header, and at least one is a DOS/4GW-bound 32-bit DOS extender binary rather than a Windows executable. |

### Against CLIC 11 — the new measurement

| # | kind | clause |
|---|---|---|
| C52 | content | `discdiff.py` between CLIC 02/97 and CLIC 11 finds a **non-zero** number of byte-identical files. |
| C53 | content | That number is **between 1 and 40**. |
| C54 | content | The crossings are **third-party redistributables and/or the magazine's own boilerplate graphics** — and if any of the magazine's own files cross, they will be navigation art (`IMG/`), not editorial text. |
| C55 | content | **No `.HTM` file crosses**: eight months of a monthly magazine leaves no shared editorial page. |
| C56 | content | The **Saga** cell of the index row therefore fills, or fails to fill, on this measurement — and I bet it **fills**. |
| C57 | content | The mastering software changed between the two discs and both discs say so in their descriptors: `1993-1995 MILES SOFTWARE ENGINEERING` here, `1997 ADAPTEC` there. This is confirmed rather than discovered, and the new part is that the **partition name also changed** — `TOAST 2.5 Partition` here against `Toast 3.5.2 PPC HFS Optimizer` there. |

### Leftovers, and the documents

| # | kind | clause |
|---|---|---|
| C58 | content | `PSPBRWSE.JBF` parses: it is a JASC thumbnail cache with a readable file list, and it names **between 20 and 200** images. |
| C59 | content | It names **at least one file that is not on this disc**. |
| C60 | content | Total leftovers land between **1,000,000 and 8,000,000 bytes**, i.e. **0.2 % to 1.6 %** of file bytes — the same order as CLIC 11's 3,813,223 / 0.5766 %. |
| C61 | method | This repository ships **20 documents**, `00` through `19`. |
| C62 | method | Scoring: **62 clauses**, and I expect **41 hits, 10 halves, 11 misses**, for **69.4 %** — with method clauses scoring higher than content clauses, as in every previous session. |

---

## What I expect to get wrong

Three places, named in advance so the scoring chapter can check whether I saw
them coming.

**The first is C05.** "Stale buffer, and it repeats the previous file" is a
satisfying story and the briefing warns in as many words that *a plausible
number is more dangerous than an absurd one*. If 7,075 sectors of padding turn
out to be non-zero, the boring explanation — that they are not padding at all
but something the ISO catalogue simply does not describe — is the one I am
least equipped to notice, because I have already written down why it should be
padding. If C02 and C05 disagree, C05 is the one to distrust.

**The second is C27–C29.** I am asserting the contents of a 1996 retail product
from twenty file names. The level list is checkable against the file names on
the disc and nothing else; whether the game is *playable* from these bytes is
not measurable without running it, which is forbidden, so C28 is at risk of
being a claim I cannot settle either way. If it cannot be settled it is a
`unresolved`, not a hit.

**The third is C56.** I want the Saga cell to fill, which is exactly the reason
to suspect the bet. Four previous rows left it empty on principle; if this one
fills it, it has to fill on measured shared bytes and on nothing else.
