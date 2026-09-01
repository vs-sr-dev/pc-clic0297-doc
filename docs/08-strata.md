# 08 — Nine strata: six suppliers, five runtimes, and nobody in charge

*Measure: nine top-level bodies of software, sized from the ISO tree, dated from
the directory records, and attributed from strings inside their own binaries.
No two of them share a build toolchain. Two of them ship different versions of
the same authoring runtime. The publisher's own contribution is the ninth
largest.*

```
python tools/census.py _work/iso
python tools/pecensus.py _work/iso
python tools/buildpaths.py _work/iso
```

---

## The nine

Shares are of the 489,034,354 bytes of the 2,818 files a PC can see.

| # | stratum | files | bytes | share | dates of its records | built with |
|---|---|---:|---:|---:|---|---|
| 1 | `LEADER/CATALOGO` | 715 | 354,228,172 | 72.4342 % | 1979–1997 | ToolBook 3.0 + Director 5 + Q+E ODBC |
| 2 | `VILLE` | 364 | 51,595,303 | 10.5504 % | 1996 | ToolBook 4.0 + Paradox Engine |
| 3 | `LEADER/DATA` + `LEADER/TOMB` | 46 | 47,619,223 | 9.7374 % | 1996 | Watcom C 10.5, DOS/4GW, HMI |
| 4 | `MAGDEMO` | 584 | 10,839,135 | 2.2164 % | 1980–1996 | DOS/4GW, Smacker |
| 5 | `IMG` | 511 | 5,753,408 | 1.1765 % | 1997 | WS_FTP |
| 6 | `DOWN` | 1 | 5,585,256 | 1.1421 % | 1996 | Microsoft, linker 3.10 |
| 7 | `MUSEO` | 4 | 5,212,705 | 1.0659 % | 1979, 1996 | Director 5 |
| 8 | `LEADER/QTW` | 2 | 3,102,720 | 0.6345 % | 1996 | Apple, linkers 2.55 / 5.60 |
| 9 | `NUMERI`+`PAG`+`RETE`+`PRE`+root | 573 | 4,012,668 | 0.8205 % | 1997 | BBEdit, a text editor, and FTP |

Nine parcels. **The magazine's own is 0.82 %** and the eighth largest of nine.

## The evidence that these are separate parcels, not sections

A disc assembled as one project by one team leaves one set of fingerprints. This
one leaves at least six, and they contradict each other.

**Two versions of one runtime, in two folders.**

```
LEADER/CATALOGO/MTB30RUN.EXE   620,864 B   Asymetrix Multimedia ToolBook 3.0
VILLE/MTB40RUN.EXE             807,296 B   Asymetrix Multimedia ToolBook 4.0
```

Different sizes, different sha1s, fourteen support DLLs each, and the two sets
do not overlap by a single file. Nobody chose to ship both; two suppliers each
brought their own and the disc took what it was given. `LEADER/CATALOGO` even
carries **its own second copy** of `TBDC.DLL` — once at the top level and once
in `SYSTEM/`, byte for byte identical.

**Two copies of the Kodak Photo CD library, in two strata.** `PCDLIB.DLL`
(83,520 B) and `PCDXBMP.DLL` (2,336 B) appear in both `LEADER/CATALOGO` and
`VILLE`, identical. Two suppliers, one middleware vendor, no coordination.

**Two DOS extenders.** `LEADER/TOMB/DOS4GW.EXE` is 265,396 bytes and
`MAGDEMO/DOS4GW.EXE` is 254,556. Same product, two versions, shipped by two
different game publishers, sitting eleven directories apart.

**Two clocks that were never set.** Every pre-1993 directory record on the disc
belongs to `MAGDEMO` or to `MUSEO`+`LEADER/CATALOGO/INFO`, and to nothing else
([chapter 07](07-clocks.md)). Fifty-four other directories have correct dates.

**Three project roots inside the binaries**, on three different machines
([chapter 13](13-paths.md)): `c:\ccode\tombraid` and `c:\watcom10.5` (Core
Design, Derby), `d:\hook` (Asymetrix, Bellevue), `d:\clic-cd` (the magazine,
Milan).

## Which arrived whole

The question issue 11 asked of its eleven bodies. Here:

| stratum | whole? |
|---|---|
| `LEADER/CATALOGO` | **Yes, and then some.** 221 database records, 213 of them with assets, plus 26 trailers. It also brought a link map, a `.BAK` file, and a browser cache it did not need. |
| `VILLE` | **Yes.** A ToolBook application, its runtime, its Paradox engine, 331 images and two `.WAV` files totalling 18.6 MB. |
| Tomb Raider | **The data, whole; the product, not.** All sixteen levels, two of four cut scenes, no FMV, no music. [Chapter 09](09-tombraider.md). |
| `MAGDEMO` | **Yes, as a demo.** `F1.EXE`, its extender, its Smacker animations, its fonts, and a Paint Shop Pro thumbnail cache somebody left behind. |
| `DOWN/MSIE301.EXE` | **Yes** — one self-extracting archive, 5,585,256 bytes, and nothing else. |
| `MUSEO` | **Yes.** A Director projector, a movie, a QuickTime file, four files. |
| `LEADER/QTW` | **Yes**, both installers, 16- and 32-bit. |
| `IMG` | **Yes, and it recorded its own arrival** — the FTP log that fetched it is still in the folder ([chapter 07](07-clocks.md), clock D). |
| the magazine | **Yes**, and it is 549 HTML files, 253 JPEGs and 247 GIFs. |

Nothing on this disc is truncated. Everything on it is complete for what it is,
and one thing — Tomb Raider — is complete as *data* while being incomplete as a
*product*, which is a distinction only a byte-level measurement can make.

## Internet Explorer, twice, eight months apart

The one direct comparison the two CLIC discs allow at the stratum level.

| | CLIC 02/97 | CLIC 11 |
|---|---|---|
| product | Internet Explorer **3.01** | Internet Explorer **4.0** build 1712 |
| delivery | **one** self-extracting archive | **121** cabinets |
| bytes | 5,585,256 | ~65 MB |
| signatures | none | 121 Authenticode blobs |
| share of disc | 1.1421 % | 10.3 % |

Same vendor, same product line, same magazine, eight months apart, and the
delivery mechanism changed completely — from a single `.EXE` a reader runs to a
signed, cabinet-based installer with a certificate on every part. That is not a
fact about CLIC; it is a fact about 1997, and it took two discs from one
publisher to see it.

## The runtimes, and what they say about the year

Five engines, none of them the disc's:

  * **Asymetrix Multimedia ToolBook**, 3.0 and 4.0 — the authoring tool of
    Italian CD-ROM publishing in the mid-nineties, here twice.
  * **Macromedia Director 5**, as `Projector for Windows Release 5.0`, in
    `LCAT.EXE` and `MUSEO/ORSAY.EXE`. Issue 11's own browser was Director too.
  * **Rational Systems DOS/4GW**, twice, under two games.
  * **Apple QuickTime for Windows**, shipped as installers so that the 32 `.MOV`
    trailers will play.
  * **HMI Sound Operating System** (Human Machine Interfaces Inc., 1995), three
    `.386` drivers and a setup utility that enumerates **eighteen sound cards**
    by port, IRQ and DMA — the shape of PC audio before Windows drivers.

Of 75 executables on the disc, **two are 32-bit PE**: Microsoft's Internet
Explorer installer and Apple's QuickTime installer. Everything else is 16-bit NE
or real-mode DOS. In February 1997, eighteen months after Windows 95 shipped,
the only 32-bit code on an Italian cover disc came from Redmond and Cupertino.
