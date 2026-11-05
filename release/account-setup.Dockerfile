# Supply the release owner's exact immutable composite image; never infer a mutable base.
ARG BASE
FROM ${BASE}
ARG SOURCE_REVISION
COPY --chmod=0644 static/connectors.js static/unified.js static/unified.css /app/static/
LABEL org.wizardos.messenger.account-setup-revision="${SOURCE_REVISION}"
