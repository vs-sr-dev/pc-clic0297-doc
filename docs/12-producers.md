# 12 — The producers: the magazine made 0.82 % of its own disc, and names itself 1,649 times

*Measure: producer shares are computed from the ISO tree over the 489,034,354
bytes a PC can read. Name counts are literal byte-string occurrences over all
2,818 files. The colophon is read and its people are named, because a colophon
is a credit; the readers' letters are counted and their contacts are not
transcribed, because a small ad is not a credit.*

```
python tools/census.py _work/iso
```

---

## Who made what

| producer | what | bytes | share |
|---|---|---:|---:|
| **Leader S.p.A.** (distributor) | `LEADER/CATALOGO` | 354,228,172 | 72.4342 % |
| **Core Design / Eidos** | Tomb Raider | 47,619,223 | 9.7374 % |
| the *Ville Venete* supplier | `VILLE` | 51,595,303 | 10.5504 % |
| the *Power F1* supplier | `MAGDEMO` | 10,839,135 | 2.2164 % |
| **Microsoft** | `DOWN/MSIE301.EXE` | 5,585,256 | 1.1421 % |
| the Orsay supplier | `MUSEO` | 5,212,705 | 1.0659 % |
| **Apple** | `LEADER/QTW` | 3,102,720 | 0.6345 % |
| **CLIC! / Mondadori Informatica / GLAMM** | the magazine | 4,012,668 | **0.8205 %** |
| — with `IMG/` counted as the magazine's | | 9,766,076 | **1.9970 %** |

The pie chart is honest and useless: it says a mail-order catalogue made 72 % of
a magazine's cover disc, which is true and tells you nothing about the magazine.

The useful one is the last row, and it needs a decision.

## Is `IMG/` the magazine's?

511 files, 5,753,408 bytes — bigger than everything else the magazine
contributed put together. It is the image directory of `clic.mondadori.com`, and
the disc records exactly how it got here: `IMG/WS_FTP.LOG` logs 535 files pulled
**down** from `www1.mondadori.com` between 1997-02-10 12:07 and 1997-02-11
13:59, into `D:\Clic-cd\img\` ([chapter 07](07-clocks.md)).

So they were fetched by the magazine's own staff from the magazine's own server.
They are also, in large part, **other people's logos and box shots**:
`compaq.gif`, `casper.jpg`, `business_tool.gif`, `basil.gif`, plus the site's own
navigation art and image maps.

Both figures are given, both are named, and this repository's headline is the
narrow one — **0.8205 %** — because `NUMERI`, `PAG`, `RETE`, `PRE` and the root
are the files the editorial staff wrote, and `IMG/` is what they downloaded. The
wide figure, 1.9970 %, is in the spec sheet for anyone who disagrees.

Either way it is **below issue 11's 3.37 %**, and the reason is not that the
magazine did less: it is that this disc's largest parcel is twice the size of
that one's.

## The colophon

`/CREDITS.HTM`, 1,750 bytes, titled *Clic! online Web Credits*. It is a
published credit list — the closing titles of the project — and it is reported
in full because without it the question *who made this disc* has no answer:

| role | name |
|---|---|
| Direttore responsabile | Francesco Di Martile |
| Redazione | Antonia Bassanetti · Marco Gatti · Mario Pettenghi |
| Progetto | Marco Gatti · Sebastiano Caccialanza · Alberto Fattori *(GLAMM Interactive)* |
| Responsabile Mondadori On Line | Paolo Riccardo Felicioli |
| Responsabile progetto | Sebastiano Caccialanza |
| Progetto grafico | Stefano Meneghetti *(GLAMM Interactive)* |
| Rete e amministrazione server | Gianfranco Pocecai *(GLAMM Interactive)* |
| Programmatori | Federico Cilloccu *(GLAMM Interactive)* · Silvia Coatti *(GLAMM Interactive)* |
| **Produzione CD-ROM** | **Federico Cilloccu** · **Stefano Meneghetti** *(GLAMM Interactive)* |
| Editore | Mondadori Informatica S.p.A. |

Thirteen people. Six of the ten roles are held by **GLAMM Interactive**, and
both names under *Produzione CD-ROM* — the people who actually built this
object — are GLAMM's.

`/GLAMM.HTM`, 535 bytes, gives the company's own details, published in the
magazine to be read by anyone: *GLAMM Interactive s.r.l., V.le Corsica n.7,
20133 Milano — Italy*, with a telephone, a fax, `http://www.glamm.com` and an
`info@` address. That is an organisation's business card and it is quoted like
any other string of the object. **Nothing on it was visited**; a 1997 domain
belongs to somebody else now.

## How often each producer names itself

Literal occurrences across all 2,818 files:

| string | occurrences |
|---|---:|
| `Clic!` | 1,104 |
| `CLIC` | 545 |
| `Mondadori` | 86 |
| `Leader` | 69 |
| `GLAMM` | 14 |

The magazine names itself **1,649 times** and contributes 0.82 % of the bytes.
The distributor whose catalogue is 72.43 % of the disc names itself **69 times**.
The company that actually produced the CD-ROM names itself **fourteen**.

That inversion is the whole shape of the object in one table: the loudest name
belongs to the smallest contributor, and it is loudest because it is on every
page of the 549 HTML files that are the only part anybody wrote for this disc.

Some of the 1,104 are an accident worth keeping. The readme spells *cliccate* —
"click" — as **`Clic!cate`**, so the brand is inside the verb:

> *Da gestione risorse posizionatevi sulla directory "leader" sul Cd-rom;
> Clic!cate su "setup.exe"*

`SETUPIE.EXE` is the only compiled binary GLAMM produced, 16,896 bytes, and its
`CompanyName` resource reads **`GLAMM Interactive`** — one of 75 executables on
the disc, and the only one whose maker also made the disc.

## The people who are not credits

`NUMERI/CLIC297/POSTA/` is **104 files** of letters to the editor, and
`NUMERI/CLIC297/PIAZZA/CAFE.HTM` is 24,440 bytes of readers' small ads. An
independent scan of all 799 text files on the disc:

```
distinct e-mail addresses : 45     occurrences: 60   in 18 files
tel / fax occurrences     : 73                       in 10 files
```

and where they are:

| file | e-mail | tel/fax | what it is |
|---|---:|---:|---|
| `NUMERI/CLIC297/PIAZZA/CAFE.HTM` | 26 | 19 | **readers' small ads** |
| `NUMERI/CLIC297/COP/AGENZIE.HTM` | — | 20 | *«Le principali agenzie di pubblicità»* — advertising agencies |
| `NUMERI/CLIC297/PIAZZA/INDIRIZ.HTM` | — | 12 | addresses |
| `NUMERI/CLIC297/COP/CURRICUL.HTM` | — | 8 | employers |
| `NUMERI/CLIC297/COP/COLLEGE.HTM` | 4 | 6 | *«In questi college puoi studiare»* — institutions |
| `RETE/CAMPANIA.HTM` | 6 | — | a regional directory of Italian websites |
| `PRE/CHI.HTM` | 5 | — | who's who |
| `GLAMM.HTM` | 2 | 2 | the CD-ROM's producer |

**The rule, applied literally: a contact that belongs to an organisation is
quoted; a contact that belongs to a person is counted.** In case of doubt it is
counted.

So `GLAMM.HTM` is quoted above. `AGENZIE.HTM` and `COLLEGE.HTM` are lists of
firms and institutions publishing office numbers on purpose, and they are
described and counted but not tabulated, because there is no measurement that
needs the numbers themselves. And `CAFE.HTM` and the 104 files of `POSTA/` are
counted and nothing else: 26 addresses and 19 telephone numbers belonging to
people who in February 1997 wrote to a magazine hoping to swap floppy disks,
and who are now around fifty and never agreed to be indexed.

Nothing from `PIAZZA/` or `POSTA/` is reproduced anywhere in this repository, in
`docs/` or in `notes/`. The general-purpose scanners that would have walked into
them are named in [chapter 16](16-tools.md), with what was done about each.

The briefing's own count was 74 tel/fax occurrences in 11 files; this
measurement finds 73 in 10, from an independently written expression. The
difference is one match in one file and it is a property of the two regular
expressions, not of the disc. It is recorded rather than reconciled, because
reconciling it would mean tuning a pattern until it agreed with a number, which
is how a measurement stops being one.
