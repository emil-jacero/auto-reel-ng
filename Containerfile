# D-1 container image: Debian trixie + the pinned jellyfin-ffmpeg + the auto-reel-ng engine + the
# built web client. `compose.yaml` builds it as `localhost/auto-reel-ng:compose` (D-17).
#
# LOCAL ONLY. This image MUST NOT be pushed to a registry: jellyfin-ffmpeg8 8.1.3 bundles
# libfdk_aac, against D-1's "never bundle the nonfree/fdk-aac variant in a published image", and a
# published image also needs D-1's GPL source offer. Publishing waits for that blocker (HLD §4.12).
#
# The base is not a jellyfin-ffmpeg image because none exists: `jellyfin/jellyfin-ffmpeg:latest`
# is on no registry. Jellyfin ships jellyfin-ffmpeg only as .deb packages, so it comes from the
# Jellyfin apt repo, pinned by JELLYFIN_FFMPEG_VERSION. Trixie, because requires-python >= 3.13
# (bookworm ships 3.11). The package bundles its own libva and the radeonsi/iHD/i965 VA drivers
# under /usr/lib/jellyfin-ffmpeg, so no host VA driver or Mesa package is installed.
#
# The title-card renderer (auto_reel_ng/render/title) draws with Cairo + Pango via
# PyGObject, resolving fonts by family name through fontconfig. That needs the Cairo/Pango
# runtime libraries and the Pango GObject-introspection typelib. The fonts are NOT a system
# package: the bundled set under fonts/ (DejaVu Sans, the default, plus eight OFL families,
# each with its license text beside the files) is copied to /app/fonts and the engine points
# fontconfig at /app/fonts/fonts.conf itself (D-22), so the image and a dev host render the
# same glyphs. The build fails if a registered family does not resolve (verify_bundled_fonts).
#
# A dev host that runs the renderer or its has-fonts-marked tests needs the same
# system libraries installed, but no font (the tests skip cleanly when they are absent).
ARG JELLYFIN_FFMPEG_VERSION=8.1.3-1-trixie

# Stage 1: the web client (web/README.md's build, in the same node:22 image the dev loop uses).
FROM docker.io/library/node:22 AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: the runtime.
FROM docker.io/library/debian:trixie-slim
ARG JELLYFIN_FFMPEG_VERSION
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && install -d /etc/apt/keyrings \
    && curl -fsSL https://repo.jellyfin.org/jellyfin_team.gpg.key -o /etc/apt/keyrings/jellyfin.asc \
    && printf 'Types: deb\nURIs: https://repo.jellyfin.org/debian\nSuites: trixie\nComponents: main\nArchitectures: amd64\nSigned-By: /etc/apt/keyrings/jellyfin.asc\n' \
        > /etc/apt/sources.list.d/jellyfin.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        "jellyfin-ffmpeg8=${JELLYFIN_FFMPEG_VERSION}" \
        python3 \
        python3-pip \
        python3-gi \
        python3-gi-cairo \
        gir1.2-pango-1.0 \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        fontconfig \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# The engine already resolves /usr/lib/jellyfin-ffmpeg as its bundled ffmpeg/ffprobe; on PATH it
# also gives accel's devices.vainfo_name() the bundled vainfo, so the worker names the GPU.
ENV PATH=/usr/lib/jellyfin-ffmpeg:${PATH}

WORKDIR /app
# Dependency layer: pyproject.toml plus stubs only, so a source edit does not re-download every
# wheel. pycairo and PyGObject are satisfied by the Debian packages above (nothing is compiled).
COPY pyproject.toml /app/
RUN touch README.md && mkdir auto_reel_ng && touch auto_reel_ng/__init__.py \
    && python3 -m pip install --no-cache-dir --break-system-packages -e .

# The bundled title-card fonts, named on their own (the `COPY . /app` below carries them too) so
# the dependency on fonts/ is visible here. After the dependency layer: a font edit does not
# re-download every wheel.
COPY fonts/ /app/fonts/

# Editable install: the .pth points at /app, so the sources copied here are what gets imported,
# and api/app.py web_dist_dir() (<package>/../../web/dist) resolves to /app/web/dist with no code
# change. /app must therefore stay the source tree of this checkout.
COPY . /app
COPY --from=web /web/dist /app/web/dist

# A build whose bundled fonts do not resolve (a missing file, a family fontconfig cannot see,
# a face of another weight) fails here, not at the first render. The engine configures its own
# fontconfig from /app/fonts before Pango is used.
RUN python3 -c "from auto_reel_ng.render.title import verify_bundled_fonts; verify_bundled_fonts()"

# The console script; `python3 -m auto_reel_ng` fails (the package has no __main__.py).
ENTRYPOINT ["auto-reel"]
