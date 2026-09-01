# 18 — The scoring: 62 bets, 75.81 %, and the one I flagged in advance and still got wrong

*Measure: the verdicts below are counted out of the table by
`python tools/checkscore.py docs/18-scoring.md`, not added up by hand. The
header of a scoring document has been wrong in this branch twice before, both
times because somebody tallied it while still editing the body.*

The predictions are [chapter 00](00-predictions.md) and have not been edited
since they were written, which was before `CLIC.ISO` was opened.

---

## The totals

| | hits | halves | misses | unresolved | score |
|---|---:|---:|---:|---:|---:|
| **method** (7) | 5 | 1 | 1 | 0 | **78.57 %** |
| **content** (55) | 37 | 9 | 7 | 2 | **75.45 %** |
| **all** (62) | **42** | **10** | **8** | **2** | **75.81 %** |

A half counts 0.5. **Two conventions, and both are given because the inherited
tool uses the other one:**

```
python tools/checkscore.py docs/18-scoring.md

  hit 42 · half 10 · miss 8 · unresolved 2      rows parsed: 62
  resolved 60 ; halves at 0.5 : 47.0 of 60 = 78.3 %
```

`checkscore.py` drops unresolved clauses from the denominator and reports
**78.3 %**. This chapter's headline keeps them in — 47.0 of 62 = **75.81 %** —
because a bet that cannot be settled is a bet that was written badly, and the
writer should pay for it. The difference is 2.5 points and it is two clauses,
C22 and C30.

Two artefacts of the inherited tool, declared rather than tuned away: it was
written for a repository whose clauses are numbered `Pnn`, and its regular
expression was widened to accept `Cnn` as well ([chapter 16](16-tools.md)); and
it adds a line for `P93, scored elsewhere`, which is another repository's
deferred clause and does not exist here, so its `grand total 63` should read 62.

**C62 predicted 41 hits, 10 halves, 11 misses and 69.4 %.** The hit count is
exactly right and the score is 6.4 points low, because six clauses that were
expected to miss came in as halves. It is scored a half: the number that
mattered was right and the distribution was not.

Method beats content by 3.1 points, as it has in every session of this branch.
Predicting *how a measurement will behave* is easier than predicting *what is
inside an object*, and it should be.

---

## The ownership map

| # | verdict | what happened |
|---|---|---|
| C01 | hit | 96.7861 % of sectors have two owner classes; the dominant combination is `hfsfile+isofile` |
| C02 | hit | 6,818 of 7,846 = **86.90 %**, just over the 85 % called |
| C03 | hit | residual **2** sectors, under 400 and not zero |
| C04 | hit | 2,821 of 2,823 = 99.9292 % on the grid, and the two exceptions hold no data |
| C05 | half | the mechanism is right — uncleared buffer, not a payload — and the specific claim is wrong: **0 of 2,395** regions repeat their own file's tail, and 17 of 39 probes are on no file at all. Flagged in advance as the likeliest miss, and it was |
| C06 | miss | there is no node-size bug. `hfs.parse_catalog()` returns **2,940 records** on this volume with no change. The briefing's premise was false and the clause inherited it |
| C07 | miss | `drCTFlSize` is **1,044,480**, half again above the top of the range called |
| C08 | half | the bitmap is 4 sectors as called; the second half — that it agrees with the catalogue to 0.1 % — was **not measured**. `drFreeBks = 0` and the extents sum to `drNmAlBlks` exactly, which is the same claim by another route, but it is not the measurement written down |

## The two files of difference

| # | verdict | what happened |
|---|---|---|
| C09 | hit | `Desktop DB` and `Desktop DF`, creator `DMGR` |
| C10 | hit | 40,960 + 0 bytes |
| C11 | hit | no Macintosh application, no `Metti in Cartella Sistema`, no Mac payload |
| C12 | hit | Q6 answered zero, structurally; all three named candidates absent |
| C13 | hit | **exactly 5** files with a resource fork, and they are the five Associated Files |

## The Associated Files

| # | verdict | what happened |
|---|---|---|
| C14 | miss | **five distinct sha1s**. Same structure to the byte, different contents |
| C15 | hit | data@256 len 364, map@620 len 50, 620 + 50 = 670, on all five |
| C16 | hit | a window rectangle, an insertion point and a font. The only printable strings are `R*ch` and `Monaco` |
| C17 | half | the mechanism was called correctly — files a Macintosh application opened — and it is **BBEdit**, named by creator code and resource type. The property bet on, "top-of-tree entry points", is not the property: it is **the last five files anybody touched**, and `CATAL.HTM` carries the newest record on the disc |
| C18 | hit | extraction leaves 2,818 files from 2,823 records, and every count in this repository names its walker |

## The media

| # | verdict | what happened |
|---|---|---|
| C19 | miss | **27 m 16 s**, not 45–100 minutes. Off by a factor of two |
| C20 | hit | Cinepak on 30 of 32 and on effectively all the bytes |
| C21 | miss | **5 m 19 s**, not 10–30; and two of the three AVIs *are* Cinepak. Wrong twice |
| C22 | unresolved | `mov.py` does not extract `tkhd` dimensions and nothing else measured them. The AVIs give 240 and 320 and the Smackers 64 and 128, which is not a median of 32 QuickTime files |
| C23 | half | 59 m 38 s is inside 20–70 minutes; the commonest rate is **11,025 Hz**, not 22,050 — 165 files of 195 |
| C24 | hit | 165 files are 8-bit mono at 11,025 |
| C25 | hit | **1 h 34 m 38 s**, inside 1 h 30 m – 3 h 00 m, close to the floor |
| C26 | hit | zero frames decoded; each reader validated on one specimen first, and `avi.py` confirmed all three RIFF sizes exactly |

## Tomb Raider

| # | verdict | what happened |
|---|---|---|
| C27 | half | **16 of 16 game levels**, exactly as called. **2 of 4 cut scenes**, not 4 — and the other two `.PHD` are `TITLE` and `CURRENT`, which are the same file |
| C28 | half | the level data is complete and it is not a one-level demo. Whether it is *playable* is not measurable without running it, and the clause should not have said so |
| C29 | hit | no `.RPL` anywhere; one data track, so no Red Book audio is possible |
| C30 | unresolved | the size of the missing FMV is a fact about the retail product, and there is nothing in this object that states it. Asserting it would be knowledge from outside the bytes |
| C31 | miss | `DEMO.DAT` is **628 bytes and every one is zero** |
| C32 | hit | `TOMB.LOG` is zero bytes and is in the leftovers |
| C33 | hit | all three name a path or a drive: `c:\tombraid`, `c:\tombdemo`, and 2,279 lines of `C:\CCODE\TOMBRAID\` |
| C34 | hit | nothing about `.PHD` derived beyond the first eight bytes, and the rest declared not derived |

## The strata

| # | verdict | what happened |
|---|---|---|
| C35 | hit | at least six organisations; three project roots on three machines; no shared toolchain |
| C36 | hit | 620,864 vs 807,296 bytes, different sha1, ToolBook 3.0 vs 4.0 |
| C37 | hit | **72.4342 %** — the range called was 72.4 % ± 2 % |
| C38 | hit | 0.8205 % narrow, 1.9970 % with `IMG/`, both below issue 11's 3.37 % |
| C39 | hit | one self-extracting archive against 121 signed cabinets eight months later |
| C40 | half | 1979 is a constant repeated thirteen times, as called. **1980 is not a constant**: it is 23 distinct times over two days, a clock that was never set and was running correctly |

## The clocks

| # | verdict | what happened |
|---|---|---|
| C41 | miss | **30** distinct pre-1993 timestamps, not fewer than 12 |
| C42 | hit | exactly **3** distinct 1979 timestamps over 15 records |
| C43 | hit | all 52 pre-1993 records live in **four directories** belonging to two strata |
| C44 | hit | **99.0622 %** even, against issue 11's 99.11 % |
| C45 | half | 27 odd records, well under 200. That they concentrate in the same folders as the impossible dates was **asserted and not measured per folder** |
| C46 | hit | **zero** records inside the 1 h 42 m 55 s mastering window |

## Paths, protection, executables

| # | verdict | what happened |
|---|---|---|
| C47 | hit | **145 DOS-shaped paths in the 70 executables**, inside the 30–400 called. Over the whole tree it is 1,281 |
| C48 | hit | four vendors' machines; the largest single root is `c:\watcom10.5` at 133 of 1,281 = 10.4 % |
| C49 | hit | drive `D` accounts for 1,031 of 1,281 |
| C50 | half | zero real hits and the control fires on all 75 — but the scanner **reported one**, `SETTEC`, and it is the middle of the Italian word *SETTECENTO* in `VILLE.EXE`. The clause said zero hits and there was one |
| C51 | hit | all MZ; ~38 NE16 with no PE; `DOS4GW.EXE` twice |

## Against CLIC 11

| # | verdict | what happened |
|---|---|---|
| C52 | hit | non-zero |
| C53 | hit | 3 matching hashes, 2 real, inside 1–40 |
| C54 | hit | both real crossings are third-party redistributables; **no file of the magazine's own crosses** |
| C55 | hit | no `.HTM` crosses. Nine basenames match and eight of them are coincidence |
| C56 | hit | the cell fills — and on measured shared *process*, not shared payload, with the rule's implicit clause made explicit |
| C57 | hit | Miles Software 1993-1995 against Adaptec 1997, and `TOAST 2.5 Partition` against `Toast 3.5.2 PPC HFS Optimizer` |

## Leftovers and the documents

| # | verdict | what happened |
|---|---|---|
| C58 | hit | **38** names, inside 20–200, and the spacing is regular at 3,332.5 bytes |
| C59 | miss | **0 absent**. All 38 are present, and the folder's 38 `.LBM` files are exactly the 38 the cache names |
| C60 | hit | **4,898,814 bytes, 1.0017 %** — inside both ranges |
| C61 | hit | **20 documents**, `00` through `19` |
| C62 | half | 41 hits called, **42** delivered; 10 halves called, 10 delivered; 11 misses called, 8 delivered; 69.4 % called, **75.81 %** delivered |

---

## What the misses have in common

Eight misses, and six of them are one error in two costumes.

**Three are ranges set from the wrong prior.** C19 (movie duration), C21 (AVI
duration) and C07 (`drCTFlSize`) were all estimated by dividing bytes by a
guessed bit rate or a guessed record size. Every one was wrong in the same
direction as the guess. 244 MB of video is 27 minutes and not 70 because Cinepak
at 240×180 costs about 1.2 Mbit/s, which is a number the disc states in its own
`avih` and which I did not look up before betting.

**Three are stories that fit.** C05 (padding repeats the previous file), C14
(five identical template forks) and C31 (`DEMO.DAT` is an attract-mode
recording) are all plausible mechanisms that explain the observation and are not
the observation. C05 was flagged in advance as the likeliest of these to fail
and it failed; the other two were not flagged and should have been, because they
have the same shape.

**One is inherited.** C06 believed the briefing's claim that
`hfs.parse_catalog()` returns two records. It does not, and the clause spent
itself defending a bug that was never there. Restating somebody else's
measurement inside a prediction is a way of scoring their error, not testing
mine.

**One is the good kind.** C59 bet that the Paint Shop Pro cache would name a
file that is no longer on the disc. It names 38 and all 38 are present — and
checking *why* produced the correction in [chapter 15](15-leftovers.md), where a
"snapshot before nineteen files arrived" story survived about a minute before
the directory turned out to hold exactly 38 `.LBM` files. **A miss that kills a
wrong story on its way out is worth more than a hit.**

## And the halves are where the interest is

Seven of the ten halves have the same structure: **the mechanism was called and
the specific consequence was not.** C17 is the clearest — the five resource
forks *are* files a Macintosh application opened, and the application is BBEdit,
and the reason they are those five is nothing to do with the tree's shape and
everything to do with the last hour before mastering. Getting the mechanism and
missing the consequence is what a half is for, and it is the most common outcome
in this branch across nine sessions.
