# 10 — The Leader catalogue: a 1997 price list with the trade margin left in

*Measure: 715 files, 354,228,172 bytes, **72.4342 %** of everything a PC can
read on this disc. Three dBase III tables hold 221 products with fourteen fields
each, including both the retail price and the dealer price. 213 of the 221 have
assets. 26 have a video trailer, and those 26 files are 287,407,594 bytes —
**58.77 % of the entire disc**.*

```
python tools/census.py _work/iso
python tools/mov.py _work/iso/LEADER/CATALOGO/TRYOUT --recurse --summary
```

---

## Shape

| directory | files | bytes | what |
|---|---:|---:|---|
| `TRYOUT` | 26 | 287,407,594 | 23 QuickTime and 3 AVI trailers |
| `INFO` | 193 | 46,793,520 | one spoken description per product, `.WAV` |
| `IMAGES` | 212 | 5,355,500 | one box shot per product, `.TIF` |
| `SYSTEM` | 18 | 1,765,642 | the Q+E / Pioneer ODBC stack |
| `REQUISIT` | 189 | 35,967 | one system-requirements paragraph per product |
| `REVIEW` | 50 | 15,840 | one press quotation per product |
| `VIDEO` | 1 | 2,182,682 | `HOLDER.MOV`, the placeholder |
| top level | 26 | 10,681,427 | `CATAL.TBK`, `LCAT.EXE`, the ToolBook 3.0 runtime, three `.DBF` |

Everything is addressed by a six-digit product code. `100742.TIF`,
`100742.WAV`, `100742.TXT` — box shot, voice-over and requirements for one
product, keyed by the same number in three directories and in the database.
**213 distinct product codes** appear across the asset folders.

## The database

Three dBase III tables, read by their public format:

```
CLASSIC.DBF   ver 0x03  updated 1996-12-05   51 records x 190 B, 14 fields
FAMILY.DBF    ver 0x03  updated 1997-02-10   74 records x 192 B, 14 fields
GAMES.DBF     ver 0x03  updated 1997-02-10   96 records x 180 B, 14 fields
```

221 live records, none deleted. Two of the three were last written on
**1997-02-10** — the same day the magazine started pulling its images off the
web server ([chapter 07](07-clocks.md)). The catalogue and the magazine were
being finished in parallel, four days out.

The fourteen fields, identical in all three tables:

| field | type | what it holds |
|---|---|---|
| `TITABBR`, `TITOLO` | C | short and full title |
| `CODICE` | C(9) | the product code that keys the assets |
| `EDITORE` | C | publisher |
| `GENERE` | C | genre |
| `FORMATI` | C | `CD-MPC`, `Floppy`, … |
| `SWITA`, `MANITA` | C(2) | software in Italian / manual in Italian |
| `DISP` | C | availability |
| **`PRPUB`** | N(9) | **price to the public** |
| **`PRRIV`** | N(9) | **price to the dealer** |
| `SUPPORTO` | C | media |
| `VIDEO` | C | whether a trailer exists |
| `DEMO` | C(2) | whether a playable demo exists |

## The prices

All 221 records carry both numbers, in lire:

| | min | max | mean |
|---|---:|---:|---:|
| `PRPUB` — retail | 39,900 | 149,000 | 86,829 |
| `PRRIV` — trade | 25,700 | 111,800 | 57,516 |

The dealer pays a mean of **66.24 %** of the shelf price, which is a trade
margin of 33.76 %. That number was never meant to leave the company: `PRRIV` is
what Leader charges a shop, and it is sitting in an unencrypted dBase table on
eighty thousand copies of a newsstand magazine.

It is not personal data and it is not a secret of a person — it is a company's
commercial terms, published by accident in 1997 and long since irrelevant — so
it is measured and reported here like any other field of the object. Individual
titles' prices are not tabulated; the aggregate is the finding.

## Who Leader sold

```
publishers:  Mondadori N.M. 24 · Sierra 22 · Virgin 20 · Knowledge Adventure 14
             Electronic Arts 12 · Warner 12 · Interplay 10 · Philips 9
             Eidos 8 · Medialab 7
genres:      Conosci 34 · Avventura 34 · Azione 22 · Educa 20 · Strategia 18
             Simulazione 13 · Sportivo 12 · Storie 12
```

**137 of 221 products are flagged as Italian-language software** and 84 are not.
The largest single publisher in an Italian distributor's catalogue is the
magazine's own parent, Mondadori New Media, with 24 titles — and the disc does
not mention that anywhere.

The genre distribution is a mid-nineties CD-ROM shop and not a games shop:
*Conosci* (reference) ties with *Avventura* at 34 each, and education and
"stories" together outweigh action.

## Two engines for one catalogue

`CATAL.TBK` is 3,074,962 bytes and begins `03 4A 42 4F` — a ToolBook book, run
by `MTB30RUN.EXE`, Asymetrix Multimedia ToolBook 3.0, with a fourteen-DLL
Q+E/Pioneer ODBC stack underneath it to read the three `.DBF` files.

`LCAT.EXE` is 4,492,357 bytes and its version resource reads **`Projector for
Windows Release 5.0`** — a Macromedia Director 5 projector.

One catalogue, two authoring systems, in the same directory. `TBLOAD.EXE`
(7,232 B, *ToolBook version loader*) and `TAPPO.EXE` (8,973 B, whose version
string is the Italian word *`Attendere...`* — "please wait") are the glue.

## The trailers are the disc

26 files in `TRYOUT/`, 287,407,594 bytes, **58.77 % of the whole object**:

  * **23 QuickTime**, all Cinepak, 1,377 seconds of declared duration;
  * **3 AVI** — `EF2000.AVI` (Cinepak, 240×180, 12 fps, 141.25 s),
    `TOPGUN.AVI` (Cinepak, 12 fps, 98.25 s) and `GK2A.AVI` (**Indeo 3.2**,
    320×240, 10 fps, 79.00 s);
  * the six largest files on the disc, and eleven of the twelve largest.

They are trailers for *other companies'* products — Casper, EF2000, Top Gun,
Mortal Kombat 3, Descent, Pinball, the Louvre, Cézanne. Thirty of the 221
database records have a `VIDEO` entry.

**This is what the disc's 73.65 % of "recorded reality" actually is**: not the
content of a work, but the advertising of a mail-order shop. See
[chapter 11](11-media.md) for the arithmetic and for what it does to the
collection's column.

## `HOLDER.MOV`

2,182,682 bytes, 17.40 seconds, Cinepak, alone in its own directory called
`VIDEO`. A holder — the clip that plays when a product has no trailer. It is the
only file in `LEADER/CATALOGO/VIDEO/` and it is 0.45 % of the disc.
