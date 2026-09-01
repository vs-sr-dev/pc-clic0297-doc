# 06 — The five resource forks: where the cursor was, on a Tuesday afternoon in 1997

*Measure: five ISO records carry the Associated-File flag, 670 bytes each,
3,350 bytes in total. All five are Macintosh resource forks with the same
structure to the byte and different contents. Each holds exactly one resource,
of type `BBSR`, and the file's creator code is `R*ch`. Both are BBEdit's. What
the resource records is the window position and the insertion point of the
person who last saved the page.*

```
python tools/twocat.py CLIC.ISO --only-hfs
python tools/hfs.py --image CLIC.ISO --tsv notes/hfs-files.tsv
```

---

## The five

| path | sha1 of the fork |
|---|---|
| `/CATAL.HTM;1` | `1dba51f513274adcf9bdd3a6f599b453053a3cc9` |
| `/DEMO.HTM;1` | `019a036a8cee5a409b0904f6944c56171a452c3c` |
| `/NUMERI/CLIC297/EDICOLA/SOMMARIO.HTM;1` | `7a8fab374f6dbdae008f3ed632050e3f937b14b2` |
| `/PROD.HTM;1` | `0659f99784f18f83c2d3d54948b2a89aead82a37` |
| `/PAG/PAGELLE.HTM;1` | `d8836e98f9cfa0cbc72ab60b353476afb7d7e13e` |

Five distinct hashes. They are **not** five copies of one template — which was
the prediction, and it was wrong. They are five instances of one *structure*
carrying five different values, which is a more interesting thing to be.

## The structure closes on 670

The Macintosh resource fork format is Apple's and is documented by Apple in
*Inside Macintosh*; it is used here by its public definition, and the definition
is checked against the file before anything is read out of it. The 16-byte
header gives four offsets, and all five forks give the same four:

```
data @ 256  len 364      map @ 620  len 50      620 + 50 = 670 = the file
```

Every one closes exactly on its own length. That is the validation, and it ran
before the census, as it should.

The map holds one type list with **one type**:

```
type 'BBSR'  1 resource
  id 592   name ''   attributes 0x00   data 360 bytes
```

## `R*ch` and `BBSR`

The HFS catalogue gives every file a four-character type and creator. For these
five:

```
19  Clic!/catal.htm   TEXT   R*ch   data 1135   rsrc 670
```

`R*ch` is the creator code of **BBEdit**, Bare Bones Software's text editor —
the initials of its author with a star for the vowel — and `BBSR` is the
resource BBEdit writes to remember what it was doing with a document. The
resource's own first four bytes repeat the signature:

```
52 2A 63 68  02 50  00 28 00 1E 02 1E 01 78  00 18
 R  *  c  h                                        …  'Monaco'
```

Reading only what the bytes plainly are, and declaring the rest not derived:

| bytes | value | reading |
|---|---|---|
| 0–3 | `R*ch` | the editor's signature, repeated inside its own resource |
| 6–13 | 40, 30, 542, 376 | a Macintosh window rectangle: **502 × 346 pixels, 30 from the left, 40 from the top** |
| 16–23 | two equal 32-bit values | selection start and end — an insertion point, not a range |
| 34–41 | `Monaco`, then 9 | the font the window was displayed in, and its size |

Nothing else in the 360 bytes is claimed. The only printable strings in any of
the five are `R*ch` and `Monaco`, twice each. **There is no prose in these
files**, which is what makes them safe to describe: they are editor furniture,
not document content.

## What the differences are

Four of the five differ from `catal.htm`'s fork in **eight bytes of 360**; the
fifth, `prod.htm`, in nine. The differing bytes are the window rectangle and the
insertion point:

| file | data bytes | insertion point | as a fraction of the file |
|---|---:|---:|---:|
| `CATAL.HTM` | 1,135 | 757 | 66.7 % |
| `DEMO.HTM` | 1,429 | 1,394 | 97.6 % |
| `SOMMARIO.HTM` | 7,962 | 932 | 11.7 % |
| `PROD.HTM` | 1,896 | 1,589 | 83.8 % |
| `PAGELLE.HTM` | 3,558 | 1,637 | 46.0 % |

`prod.htm` is the ninth differing byte because its window was six pixels further
right — left edge 46 instead of 40.

**That is the caret of whoever edited these pages, frozen where they left it.**
Not a metaphor: byte 16 of a BBEdit state resource is where the blinking bar
was when the file was last written to disk, and the disc has carried five of
them for twenty-nine years.

## Why these five of 549

549 HTML files are on this disc and five have a resource fork. The prediction
was that they would be the tree's entry points; three of them are at the root
and one is one level down, but `NUMERI/CLIC297/EDICOLA/SOMMARIO.HTM` is three
levels down, so "entry point" is not the property.

The property that actually separates them is visible in the directory records:

| file | ISO record timestamp |
|---|---|
| `DEMO.HTM` | 1997-02-14 16:42:18 |
| `PROD.HTM` | 1997-02-14 16:57:58 |
| `CATAL.HTM` | 1997-02-14 17:03:32 |

`1997-02-14 17:03:32` is **the newest directory record on the entire disc**, and
`16:42:18` is the third newest. Of the thirteen records dated 14 February 1997,
these five files account for ten — each appearing twice, as fork and as data.

**These are the last five files anybody touched.** Somebody opened them in
BBEdit on the afternoon of the master, made a final edit, saved, and BBEdit
wrote its state resource as it always does. Eight minutes and five seconds later
the HFS volume was closed; an hour and forty-three minutes after that the ISO
descriptor was written. Every other HTML file on the disc had been copied in
from elsewhere and had no fork because nothing on a Macintosh had ever opened
it.

The forks are not a property of those five pages. They are a property of the
last hour of work before the disc was cut.

## The layout confirms it

```
LBA   1163  /CATAL.HTM;1                              670 B  ASSOC
LBA   1168  /CATAL.HTM;1                             1135 B
LBA   1173  /DEMO.HTM;1                               670 B  ASSOC
LBA   1178  /DEMO.HTM;1                              1429 B
LBA   1183  /NUMERI/CLIC297/EDICOLA/SOMMARIO.HTM;1    670 B  ASSOC
LBA   1188  /NUMERI/CLIC297/EDICOLA/SOMMARIO.HTM;1   7962 B
LBA   1193  /PROD.HTM;1                               670 B  ASSOC
LBA   1198  /PROD.HTM;1                              1896 B
LBA   1203  /PAG/PAGELLE.HTM;1                        670 B  ASSOC
LBA   1208  /PAG/PAGELLE.HTM;1                       3558 B
```

Ten allocation blocks, perfectly regular, and they are the **first file data on
the volume** — LBA 1,163 is the sector immediately after the HFS catalogue
B-tree ends at 1,162. Toast laid the forked files down first, in pairs, before
anything else on the disc.

## What it costs a hash list

3,350 bytes, five records, and any list of this disc built by walking a mounted
volume misses all of them silently. Issue 11 made the same point with eighteen
forks and 26,607,777 bytes of Macintosh-only data behind them; here the amount
is trivial and the principle is not. **A published hash list of a hybrid is
incomplete unless it says which walker made it** — and this repository's does
([chapter 03](03-file-count.md)).
