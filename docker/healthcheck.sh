#!/bin/bash
# The image's HEALTHCHECK: healthy means the control API answers /api/state
# with a 200.
#
# It reads the same WEBLINKED_* variables the entrypoint does, because the
# inline check this replaced asked 127.0.0.1:7654 with no token — so binding to
# a tailnet address, moving the port, or setting the token the README insists
# on all left a working container reported "unhealthy". A port or bind given as
# a command-line flag rather than a variable is still invisible to it.
#
# bash rather than sh for /dev/tcp: the image carries no curl, and adding one
# for this would be the only reason it was there.
set -u

host="${WEBLINKED_BIND:-127.0.0.1}"
case "$host" in
  0.0.0.0) host=127.0.0.1 ;;  # every interface includes loopback
  ::|"[::]") host=::1 ;;
esac
port="${WEBLINKED_PORT:-7654}"

exec 3<>"/dev/tcp/${host}/${port}" || exit 1

if [ -n "${WEBLINKED_TOKEN:-}" ]; then
  printf 'GET /api/state HTTP/1.0\r\nAuthorization: Bearer %s\r\n\r\n' "$WEBLINKED_TOKEN" >&3
else
  printf 'GET /api/state HTTP/1.0\r\n\r\n' >&3
fi

# "HTTP/1.1 200 OK" — the status code is the second field of the first line.
read -r -t 4 _ status _ <&3 || exit 1
[ "$status" = "200" ]
