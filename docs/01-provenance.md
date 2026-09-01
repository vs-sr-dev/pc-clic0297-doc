# 01 — Provenance: an image of a disc, and nine parcels that never met

*Measure: everything in this chapter comes from `CLIC.ISO`, a 509,257,728-byte
file on a local hard disk, sha1 `ee3c2b6f7e16a178d4dd9093cdfe44ae007efca9`. It
is not a disc. The distinction runs through every sentence below and is stated
first because it limits what this repository is allowed to claim.*

---

## What the object is

A CD-ROM bound into an Italian computer magazine called **CLIC!**, published by
**Mondadori Informatica S.p.A.**, with the CD-ROM produced by **GLAMM
Interactive s.r.l.** of Milan. The ISO 9660 volume descriptor was written on
**14 February 1997 at 18:54:32 GMT**. Half a gigabyte, 2,818 files a PC can
see, and nine separately-assembled bodies of software that have nothing to do
with one another.

It is the second CLIC disc measured here. The first,
[`pc-clic11-doc`](https://github.com/vs-sr-dev/pc-clic11-doc), is issue 11 from
the following October. That makes this the first time two objects from the same
publication have been measurable against each other, and
[chapter 14](14-against-clic11.md) is what that produced.

## Which issue is it? The disc says, and the briefing said it does not

The volume identifier is `CLIC` — no number, no date. Issue 11's said `CLIC_11`.
The session briefing concluded from this that *the name of a directory,
`NUMERI/CLIC297/`, is the only thing on this disc that says which issue this
is.*

That is wrong, and the file that refutes it is 2,433 bytes at the root:

```
python tools/iso9660.py CLIC.ISO --extract _work/iso --only LEGGIMI
```

`/LEGGIMI.TXT` — *readme* — opens:

> **Clic! Cd-rom di Marzo**
> Il Cd-rom Contiene: Il sito di "Clic! On line" di Febbraio con le pagelle di
> tutti i numeri precedenti

**The disc is the March 1997 cover disc, and it carries the February website.**
That is why the directory is called `CLIC297` — 2/97 is the *content*, not the
issue. The same file dates itself again by advertising a trade show:
*«al FuturShow dal 9 al 13 aprile a Bologna»* — an April event, which nobody
promotes on a February disc.

So the object has two defensible names and they are eight weeks apart. This
repository calls it **CLIC 02/97** because that is what its own directory says
and what the collection's index will sort on, and records here that the disc
itself calls the *product* March and the *contents* February. The index row
argues it in the cell rather than picking silently.

## It is an image, and that costs three measurements

Nine previous sessions in this branch read a physical disc in a physical drive.
This one did not, and the difference is not cosmetic:

| measurable from a drive | measurable here |
|---|---|
| lead-out LBA from `READ TOC` | no |
| the sectors past the volume space | no |
| subchannel, session layout, track count | no |
| the drive's maximum transfer | no |

What *is* here is a 302-sector tail — 618,496 bytes, every one of them zero —
between the end of the declared volume space (248,359 sectors) and the end of
the file (248,661 sectors). **That number is a property of whoever made this
image, not of the disc.** Issue 11 measured 152 sectors of lead-out with a
command sent to a drive; 302 is a subtraction between two numbers in a file.
They are not the same measurement and they do not belong in the same table. See
[chapter 17](17-open-questions.md), Q1 and Q2, which are closed here as *not
applicable* rather than repeated.

## Nobody organised this disc

The temptation, having found nine top-level directories holding nine unrelated
products, is to write that the disc *is organised into nine sections*. It is
not. It is nine parcels that arrived from nine places and were copied into nine
folders by people with a deadline, and the only coherence on the object is the
coherence of the program that wrote it.

The evidence for that reading is in the bytes rather than in the impression:

  * **Nine strata, six vendors, no shared toolchain.** Two different versions of
    the same authoring runtime ship in two different folders because two
    different suppliers each brought their own ([chapter 08](08-strata.md)).
  * **Fifty-two directory records are dated before 1993**, one of them 1979, and
    every single one of them lives in one of four directories belonging to two
    strata ([chapter 07](07-clocks.md)). A disc assembled by one process would
    not have two folders with a broken clock and fifty-four without.
  * **The magazine made 0.82 % of its own disc** — 1.997 % if the promotional
    image folder is counted as its own, which is itself a decision rather than a
    fact ([chapter 12](12-producers.md)).
  * **A retailer's mail-order catalogue is 72.4342 % of the file bytes**, and
    half the object by weight is that catalogue's video trailers for other
    companies' games ([chapter 10](10-leader.md)).

The right question is not whether the disc is coherent. It is **how
heterogeneous it is, and whether that is readable from the bytes**. It is, and
the number is nine.

## The five clocks, and the production week they describe

Five independent time sources agree on one week in February 1997, and together
they reconstruct the assembly of the object almost hour by hour
([chapter 07](07-clocks.md)):

| when | what | where it is written |
|---|---|---|
| 1997-02-07 13:16:32 | the HFS volume is created | `drCrDate` in the Master Directory Block |
| 1997-02-10 12:07 → 02-11 13:59 | 535 image files are pulled off `www1.mondadori.com` by FTP | `IMG/WS_FTP.LOG` |
| 1997-02-12 14:16:04 | the disc's launcher is compiled | COFF timestamp in `SETUPIE.EXE` |
| 1997-02-14 16:42:18 → 17:03:32 | the last five HTML pages are saved from BBEdit | ISO directory records + their resource forks |
| 1997-02-14 17:11:37 | the HFS volume is closed | `drLsMod` |
| 1997-02-14 18:54:32 | the ISO descriptor is written | primary volume descriptor |

**No directory record on the disc falls inside the 1 h 42 m 55 s between the
last two.** That gap is the mastering run itself, and it is empty because
nothing was still being edited while Toast was writing.

## What is on it

| stratum | files | bytes | share | what it is |
|---|---:|---:|---:|---|
| `LEADER/CATALOGO` | 715 | 354,228,172 | 72.4342 % | Leader's mail-order games catalogue, in ToolBook and Director, with 35 video trailers |
| `VILLE` | 364 | 51,595,303 | 10.5504 % | *Ville Venete*, an architecture title, ToolBook 4.0 |
| `LEADER/DATA` + `LEADER/TOMB` | 46 | 47,619,223 | 9.7374 % | **Tomb Raider**, the whole level set ([chapter 09](09-tombraider.md)) |
| `MAGDEMO` | 584 | 10,839,135 | 2.2164 % | *Power F1*, a DOS/4GW racing demo |
| `IMG` | 511 | 5,753,408 | 1.1765 % | the website's images, fetched by FTP four days before mastering |
| `DOWN` | 1 | 5,585,256 | 1.1421 % | Internet Explorer 3.01, one self-extracting archive |
| `MUSEO` | 4 | 5,212,705 | 1.0659 % | a Musée d'Orsay demo, Director |
| `LEADER/QTW` | 2 | 3,102,720 | 0.6345 % | QuickTime for Windows, 16- and 32-bit installers |
| `NUMERI`+`PAG`+`RETE`+`PRE`+root | 573 | 4,012,668 | 0.8205 % | the magazine itself |

Nine parcels. One of them is a complete commercial game; one is 354 MB of a
shop's catalogue; one is the magazine. **The magazine is the smallest thing on
its own disc.**

## And it contains its readers

`NUMERI/CLIC297/POSTA/` is 104 files of letters to the editor and
`NUMERI/CLIC297/PIAZZA/CAFE.HTM` is 24,440 bytes of readers' small ads. Between
them and sixteen other files sit **45 distinct e-mail addresses and 74
telephone and fax numbers**, some belonging to companies and some belonging to
teenagers who in February 1997 wrote to a magazine hoping to swap floppy disks.

This repository counts those and does not transcribe them. Recipients that
belong to an organisation — `GLAMM Interactive s.r.l., V.le Corsica n.7, 20133
Milano`, published in `/GLAMM.HTM` to be read by anyone who bought the magazine
— are quoted like any other string of the object. Recipients that belong to a
person are counted. The rule and its application are in
[chapter 12](12-producers.md); the tools that were pointed away from those two
directories are named in [chapter 16](16-tools.md).
