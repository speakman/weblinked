# WebLinked in Docker

> **AI-assisted packaging.** Created with [Claude](https://claude.com/claude-code)
> (Anthropic), directed and reviewed by a human author. The image builds and
> renders real pages headless, and WebLinked's unit suite runs inside it as a
> build step; every build is smoke-tested in CI before it is pushed. **The NDI
> output has never been received from this image**, because libndi is not in it
> and is not ours to ship. [What is actually verified](#what-is-actually-verified)
> is specific about which is which.

> [!WARNING]
> **This is designed to run purely inside a [Tailscale](https://tailscale.com) tailnet (or
> another private network you trust end to end). Do not expose it to the public internet.**
> The control API has no authentication until you set `--token`, and `POST /api/script`
> **runs arbitrary JavaScript in the rendered page** — an unauthenticated port here is
> remote code execution in a browser on your network, not merely a feed someone can
> retune. Its security has **not** been independently reviewed by a human. This image
> binds `0.0.0.0` by default and runs with host networking, so it is on every interface
> the server has. Set `WEBLINKED_BIND` to your tailnet address, set a token, and keep it
> off the open internet. No reverse proxy, no port forward, no "it's fine, it has a
> password".

**A URL in. NDI out. No display, no card, no desktop.**

The container for the part of WebLinked that makes sense on a server: point it at
a dashboard, a scoreboard or a clock, and it becomes an NDI source your vision
mixer, decoder or recorder can take.

```bash
docker run -d --name weblinked --network host \
  -v /mnt/user/appdata/weblinked/ndi:/opt/ndi/lib:ro \
  ghcr.io/stoatworks-labs/weblinked:edge \
  --url 'https://grafana.example/public-dashboards/abc123' \
  --format 1080p50 --ndi=Grafana
```

Or with Compose: [`docker-compose.yml`](docker-compose.yml) beside this file.

## The image, and its old name

| Tag | What |
|---|---|
| `ghcr.io/stoatworks-labs/weblinked:edge` | `main`, rebuilt on every push that touches the build |
| `ghcr.io/stoatworks-labs/weblinked:X.Y.Z`, `:X.Y` | a release, from its `v*` tag |
| `ghcr.io/stoatworks-labs/weblinked:sha-xxxxxxx` | one exact commit |

Until October 2026 the packaging lived in its own repository,
[weblinked-docker](https://github.com/stoatworks-labs/weblinked-docker), and the
image was **`ghcr.io/stoatworks-labs/weblinked-docker:edge`**. That name is no
longer updated: its `:edge` is frozen at a build of WebLinked as of 22 August 2026 (just after v1.0.1). Change an
existing compose file or Unraid template to `ghcr.io/stoatworks-labs/weblinked:edge`.

One thing the move fixed: the old image cloned `main` at build time, and that
layer was always a cache hit, so its `:edge` quietly stayed on WebLinked as of
22 August 2026 (just after v1.0.1). If you pulled it after that, you were not
running what you thought. The new image is built from the checkout, and carries
the version it was built from in a label:

```bash
docker inspect --format '{{ index .Config.Labels "com.stoatworks.weblinked.version" }}' \
  ghcr.io/stoatworks-labs/weblinked:edge
```

---

## What is in here, and what cannot be

| Output | In the image | Why |
|---|---|---|
| **NDI** | Yes (needs a mounted runtime) | The point of the exercise |
| **OMT** | Yes | Compiled in, but has never been tested against any receiver |
| Preview + HTTP/OSC control | Yes | The control page is the whole UI |
| DeckLink, AJA | **No** | SDI wants a card and a kernel driver on the host |
| Syphon / Spout | **No** | macOS and Windows respectively; Linux has no equivalent |
| Fullscreen screen output | **No** | Needs X11 and a GPU-attached display, which a server has not got |
| KMS (Linux, no X) | **No** | Built off. It needs `/dev/dri`, DRM master and a monitor on the server itself — a board driving its own screen, which the Linux release tarball does without a container in the way |
| RTMP/SRT stream | **No** | Built off. It needs an `ffmpeg` binary at run time, and shipping one would put an H.264/AAC encoder in a public image, a codec-licensing question we would rather not answer by accident. Run the release build where ffmpeg is installed if you need it |

`compiled_backends` in `/api/state` lists exactly what this build contains;
asking for an output that is not there fails with
`output kind '…' was not compiled into this build`.

Chromium renders through **SwiftShader on the CPU**, deliberately — no GPU
passthrough, no `/dev/dri`, nothing to arrange on the host. A dashboard is
nowhere near heavy enough to want a GPU.

## The NDI runtime is not in this image, and you have to supply it

`libndi` is loaded with `dlopen` at run time, by design — WebLinked never links
it. Its licence permits redistribution only where the distributor's own terms
forbid modification and reverse engineering, which MIT cannot impose — so
**baking it into a public image would be a licence violation, not a packaging
shortcut.** (The release installers can carry it because they carry an EULA; this
image has none. See [docs/06-ndi-distribution.md](../docs/06-ndi-distribution.md).)

Without it, the container still starts, still serves the control page, and
simply reports the NDI backend unavailable. To get NDI:

1. Download the **NDI SDK for Linux** from [ndi.video](https://ndi.video/for-developers/ndi-sdk/)
   and accept their licence yourself. It is free, and gated behind an email.
2. Take `libndi.so.6` (and the symlinks beside it) out of `lib/x86_64-linux-gnu/`.
3. Put them in a directory on the host and mount it at `/opt/ndi/lib`:

```bash
-v /mnt/user/appdata/weblinked/ndi:/opt/ndi/lib:ro
```

`LD_LIBRARY_PATH` in the image already includes that path. Confirm it took —
before a show rather than after, because an unavailable backend is a running
container that produces nothing. `compiled_backends` will list `ndi` either way;
what tells you is whether the NDI output carries an `error`:

```bash
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:7654/api/state \
  | grep -o '"error":"[^"]*"'
```

Nothing printed means no output reported a fault. A missing runtime prints
`NDI runtime not found (libndi.so.6)` and how to get one.

## Host networking is not optional for NDI

**NDI discovery is mDNS.** On Docker's bridge network the sender is invisible to
every receiver on the LAN — it does not error, it just never appears. Use
`--network host`, or run an NDI Discovery Server and point both ends at it.

On host networking the container binds the host's ports directly: **7654/tcp**
for the control page and API, **7655/udp** for OSC. Change them with `--port`
and `--osc-port` (or `WEBLINKED_PORT`, `WEBLINKED_OSC_PORT`) if something else
already has them.

### WebLinked's own advertisement is not in this image

WebLinked advertises its control API as `_weblinked._tcp`, so rookery and the
Companion module can find it. On Linux that registration goes through
avahi-daemon over D-Bus, and **this image is built without avahi**, so it does
not advertise: find it by address. The log says so at startup —
`control: mDNS unavailable: this build has no avahi support` — which is expected,
not a fault. `WEBLINKED_MDNS=0` turns the attempt off and the message with it.

(The weblinked-docker README used to say that mounting the host's avahi socket
would make discovery work. It could not have: that image had no avahi support
either, and avahi-client talks to the daemon over the D-Bus system bus, not that
socket. Handing a container the host's system bus is a bigger grant than this
feature is worth, so it has not been added.)

### Keeping it on the tailnet

Host networking means the control port is on **every** interface the server has,
including whatever faces your LAN. Two things narrow that, and you want both:

- **`WEBLINKED_BIND`** — a literal address to bind, e.g. `100.64.0.5`. There is
  no interface-name form: WebLinked's `--bind` takes an address, so use the
  tailnet IP. Because host networking puts the container in the host's network
  namespace, the host's `tailscale0` address is directly bindable; Unraid's
  per-container Tailscale toggle also works.
- **`WEBLINKED_TOKEN`** — required on every HTTP request once set, as
  `Authorization: Bearer <token>` or `?token=<token>`. Set it even on a tailnet,
  because `/api/script` is arbitrary code execution in the page.

The healthcheck follows `WEBLINKED_BIND`, `WEBLINKED_PORT` and `WEBLINKED_TOKEN`,
so setting them does not turn the container "unhealthy". It cannot see a port or
bind given as a command-line flag — use the variables if you rely on it.

A container on the default bridge network cannot see the host's `tailscale0` at
all — but bridge networking breaks NDI discovery anyway, so that combination is
not one to reach for here.

## Pointing it at Grafana

Grafana's own auth will not follow an offscreen browser that cannot be typed
into, so give it a URL that needs no login. In order of preference:

- **A public dashboard** — Dashboard → Share → Public dashboard. Read-only, one
  dashboard, no server-wide change. This is the one to use.
- **Anonymous viewer access** (`GF_AUTH_ANONYMOUS_ENABLED=true`,
  `GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer`) if the Grafana is on a trusted network
  and you would rather not mint links per dashboard.

Add `&kiosk` to drop Grafana's chrome, and `&refresh=10s` to keep the panels
moving. WebLinked repeats the last frame between changes, so a slow refresh
costs nothing in output pacing — the feed stays at rate either way.

## Configuration

Everything is a command-line flag, appended after the image name; see
[docs/00-overview.md](../docs/00-overview.md) and `--help`. The ones that matter
here:

| Flag | Does |
|---|---|
| `--url <url>` | The page. Default `about:blank` |
| `--format <spec>` | `1080p50`, `720p59.94`, `1920x1080i25`. Default `1080p50` |
| `--ndi[=name]` | NDI sender name. Default `WebLinked` |
| `--omt[=name]` | OMT sender name |
| `--alpha` | Send BGRA with the page's alpha intact |
| `--port <n>` | Control HTTP port. Default 7654 |
| `--token <secret>` | Require a token on every HTTP request |
| `--cache <dir>` | Persist cookies and storage. Give each instance its own |
| `--name <text>` | What this instance calls itself. Default: host and port |
| `--no-mdns` | Do not try to advertise (see above) |

The environment variables the entrypoint understands map one to one onto those,
for container UIs that offer nothing but a variable form:

| Variable | Flag |
|---|---|
| `WEBLINKED_URL` | `--url` |
| `WEBLINKED_FORMAT` | `--format` |
| `WEBLINKED_NDI_NAME` | `--ndi` |
| `WEBLINKED_OMT_NAME` | `--omt` |
| `WEBLINKED_PORT` | `--port` |
| `WEBLINKED_OSC_PORT` | `--osc-port` |
| `WEBLINKED_TOKEN` | `--token` |
| `WEBLINKED_CACHE` | `--cache` |
| `WEBLINKED_NAME` | `--name` |
| `WEBLINKED_BIND` | `--bind`, default `0.0.0.0` |
| `WEBLINKED_ALPHA=true` | `--alpha` |
| `WEBLINKED_NO_AUDIO=true` | `--no-audio` |
| `WEBLINKED_MDNS=0` | `--no-mdns` |

Variables become flags *before* anything you pass explicitly, so an explicit flag
always wins.

The entrypoint already supplies `--ozone-platform=headless`, `--use-gl=angle`,
`--use-angle=swiftshader`, `--bind` and `--no-settings`. The first three are what
make Chromium render with no display at all; without them it exits with
`Missing X server or $DISPLAY`.

## Unraid

The Community Applications template is [`unraid/weblinked.xml`](../unraid/weblinked.xml)
in this repository. CA reads templates only from
[stoatworks-unraid](https://github.com/stoatworks-labs/stoatworks-unraid), whose
`scripts/gen-templates.mjs` copies this one across as it is. A port, mount or
variable changed here has to be changed in that file too, and it only reaches CA
when stoatworks-unraid's templates are next regenerated.

## Building it yourself

From the root of a WebLinked checkout — the build context is the whole
repository, and [`.dockerignore`](../.dockerignore) narrows it to what the build
reads:

```bash
docker build -f docker/Dockerfile -t weblinked .
```

About 6 minutes on a 4-vCPU CI runner from a cold cache, and ~4 GB of scratch
space: it downloads the CEF distribution
pinned in `cmake/FetchCEF.cmake` (315 MB, checked against its sha1), compiles
WebLinked and CEF's wrapper, and **runs the unit tests as a build step** — a
failing suite fails the build. The result is ~1.9 GB, most of it Chromium.

To build a release rather than `main`, check out its tag first.

## What is actually verified

**On every CI build** ([`.github/workflows/docker.yml`](../.github/workflows/docker.yml)),
before anything is pushed: the unit suite passes inside the builder; the
container starts headless with a token set; the engine reports running, ticking
and painting, at the version of the checkout; NDI is compiled in and the
backends built off are absent; the preview returns a correctly sized 480×270
frame; and the healthcheck passes. That is what
[`smoke_assert.py`](smoke_assert.py) and the workflow check; the first run's output
is in §39 of [docs/04-verification.md](../docs/04-verification.md).

**Measured once, on the image this replaced** (WebLinked as of August 2026, on a
24-core Unraid host at 1080p50) and not yet repeated on this one:

- **50.1 ticks/sec, 0 dropped ticks**, 289 µs clock lateness.
- **97% of ticks carried a fresh paint** on a full-screen `requestAnimationFrame`
  animation; the rest repeated the previous frame, which is what SwiftShader
  costs on a pathological page. A dashboard is far lighter.
- Real pages render correctly — fonts, gradients, web CSS, 0 console errors.
- `WEBLINKED_BIND=127.0.0.1` refuses connections from outside.

Not verified, and you should assume nothing:

- **No NDI receiver has ever seen output from this image.** No libndi, no test.
  The mount path, the soname (`libndi.so.6`) and `LD_LIBRARY_PATH` are read off
  the source rather than demonstrated. NDI from the *release* Linux build is
  verified against an independent receiver; from this image it is not.
- **OMT has never been tested against a receiver** anywhere in the project.
- Audio rides along with the frames but has not been checked here.
- `frames_overwritten` climbed roughly in step with `frames_published` on the
  old image, which under external pacing should stay near zero. It may be a
  counter that means something different from what its name suggests; it has
  not been chased down.

## If something is wrong

| Symptom | Cause |
| --- | --- |
| **No NDI source appears anywhere** | Either the runtime is not mounted — check the NDI output's `error` in `/api/state` — or bridge networking is hiding the mDNS. |
| **NDI reports unavailable** | The library is not mounted at `/opt/ndi/lib`, or is not `libndi.so.6`. |
| **rookery or Companion cannot discover it** | Expected: this image does not advertise. Add it by address. |
| **The container shows unhealthy** | The control port or bind was set by flag rather than by variable, so the healthcheck is asking the wrong place. |
| **Frames are repeated on a heavy page** | CPU rendering. That is the trade for needing nothing on the host. |

---

MIT, matching WebLinked itself. NDI® is a registered trademark of Vizrt NDI AB
(<https://ndi.video>); this image neither includes nor distributes any part of the
NDI SDK.
