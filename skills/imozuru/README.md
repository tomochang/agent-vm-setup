# imozuru — fetch.py and the private-address guard

This skill is adapted from upstream imozuru v2.0.0
(https://github.com/MaryCache/imozuru; see `UPSTREAM`) with local
changes. Only the skill text, the theory reference, and the
standalone `scripts/*.py` helpers ship here; the guide-site assets
and guide-screenshot generators are omitted.

## What fetch.py does

`scripts/fetch.py <sources_dir> <name> <url>` downloads one source
text, verifies it looks like real body text (not a 404 page, login
wall, or HTML wearing a PDF extension), and saves it under
`<sources_dir>/`. It prints one tab-separated line: `OK <name>
<saved-file> <chars> <first-line>` or `FAIL <name> <reason>`.
It uses only the Python standard library plus the external tools
it shells out to by list-argument (`pdftotext`, `pdftoppm`,
`tesseract`, `yt-dlp` where installed); it never runs a shell.

## The private-address guard (SSRF protection)

Before fetching, `fetch.py` resolves the target host and refuses
the fetch when the address is private, loopback, link-local, or
otherwise reserved (checked with `ipaddress`). This is the guard
that keeps a research fetcher from being pointed at internal
services. Keep it on.

## The IMOZURU_ALLOW_PRIVATE operator option

Some VMs resolve every public DNS name to an egress-proxy range
that the guard classifies as private, so `fetch.py` refuses even
ordinary public URLs there. For that environment only, the
operator may set `IMOZURU_ALLOW_PRIVATE=1` per invocation:

```sh
IMOZURU_ALLOW_PRIVATE=1 python3 scripts/fetch.py <sources_dir> <name> <url>
```

This is an operator decision, not an agent default: the agent
must not set it on its own. Even with the flag, fetch only the
public URLs from the research at hand — never internal hosts.
If the flag is not needed in your environment, do not set it.
