ARG DEBIAN_RELEASE
FROM debian:${DEBIAN_RELEASE}
ARG DEBIAN_RELEASE

# bullseye is end-of-life: its packages (incl. security updates) are only on archive.debian.org.
RUN if [ "$DEBIAN_RELEASE" = bullseye ]; then \
        sed -i 's|http://deb.debian.org|http://archive.debian.org|' /etc/apt/sources.list; \
    fi

# kodi-repository-kodi provides the official addon repository (needed to install inputstreamhelper etc.).
# libgl1-mesa-dri, libegl-mesa0, mesa-va-drivers: Mesa GL/EGL and VAAPI drivers for the host GPU.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        kodi \
        kodi-inputstream-adaptive \
        kodi-eventclients-kodi-send \
        kodi-repository-kodi \
        libgl1-mesa-dri \
        libegl-mesa0 \
        mesa-va-drivers \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Guards against a moving release (sid) shipping another Kodi major version than the box promises.
ARG KODI_MAJOR
RUN version="$(dpkg-query -W -f='${Version}' kodi)" \
    && major="${version#*:}" \
    && major="${major%%.*}" \
    && if [ "$major" != "$KODI_MAJOR" ]; then \
        echo "kodi-box: expected Kodi major '$KODI_MAJOR', but debian:$DEBIAN_RELEASE ships kodi $version" >&2; \
        exit 1; \
    fi
ENV KODI_MAJOR=${KODI_MAJOR}

# The container runs as the (arbitrary) host uid, so HOME must be writable for everyone.
RUN mkdir -m 1777 /kodi-home
ENV HOME=/kodi-home \
    PYTHONDONTWRITEBYTECODE=1

COPY advancedsettings.xml /usr/local/share/kodi-box/advancedsettings.xml
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
