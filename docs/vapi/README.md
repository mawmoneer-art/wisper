# Vapi docs snapshot

Local, agent-readable copy of the Vapi documentation, mirroring what
https://docs.vapi.ai/llms.txt and https://docs.vapi.ai/llms-full.txt serve.

| File | What it is |
|------|------------|
| `llms.txt` | Index: every doc page with title, canonical URL, one-line summary, plus every REST endpoint grouped by resource. Start here. |
| `llms-full.txt` | Full markdown body of every doc page (about 2 MB). Grep it, or load a section by its `Source:` URL. |
| `llms-changelog.txt` | Dated product changelog, newest first. |
| `openapi.json` | The Vapi REST API OpenAPI 3 spec, copied verbatim from upstream. |
| `SNAPSHOT.json` | Provenance: upstream commit, date, page counts. |

## Why a local copy

The hosted `docs.vapi.ai` is not reachable from every build or agent
environment. The docs source is public at https://github.com/VapiAI/docs
(a Fern site), so this snapshot is generated straight from that repo instead
of scraped from the site. Page bodies are the raw MDX, so Fern components
such as `<Card>` and `<Steps>` appear as tags. The prose and code samples are
intact.

## Refreshing

```sh
git clone --depth 1 https://github.com/VapiAI/docs /tmp/vapi-docs
python3 scripts/build-vapi-llms-docs.py /tmp/vapi-docs docs/vapi
```

Requires Python 3 and PyYAML. Check `SNAPSHOT.json` for the upstream commit
the current files were built from.
