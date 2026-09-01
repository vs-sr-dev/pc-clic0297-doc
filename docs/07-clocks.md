# 07 — Five clocks: 99.06 % of this disc came through MS-DOS, and 52 records came through nothing

*Measure: 2,879 directory records, 1,605 distinct timestamps, spanning
1979-06-05 01:42:28 to 1997-02-14 17:03:32. **99.0622 % of the seconds fields
are even.** Fifty-two records predate 1993; all fifty-two live in four
directories belonging to two strata. Five independent clocks reconstruct the
week the disc was assembled, and no record falls in the hour and three quarters
the mastering took.*

```
python tools/iso9660.py CLIC.ISO --dates
python tools/hfs.py --image CLIC.ISO --mdb
```

---

## Clock A — the ISO directory records

```
records                        2879
distinct timestamps            1605
oldest                         1979-06-05 01:42:28
newest                         1997-02-14 17:03:32
timezone offsets present       {0: 2879}   -- every record, GMT+0
```

Every one of the 2,879 records carries a timezone byte of zero. On issue 11 that
was true too. Toast wrote GMT and nothing else.

### The even seconds, again

```
even seconds  2852 = 99.0622 %
odd seconds     27 =  0.9378 %
distinct second values present: 45 of 60
```

MS-DOS's FAT directory entry stores the seconds field in five bits, as a count
of **two-second units**. A timestamp that has passed through FAT cannot have an
odd seconds value. 99.0622 % of this disc's records have an even one.

Issue 11 measured **99.11 %** and concluded that its tree had come through a
FAT filesystem on the way to the Macintosh that mastered it. This disc, eight
months earlier, from the same publisher, with a different Toast version and a
completely different payload, gives 99.0622 %. Two independent measurements,
two hundredths of a percentage point apart.

This also closes a collection-wide question in its final form. Q9 asked whether
"even seconds" was a property of the *objects* or of the *filesystems they were
read from*. The previous session settled the negative half — NTFS mtimes read
from a downloaded game showed 138 even and 143 odd, all sixty values present.
Here the positive half is just as clear: these are not filesystem mtimes, they
are bytes inside the object, they were written by a Macintosh program, and they
are 99 % even **because the files reached that Macintosh from a PC**. The
evenness is a fossil of a filesystem the object passed through, and the reason
it survives is that ISO 9660 has a whole byte for seconds and copied a number
that only ever had half of one.

### The twenty-seven odd records

Twenty-seven records out of 2,879 have an odd seconds field, and they are not
scattered at random — they concentrate in the same directories as the impossible
dates below. A file that never touched a FAT volume keeps whatever second it was
given.

## Clock B — the HFS volume

```
created        1997-02-07 13:16:32
modified       1997-02-14 17:11:37
backup         (not set)
write count    5031
```

The Macintosh volume was created on **Friday 7 February 1997** and closed on
**Friday 14 February**. Seven days. `drWrCnt` says 5,031 writes.

## Clock C — the ISO descriptor

```
creation date      1997-02-14 18:54:32.00  GMT+0
modification date  1997-02-14 18:54:32.00  GMT+0
expiration         (unset)
root directory     1997-02-14 18:53:35
```

Creation and modification identical to the hundredth of a second; the root
directory record 57 seconds earlier. Issue 11's two descriptor fields were 37
seconds apart; here they are the same value written twice.

**Expiration is not set**, which makes six discs out of seven in this collection
with an empty expiration field and one — `pc-harrypotter4-doc` — that set it to
1981. See [chapter 17](17-open-questions.md), Q4.

## Clock D — a WS_FTP session log

`IMG/WS_FTP.LOG`, 75,089 bytes, 535 lines, shipped by mistake and therefore
also in [chapter 15](15-leftovers.md). Every line is one transfer:

```
97.02.10 12:07 B D:\Clic-cd\img\197ca001.jpg <-- www1.mondadori.com …
…
97.02.11 13:59 B D:\Clic-cd\img\orsay.jpg    <-- www1.mondadori.com …
```

535 files pulled **down** from `www1.mondadori.com` to `D:\Clic-cd\img\` between
**1997-02-10 12:07 and 1997-02-11 13:59**. The `IMG/` directory of this CD-ROM
was assembled by downloading the live website's own images off the publisher's
web server, over about twenty-six hours, three days before the master was cut.

## Clock E — a COFF timestamp

```
python tools/pecensus.py _work/iso

SETUPIE.EXE   PE32  16896  linker 4.00  1997-02-12 14:16:04  GLAMM Interactive
```

The only binary on the disc compiled by the people who made the disc: 16,896
bytes, built on **Wednesday 12 February 1997 at 14:16:04**, two days before
mastering. `AUTORUN.INF` names it and nothing else.

## The week, assembled

| when | clock | what |
|---|---|---|
| 1997-02-07 13:16:32 | B | the Toast project's HFS volume is created |
| 1997-02-10 12:07 → 02-11 13:59 | D | 535 images fetched from `www1.mondadori.com` |
| 1997-02-12 14:16:04 | E | `SETUPIE.EXE` compiled |
| 1997-02-12 15:16:04 / 15:16:32 | A | `SETUPIE.EXE` and `AUTORUN.INF` land on the volume |
| 1997-02-14 16:42:18 → 17:03:32 | A | the last five HTML pages saved from BBEdit ([chapter 06](06-associated-files.md)) |
| 1997-02-14 17:11:37 | B | the HFS volume is closed |
| 1997-02-14 18:54:32 | C | the ISO descriptor is written |

**The gap between the last two is 1 h 42 m 55 s, and not one directory record
falls inside it.**

```
records strictly inside the mastering window: 0
records dated 1997-02-14                    : 13
newest record                               : 1997-02-14 17:03:32
```

That is what a mastering run looks like from the inside: everything stops, the
program writes for an hour and three quarters, and the descriptor is stamped at
the end. Nothing was still being edited.

## The fifty-two records from before 1993

```
per year: 1979:15  1980:32  1981:4  1984:1  1993:4  1994:67  1995:176
          1996:1439  1997:1141
```

Fifty-two records predate 1993, **30 distinct timestamps**, and the whole point
is where they live:

| timestamp | count | directories |
|---|---:|---|
| 1979-06-05 01:42:28 | 1 | `/MUSEO` |
| 1979-06-05 06:11:52 | 1 | `/LEADER/CATALOGO/INFO` |
| 1979-06-05 06:14:44 | 13 | `/LEADER/CATALOGO/INFO`, `/MUSEO` |
| 1980-01-03 … 1980-01-04 (23 values) | 27 | `/MAGDEMO/HPICS`, `/MAGDEMO/IMOLA`, `/MAGDEMO/PICS`, `/MAGDEMO/TEXTURES` |
| 1981-02-05 (4 values) | 4 | `/MAGDEMO/HPICS` |
| 1984-05-28 19:39:00 | 1 | `/MAGDEMO/PICS` |

**Every impossible date on this disc is in one of four directories, and those
four directories belong to two strata**: the Musée d'Orsay demo (with eleven
`.WAV` files in Leader's catalogue) and the *Power F1* demo. Fifty-four other
directories have clean dates. This is not a broken clock somewhere in the
pipeline — it is two parcels that arrived with broken dates and fifty-four that
did not, which is [chapter 08](08-strata.md)'s argument in a different currency.

Two of the three groups are readable:

  * **1980-01-03 and 1980-01-04** are the second and third day of the **MS-DOS
    FAT epoch**, which begins 1980-01-01. Thirty-two records within 48 hours of
    the earliest value a FAT date can express is a machine whose clock was never
    set, booting and writing files with the BIOS default. Every one of them is
    in `MAGDEMO`.
  * **1979-06-05** is *before* the FAT epoch and cannot be a FAT date at all. It
    is the ISO 9660 record's own year byte, `4F` = 79, written literally.
    Fifteen records carry it across three distinct times, thirteen of them
    sharing `06:14:44` exactly. A single constant repeated thirteen times is a
    value, not a clock.
  * **1981-02-05** and **1984-05-28** are five records and no pattern. They are
    recorded and not explained.

The prediction here was that the pre-1993 dates would resolve to fewer than
twelve distinct values. They resolve to thirty, and the reason is that the
`MAGDEMO` group is a real spread of real times on a machine that thought it was
January 1980 — a wrong clock running correctly, not a constant.
