# Build from the Messenger repository root on the admitted Linux/amd64 worker.
# Full pinned libsignal + Go build; never reuse an unmodified Signal binary.
FROM rust:1-alpine@sha256:f432d4b8663fbc50b29e33846bf6a1fb9f17f142023598899d641cddf57c6b22 AS signal-rust
RUN apk add --no-cache git make cmake protoc musl-dev g++ clang-dev protobuf-dev
WORKDIR /build
RUN git init . && git remote add origin https://github.com/mautrix/signal.git && \
    git fetch --depth=1 origin d129f0ecc6bd29cfb5e54b18e025bd0c8a20a4bf && git checkout --detach FETCH_HEAD && \
    test "$(git rev-parse HEAD)" = d129f0ecc6bd29cfb5e54b18e025bd0c8a20a4bf && \
    git submodule update --init --depth=1 && \
    test "$(git -C pkg/libsignalgo/libsignal rev-parse HEAD)" = 4beb029d8a941f81e7d9c6d8af1ed25a677569a8
ENV CARGO_BUILD_JOBS=2
RUN cd pkg/libsignalgo/libsignal && RUSTFLAGS="-Ctarget-feature=-crt-static" RUSTC_WRAPPER="" \
    cargo build --locked -p libsignal-ffi --profile=release && \
    mkdir /out && cp target/*/libsignal_ffi.a /out/libsignal_ffi.a

FROM golang:1-alpine3.24@sha256:b8c9b82affbbb82a020bbcf998dad2ba9516944ac7e883524642a481a9505e9c AS signal-go
RUN apk add --no-cache git ca-certificates build-base olm-dev zlib-dev patch
WORKDIR /build
RUN git init . && git remote add origin https://github.com/mautrix/signal.git && \
    git fetch --depth=1 origin d129f0ecc6bd29cfb5e54b18e025bd0c8a20a4bf && git checkout --detach FETCH_HEAD && \
    test "$(git rev-parse HEAD)" = d129f0ecc6bd29cfb5e54b18e025bd0c8a20a4bf && \
    git fetch --depth=1 origin refs/tags/v0.2610.0:refs/tags/v0.2610.0 && \
    test "$(git rev-parse 'v0.2610.0^{commit}')" = d129f0ecc6bd29cfb5e54b18e025bd0c8a20a4bf
COPY --from=signal-rust /out/libsignal_ffi.a /build/libsignal_ffi.a
ENV LIBRARY_PATH=/build GOMAXPROCS=2 GOFLAGS=-p=2
COPY plumbing/signal-bridge/converter-fixture_test.go pkg/msgconv/wizard-converter-fixture_test.go
RUN mkdir -p /proof && WIZARD_EXPECT_ALBUM=0 WIZARD_FIXTURE_OUT=/proof/baseline.json \
    go test -count=1 -v ./pkg/msgconv -run '^TestWizardConverterFixture$' > /proof/baseline-go.log 2>&1 || (cat /proof/baseline-go.log; exit 1)
COPY plumbing/signal-bridge/albums.patch /albums.patch
RUN git apply --check --unidiff-zero /albums.patch && git apply --unidiff-zero /albums.patch
RUN WIZARD_EXPECT_ALBUM=1 WIZARD_FIXTURE_OUT=/proof/candidate.json \
    go test -count=1 -v ./pkg/msgconv/... ./pkg/connector/... > /proof/candidate-go.log 2>&1 || (cat /proof/candidate-go.log; exit 1)
RUN go vet ./pkg/msgconv/... ./pkg/connector/... && ./build-go.sh
RUN sha256sum mautrix-signal > /proof/binary.sha256 && go version -m mautrix-signal > /proof/go-version.txt

FROM dock.mau.dev/mautrix/signal@sha256:39afa721aa69472b2e91c75bd7d81a739e47f7e480fc0ff5ac8247af28eb2d0a AS runtime
COPY --from=signal-go /build/mautrix-signal /usr/bin/mautrix-signal
COPY --from=signal-go /proof /usr/share/wizard-signal-albums
RUN ldd /usr/bin/mautrix-signal && /usr/bin/mautrix-signal --version
LABEL org.opencontainers.image.source="https://github.com/humanitylabs-org/wizard-messenger" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.wizard.signal.upstream="d129f0ecc6bd29cfb5e54b18e025bd0c8a20a4bf" \
      org.wizard.signal.patch="native-albums1"
