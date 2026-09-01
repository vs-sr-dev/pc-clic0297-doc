# 15 — Leftovers: 4,898,814 bytes, 1.0017 %, and twelve logs of the disc making itself

*Measure: this is not a list of mistakes made while writing this repository —
those are [chapter 19](19-corrections.md). It is what is **on the object that
should not be**, with a byte total and a share, by stratum. It comes to
4,898,814 bytes, **1.0017 %** of the 489,034,354 a PC can read. Issue 11 closed
at 3,813,223 bytes and 0.5766 %.*

---

## The total

| class | files | bytes | share |
|---|---:|---:|---:|
| redundant duplicate copies | 118 | 4,296,305 | 0.8785 % |
| build and session artefacts, named below | 14 | 853,439 | 0.1745 % |
| other `.BAK` / `.OLD` / `.TMP` / `.LOG` | 34 | 177,064 | 0.0362 % |
| *less the two counted twice* | | −427,994 | |
| **total** | | **4,898,814** | **1.0017 %** |

And, separately, **13,850,624 bytes — 2.8322 %** — that are not files at all:
the non-zero HFS allocation-block padding of [chapter 05](05-the-padding.md).
It is excluded from the total above because it is not something anybody put on
the disc; it is what the disc has instead of nothing.

## `PSPBRWSE.JBF` — somebody browsing a folder in 1996

127,800 bytes in `MAGDEMO/PICS/`. A **JASC Paint Shop Pro browser cache**: the
file Paint Shop Pro writes into a directory the moment somebody opens it in the
image browser, so the thumbnails are there next time.

```
python tools/jbf.py _work/iso/MAGDEMO/PICS/PSPBRWSE.JBF --against _work/iso/MAGDEMO/PICS
```

```
signature   : 'JASC BROWS FILE'
bytes 16-40 : 01 00 01 2F 00 00 00 63 3A 5C 44 66 31 5C 70 69 63 73 …
                                    c  :  \  D  f  1  \  p  i  c  s
names found : 38 distinct
  first at offset 1028, last at 124332, span 123304 bytes
  mean spacing 3332.5 bytes -- regular, so this is a record array
```

**The header names the directory it was made for: `c:\Df1\pics`** — the *Power
F1* demo's own build folder, on a Windows machine, on drive C.

The 38 names are recovered by pattern, and the pattern is narrow on purpose:
each 8.3 name is followed immediately by its own extension reversed
(`Waitscr.lbm` then `MBL`), and that tag is required and checked, because a
loose scan over 127 KB of thumbnail data finds byte sequences and invents files
that never existed.

The interesting question was whether the cache outlived its files — whether it
names images that are no longer on the disc. It does not, and the check is worth
more than the answer:

```
checked against _work/iso/MAGDEMO/PICS
  named and present : 38
  named and ABSENT  :  0
```

The directory holds 57 files and the cache names 38, which for one satisfying
minute looked like *a snapshot taken before nineteen more files arrived*. It is
not. The directory holds **exactly 38 `.LBM` files**, and the other nineteen are
`.BBM`, `.SHD`, `.BIF`, `.RST`, `DP_PREFS` and the cache itself. Paint Shop Pro
caches the format it reads and ignores the rest. **The cache is complete and the
story was wrong**, which is recorded here because it is exactly the shape of
error this branch keeps warning about: a number that supports a good story is the
number to check first.

What survives is still a reperto: **someone opened a folder of pictures on a PC
in 1996 to choose images, and the fact that they did was pressed onto every copy
of a national magazine.**

## Twelve FTP logs, and the disc assembling itself

Not one WS_FTP log but **twelve**, 884 transfers in total, one per directory the
operator downloaded into:

| log | lines | when |
|---|---:|---|
| `IMG/WS_FTP.LOG` | 535 | 97.02.10 12:07 → 97.02.11 13:59 |
| `NUMERI/CLIC297/POSTA/WS_FTP.LOG` | 104 | 97.02.11 09:00 → 09:01 |
| `NUMERI/CLIC297/INTERNET/WS_FTP.LOG` | 62 | 97.02.11 09:01 |
| `IMG/VOTI/WS_FTP.LOG` | 41 | 97.02.10 12:16 |
| `IMG/CLIC297/WS_FTP.LOG` | 36 | 97.02.10 12:07 → 12:08 |
| `IMG/CLIC11/WS_FTP.LOG` | 25 | 97.02.10 12:06 |
| `IMG/CLIC12/WS_FTP.LOG` | 21 | 97.02.10 12:06 |
| `NUMERI/CLIC297/PIAZZA/WS_FTP.LOG` | 21 | 97.02.11 09:00 → 12:28 |
| `NUMERI/CLIC297/EDICOLA/WS_FTP.LOG` | 19 | 97.02.11 12:08 |
| `NUMERI/CLIC297/COP/WS_FTP.LOG` | 12 | 97.02.11 09:02 |
| `IMG/CLIC10/WS_FTP.LOG` | 6 | 97.02.10 12:05 |
| `NUMERI/CLIC297/TECNICO/WS_FTP.LOG` | 2 | 97.02.11 08:59 |

Every line names the local path, the remote host `www1.mondadori.com`, and the
server-side directory
`/online/www/new_docs/periodici/specializzati/Clic/Cliccd/…`.

**This is the disc's own build log, kept by accident.** On Monday 10 February at
12:05 the operator started with the back issues — six files of issue 10, then
25 of issue 11, then 21 of issue 12 — moved to the current issue's images at
12:07, and to the review marks at 12:16. On Tuesday morning at 08:59 they came
back for the editorial pages, section by section: two files of `TECNICO`, then
104 letters in `POSTA`, then `PIAZZA`, `INTERNET`, `COP`, and finally `EDICOLA`
at 12:08. The last transfer of all is `ville.jpg` and `orsay.jpg` at 13:59 —
the two cover images for the two demos on the disc.

None of the twelve logs contains a user name or a password; WS_FTP's log format
has no field for either. They name a company's server and a company's directory
tree, so they are quoted ([chapter 13](13-paths.md)).

## Tomb Raider's build artefacts

| file | bytes | why it should not be here |
|---|---:|---|
| `LEADER/TOMB/TOMB.MAP` | 78,515 | a **Watcom linker map**: 2,279 lines naming every source file of a commercial game and the machine it was built on |
| `LEADER/TOMB/UPDATE.BAT` | 135 | a developer's own two-line script — `copy tomb.map c:\tombdemo` — which is *why* the map is here |
| `LEADER/TOMB/HMISET.BAK` | 227 | the backup of a sound-card configuration, differing from the live one in one line |
| `LEADER/TOMB/TOMB.LOG` | 0 | an empty log file, pointing at LBA 136 |
| `LEADER/DATA/CURRENT.PHD` | 352,678 | the game's runtime scratch level, byte-identical to `TITLE.PHD` |

`TOMB.MAP` is the single most consequential leftover on the disc: it is the only
reason this repository can state a build date for Tomb Raider
(`96/09/03 22:38:51`) and the only reason it can name Core Design's source tree.
A magazine gave that away with the cover price.

## `MAGDEMO`'s working directory

| file | bytes | what |
|---|---:|---|
| `MAGDEMO/IMOLA/IMOLA.CDF` | 215,842 | **ASCII track geometry**: `; From ram object ccube758, rom object ccube7581`, then thousands of `x,y,z ; Point n` triples. An intermediate export, not a shipped asset |
| `MAGDEMO/DP_PREFS` | 324 | an editor's preferences file |
| `MAGDEMO/PICS/DP_PREFS` | 324 | the same, again |
| `MAGDEMO/OBJECTS/TEMP.` | 1,939 | a file called `TEMP` with no extension |
| `MAGDEMO/OBJECTS/STATE.RST` | 460 | saved editor state |
| `MAGDEMO/IMOLA/IMOLA.CD2` | 0 | empty; the disc's other LBA-136 file |
| `MAGDEMO/OBJECTS/*.BAK`, `*.OLD` | 36,074 | nine backups of object files, including `FERRARI7.BAK` and `STARTLI.OLD` |

`MAGDEMO` is not a demo that was packaged. It is **a working directory that was
copied**, and the difference is visible in a dozen files nobody would ship on
purpose — plus the Paint Shop Pro cache and the pre-1993 timestamps of
[chapter 07](07-clocks.md).

## The 118 redundant copies

4,296,305 bytes, 0.8785 %, 101 groups. The biggest:

| bytes | copies | where |
|---:|---:|---|
| 353,152 | 2 | `CATALOGO/INFO/1003.WAV` and `626.WAV` |
| 352,678 | 2 | `DATA/CURRENT.PHD` and `TITLE.PHD` |
| 318,060 | 2 | `CATALOGO/IMAGES/100703.TIF` and `100704.TIF` |
| 235,704 | 2 | `VILLE/IMML/SAP3_2.TIF` and `SAP5_2.TIF` |
| 176,032 | 2 | `CATALOGO/TBDC.DLL` and `CATALOGO/SYSTEM/TBDC.DLL` |

Most of them are Leader's catalogue giving two product codes the same asset —
two products sharing one voice-over or one box shot, which is a database
pointing twice at the same content and then the content being written twice.
Only a handful are libraries duplicated across strata: `TBDC.DLL` twice inside
one folder tree, and `PCDLIB.DLL`/`PCDXBMP.DLL` shared between `LEADER/CATALOGO`
and `VILLE`.

## What is *not* counted as a leftover

  * **Two ToolBook runtimes** (3.0 and 4.0) and **two QuickTime installers**
    (16- and 32-bit). Each is needed by the stratum that ships it
    ([chapter 08](08-strata.md)). They are evidence of no coordination, not of
    waste.
  * **The 302 zero sectors at the end of the image.** They belong to whoever made
    the image, not to the disc ([chapter 01](01-provenance.md)).
  * **The 13,850,624 bytes of non-zero padding.** Reported separately above,
    because calling it a leftover implies somebody left it, and nobody did.
