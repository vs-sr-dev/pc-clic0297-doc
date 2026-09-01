# 09 — Tomb Raider: all sixteen levels, half the cut scenes, none of the film

*Measure: 46 files, 47,619,223 bytes, 9.7374 % of the disc. Twenty `.PHD`
records and nineteen distinct files. Sixteen of the sixteen retail level names
are present; two of the four cut scenes are; there is no FMV and there is no
music, and there cannot be, because this is one data track. The build date is
inside a linker map the game was not supposed to ship.*

```
ls -l _work/iso/LEADER/DATA _work/iso/LEADER/TOMB
sha1sum _work/iso/LEADER/DATA/*.PHD
```

---

## What is here

`/LEADER/DATA/` — 26 files, 45,870,780 bytes:

| | |
|---|---|
| level files | `GYM`, `LEVEL1`, `LEVEL2`, `LEVEL3A`, `LEVEL3B`, `LEVEL4`, `LEVEL5`, `LEVEL6`, `LEVEL7A`, `LEVEL7B`, `LEVEL8A`, `LEVEL8B`, `LEVEL8C`, `LEVEL10A`, `LEVEL10B`, `LEVEL10C` — **16** |
| cut scenes | `CUT1.PHD`, `CUT2.PHD` — **2** |
| interface | `TITLE.PHD`, `CURRENT.PHD` — **2**, and they are the same file |
| scripts | `CUT1.CIN`, `CUT2.CIN`, `LEVEL3B.CIN`, `LEVEL6.CIN` |
| art | `TITLE.PCX` (46,591), `TITLEH.PCX` (218,489) |

`/LEADER/TOMB/` — 20 files, 1,748,443 bytes: `TOMB.EXE` (462,165), `DOS4GW.EXE`
(265,396), `SETUP.EXE` (188,279), `TEST.EXE` (147,114), the three HMI `.386`
drivers, `TOMB.MAP` (78,515), `DEMO.DAT` (628), `TOMB.LOG` (0), two batch files,
two instrument banks and the HMI configuration pair.

## Sixteen of sixteen

The retail Tomb Raider level set is sixteen playable levels — a training level
and fifteen game levels, numbered with the 3A/3B, 7A/7B, 8A/8B/8C and
10A/10B/10C splits that the naming above reproduces exactly. **All sixteen names
are present, none is missing, and the numbering has no gaps.**

This is not a one-level demo. 45.87 MB of level data is the game's level data.

## And two of four cut scenes

Four `CUT` levels ship with the retail game. Two are here — `CUT1` and `CUT2` —
and `CUT3` and `CUT4` are absent. Two of the four `.CIN` camera scripts are also
absent for the same reason.

That is the first of the three things missing, and it is the smallest.

## What is missing, and it is bigger than what is here

**No FMV.** The retail product's full-motion sequences are `.RPL` files in an
`FMV` directory. There is no `.RPL` file anywhere in this image and no `FMV`
directory:

```
python tools/census.py _work/iso     # 46 extensions; .rpl is not among them
```

**No music.** Tomb Raider's score is Red Book audio — CD tracks, not files. This
image is a single data track of 248,359 sectors with no track descriptor of any
kind, so the music cannot be here in any form. What *is* here is the MIDI side:
`DRUM.BNK` and `MELODIC.BNK`, the HMI instrument banks, 5,404 bytes each.

**Two cut scenes.**

So: **the whole of the game's geometry and none of its film.** Whether the
result is playable is not measurable without running it, which this repository
does not do, and so it is not claimed either way.

## `CURRENT.PHD` is `TITLE.PHD`

```
300cf18522bce3028cb1ac83caefaf3d066083bb  DATA/CURRENT.PHD
300cf18522bce3028cb1ac83caefaf3d066083bb  DATA/TITLE.PHD
```

Both 352,678 bytes, identical sha1. Twenty `.PHD` records, **nineteen distinct
files**. `CURRENT.PHD` is the game's scratch copy of whatever level is loaded,
shipped with the title screen still in it — a runtime artefact that got onto the
master. It is in [chapter 15](15-leftovers.md).

## The format, as far as the bytes go

`.PHD` is Core Design's and is not documented by them. **No third-party
implementation was consulted and none is needed for what is claimed here**,
which is only this:

```
CURRENT.PHD   20 00 00 00 04 00 00 00 43 43 43 02 …
LEVEL1.PHD    20 00 00 00 0b 00 00 00 f3 f3 d8 f1 …
LEVEL8A.PHD   20 00 00 00 0e 00 00 00 a8 a9 a9 a9 …
```

  * the first four bytes are `20 00 00 00` — 32 as a little-endian 32-bit
    integer — on **all twenty files without exception**;
  * the second four bytes vary, taking eight distinct values between 4 and 14;
  * what follows is byte-triples in the range `00`–`3F`, which is the shape of a
    six-bit VGA palette, and that is an observation about the numbers rather
    than a claim about the format.

Everything past byte 8 is **declared not derived**.

## The build date, in a file that should not be here

`TOMB.MAP`, 78,515 bytes, is a **Watcom linker map**:

```
WATCOM Linker Version 10.6
Copyright by WATCOM International Corp. 1985, 1996. All rights reserved.
Created on:       96/09/03 22:38:51
Executable Image: tomb.exe
creating a DOS/4G executable
```

**3 September 1996 at 22:38:51** — a build timestamp for Tomb Raider, from the
linker that made it, on a magazine cover disc. And 2,279 lines of it are the
module table:

```
Module: INPUT.OBJ(C:\CCODE\TOMBRAID\specific\input.c)
Module: BAT.OBJ(C:\CCODE\TOMBRAID\GAME\bat.c)
Module: CAMERA.OBJ(C:\CCODE\TOMBRAID\GAME\camera.c)
Module: CINEMA.OBJ(C:\CCODE\TOMBRAID\GAME\cinema.c)
Module: COLLIDE.OBJ(C:\CCODE\TOMBRAID\GAME\collide.c)
Module: CROC.OBJ(C:\CCODE\TOMBRAID\GAME\croc.c)
Module: DINO.OBJ(C:\CCODE\TOMBRAID\GAME\dino.c)
…
```

**The source tree of Tomb Raider, on the machine that built it**, split into
`GAME\` for the portable code and `specific\` for the platform layer, with one
object file per creature. It carries 133 of the disc's 1,281 absolute paths
single-handedly, most of them `c:\watcom10.5\…` library references
([chapter 13](13-paths.md)).

## What the small files say

**`TOMB.LOG` is zero bytes**, and its directory record points at LBA 136, one of
the two sectors on this disc that belong to nobody ([chapter 04](04-two-catalogues.md)).

**`DEMO.DAT` is 628 bytes and every one of them is zero.** The expectation was an
attract-mode input recording; it is an empty file with a name.

**`INSTALL.BAT` and `UPDATE.BAT` disagree about where the game goes:**

```
INSTALL.BAT:  md c:\tombraid  /  copy *.* c:\tombraid
              echo Type 'setup' to setup sound, 'tomb' to run demo

UPDATE.BAT:   echo  Updating New TombRaider executable
              copy tomb.exe c:\tombdemo
              copy tomb.map c:\tombdemo
```

One installs to `c:\tombraid`, the other patches `c:\tombdemo`. `UPDATE.BAT` is
not an installer at all — it is a developer's own two-line script for dropping a
fresh build over a test copy, and it shipped. It is what put `tomb.map` on the
disc: the map file is on the CD **because a build script copied it next to the
executable**, and nobody removed either.

**`HMISET.CFG` and `HMISET.BAK` are somebody's sound card.**

```
CFG line 3:  DeviceName  = Sound Blaster
BAK line 3:  DeviceName  = Sound Blaster Pro
```

Identical but for that line. Somebody ran `SETUP.EXE`, chose *Sound Blaster
Pro*, ran it again, chose *Sound Blaster*, and both the answer and the backup of
the previous answer were pressed onto the disc, along with `DeviceIRQ = 5`,
`DeviceDMA = 1`, `DevicePort = 0x220` — the hardware configuration of one PC in
1996.

`SETUP.INI` is the HMI setup utility's device table, 18 sound cards deep, from
`Sound Blaster` to `NewMedia .WAVJammer` and `I/O Magic Tempo`.

## Why it is on this disc at all

Because it is a product in the catalogue that shares the disc with it.

```
GAMES.DBF, record: TITOLO 'Tomb Raider'  CODICE '100742'  EDITORE 'Eidos'
                   GENERE 'Avventura'    PRPUB 99900  PRRIV 64500  DEMO 'Si'
```

Product **100742**, published by Eidos, 99,900 lire retail and 64,500 lire
trade, with a box shot at `CATALOGO/IMAGES/100742.TIF`, a spoken description at
`CATALOGO/INFO/100742.WAV` and its system requirements at
`CATALOGO/REQUISIT/100742.TXT`.

**It is the only one of 221 products in the catalogue whose `DEMO` field is set.**
The mail-order catalogue on this disc advertises exactly one playable
demonstration, and that demonstration is sitting two directories away. The disc
closes on itself.
