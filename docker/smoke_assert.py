#!/usr/bin/env python3
"""Assert that a running container is actually rendering.

Reads WebLinked's /api/state on stdin. A green `docker build` only proves the
image assembled; CEF failing to initialise headless is a *runtime* failure, and
this is what catches it.

    python3 docker/smoke_assert.py [--version 1.2.0] < state.json

With --version it also checks the engine reports that version, which is what
proves the image was built from this checkout rather than from a cached layer:
the image this replaced reported a version six releases old for two months
while every build of it went green.

Lives in a file rather than inline in the workflow because a `python3 -c`
heredoc inside a YAML block scalar has to stay indented, and Python does not
forgive that — the first version of this broke the workflow file itself.
"""

import argparse
import json
import sys

# Built OFF on purpose (see docker/Dockerfile). If one of these turns up, the
# image's documented contract and its contents have drifted apart.
NOT_IN_THE_IMAGE = ("kms", "stream", "screen", "decklink", "aja", "shared")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="the version the engine must report")
    args = parser.parse_args()

    state = json.load(sys.stdin)

    pacing = state["pacing"]
    source = state["source"]
    backends = state["compiled_backends"]

    print(
        f"version: {state.get('version')} | format: {state['format']} "
        f"| ticks: {pacing['ticks']} | paints: {source['paints']} "
        f"| dropped: {pacing['dropped_ticks']}"
    )
    print(f"backends: {backends}")

    if args.version and state.get("version") != args.version:
        print(
            f"::error::the engine reports version {state.get('version')!r}, "
            f"but this checkout is {args.version!r}"
        )
        return 1

    if not state["running"]:
        print("::error::the engine reports itself not running")
        return 1

    # A clock that never ticked means CEF came up but nothing drives it.
    if pacing["ticks"] < 1:
        print("::error::the clock never ticked")
        return 1

    # One paint is the initial paint of a static page. Zero means the browser
    # never rendered anything, which is the headless failure we are hunting.
    if source["paints"] < 1:
        print("::error::the browser never painted a frame")
        return 1

    # The image is pointless if the NDI backend did not compile in.
    if "ndi" not in backends:
        print("::error::the NDI backend is missing from this build")
        return 1

    unexpected = [b for b in backends if b in NOT_IN_THE_IMAGE]
    if unexpected:
        print(f"::error::built OFF in docker/Dockerfile, yet compiled in: {unexpected}")
        return 1

    print("ok: headless render path is alive")
    return 0


if __name__ == "__main__":
    sys.exit(main())
