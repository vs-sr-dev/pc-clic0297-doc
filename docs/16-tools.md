# 16 — The tools: 158 scripts, four written, and 56 that would lie about this disc

*Measure: `toolclass.py` refuses to print until every `.py` in `tools/` is in
exactly one class and the classes sum to the file count. They do: **158**.*

```
python tools/toolclass.py
python tools/toolclass.py --markdown
```

```
written for this disc                                  4
inherited and used                                    13
inherited, superseded here                            29
inherited, applicable, not needed                     56
inherited and misleading here                         33
does not apply: another engine or another publisher    23
total                                                158
```

---

## Four written, and why only four

Issue 11 wrote eighteen, the most any session in this branch has needed. This
one wrote four. That is not because this disc was easier — it has two
filesystems where most have one — but because 154 inherited scripts already
covered everything except the join between them.

**`twocat.py`** — the ownership map walked from both catalogues at once
([chapter 04](04-two-catalogues.md)). It exists because every inherited sector
map assigns each sector to at most one owner, and on a hybrid that is the wrong
data structure: 96.79 % of this disc is owned twice and a one-owner map has to
either double-count or discard a catalogue. It also does the ISO↔HFS file
comparison, and it does it **by extent rather than by name**, because the ISO
side is 8.3 upper case and the HFS side carries the real 31-character names and
the mapping is not recoverable from the strings.

**`abslack.py`** — the arithmetic of the 10,240-versus-2,048 granularity, file
by file, and the classification of what is in the gap
([chapter 05](05-the-padding.md)). Named `abslack` and not `slack` after this
session **overwrote the inherited `slack.py`** with it and had to restore it;
see [chapter 19](19-corrections.md). The two measure different regions and both
were run.

**`slackorigin.py`** — takes a probe from each padding region and searches the
whole image for it, to distinguish *this file's tail repeated*, *another file's
bytes*, and *bytes that are on no file at all*. It samples, and it says so on
the line that prints the number.

**`jbf.py`** — a reader for JASC Paint Shop Pro's thumbnail cache, which is a
format of a program somebody ran and not a format of this object
([chapter 15](15-leftovers.md)).

## Thirteen inherited and used

Every one ran and produced a figure a document cites:

| tool | what it settled |
|---|---|
| `iso9660.py` | the descriptors, the tree, the dates, the extraction. **Ran unmodified on the image** |
| `hfs.py` | the partition map, the MDB, the catalogue, the TSV. **Ran unmodified**, and `parse_catalog()` returned 2,940 records with no change |
| `pecensus.py` | 75 executables, two of them PE32, and `GLAMM Interactive` in a version resource |
| `census.py` | 46 extensions and the per-directory shares |
| `protscan.py` | twelve markers over 75 executables |
| `buildpaths.py` | 1,281 DOS-shaped paths, run **intact** for comparability with nine objects |
| `discdiff.py` | three matching hashes against CLIC 11, two of them real |
| `mov.py` `avi.py` `audio.py` | 27 m 16 s, 5 m 19 s, 59 m 38 s |
| `slack.py` | intra-sector slack: 2,820 files of 2,821 with a dirty tail |
| `checkscore.py` `toolclass.py` | this repository's own arithmetic |

`iso9660.py --compare` was **not run and is not counted as a failure**: it
compares the primary namespace against Joliet, and this disc has no Joliet
descriptor, so there is nothing to compare. It refuses with *no volume
descriptor of type 2*, which is the correct answer. `--gaps` refuses for the
same reason.

## Fifty-six that do not apply, and 33 that mislead

**35.4 % of the inherited apparatus is wrong about this disc**, and the
interesting ones are wrong in specific ways:

  * **`spti.py`, `toc.py`, `isodev.py`, `hfsx.py`** address a *drive*. There is
    no drive this session. `hfsx.py` demands a drive letter on the command line
    and fails on an image; the other three would report on a machine rather than
    on this object. They are in "misleading" rather than "not applicable"
    because they run and print something.
  * **`mzcensus.py`** crashes: it has a hard-coded file list from another disc
    and raises `FileNotFoundError: '_work/iso\\MM.OVR'` after printing a table
    of one executable. It is a disc-specific tool wearing a general name.
  * **`leadout.py`, `sweep.py`, `interleave.py`, `xfermax.py`, `discpass.py`**
    are the drive-discipline apparatus that opened issue 11's session. On an
    image they are not merely unnecessary; running them would produce numbers
    about a dumper.
  * **`pkgsame.py`, `listdiff.py`** were nominated by the briefing for the CLIC
    11 comparison. `discdiff.py` answered it in one command; the other two are
    in "superseded" so that nobody thinks the question went unasked.

## The forty-four that are the debt

Issue 11 declared 44 tools "inherited, applicable, not needed" and called it a
list of measurements its disc could support and its repository did not take.
This session's equivalent class is **56**, and it is bigger for an honest
reason: this disc has nine strata and only some of them were opened.

The four most interesting things not done:

  * **`rsrc.py`** — the PE and NE resource trees were never walked. `VILLE.EXE`
    is 10.6 MB of compiled ToolBook with a version resource and an icon nobody
    has looked at, and `LCAT.EXE` is a 4.5 MB Director projector.
  * **`director.py`** — `MUSEO/MAIN.DIR` is 3,468,344 bytes of RIFX and this
    repository states only its magic and its 1979 timestamp. Its chunk map would
    say what the Orsay demo is made of.
  * **`filemaker.py`, `requires.py`, `strata.py`, `producers.py`** — four tools
    written for issue 11's producer analysis, none of them run here. The
    producer figures in [chapter 12](12-producers.md) come from `census.py` and
    a byte-string count instead, which is a thinner method.
  * **`encodinghunt.py`** — 549 HTML files in Italian, and the character
    encoding of not one of them was checked. Issue 11 found a FileMaker database
    shipped in the wrong encoding by running exactly this.

## Where the tools were pointed away from people

Three general-purpose scanners walk every file and print what they find, and two
directories on this disc are readers' letters and readers' small ads
([chapter 12](12-producers.md)).

  * **`buildpaths.py`** was run over the whole tree, `NUMERI/CLIC297/POSTA/` and
    `PIAZZA/` included. Its output, `notes/buildpaths.txt`, was **read before it
    was committed**; it contains no hit from either directory, because a
    small ad has no drive letters in it. Nothing was removed.
  * **`slackorigin.py`** prints file names and offsets and **never prints the
    bytes it matched**, by construction, because the padding it samples is
    somebody's uncleared memory ([chapter 05](05-the-padding.md)).
  * **`strdump.py`, `refs.py`, `encodinghunt.py`** were **not run**. Each would
    walk `POSTA/` and `PIAZZA/` and dump readable text, and none of them was
    needed for any figure in this repository. That is a decision and it is
    recorded as one rather than as an omission.

The counts of addresses and telephone numbers in [chapter 12](12-producers.md)
were made by a purpose-written regular expression that **reports totals per file
and never the matches themselves**, run inline and not committed as a tool,
because a tool that extracts contact details is worse to have in a repository
than the numbers are.

`notes/` was checked before committing for three things: no reader's e-mail
address, no private telephone number, and no `D:\` path belonging to this
machine. The absolute paths that *are* in `notes/buildpaths.txt` all resolve on
machines in Derby, Bellevue and Milan in 1996 and 1997, which is the exception
the branch has always made.
