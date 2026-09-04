# Local HTTP security

Beads Map is a single-user desktop-style tool delivered through a loopback HTTP server. Its controls are designed to stop an unrelated website from reading its API or causing local repository/catalog changes through the browser. They do not turn the process into a service safe for a shared or hostile machine.

**One-minute summary:** the server binds only to IPv4 loopback, validates every request's `Host`, rejects API requests carrying a different `Origin`, and requires both an exact same-origin `Origin` and a random per-launch capability for every state-changing request. The capability is delivered only in the no-store app document, kept in memory for that process lifetime, and returned in a custom request header. No CORS origin is granted.

## 1. Threat model

The protected assets are Beads metadata, the repository catalog and its view preferences, repository paths, and the native folder-picker action. The relevant attacker is JavaScript or markup on an unrelated webpage opened in the same browser while Beads Map is running.

The principal browser attacks considered are:

- sending a form or `fetch()` request to a predictable loopback port;
- using DNS rebinding so an attacker-controlled hostname later resolves to loopback;
- embedding the app and inducing clicks;
- reading API responses cross-origin or interpreting them as another resource type.

Beads Map does not claim to protect against malicious software running as the same user, a browser extension with broad privileges, browser compromise, an attacker who can modify the installed package, or arbitrary command execution in the selected repository. Such actors can read process memory, make loopback requests, alter files, or invoke `bd` directly.

## 2. Enforced request boundary

Every routed application request must contain exactly one `Host` matching either `127.0.0.1:<actual-port>` or `localhost:<actual-port>`. This uses the real bound port, including automatic fallback ports. A DNS-rebound hostname therefore fails before routing even if it resolves to `127.0.0.1`.

For `/api/*`, any supplied `Origin` must exactly equal `http://<validated-host>`. State-changing `POST` and `DELETE` requests must supply that exact origin; missing, opaque (`null`), duplicated, or different origins are rejected. Read-only API requests without `Origin` remain available to local diagnostic clients, while cross-origin browser reads receive no CORS permission.

At process start, Beads Map generates a cryptographically strong random capability. The server inserts it into the no-store HTML response, and the frontend removes its bootstrap meta element after reading it. The value is sent only as `X-Beads-Map-Capability` on state-changing requests; it is never put in a URL, catalog file, cookie, browser storage, or application log. The server compares it in constant time. Restarting Beads Map invalidates the previous capability.

This capability is additional to—not a replacement for—the existing repository-selection, snapshot-hash, issue-ID, body-size, and five-field metadata allowlists.

## 3. Browser response policy

Responses are marked `no-store` and include:

- a Content Security Policy limiting scripts, styles, images, and connections to what the dependency-free page needs, disabling forms and objects, and forbidding framing;
- `Cross-Origin-Resource-Policy: same-origin`;
- `Referrer-Policy: no-referrer`;
- `X-Content-Type-Options: nosniff`;
- `X-Frame-Options: DENY` as a compatibility companion to CSP;
- a restrictive `Permissions-Policy` for camera, geolocation, microphone, payment, and USB.

The CSP permits inline script and style because the application intentionally ships as one dependency-free HTML asset. It is therefore not a substitute for safe DOM construction. Exported Beads values must continue to be inserted as text rather than executable markup.

## 4. Residual limits and safe operation

- Keep the app bound to loopback. It is not designed for LAN exposure, reverse proxying, remote access, or multi-user authorization.
- HTTP is intentionally unencrypted on loopback. Do not change the bind address to a non-loopback interface.
- Anyone with sufficient access to read the local HTML response can obtain the current write capability. The capability distinguishes the served app from an unrelated web origin; it is not an operating-system authentication mechanism.
- Read-only API routes intentionally allow requests without `Origin` for local tooling. They do not emit CORS headers, and their responses are protected by same-origin resource policy and `nosniff`, but a compromised local process is outside this boundary.
- Metadata saving still executes the installed `bd` binary in the selected working copy. Review repositories and the executable environment with the same care as direct CLI use.

Stop Beads Map with `Ctrl-C` when it is no longer needed. Report security concerns privately to the maintainer before including repository paths or issue contents in a public report.

## 5. Basis for the controls

The target authority check follows [RFC 9110's `Host` semantics](https://www.rfc-editor.org/rfc/rfc9110.html#name-host-and-authority). Browser `Host` and `Origin` are [forbidden request headers](https://developer.mozilla.org/en-US/docs/Glossary/Forbidden_request_header), and the browser supplies `Origin` on same-origin Fetch `POST` requests as described by [MDN's Origin reference](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Origin). The token-in-custom-header pattern and exact source/target origin comparison follow the [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html). Framing is disabled with CSP [`frame-ancestors 'none'`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/frame-ancestors).
