# One file-only layer on exact full live Config and ordered RootFS. No native build.
ARG BASE
FROM ${BASE}
ARG REVISION
LABEL org.opencontainers.image.revision=$REVISION
# The runner seals a five-file payload context from exact pushed source only.
COPY --chmod=0644 payload/ /app/
