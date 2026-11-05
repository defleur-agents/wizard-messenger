# Overlay on the proven full live Config + ordered RootFS; no native build.
# Carries exactly the verified Signal-album Messenger files, nothing from account/attachment work.
ARG BASE
FROM ${BASE}
ARG REVISION
LABEL org.opencontainers.image.revision=$REVISION
COPY --chmod=a+rX unified.py /app/unified.py
COPY --chmod=a+rX static/unified.js /app/static/unified.js
COPY --chmod=a+rX plumbing/connectors-provenance.json /app/plumbing/connectors-provenance.json
