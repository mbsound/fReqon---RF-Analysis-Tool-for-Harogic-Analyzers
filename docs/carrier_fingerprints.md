# Carrier fingerprints: what the spec sheets say

Reference for fReqon's transmitter fingerprinting. Built from manufacturer spec
sheets and FCC equipment authorizations, not from measurements of real units, so
every value here still needs confirming against real transmitters.

**FCC emission designators** state a transmitter's *necessary bandwidth* plus its
modulation, e.g. `183KD1E` means 183 kHz, with `D` = amplitude and phase
(digital), `1` = one digital channel, and `E` = audio. Other letters below: `G` =
phase modulation, `F` = frequency modulation, `F3E` = analog FM audio, `7` = two or
more digital channels (multi-carrier/multiplexed), and `X` = other.

## Signatures

| System / mode | Bandwidth | Modulation | Channel plan | Time behaviour | Sources |
|---|---|---|---|---|---|
| **Shure Axient Digital** (AD1/AD2, ADX), Standard mode | 180–183 kHz (FCC `180KD1E`–`183KD1E`; ADX1 `182KG7D`) | Single-carrier digital | 350 kHz spacing; 17 per 6 MHz / 23 per 8 MHz; 25 kHz tuning steps | Continuous | AD1/AD2/ADX1 FCC grants; Axient Digital spec sheet |
| **Shure Axient Digital**, High Density (HD) mode | Not published; must be under 125 kHz to fit its spacing (estimate ~100 kHz) | Single-carrier digital | 125 kHz spacing; 47 per 6 MHz / 63 per 8 MHz | Continuous | Axient Digital spec sheet (spacing and latency 2.96 ms vs 2.08 ms) |
| **Shure ADPSM**: Multi-Channel Wideband (WMAS) | ~600 kHz (FCC `599KD7E`/`600KD7E`); Shure quotes an ~800 kHz carrier | OFDM, several stereo mixes per carrier | 28 per 6 MHz / 40 per 8 MHz | Continuous | ADTD/ADTQ FCC grants; Shure transmission-modes article |
| **Shure ADPSM**: Narrowband | Likely ~182 kHz (FCC `181KG7E`/`182KG7E`; which mode this designator covers isn't stated) | OFDM | 17 per 6 MHz / 23 per 8 MHz | Continuous | Shure article; ADTD/ADTQ grants |
| **Shure ADPSM**: SC Narrowband | Likely ~182 kHz | Single-carrier digital | 17 per 6 MHz / 23 per 8 MHz | Continuous | Shure article (latency 2.8 ms) |
| **Shure ADPSM**: Analog FM | ~100 kHz (FCC `96K5F7E`/`100KF7E`, probably this mode) | FM stereo multiplex, PSM1000-compatible: ±34 kHz nominal deviation, **19 kHz pilot** | 9 per 6 MHz / 11 per 8 MHz | Continuous; the spectrum moves with the audio | Shure article; PSM1000 spec sheet |
| **Shure ADPSM**: AD Standard / PTP | Same as Axient Digital Standard (~183 kHz) | Axient Digital protocol | 17 per 6 MHz | Continuous | Shure article |
| Shure PSM1000 (for comparison) | 126 kHz (FCC `126KF3E`) | FM stereo multiplex, ±34 kHz, 19 kHz pilot | | Continuous | P10T FCC grant; PSM1000 spec sheet |
| **Sony DWX** digital (DWT-B01/B30) | 192 kHz (DWT-B01 FCC `192KG1D`; B30 is certified under Part 15 with no designator) | Proprietary digital (phase modulation) | 375 kHz high-density plan; 25 kHz tuning steps | Continuous | DWT-B01 FCC grant; Sony DWT-B30 page |
| **Sennheiser Digital 6000**, Long Range | ~171–172 kHz (Digital 9000 is `171KF1W`/`172KG1W`; Long Range mode is the 9000 transmission) | Digital | 400 kHz equidistant grid | Continuous | SKM/SK 9000 FCC grants; Digital 6000 specs |
| **Sennheiser Digital 6000**, Link Density | Not published; under 200 kHz to fit its spacing | Digital | 200 kHz equidistant grid | Continuous | Digital 6000 specs |
| **Sennheiser Spectera** (WMAS) | 5.46–5.53 MHz in a 6 MHz channel (FCC `5M50D7X`/`5M53D7X` UHF, `5M46D7X` 1.4 GHz); 8 MHz channels in Europe | Multicarrier, **TDMA/TDD** | One block per 6/8 MHz TV channel; UHF 470–608 / 630–698 MHz, also 1.35–1.4 / 1.435–1.525 GHz | **Bursty**: one device transmits at a time, so the level flickers | Spectera SEK FCC grants; Spectera spec sheet and RF FAQ |
| **Wisycom transmitters** (MTP60/MTP61) | ~150 kHz wideband / ~100 kHz narrowband (stated by Wisycom) | Analog FM, mono: ±40/±56 kHz (WB), ±25/±35 kHz (NB) | | Continuous; moves with the audio | MTP60/MTP61 manuals |
| **Wisycom IEM** (MTK982) | ~150–200 kHz (estimate from deviation) | FM stereo multiplex: ±48 kHz (stereo preset), **19 kHz pilot**; mono ±56/±35 kHz | | Continuous; moves with the audio | MTK982 datasheet |
| ATSC digital TV (for exclusion) | ~5.4 MHz in a 6 MHz channel | 8-VSB, pilot 309.44 kHz above the lower edge | | Constant level | ATSC A/53 |

## What can tell them apart

1. **Width.** Groups that differ by 3 times or more are easy, even at coarse
   resolution:
   - ~5.5–7.5 MHz: Spectera or TV.
   - ~600–800 kHz: ADPSM Wideband.
   - ~100–200 kHz: everything else.

   Within the 170–195 kHz group (Axient Digital 183, ADX 182, ADPSM 182,
   Digital 6000 172, Sony 192), the differences are only 5–10%. That needs about
   1–2 kHz resolution and is never conclusive on width alone.
2. **Analog vs digital.**
   - Digital carriers have a stable, flat-topped spectrum with steep edges, whose
     width doesn't change with the audio.
   - Analog FM is rounded, and its width and shape change from sweep to sweep
     with the audio.
3. **Stereo pilot.** A line 19 kHz either side of the carrier marks stereo FM
   (ADPSM Analog FM, PSM1000, Wisycom IEM). Mono FM transmitters (Wisycom MTP)
   have none. Seeing it needs about 3 kHz resolution or better.
4. **Deviation.** Among stereo IEMs, Wisycom MTK982's ±48 kHz is wider than
   PSM1000/ADPSM's ±34 kHz.
5. **OFDM vs single carrier.** OFDM is flat with near-vertical edges;
   single-carrier digital has rounded (root-raised-cosine) shoulders. This
   separates ADPSM Narrowband from AD and SC Narrowband. It needs fine
   resolution.
6. **TDMA.** Spectera's level flickers between sweeps while TV is steady; TV
   also has its pilot.

## Not distinguishable from the spectrum

- **ADPSM in AD Standard/PTP mode** *is* the Axient Digital protocol. It looks
  like an Axient Digital microphone.
- **ADPSM SC Narrowband** is single-carrier digital at about the same width.
  It's likely indistinguishable from Axient Digital without decoding.
- **Axient Digital HD** vs **Digital 6000 Link Density**: neither bandwidth is
  published.

## Resolution available in fReqon

| Source | Resolution per carrier | Useful for |
|---|---|---|
| Main sweep, default 470–608 MHz | 50 kHz RBW (~35 kHz per point) | Width groups only |
| Main sweep, ≤15 MHz span | 10 kHz RBW | Width within ~10–20%; analog vs digital over time |
| MSCAN (Rapid Channel Monitor) | ~1 kHz (512-point FFT over ~490 kHz) | All spectral features, including pilots and edge shape |
| IQ capture (deep dive) | Arbitrary | Envelope statistics, FM demodulation (pilot, deviation), symbol rate, TDMA timing |

## How fReqon uses this

`RF_Recon_Modern/core/carrier_fingerprint.py`, shown in the Threats panel.

**Stage 1, automatic, from the sweep.** Every detected carrier is measured on
every sweep:

- widths at −6/−20/−26 dB and 99% occupied bandwidth, corrected for resolution;
- peakedness;
- top ripple;
- stereo pilot lines;
- level;
- extent, with gaps tolerated so ragged TDMA blocks still measure whole.

Labels refresh once a second as history accumulates. Peaks inside one wide block
(and its shoulders) are merged into a single entry. Confidence is capped by
resolution: 55% at >10 kHz, 70% at >4 kHz, 90% otherwise. Close candidates are
reported together ("A or B"), and at coarse resolution similar digital systems
are reported as a group ("Digital wireless ~180 kHz").

**Stage 1b, MSCAN, user-triggered.**

- **Fingerprint Carriers** dwells on the detected carriers (RMS detector, ~1 kHz
  resolution) for 3–12 s. It then returns to the sweep; the waterfall history is
  kept.
- **Use Analyzer B** runs this continuously on a second analyzer while
  Analyzer A keeps sweeping (Single or Independent topology).

**Stage 2, deep dive (not built yet).** A user-triggered IQ capture of one
carrier, for FM demodulation (pilot, deviation), envelope statistics and
symbol rate.

### Measured on synthetic signals

Each system was simulated from its spec: QAM with root-raised-cosine filtering,
OFDM, mono and stereo-multiplex FM driven by varying programme audio, and a
swept TDMA block. The results:

| System | Default sweep (35 kHz points) | Narrow span (10 kHz) | MSCAN (1 kHz) |
|---|---|---|---|
| Axient Digital | "Digital wireless ~180–200 kHz" | AD or ADPSM Narrowband | ✅ |
| Axient Digital HD | ✅ | ✅ | ✅ |
| ADPSM Narrowband (OFDM) | group | ADPSM NB or AD | ✅ |
| ADPSM Multi-Channel Wideband | ✅ | ✅ | ✅ (from the sweep; wider than the MSCAN span) |
| ADPSM Analog FM / PSM1000 | analog, ambiguous | ✅ or Wisycom NB | ✅ |
| Sony DWX | group | ✅ | ✅ |
| Sennheiser Digital 6000 | group | D6000 or ADPSM NB | ✅ |
| Wisycom IEM (MTK982) | stereo/analog ambiguous | analog, ambiguous | stereo IEM (named PSM1000; widths overlap) |
| Wisycom transmitter WB/NB | analog, ambiguous | ✅ or a close analog | ✅ (or tied with a close analog) |
| Sennheiser Spectera | ✅ (TDMA dropouts) | ✅ | (wider than MSCAN span; from the sweep) |
| Digital TV | "Wideband block (TV or WMAS)", steady | same | same |
| Unmodulated carrier | "Narrow carrier (unresolved)" | same | "Narrowband carrier, not wireless audio" |

These are synthetic results. Real transmitters will differ, especially in
programme-dependent FM width and in the spectral details of each digital mode;
the signature widths and thresholds should be revisited once real captures are
available.

## Sources

- [Shure Axient Digital specifications (Full Compass PDF)](https://www.fullcompass.com/common/files/84134-AxientDigitalSpecifications.pdf)
- [Shure: Axient Digital PSM transmission modes](https://www.shure.com/en-US/insights/axient-digital-psm-transmission-modes-versatile-solutions-for-every-application)
- [Shure PSM1000 spec sheet](https://content-files.shure.com/Pubs/PSM1000/PSM1000_Spec_Sheet.pdf)
- FCC grants (via [fccid.io](https://fccid.io)): Shure DD4AD1K53, DD4AD1G57, DD4AD2G57, DD4ADX1G57S, DD4ADTQG57, DD4ADTDG57, DD4P10TH22, DD4P9TH21; Sony AK8DWTB01, AK8DWTB30; Sennheiser DMOSK9000, DMOSKM9000, DMOSEKUHF, DMOSEK1G4
- [Sennheiser Digital 6000 EM 6000 product specification](https://assets.sennheiser.com/global-downloads/file/9714/SP_1192_v13.0_EM_6000_Product_Specification_EN.pdf)
- [Sennheiser Spectera base station specification](https://www.sennheiser.com/globalassets/digizuite/48695-en-spectera_basestation_product_specification_v1.2_en.pdf), [Spectera RF FAQ](https://help.sennheiser.com/hc/en-us/articles/27366758528018-Spectera-RF-FAQ)
- [Sony DWT-B30](https://pro.sony/en_IE/products/dwx-digital-series-transmitters/dwt-b30)
- [Wisycom MTK982 datasheet](https://wisycom.com/app/uploads/MTK982-en-b07.pdf), [Wisycom MTP60 datasheet](https://wisycom.com/app/uploads/MTP60-en-b09.pdf)
