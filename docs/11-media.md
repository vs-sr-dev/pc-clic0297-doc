# 11 — The media: 1 h 34 m 38 s, read from headers, and 73.65 % of a disc that is mostly advertising

*Measure: 252 media files declare 5,678.08 seconds between them. Not one frame
was decoded and not one sample was played. Every figure comes from a header the
file writes about itself, using each format's public definition, and each tool
was validated against one specimen before being run on its population.*

```
python tools/mov.py _work/iso --recurse --summary
python tools/avi.py _work/iso/LEADER/CATALOGO/TRYOUT/EF2000.AVI
python tools/audio.py _work/iso --by-dir
```

---

## The total

| format | files | bytes | declared duration |
|---|---:|---:|---:|
| RIFF WAVE | 195 | 65,425,804 | 3,577.92 s = **59 m 37.92 s** |
| QuickTime | 32 | 244,216,303 | 1,636.18 s = **27 m 16.18 s** |
| RIFF AVI | 3 | 49,506,782 | 318.50 s = **5 m 18.50 s** |
| Smacker | 22 | 405,712 | 145.48 s = **2 m 25.48 s** |
| **total** | **252** | **359,554,601** | **5,678.08 s = 1 h 34 m 38.08 s** |

Plus 22 `.SND` files, 637,667 bytes, in `MAGDEMO/SAMPLES/`. They are headerless
signed 8-bit PCM — the first bytes are sample values, not a chunk tag — and
**they declare no sample rate**, so their duration is *not derived* and is not
in the total above. At the rate the rest of that stratum uses they would be
about a minute; that is an inference and it is not counted.

Counting bytes rather than seconds, and including the `.SND`:

```
recorded reality  (.MOV .AVI .WAV .SND .SMK)   360,192,268 B = 73.6533 %
still images      (.TIF .JPG .GIF .LBM .PCX .BBM .BMP)  30,096,122 B = 6.1542 %
```

## QuickTime

32 files, all read through the public atom layout, `mvhd` for the time scale and
duration, `stsd` for the codec.

```
files                 : 32
fast-start (moov 1st) : 7
not fast-start        : 25
total duration        : 1636.18 s = 27.27 min
```

**Cinepak (`cvid`) is 30 of the 32** and every byte that matters. The exceptions
are `MUSEO/MAIN.MOV`, which is `rle`, and five files in `VILLE/SPEAK/` which
have an audio track and **no video track at all** — QuickTime used as an audio
container, 101.23 seconds of Italian narration in `.MOV` files.

Audio inside the movies splits three ways and the split is chronological:

| audio codec | files | `mvhd` creation dates |
|---|---:|---|
| `ima4` | 7 | 1995-10-11 → 1995-10-14 |
| `raw ` | 9 | 1996-02-17 → 1996-05-14 |
| `twos` | 11 | 1994-12-24 → 1996-10-18 |

The seven IMA-compressed files were all made in a **four-day window in October
1995** and they are the only seven that are fast-start. One supplier, one
session, one set of export settings — visible only because QuickTime writes its
own creation date and nobody has changed it since.

The oldest `mvhd` on the disc is `PAWS.MOV` at 1994-10-28 and the newest is
`MUSEO/MAIN.MOV` at 1996-12-03.

## AVI

Three files, all in `LEADER/CATALOGO/TRYOUT/`, all with an index, all
interleaved, and all three declare their RIFF size **exactly**:

| file | bytes | frame | fps | frames | duration | video | audio |
|---|---:|---|---:|---:|---:|---|---|
| `EF2000.AVI` | 20,783,962 | 240×180 | 12.000 | 1,695 | 141.25 s | `cvid` | PCM 22,050 Hz, 2 ch, 8 bit |
| `TOPGUN.AVI` | 15,002,312 | — | 12.000 | 1,179 | 98.25 s | `cvid` | PCM |
| `GK2A.AVI` | 13,720,508 | 320×240 | 10.000 | 790 | 79.00 s | **`iv32`** | PCM 22,050 Hz, 1 ch, 16 bit |

The prediction was that the AVI codec would *not* be the QuickTime codec. Two of
three are Cinepak, the same as the movies; only `GK2A.AVI` is Indeo 3.2. Three
files, two codecs, and the reason is that they came from three different
publishers' press kits.

`EF2000.AVI` is **8 bits per sample in stereo** — an unusual choice, and one the
`strf` chunk states outright rather than leaving to be guessed.

## RIFF WAVE

195 files, 100 % valid, and every one is uncompressed PCM with a `fmt ` chunk
followed by a `data` chunk and nothing else:

```
   encoding      ch       Hz  bits    count
   PCM            1    11025     8      165
   PCM            1    22050    16       13
   PCM            1    11127     8       12
   PCM            1    22050     8        3
   PCM            2    22050    16        2
```

  * **165 of 195 are 8-bit mono at 11,025 Hz** — the cheap end of 1996 PC audio,
    and the format of Leader's 193 product voice-overs.
  * **12 files declare 11,127 Hz.** Not 11,025. That is not a standard rate and
    it is not a typo the same way twelve times: it is what you get when a rate
    is derived from a hardware divisor rather than chosen from a list, the same
    class of artefact as the 22,222.22 Hz found in `pc-landsoflore-doc`. The
    twelve are recorded and the divisor is not derived.
  * The two 16-bit stereo files are `VILLE/MUSIC/A.WAV` (11,100,716 B) and
    `INTRO.WAV` (7,531,568 B) — 211.25 seconds between them, and 3.81 % of the
    disc for two files of background music.

By directory: `LEADER/CATALOGO/INFO` holds 193 files and 3,366.67 s;
`VILLE/MUSIC` holds 2 files and 211.25 s. **Fifty-six minutes of the disc's
hour of audio is a shop reading its own catalogue aloud.**

## Smacker

22 files, 405,712 bytes, all `SMK2`, all in `MAGDEMO/PITSMACK/`:

```
FMAN.SMK      64x72    107 frames  rate -8333 -> 12.00 fps   8.92 s
FUELMAN.SMK  128x128   106 frames  rate -8333 -> 12.00 fps   8.83 s
WINGB.SMK    128x128   106 frames  rate -8333 -> 12.00 fps   8.83 s
…
W3MAN.SMK     64x72     66 frames  rate -6666 -> 15.00 fps   4.40 s
```

Twenty-one at 12 fps and one at 15, 64×60 to 128×128, 3.92 to 9.25 seconds each.
They are pit-crew animations for a racing demo: a man with a jack, a man with
fuel, a man with a wheel. 145.48 seconds of mechanics, in total, at postage-stamp
size.

## Frame sizes

The prediction was that the median frame width would be 240 or less. The three
AVIs give 240, 320 and one unread; the Smackers give 64 and 128; the QuickTime
files' `tkhd` dimensions were not extracted by `mov.py` and were **not
measured**, so the claim cannot be settled from what was run. It is recorded as
unresolved rather than argued from the two thirds of the population that is
convenient.

## What the 73.65 % is

This is where the collection's *recorded reality* column meets a problem it has
not had before.

```
2014   82.93 %   video shot with a camera
1994   88.11 %   speech recorded by actors
1994   77.81 %   speech recorded by actors
2000   46.44 %   film rendered
2026   17.46 %   sound and film
1987    0        Infocom
1997   73.65 %   <-- this object
```

On twenty-four monographic objects, *the recorded reality of the work* and *the
recorded bytes of the medium* were the same thing, because the medium carried
one work. Here they are not, and the gap is not marginal:

  * **287,407,594 bytes — 58.77 % of the disc — are 26 trailers in
    `LEADER/CATALOGO/TRYOUT/`**, advertising products made by Sierra, Virgin,
    Warner, Eidos and twenty other companies;
  * another **46,793,520 bytes — 9.57 %** — are a shop's spoken product
    descriptions;
  * together, **68.34 % of the object is a retailer's sales material**.

Of the 73.65 %, **92.8 % belongs to the catalogue**. The remaining 5.3 % of the
disc is *Ville Venete*'s music and narration and a racing demo's pit crew.

So the honest reading is that **the column does not apply to this object as a
work, because this object is not a work.** Issue 11 reached the same conclusion
by a different route and left the column at a figure with a caveat; the
preceding session put the column under pressure and refused to widen it,
adding a second column rather than diluting the first.

The same discipline applies here. The figure is **73.6533 %**, it is real, it is
reproducible, and *what it measures is the weight of one shop's advertising on a
disc that a magazine gave away*. Written without that sentence it is not a
measurement, it is a decoration. It goes in the index row with the sentence
attached, and [chapter 14](14-against-clic11.md) says what the row does with it.
