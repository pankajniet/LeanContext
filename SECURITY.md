# Security Policy

## Reporting a vulnerability

Please report security issues privately via GitHub Security Advisories
("Report a vulnerability" on the repository's Security tab) rather than a public issue.
We aim to acknowledge reports within a few days.

## Scope and design notes

LeanContext runs locally and in-process. It has no network calls in its core path, no use of
`eval`/`exec`, and no required third-party dependencies. A few things worth knowing:

- **Fail-open by design.** Any error, unknown content type, or low fidelity score returns the
  original text unchanged. LeanContext never raises into your agent loop.
- **No data leaves the machine.** Reducers operate on the strings you pass in. Optional
  integrations (telemetry, gateways) only do what you wire up.
- **Untrusted/oversized input.** Reducers are linear-time and use simple regexes, but if you
  process very large or adversarial payloads you can cap work with
  `leancontext.CONFIG.max_input_chars` (anything larger passes through untouched).
- **Content store (paging).** `ContentStore` can persist originals to disk when given a `root`.
  Treat that directory like any cache of potentially sensitive content.
