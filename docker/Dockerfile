# syntax=docker/dockerfile:1
#
# WebLinked, containerised for headless Linux. Built from this checkout, with the
# repository root as the build context:
#
#   docker build -f docker/Dockerfile -t weblinked .
#
# Until October 2026 this lived in stoatworks-labs/weblinked-docker and cloned main at
# build time. That `git clone` layer's cache key was the command text, never what
# main pointed at, so every CI run was a cache hit and the published :edge stayed
# on main as of 22 August 2026 (just after v1.0.1) through six releases. COPY
# layers are keyed on the files themselves, so a source change always reaches it.
#
# What is in here: NDI, OMT and the HTTP/OSC control API. What is not, and why:
#
#   DeckLink, AJA   want a card and a kernel driver on the host.
#   shared          Syphon is macOS and Spout is Windows; Linux has neither.
#   screen          needs X11 and a GPU-attached display.
#   kms             needs /dev/dri, DRM master and a monitor on the server: a
#                   board driving its own screen, which is the release tarball's
#                   job rather than a container's. Built OFF so the image's
#                   compiled_backends says what it can actually do.
#   stream          needs an ffmpeg binary at run time, and shipping one would put
#                   an H.264/AAC encoder in a published image — a codec-licensing
#                   question docs/06-ndi-distribution.md says is ours to answer.
#                   Built OFF rather than compiled in and always failing.
#
# Chromium renders through SwiftShader on the CPU, deliberately. It makes the
# image portable across hosts with no GPU passthrough, and a dashboard is nowhere
# near heavy enough to want one: measured 50.1 ticks/sec at 1080p50 with zero
# dropped ticks on a 24-core host.
#
# libndi is NOT baked in, and must never be. It is dlopen'd at run time by design,
# and its licence requires the distributor to forbid modification and reverse
# engineering — which an MIT-licensed public image cannot do. The release
# installers can carry it because they carry an EULA; this image has none. Mount
# it instead; see docker/README.md.

# ---------------------------------------------------------------------------
# CEF, in its own stage so editing a source file does not re-download 315 MB.
# The version and the linux64 sha1 are read from cmake/FetchCEF.cmake, so a CEF
# bump there reaches the image, and one that forgets the linux64 sha1 fails here
# rather than building against an unverified download.
# ---------------------------------------------------------------------------
FROM ubuntu:24.04 AS cef
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates bzip2 \
    && rm -rf /var/lib/apt/lists/*
COPY cmake/FetchCEF.cmake /tmp/FetchCEF.cmake
RUN set -eux; \
    ver="$(sed -n 's/^set(WEBLINKED_CEF_VERSION "\([^"]*\)".*/\1/p' /tmp/FetchCEF.cmake)"; \
    sha="$(sed -n 's/^set(_weblinked_cef_sha1_linux64 *"\([0-9a-f]\{40\}\)").*/\1/p' /tmp/FetchCEF.cmake)"; \
    [ -n "$ver" ] || { echo "no WEBLINKED_CEF_VERSION in cmake/FetchCEF.cmake" >&2; exit 1; }; \
    [ -n "$sha" ] || { echo "no linux64 sha1 pinned in cmake/FetchCEF.cmake" >&2; exit 1; }; \
    url_ver="$(printf '%s' "$ver" | sed 's/+/%2B/g')"; \
    curl -fSL -o /tmp/cef.tar.bz2 \
      "https://cef-builds.spotifycdn.com/cef_binary_${url_ver}_linux64_minimal.tar.bz2"; \
    echo "${sha}  /tmp/cef.tar.bz2" | sha1sum -c -; \
    mkdir -p /cef; \
    tar -xjf /tmp/cef.tar.bz2 -C /cef --strip-components=1; \
    rm /tmp/cef.tar.bz2

# ---------------------------------------------------------------------------
# Build. The -dev packages are not optional decoration: libcef.so carries
# DT_NEEDED entries for the whole Chromium runtime, and the link fails with a
# wall of "undefined reference to dbus_/snd_/atk_/NSS_" without them. libdrm-dev
# was in this list for libcef.so before the KMS output existed, and stays although
# KMS is built OFF.
# ---------------------------------------------------------------------------
FROM ubuntu:24.04 AS build
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake ninja-build python3 pkg-config ca-certificates \
        libx11-dev libxext-dev libxrender-dev libxi-dev libxtst-dev \
        libxcomposite-dev libxdamage-dev libxfixes-dev libxrandr-dev \
        libnss3-dev libatk1.0-dev libatk-bridge2.0-dev libcups2-dev \
        libdrm-dev libgbm-dev libxkbcommon-dev libpango1.0-dev libcairo2-dev \
        libasound2-dev libdbus-1-dev libglib2.0-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=cef /cef /cef

# Only what the build reads, in roughly the order it changes least to most.
# .dockerignore at the repository root admits the same set and nothing else.
WORKDIR /src
COPY CMakeLists.txt ./
COPY cmake/ cmake/
COPY third_party/ third_party/
COPY tests/ tests/
COPY src/ src/

RUN cmake -S . -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCEF_ROOT=/cef \
        -DWEBLINKED_WITH_SCREEN=OFF \
        -DWEBLINKED_WITH_SHARED=OFF \
        -DWEBLINKED_WITH_DECKLINK=OFF \
        -DWEBLINKED_WITH_AJA=OFF \
        -DWEBLINKED_WITH_KMS=OFF \
        -DWEBLINKED_WITH_STREAM=OFF
RUN cmake --build build -j"$(nproc)"

# The suite links weblinked_core only and needs no display. If it fails the
# image does not get built, which is the point of running it here.
RUN ./build/Release/weblinked_tests

# CEF finds its resources next to the executable, and SET_CEF_TARGET_OUT_DIR()
# sits above add_executable(weblinked …) so the binary lands in build/Release/
# beside them. If that ever stops being true the image would start a browser
# that renders nothing, so refuse to build it instead.
RUN test -x build/Release/weblinked

# ---------------------------------------------------------------------------
# Runtime.
# ---------------------------------------------------------------------------
FROM ubuntu:24.04

# Not decoration: GHCR only links a package to its repository — and so only
# lets it be made public — when it can tell which repository built it. The
# workflow's metadata step sets the same labels; these are for a local build.
LABEL org.opencontainers.image.source="https://github.com/stoatworks-labs/weblinked" \
      org.opencontainers.image.description="WebLinked: renders a URL to NDI, headless" \
      org.opencontainers.image.licenses="MIT"

RUN apt-get update && apt-get install -y --no-install-recommends \
        libx11-6 libxext6 libxrender1 libxi6 libxtst6 \
        libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libxcb1 \
        libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 \
        libdrm2 libgbm1 libxkbcommon0 libpango-1.0-0 libcairo2 \
        libasound2t64 libdbus-1-3 libglib2.0-0t64 libexpat1 libuuid1 \
        ca-certificates fonts-liberation fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /src/build/Release /app
COPY docker/docker-entrypoint.sh /docker-entrypoint.sh
COPY docker/healthcheck.sh /healthcheck.sh
RUN chmod +x /docker-entrypoint.sh /healthcheck.sh
WORKDIR /app

# no_sandbox is set in code (src/browser/cef_app.cpp), so the setuid helper is
# dead weight; the test binary has done its job at build time.
RUN rm -f /app/chrome-sandbox /app/weblinked_tests

# Where a mounted NDI runtime is looked for. libndi.so.6 is dlopen'd, so its
# absence costs the NDI output and nothing else — the process still starts and
# reports the backend unavailable.
ENV LD_LIBRARY_PATH=/app:/opt/ndi/lib

EXPOSE 7654/tcp 7655/udp

# A script rather than an inline command, because it has to follow
# WEBLINKED_BIND, WEBLINKED_PORT and WEBLINKED_TOKEN: the inline version this
# replaced asked 127.0.0.1:7654 with no token, so setting the token the README
# insists on left the container permanently "unhealthy".
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD ["/healthcheck.sh"]

# The entrypoint supplies the headless switches and translates WEBLINKED_* env
# vars into flags, so a container UI with nothing but an environment-variable
# form can still configure this. Explicit arguments still win over env vars.
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD []

# Host networking is not a convenience here — NDI discovery is mDNS, and a
# bridge network hides the sender from every receiver on the LAN:
#
#   docker run -d --name weblinked --network host \
#     -v /path/to/ndi/lib:/opt/ndi/lib:ro \
#     ghcr.io/stoatworks-labs/weblinked:edge \
#     --url 'https://grafana.example/d/abc?kiosk&refresh=10s' \
#     --format 1080p50 --ndi=Grafana
