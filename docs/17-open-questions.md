# 17 — Open questions: six this disc raised, three it cannot touch, and four it closed

*Measure: each entry says what was measured, what it did not settle, and the
command that would settle it. An entry with no such command does not belong
here.*

---

## Closed as not applicable, from `pc-clic11-doc/docs/21-open-questions.md`

Three inherited questions need a drive. **There is no drive this session**: the
object is a file on a hard disk ([chapter 01](01-provenance.md)). They are
closed here as not applicable rather than repeated, and each gets its line.

**Q1 of issue 11 — is the 152 Toast's, or the Apple partition map's?** It needed
a non-hybrid Toast disc or a non-Toast hybrid, **read from a drive**. This is
Toast *and* hybrid *and* an image. **Not applicable.** What is recorded instead:
this image is **302 sectors longer** than its declared volume space and all 302
are zero. That number is a property of whoever dumped the disc. The day somebody
reads this disc physically, **the difference between 302 and what `READ TOC`
says is itself the measurement** — and it is worth taking, because 152 was the
same on two discs and 302 is a different number entirely.

**Q2 of issue 11 — what is in the 152 sectors?** Not applicable: no disc, no
sectors past the image.

**Q3 of issue 11 — the drive's maximum transfer.** Not applicable: no drive.
Open for eight sessions now, and still not this session's fault. It is a
property of a driver, not of any object, and it costs ten minutes of drive time
that nobody has yet been willing to spend.

---

## Q1 — Which "11" is `CLIC_11`?

**Measured.** This disc's back-issue archive numbers issues **4, 6, 7, 9, 10,
11, 12** and then switches to month-and-year — `197` for January 1997, `297` for
February 1997 — so issue 12 is December 1996 and **issue 11 is November 1996**.
It carries 22 review pages in `PAG/11*.HTM` and 25 images in `IMG/CLIC11/`,
fetched from `…/Cliccd/img/clic11` on 1997-02-10 at 12:06.

`pc-clic11-doc`'s volume identifier is `CLIC_11` and it was mastered
**1997-10-20**, eight months later. None of the 25 images crosses.

**Not settled.** Either the magazine returned to sequential numbering after the
month-and-year experiment, or `CLIC_11` counts CD-ROMs rather than issues, or it
is a second series. Two objects cannot separate those.

**What would settle it**: a third CLIC disc, or either disc's own `SOMMARIO` or
cover page naming a month. Issue 11's own HTML contains one month word in the
whole tree (`maggio`, once) and no issue number, so it is not there.

    grep -rhoiE "gennaio|febbraio|…|dicembre" ../pc-clic11-doc/_work/iso

Until then, this repository calls its own object **CLIC 02/97** on the strength
of `NUMERI/CLIC297/` and `/LEGGIMI.TXT`, and treats `CLIC_11` as a label whose
unit is unknown.

## Q2 — Where did 13.85 MB of somebody's memory come from?

**Measured.** Every one of the 6,763 padding sectors between the ISO extent and
the HFS allocation block is non-zero, none repeats its own file's tail, and of
39 sampled probes **17 appear nowhere else in the image**
([chapter 05](05-the-padding.md)). One region holds a fax cover-sheet template
that is on no file of this disc.

**Not settled.** Whether the residue is Toast's read buffer, the Macintosh's
free memory, or blocks of the source volume that the CD writer picked up is not
decidable from 39 probes.

**What would settle it**, and it is cheap:

    python tools/slackorigin.py CLIC.ISO --sample 400 --probe 64

A census rather than a sample, with a longer probe, plus a check of whether the
*same* residue appears in several padding regions in sequence — which would mean
a buffer being reused — or only once each, which would mean a scan of a disk.

## Q3 — Do 11,127 Hz and 22,222.22 Hz have the same cause?

**Measured.** Twelve `.WAV` files on this disc declare a sample rate of
**11,127 Hz**, which is not a standard rate and is not 11,025
([chapter 11](11-media.md)). `pc-landsoflore-doc` found 5,508 files at
**22,222.22 Hz** and showed that the rate was a one-byte time constant the
format could not express otherwise.

**Not settled.** These twelve are RIFF WAVE, which *can* express 11,025 exactly,
so the odd rate was not forced by the container. It was carried in from
somewhere.

**What would settle it**: the twelve files' provenance. They are in
`LEADER/CATALOGO/INFO/`, so:

    python tools/audio.py _work/iso/LEADER/CATALOGO/INFO --wav

and a check of whether the twelve share a directory-record date with each other
and not with the other 181.

## Q4 — The 1981 expiration date

**One more data point, no answer.** This disc's expiration field is sixteen zero
bytes. That makes **six discs of seven** with no expiration and one —
`pc-harrypotter4-doc` — that set it to 1981.

**What would settle it**: a second disc with a non-empty expiration date. Until
one turns up, 1981 is a single observation and the question is whether it is a
value or an artefact. Carried forward unchanged from issue 11.

## Q5 — Is non-zero slack normal for Toast, or normal for 1997?

**Measured, twice, on this disc.** Whole-sector padding: **6,763 of 6,763
non-zero**. Intra-sector slack, measured by the inherited `slack.py` on a region
it was written for: **2,820 files of 2,821 with a dirty tail**, 82.09 % of
3,254,392 bytes.

**Not settled.** One disc. Issue 11 was never asked this question, and its image
is on the same machine.

**What would settle it**, in one command:

    python tools/slack.py --image ../pc-clic11-doc/_work/clic11.img

If Toast 3.5.2 zeroes its buffer and Toast 2.5 does not, that is a change in one
program between February and October 1997 and it dates itself. If both are
dirty, it is a property of the program; if neither is unusual against the
collection's non-Toast discs, it is a property of 1997. **This is the cheapest
open question in this chapter and it was left undone for time.**

## Q6 — What is `MUSEO/MAIN.DIR` made of?

**Measured.** 3,468,344 bytes, magic `52 49 46 58` = `RIFX`, a Macromedia
Director movie, directory-record date **1979-06-05 01:42:28**, and it names
`C:\WINDOWS\Desktop\Orsay` four times ([chapter 13](13-paths.md)).

**Not settled.** Its chunk map was never walked, so this repository can say what
it is and not what is in it. `director.py` is inherited, applies, and was not run
([chapter 16](16-tools.md)).

    python tools/director.py _work/iso/MUSEO/MAIN.DIR --map

## Q7 — Why is `IMOLA.CDF` on the disc in ASCII?

**Measured.** 215,842 bytes of plain text, opening `; From ram object ccube758,
rom object ccube7581`, then thousands of `x,y,z ; Point n` triples — track
geometry for the *Power F1* demo, in a human-readable intermediate format,
alongside `IMOLA.BZP` and `IMOLA.LZP` which are the compressed forms.

**Not settled.** Whether the game reads the `.CDF` at runtime or whether it is an
export that was never removed. If it is the latter it is a leftover and belongs
in [chapter 15](15-leftovers.md)'s total, which would rise by 215,842 bytes to
1.0458 %.

**What would settle it**: whether `F1.EXE` contains the string `CDF` or `IMOLA.CDF`.

    python tools/buildpaths.py _work/iso/MAGDEMO   # and a string search of F1.EXE

## Q8 — Sixty-nine `.HLP` files of 592 bytes mean

**Measured, and not looked at.** `MAGDEMO/HELPE`, `HELPF`, `HELPG`, `HELPI` hold
17 files each — English, French, German, Italian — totalling 40,895 bytes, mean
592. Four parallel language trees on a disc that is otherwise entirely Italian.

**Not settled.** Whether they are the same file translated four times, and what
a translation costs in this format, which is the measurement
`pc-landsoflore-doc` made on `.PAK` archives and got 0.739 %.

    python tools/dircensus.py _work/iso/MAGDEMO   # then diff the four trees

## Q9 — Fifty-six tools that would run here and did not

`toolclass.py` puts **56 of 158** in "inherited, applicable, not needed" — 35.4 %
of the apparatus. Issue 11's equivalent class was 44 and it called the list a
debt. It is a bigger debt here because this disc has nine strata and four of them
were characterised only by size and toolchain.

The four that would pay best are named in [chapter 16](16-tools.md): `rsrc.py`
on two multi-megabyte resource trees, `director.py` on the one `.DIR`,
`encodinghunt.py` on 549 Italian HTML files whose encoding nobody checked, and
the four producer tools written for issue 11 and unused here.

---

## What this disc closed

  * **Q6 of issue 11 — does the Macintosh side of two hybrids cross?**
    Answered **zero, structurally**: this hybrid has no Macintosh side to cross,
    and the three named candidate files are absent
    ([chapter 14](14-against-clic11.md)).
  * **The two-catalogue ownership map**, which issue 11 wanted and could not
    build. It closes at **two unowned sectors of 248,359**, both zero
    ([chapter 04](04-two-catalogues.md)).
  * **Q9 of the collection — the even seconds.** The previous session closed the
    negative half on NTFS mtimes. This disc closes the positive half: 99.0622 %
    even against issue 11's 99.11 %, on directory-record bytes written by a
    Macintosh program, which makes the evenness a fossil of a filesystem the
    files passed through rather than a property of the object or of the reader
    ([chapter 07](07-clocks.md)).
  * **Q1 of the collection — what is a volume descriptor for?** The current
    formulation is *the descriptor is a property of what can go wrong between
    the maker and the reader.* This object is a direct test: a physical medium
    from 1997 that declares a length and carries no hash. It holds — and the way
    it holds is instructive. The descriptor got the **length** right to the
    sector, and every failure this repository found is a failure of something the
    descriptor has no field for: 13.85 MB of uncleared buffer, a linker map, a
    thumbnail cache, an FTP log, a trade price list. **The descriptor is exactly
    as good as its designers' model of what could go wrong, and in 1997 that
    model was "the reader might not know how long the volume is".** It was right
    about that and had nothing to say about anything else. Twelfth answer, and
    the first from an object where the descriptor was *correct* and still
    insufficient.
