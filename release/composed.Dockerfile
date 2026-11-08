# Five file-only layers on exact full live Config and ordered RootFS. No native build.
ARG BASE
FROM ${BASE}
ARG REVISION
LABEL org.opencontainers.image.revision=$REVISION
# The runner seals a five-file payload context from exact pushed source only.
# Copy only files: recursive --chmod=0644 removes base directory traversal bits.
COPY --chmod=0644 payload/unified.py /app/unified.py
COPY --chmod=0644 payload/static/unified.js /app/static/unified.js
COPY --chmod=0644 payload/static/unified.css /app/static/unified.css
COPY --chmod=0644 payload/static/connectors.js /app/static/connectors.js
COPY --chmod=0644 payload/plumbing/connectors-provenance.json /app/plumbing/connectors-provenance.json
