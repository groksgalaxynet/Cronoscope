# Cronoscope static demonstration

This directory is the self-contained GitHub Pages artifact for Cronoscope's
offline demonstration. It uses only relative paths and browser-native HTML,
CSS, JavaScript, and packaged assets. No Python server, archive retrieval,
credentials, or live API is required.

## Local preview

Serve this directory with any static-file server and open it below the intended
project subpath (for example, `/cronoscope/`). The page must not be opened with
`file://`, because the browser blocks JSON fetches in that context.

## Scientific boundaries

- Target imagery is a labelled static display derived from retained SPHEREx
  Level-2 cutouts, not a raw FITS viewer or calibrated source-flux tool.
- The coordinate form matches only retained five-decimal Horizons endpoint
  coordinates. It does not search footprint coverage or retrieve new data.
- NASA-target image pairs have no validated registered difference product in
  this artifact. The browser intentionally does not derive one.
- WCS-WAVE text is wavelength context, not a source spectrum. The separately
  labelled spectral explorer retains its own provenance, units, flags, and
  limitations.
- Neither image context, blink, predicted position, nor research comparison is
  a confirmed moving-object detection or variability claim.

## GitHub Pages workflow

`.github/workflows/deploy-static-pages.yml` deploys only this directory. It
excludes supplied research-export archives and unused duplicate artwork from
the Pages artifact. The workflow is present but does nothing until the owner
authorizes a push or a manual workflow dispatch in GitHub.
