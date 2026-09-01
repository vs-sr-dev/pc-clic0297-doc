# 05 — The padding: 13,850,624 bytes of a hard disk that no longer exists

*Measure: 6,763 sectors sit between the end of a file's ISO extent and the end
of its HFS allocation block. **Not one of them is zero.** A sample of 39 probes
finds that 17 of them appear nowhere else in the image and 14 more appear only
in other padding — so the padding is not a copy of this disc's own data. It is
residue of the volume that made it.*

```
python tools/abslack.py CLIC.ISO --content
python tools/slackorigin.py CLIC.ISO --sample 40
```

---

## The arithmetic first

```
file records            2823
ISO extent sectors      240377
HFS allocation sectors  247140
difference              6763 sectors = 13850624 bytes
files with slack        2395 of 2823 = 84.8388 %

slack length, in sectors:
  1 sector(s)  x   369  =    369 sectors
  2 sector(s)  x   605  =   1210 sectors
  3 sector(s)  x   500  =   1500 sectors
  4 sector(s)  x   921  =   3684 sectors
```

Five sectors per allocation block means the padding after any file is 0, 1, 2, 3
or 4 sectors, and the distribution above is what you get when file lengths are
spread more or less evenly across the remainder — 921 files land in the worst
case and waste four sectors, 428 land exactly on the boundary and waste none.
This is the model of [chapter 04](04-two-catalogues.md), summed over every file
rather than argued from one.

The walked extents give 6,818 sectors rather than 6,763; the 55 extra are the
Finder's two files, which the model does not see because it walks the ISO tree.

## Every last byte of it is non-zero

```
slack sectors by content:
  not zero      6763 sectors = 13850624 bytes  100.0000 % of slack
```

**There is no zero-filled padding on this disc at all.** That is the finding
this chapter exists for, and it was not expected: padding is supposed to be
padding.

The obvious first hypothesis was that the mastering program wrote each file's
last block from a buffer and left the file's own tail repeated behind it. It is
testable and it is wrong:

```
non-zero slack regions that repeat their own file's tail: 0 of 2395
```

Zero of 2,395. Whatever is in the gap after a file, it is not that file.

## So where is it from?

Three origins are possible and they are distinguishable. Take a probe of 32
bytes from the middle of each sampled padding region and search the whole
509 MB image for it:

```
of 39 probes:
  found inside the SAME file's extent    0
  found inside ANOTHER file's extent     8
  in the image but inside NO file extent 14
  absent from the image entirely         17
  probe too uniform to search            1
```

  * **8 of 39** are bytes of some other file that is on this disc. Those are the
    mastering program's read buffer holding the previous file when it wrote this
    one — `/CATAL.HTM`'s padding contains `/IMG/HOME1.JPG` at offset 118,784;
    `/LEADER/CATALOGO/REQUISIT/400120.TXT`'s padding contains
    `MTB30BAS.DLL` at offset 845,819.
  * **14 of 39** are in the image but in no file: they appear only in *other*
    padding, which is the same buffer surviving several writes.
  * **17 of 39 — 43.6 % — exist nowhere on this disc.**

That last class is the interesting one. Those bytes were in the machine's memory
or on the machine's disk when the master was cut, they were written to the
CD-ROM, and **they are not part of any file the CD-ROM carries**. One sampled
region, the four sectors after `MTB30BMP.DLL`, holds legible text — a fax cover
sheet template, in Italian and English, with a field reading *«N. di pagine»*.
There is no fax template on this disc.

**This is a sample, not a census: 39 probes of 2,395 regions, one every 59th.**
The proportions above carry that uncertainty. What does not is the census
figure: 6,763 of 6,763 padding sectors are non-zero, and 0 of 2,395 repeat their
own file.

## What that makes it

**13,850,624 bytes — 2.83 % of this object — are the uncleared working memory
of a Macintosh in Milan in February 1997.** Pressed, according to the magazine's
own readme, onto every copy of a national newsstand title.

It is not a payload, it is not a message, and nobody put it there on purpose. It
is what happens when a program allocates in units of ten kilobytes, writes files
that are not multiples of ten kilobytes, and never asks what was in the buffer
before.

## The care this needs

Residue of somebody's working disk is exactly the class of material this branch
handles carefully. The padding is **counted and characterised and not
transcribed**: no fragment of it is reproduced in this repository beyond the one
template phrase above, which is a printed form's field label and belongs to no
person. `slackorigin.py` prints file names and offsets, not contents, and its
output in `notes/slack-origin.txt` was read before it was committed.

The same rule that governs [chapter 12](12-producers.md) governs this: a string
that belongs to an organisation is quoted, a string that belongs to a person is
counted. In 13.85 MB of somebody's RAM there is no way to be sure which is
which, so it is all counted.

## The other slack, and it agrees

There are two kinds of unused space on a hybrid and this chapter has so far
measured one. The inherited `slack.py` measures the other: the bytes between the
end of a file and the end of its **last 2,048-byte sector**, which exists on any
ISO 9660 disc.

```
python tools/slack.py --image CLIC.ISO --samples 6
```

```
file records with a data extent   : 2821
slack bytes in last sectors       : 3254392
  of which zero                   :  582990   17.9139 %
  of which non-zero               : 2671402   82.0861 %
files whose slack is not all zero : 2820 of 2821
```

**2,820 of 2,821.** A second tool, written for a different disc, asking a
different question about a different region, reaches the same verdict: this
mastering program does not clear its buffer, anywhere, ever. The one file whose
sector tail is clean is clean by luck.

The commonest non-zero byte in that slack is `0xFF` at 172,746 occurrences,
followed by `0x03`, `0x20`, `0x07` — and then `T`, `I`, `A`, `i`, which is
readable Italian text arriving in the tail of files that are not text.

So the disc carries, in round numbers, **16.5 megabytes of somebody's working
memory**: 13,850,624 bytes in whole sectors between the two grids, and 2,671,402
more in the last partial sector of nearly every file.

## Against issue 11

Issue 11's sector map left **two** sectors unowned, both zero, and had nothing
of this kind, because its allocation block was smaller relative to its files and
because nobody asked. The question "is the padding zero?" had never been put to
a hybrid in this collection. Asked here, on 2,395 regions, the answer is no —
**not once**.

That is worth carrying forward as a thing to check on the next hybrid, and it is
in [chapter 17](17-open-questions.md) as Q5.
