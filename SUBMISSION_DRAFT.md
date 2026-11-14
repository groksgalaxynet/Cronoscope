# Cronoscope Submission Draft

## Project description

Cronoscope is a browser-based astronomy exploration project that brings
genuine SPHEREx observations, celestial coordinates, local wavelength context,
and observations made at different times into one careful visual experience.
It helps people inspect what an astronomical image and its metadata can show,
while keeping the limits of that evidence visible.

The project uses public NASA/IPAC IRSA SPHEREx releases and frozen JPL Horizons
prediction context. The full local application can inspect retained FITS
products, celestial WCS, WCS-WAVE context, pixel values, quality arrays, and
bounded two-epoch comparisons. The GitHub Pages demonstration is an offline,
labelled static companion: it does not make archive requests, convert PNG
colors into measurements, or replace the full FITS viewer.

Comparing observations across wavelength and time can highlight a predicted
location, changing context, or a research candidate. It cannot by itself
confirm motion, variability, object identity, or a discovery. Cronoscope
keeps that distinction in its interface and documentation. No validated blind
moving-object discovery is claimed.

Cronoscope is a solo, AI-assisted project. The creator directed the research,
testing, product decisions, data-provenance checks, and scientific limits.

## Technical summary

- Python scientific backend for controlled discovery, FITS normalization,
  celestial WCS/WCS-WAVE context, and two-epoch comparison support.
- Local browser interface for genuine retained FITS inspection and bounded
  comparison workflows.
- GitHub Pages static demonstration using packaged, labelled displays with no
  runtime archive, Horizons, detector, or API dependency.
- Provenance, release/detector/time labels, source credits, and explicit
  non-detection limits embedded in the experience.

## Submission links

- **Project:** `https://github.com/groksgalaxynet/Cronoscope`
- **Demonstration:** GitHub Pages URL pending owner-authorized deployment and
  post-deployment verification. Do not enter a speculative URL as operational.
