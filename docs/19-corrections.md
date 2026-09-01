# 19 — Corrections: seven in the briefing, eleven of mine

*Measure: an error is listed here if a figure or a claim was written down and is
wrong. Errors caught before anything depended on them are still listed, because
the useful part is how they were caught.*

---

## In the session briefing

**B1 — `hfs.parse_catalog()` does not return two records.** The briefing said it
returned 2 on this volume and that the node size or the parser needed
investigating. It returns **2,940** — 2,820 files, 60 directories, 60 threads,
over 882 leaves — with no change at all, from `python tools/hfs.py --image
CLIC.ISO --catalog`. The likely cause is the one the briefing itself named two
paragraphs earlier: calling `read_mdb(src, part)` instead of
`read_mdb(src, part["start"])`. This cost prediction C06, which was written to
defend a bug that was never there.

**B2 — `paths.py` does not exist.** The briefing instructs *«giralo intatto»* —
run it unmodified — on a tool that is not in `tools/`. The 154 inherited scripts
contain `buildpaths.py`, `machpaths.py`, `machpaths2.py` and `pathdiff.py`. The
one with the comparable output is `buildpaths.py`, and it is what issue 11 used
for its own 280-path figure.

**B3 — the disc says which issue it is.** The briefing states that
*«il nome della directory è l'unica cosa sul disco che dice quale numero è
questo»*. `/LEGGIMI.TXT`, 2,433 bytes at the root, opens **«Clic! Cd-rom di
Marzo»** and says it contains the February website. The disc names its own month
in prose, and it disagrees with the directory ([chapter 01](01-provenance.md)).

**B4 — the unowned sector count is 7,846, not 7,846 *and* 7,847.** A first run of
`twocat.py` reported 7,847 because the tool did not claim the root directory's
own extent. That was my bug, not the briefing's, and it is M1 below — but it is
recorded here too because it briefly looked like a disagreement with the
briefing and was not.

**B5 — the twenty `.PHD` files are nineteen.** The briefing describes «venti file
`.PHD`» as the complete level series. There are twenty records and
**nineteen distinct files**: `CURRENT.PHD` and `TITLE.PHD` are byte-identical,
sha1 `300cf185…`. And the set is not the complete retail series: 16 of 16 game
levels, but **2 of 4 cut scenes** ([chapter 09](09-tombraider.md)).

**B6 — `DEMO.DAT` is not an attract-mode recording.** The briefing suggests
*«suggerisce una modalità attract»*. It is 628 bytes and **every one is zero**.

**B7 — the tel/fax count is 73 in 10 files, not 74 in 11.** An independently
written expression over all 799 text files finds 73 occurrences in 10 files; the
e-mail figures match the briefing exactly at 45 distinct addresses, 60
occurrences, 18 files. The difference is one match and it belongs to the two
regular expressions rather than to the disc. It is recorded and **not
reconciled**, because tuning a pattern until it agrees with a target number is
how a measurement stops being one ([chapter 12](12-producers.md)).

Also worth noting rather than correcting: the briefing's year histogram
(1996: 1,410 · 1997: 1,118) counts the 2,823 **file** records; this repository's
(1996: 1,439 · 1997: 1,141) counts all 2,879 **directory** records. Different
populations, both right, and exactly the ambiguity [chapter 03](03-file-count.md)
exists to remove.

---

## Mine

**M1 — the ownership map reported 7,847 unowned sectors and three orphans.**
`twocat.py`'s first version walked the ISO tree with `tree_of()`, which emits the
root's *contents* and never a record for the root itself, so **LBA 20 — the root
directory extent — was reported as belonging to nobody.** The map closed at
three unowned sectors instead of two. Caught because 20 is a suspiciously
round number to be orphaned and because the primary volume descriptor names it
outright as the root extent. Fixed with an explicit claim, and the fix carries a
comment saying why, because this is precisely the plausible-looking wrong answer
the chapter exists to avoid.

**M2 — I compared the two catalogues by name, and the names cannot be
compared.** The first `--only-hfs` / `--only-iso` run reported dozens of files
"present in the ISO tree and absent from HFS", including whole directories of
`IMG/` and `NUMERI/`. The reason is that the ISO side is ISO 9660 level 1 —
eight-plus-three, upper case — and the HFS side carries the real 31-character
Macintosh names, and Toast truncated one from the other by a mapping that is not
recoverable from the strings. The comparison was rewritten to match **by the LBA
of the first extent**, which is the one thing both catalogues agree on and
cannot truncate, and the answer became two files and three directories
([chapter 03](03-file-count.md)).

**M3 — I overwrote an inherited tool.** `abslack.py` was first written as
`slack.py`, clobbering a 107-line inherited script of the same name that
measures a **different region** — the tail of each file's last 2,048-byte
sector, rather than the whole sectors between the ISO and HFS grids. Caught by
`toolclass.py`, which reported 157 files on disk when 158 were expected and
named the three that were unclassified. The inherited tool was restored from
`../pc-clic11-doc/tools/`, mine was renamed, and **both were then run** — which
is how [chapter 05](05-the-padding.md) got its second, independent confirmation
that the mastering program never clears its buffer. The rule this violated is
the branch's own: check what a name already means before writing to it.

**M4 — a filter that rejected everything looked like a file with nothing in
it.** `jbf.py` reported *names found: 0* on a 127,800-byte thumbnail cache for
twenty minutes. The regular expression matched 46 times; the validation step
that follows it compared `m.group(2).lower()` — **bytes** — against
`ext[::-1].lower()` — **str** — which is never equal in Python 3, so every
record was silently dropped. It was found by instrumenting the loop rather than
by re-reading the code, and the fix carries a comment. **A tool that finds
nothing and a tool that discards everything print the same thing.**

**M5 — I broke the branch's own backslash rule twice.** Rule 0 of the briefing:
*`Write`, never a heredoc, for any script containing a backslash.* Two heredoc
patches mangled `\-` into an invalid escape and one produced a regular
expression that matched nothing; a third heredoc attempt at a path-scanning
regex silently found **zero paths in 2,818 files** because the `%`-formatted
backslashes did not survive. All three were replaced with `Edit` or with the
authoritative tool's own output. The rule is in the briefing because it has cost
previous sessions real time, and it cost this one about half an hour.

**M6 — I nearly published a story that the data refutes.** The Paint Shop Pro
cache names 38 files and the directory holds 57, which reads beautifully as *a
snapshot taken before nineteen more files arrived*. The directory holds **exactly
38 `.LBM` files**, and the other nineteen are `.BBM`, `.SHD`, `.BIF` and
friends: Paint Shop Pro caches the format it reads. Caught by counting the
extensions before writing the sentence, which took one command
([chapter 15](15-leftovers.md)).

**M7 — I nearly published a second one.** Nine basenames appear on both CLIC
discs — `credits.htm`, `home.htm`, `lazio.htm`, `sommario.htm`, `copertin.jpg`
— which reads as *the magazine's own template surviving across issues*. Six of
the nine are in `CalcioHP/` on issue 11, a Hewlett-Packard football website that
happens to use ordinary Italian nouns for file names. `lazio.htm` is a **region**
here and a **football club** there. One of the nine is genuinely the same
feature. Caught by looking at where the files are before writing what they mean
([chapter 14](14-against-clic11.md)).

**M8 — I double-counted 75,316 bytes of leftovers.** The first leftovers total,
4,974,130 bytes, counted `IMG/WS_FTP.LOG`, `TOMB.LOG` and `HMISET.BAK` twice:
once by name and once in the `.BAK`/`.LOG` sweep, because the exclusion test
compared a path built with mixed separators (`_work/iso\IMG\WS_FTP.LOG`) against
one built with `os.sep`. The corrected figure is **4,898,814 bytes, 1.0017 %**.
The same bug is why the sweep found 34 files where 32 were expected — and
following that discrepancy is what turned up the **other eleven WS_FTP logs**,
which are the best single find in [chapter 15](15-leftovers.md). A miscount that
leads somewhere is still a miscount, and it is listed as one.

**M9 — I edited the predictions file, and here is exactly what I changed.**
[Chapter 00](00-predictions.md) says of itself *«it is not edited
afterwards»*, and three of its cross-references pointed at
`22-prediction-scoring.md` and `21-open-questions.md` — CLIC 11's chapter
numbers, written from habit before this repository's own numbering existed.
They were repointed to `18-scoring.md` and `17-open-questions.md`, which is
three link targets and **no word of any clause**: the file still holds 62 rows
matching `^\| C\d\d \|`, verified after the edit. The bets are what the rule
protects; a pointer to a file that does not exist is not a bet, and leaving it
broken to honour the letter of the rule would have been worse than saying this.

**M10 — I left a question open that this disc had already answered, and I left
it open by reading a number instead of reading the prose.** The first version of
[chapter 14](14-against-clic11.md) concluded that the archive codes 4, 6, 7, 9,
10, 11, 12 were *positions in a sequence*, that issue 11 was therefore November
1996, and that what `CLIC_11` counted on a disc mastered in October 1997 could
not be determined from two objects. All of that was wrong except the November.

The codes are **month numbers**, and the evidence was in a directory I had
already walked. The magazine never once refers to a back issue by an ordinal:
five references across `PAG/` and `NUMERI/` all read *«numero di ottobre»*,
*«di maggio»*, *«di giugno»*, *«di luglio»*, *«di settembre»*. `PAG/12CO003.HTM`
cites the October issue as a back issue, fixing 10 = October and 12 = December.
`PAG/11CO005.HTM` previews a release *«Il 15 novembre»* in the future tense.
There is no running issue count on this disc at all, so there was no sequence
for `CLIC_11` to be the eleventh of, and `11` is **November** — 1997, dated by
that disc's contents rather than by its label.

I had the month-to-code mapping in hand the moment I printed the `PAG/` prefixes
and did not ask what the prefixes *were*. Counting a set of numbers is not the
same as reading them, and this is the fourth entry in this chapter where the
error was a plausible reading that one command would have killed.

**M11 — I weighed the two objects the wrong way round.** [Chapter 01](01-provenance.md)
correctly says that measuring an image costs the lead-out, the table of contents
and the subchannel, and that any sentence here about the physical medium is a
deduction from a file. What it did not say is the consequence for the
comparison: **`pc-clic11-doc` was read from a physical disc in a drive, and this
object is an image of unknown provenance.** That makes the other disc the better
witness of the two, not the lesser one, and chapter 14 was written as though the
newer measurement were automatically the stronger. On everything the two discs
disagree about — and on the 302 sectors this image has where that disc has a
measured 152-sector lead-out — **the first-hand artefact wins**, and the fact
that this repository could settle the dating question is a fact about which disc
carried the archive, not about which was better read.

---

## What the eight measurement errors have in common

M9 is a bookkeeping note, M10 is a wrong conclusion corrected after
publication and M11 is a misjudgement about evidence rather than about bytes,
so the eight below are M1 to M8.

Four of them — M1, M2, M4, M8 — are the same failure: **a wrong answer that
looked reasonable.** Three orphan sectors instead of two; dozens of missing
files instead of two; zero cache entries instead of 38; a leftovers total 1.5 %
too high. None of them was absurd, and none would have been caught by reading
the code again. Every one was caught by asking where a specific number came
from.

Two more — M6, M7 — are the failure the briefing warned about in its own words:
*the risk here is not an invented taxonomy, it is an invented coherence.* Both
were stories that explained the data and were not in it, and both died to one
command.

Which leaves the branch's oldest lesson, restated because this session paid for
it four times in one day: **when a number confirms what you expected, that is
the moment to look at how it was produced.**
