# Overlay on the proven full live Config + ordered RootFS; no native build.
ARG BASE
FROM ${BASE}
ARG REVISION
LABEL org.opencontainers.image.revision=$REVISION
COPY --chmod=a+rX static/unified.js static/unified.css static/connectors.js /app/static/
