# D-1 container image: Debian-based jellyfin-ffmpeg + the auto-reel-ng engine.
#
# The title-card renderer (auto_reel_ng/render/title) draws with Cairo + Pango via
# PyGObject, resolving fonts by family name through fontconfig (never a hardcoded
# path). That needs the Cairo/Pango runtime libraries, the Pango GObject-introspection
# typelib, a bundled default font family (DejaVu Sans), and a populated fontconfig
# cache so the family resolves at render time.
#
# A dev host that runs the renderer or its has-fonts-marked tests needs the same
# system libraries installed (the tests skip cleanly when they are absent).
FROM jellyfin/jellyfin-ffmpeg:latest

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-gi \
        python3-gi-cairo \
        gir1.2-pango-1.0 \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        fonts-dejavu \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN python3 -m pip install --no-cache-dir --break-system-packages .

ENTRYPOINT ["python3", "-m", "auto_reel_ng"]
