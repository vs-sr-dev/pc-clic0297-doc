# 13 — Absolute paths: 1,281 of them, three machines, and a heuristic that reads Cinepak as Macintosh

*Measure: `buildpaths.py` run unmodified over all 2,816 readable files,
489,034,354 bytes. **1,281 DOS-shaped paths, 857 distinct, in 81 files.** The
248 "Macintosh-shaped" hits are almost entirely false positives from compressed
video and audio, and this chapter says so rather than adding them to a total.*

```
python tools/buildpaths.py _work/iso
```

---

## The number, against the series

| year | object | absolute paths |
|---|---|---:|
| 1990 | Mega Man | 0 |
| 1992/94 | Lands of Lore | 0 in the shipped executables |
| 1994 | Sam & Max | 34, of which 1 build machine |
| 1997 | **CLIC 02/97** | **1,281** |
| 1997 | CLIC 11 | 280 |
| 2000 | Final Fantasy VIII | 31,737 |
| 2014 | Tesla Effect | 101, of five vendors |
| 2026 | Allods Online | 2,002, from 21 build roots |

**This is the most path-leaking object in the collection that is not a modern
game**, and it beats the other disc from the same magazine by 4.6×. The reason
is not that 1997 was leakier than October 1997. It is that this disc carries two
files that are *made of* paths.

## Where they are

| carrier | hits | what it is |
|---|---:|---|
| `LEADER/TOMB/TOMB.MAP` | 133 | a Watcom linker map |
| `IMG/WS_FTP.LOG` | 102 | an FTP session log |
| `LEADER/CATALOGO/MTB30BAS.DLL` | 80 | Asymetrix's ToolBook, with `__FILE__` left in |
| `LEADER/CATALOGO/MTB30UTL.DLL` | 5 | the same |
| `MUSEO/MAIN.DIR` | 4 | a Director movie |
| `MUSEO/ORSAY.EXE` | 4 | its projector |

Eighty-one files carry at least one. Two of them carry a fifth of the total, and
neither is a program: one is a build artefact and one is a network log.

## Three project roots, three organisations, three cities

```
by volume / drive letter:  D 1031 · C 245 · F 2 · M 1 · G 1 · J 1
```

| root | hits | whose machine |
|---|---:|---|
| `c:\watcom10.5\…` | 133 | **Core Design**, Derby — the compiler's own library tree, referenced by `TOMB.MAP` |
| `c:\ccode\tombraid\…` | (in the 857 distinct) | **Core Design** — the source tree of Tomb Raider |
| `d:\clic-cd\img\…` | 102 | **the magazine**, Milan — the CD-ROM being assembled |
| `d:\hook\src\…` | 85 | **Asymetrix**, Bellevue — ToolBook's source tree, project codename `hook` |
| `c:\windows\…` | 8 | nobody's; system DLL references |
| `C:\WINDOWS\Desktop\Orsay`, `C:\WINDOWS\Desktop\D` | 8 | **the Orsay supplier** — somebody's *desktop* |

**Four vendors' build machines on one disc**, which is what nine unrelated
parcels produces, and the prediction that no single machine would account for
more than half holds: the largest is `c:\watcom10.5` at 133 of 1,281, 10.4 %.

`D` beats `C` 1,031 to 245 because the two biggest carriers both worked on a
second drive.

## What each one is

**`TOMB.MAP`** — 78,515 bytes, 2,279 lines, a Watcom Linker 10.6 map created
`96/09/03 22:38:51`. Its module table is the source tree of a commercial game:

```
Module: CAMERA.OBJ(C:\CCODE\TOMBRAID\GAME\camera.c)
Module: COLLIDE.OBJ(C:\CCODE\TOMBRAID\GAME\collide.c)
Module: CROC.OBJ(C:\CCODE\TOMBRAID\GAME\croc.c)
Module: DINO.OBJ(C:\CCODE\TOMBRAID\GAME\dino.c)
Module: INPUT.OBJ(C:\CCODE\TOMBRAID\specific\input.c)
```

`GAME\` for the portable code and `specific\` for the platform layer, one object
file per creature. `UPDATE.BAT` in the same directory explains how it got here:
`copy tomb.map c:\tombdemo` — a developer's own script, shipped
([chapter 09](09-tombraider.md)).

**`IMG/WS_FTP.LOG`** — 75,089 bytes, 535 lines, one per transfer:

```
97.02.10 12:07 B D:\Clic-cd\img\197ca001.jpg <-- www1.mondadori.com
                 /online/www/new_docs/periodici/specializzati/Clic/Cliccd/img/clic197
```

The local path, the remote host, and **the full server-side directory tree of
Mondadori's website** — `/online/www/new_docs/periodici/specializzati/Clic/`.
This is the only file on the disc that names a machine belonging to the
publisher, and it names its filesystem layout. It is an organisation's
infrastructure, not a person's, so it is quoted; the log records no user name
and no password, because WS_FTP's log format has no field for either.

**`MTB30BAS.DLL`** — 85 paths of the form `d:\hook\src\memory\heap.c`,
`…\block.c`, `…\arena.c`, `…\cdbheap.c`, `…\gdimgr\tbkf1.c`. These are
`__FILE__` strings from assertion macros left in a shipped release build.
Asymetrix's internal name for Multimedia ToolBook was apparently `hook`, and the
same strings are in the ToolBook 4.0 DLLs in `VILLE/`.

**`C:\WINDOWS\Desktop\Orsay`** — four occurrences in `MUSEO/MAIN.DIR` and four
more in `MUSEO/ORSAY.EXE`. Somebody built a Director project **on their Windows
95 desktop**, in a folder called `Orsay`, and Director wrote the path into the
movie. `C:\WINDOWS\Desktop\D` is the same person, one directory over.

## The 248 Macintosh-shaped hits are noise

`buildpaths.py` looks for two shapes, and the Macintosh one —
`Volume:Folder:File`, colon-separated, no leading slash — is far looser than a
drive letter. On issue 11 it found 188 hits and they were real. Here it finds
248 and they are not:

```
   15  AJAJU:U:EQEQ                    LEADER/CATALOGO/TRYOUT/GULL.MOV
    3  AU:U:EQEQ                       LEADER/CATALOGO/TRYOUT/GULL.MOV
    2  DD:IDDI:DD:IDDS:DD:IDD          LEADER/CATALOGO/TRYOUT/CASPER.MOV
    1  ImD:IDDIIDDS2_D:2DDS:DD:IDDS2DD2:__   LEADER/CATALOGO/TRYOUT/CASPER.MOV
    1  QqE:Z:qQ                        LEADER/CATALOGO/TRYOUT/3DBODY.MOV
    1  UOIB:6:CEHR                     LEADER/CATALOGO/INFO/100600.WAV
```

Cinepak keyframe data and 8-bit PCM contain long runs of upper-case ASCII with
colons in them, and 244 MB of Cinepak will produce a few hundred of anything.
The tool's own summary betrays it: its "by volume" table lists `AJAJU` as the
most common volume name on the disc, 44 times.

**Two of the 248 are real and neither is a path:**

  * `DATE:Thu Jan 23 18:19:32 1997` in `IMG/CLIC297.MAP` — a sixth clock,
    three weeks before mastering;
  * `LINEXE: Using DOS:Extended Startup Conditions...` in both copies of
    `DOS4GW.EXE` — a diagnostic message.

So the headline is **1,281**, the DOS figure, and the Macintosh figure is
reported as a measurement of the heuristic rather than of the disc. The tool was
run **unmodified**, as the series requires, and the honest thing to do with its
output is not to add it up but to look at it.

That is also the answer to a question this disc could have got wrong: with no
Macintosh payload at all ([chapter 03](03-file-count.md)), **the true count of
Macintosh build paths on this hybrid is zero**, and a total of 1,529 would have
buried that under noise.
