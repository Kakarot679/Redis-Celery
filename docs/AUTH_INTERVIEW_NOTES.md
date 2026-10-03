# Auth & Security Interview Notes (10-min Revision)

Covers everything built/fixed/discussed across password auth hardening, OAuth/OIDC (Google login), and RBAC, in `redis_learnings`.

---

## 1. Password Hashing

- **The bug:** `create_user` did `User(**user.model_dump())`, writing the client's raw password straight into Postgres. `model_dump()` just copies whatever the Pydantic model holds — it doesn't transform values, so hashing has to be a separate explicit step.
- **The fix:**
```python
data = user.model_dump()
data["password"] = hash_password(data["password"])
new_user = User(**data)
```
- **Why bcrypt, not MD5/SHA-256:** MD5/SHA-256 are *designed to be fast* — great for checksums, terrible for passwords, since a fast hash lets an attacker brute-force billions of guesses/sec on stolen hashes. bcrypt is deliberately slow with a tunable work factor, making large-scale offline cracking expensive even with the hash in hand.
- **Interview Q&A:**
  - *Q: Why can't you just store the password as-is?* → Any DB breach instantly exposes every user's real password (and likely their password on other sites, due to reuse).
  - *Q: What does `pwd_context.hash()` actually produce — is it reversible?* → No — a one-way hash. You never "decrypt" a password; login re-hashes the attempt and compares hashes (`pwd_context.verify`).

---

## 2. Authorization vs Authentication (IDOR)

- **Authentication** = proving who you are (valid login). **Authorization** = deciding what you're allowed to do. A valid login proves identity but says nothing about which resources you can touch — that's a separate check you must write.
- **The bug:** `get_user` required `Depends(get_current_user)` but never checked the caller's id against the requested id — any logged-in user could read any other user's record (IDOR — Insecure Direct Object Reference).
- **The fix:**
```python
if Current["user"].id != id:
    raise HTTPException(403, "Not Authorized")
```
- Same fix applied to `update_user`, which originally had **no auth dependency at all**.
- **Interview Q&A:**
  - *Q: How do you prevent IDOR?* → Never trust a resource ID from the request alone; always verify the authenticated user owns (or is permitted to access) that specific resource, on every route that looks one up.

---

## 3. Mass Assignment / Privilege Escalation

- **The risk:** `update_user` does `for key,value in user.model_dump(exclude_unset=True).items(): setattr(to_update,key,value)` — blindly applies every field the client sent. If a sensitive field (like `role`) were ever added to the `UserUpdate` schema the same way as any other field, any user could PUT `{"role":"admin"}` to their own profile and self-promote.
- **The fix:** `role` exists only on `UserRead` (for display) and the DB model — never on `UserCreate`/`UserUpdate`. Verified live: a regular user PUTting `{"role":"admin"}` succeeds (200) but the field is silently dropped (not in the schema), role stays `"user"`.
- **Interview Q&A:**
  - *Q: What's mass assignment, and how do you prevent it?* → Blindly applying all request fields to a model lets clients set fields they shouldn't control. Prevention: explicit allowlist schemas that simply never include sensitive fields.

---

## 4. Refresh Token Rotation

- **The gap:** `/auth/refresh` originally only checked the JWT's signature/expiry — never checked Redis for the session's existence, so a refresh token kept working even after logout deleted the session.
- **Fix 1 (session-aware):** check `redis_client.get(f"session:{session_id}")` before issuing a new access token; reject if the session's gone.
- **Fix 2 (rotation/single-use):** every successful refresh also issues a **new** refresh token and overwrites `refresh:{session_id}` in Redis. On the next refresh, the presented token is compared against what's stored — mismatch means the token was already used (replay/theft), and the whole session gets killed.
```python
stored_refresh = redis_client.get(f"refresh:{session_id}")
if stored_refresh != refresh_token:
    redis_client.delete(f"session:{session_id}")
    redis_client.delete(f"refresh:{session_id}")
    raise HTTPException(401, "Refresh token reused or invalid")
# else: rotate — issue new refresh_token, overwrite Redis, return both new tokens
```
- **Interview Q&A:**
  - *Q: Stateless JWT vs session-based token — security tradeoff?* → A pure JWT can't be revoked before expiry (no server-side record). Session-based (Redis-checked) allows instant revocation but adds a lookup + dependency on that store per request. Many systems hybridize: short-lived stateless access token + a server-checked, rotating refresh token.
  - *Q: How do you protect against refresh token theft?* → Rotation — single-use tokens, with reuse-of-a-stale-token as the detection signal for theft.

---

## 5. Reflected XSS

- **The bug:** `reset_password_page` interpolated the URL's `token` directly into an HTML f-string: `<input ... value="{token}">`. A crafted `token` like `"><script>...</script>` breaks out of the attribute and becomes live, executing HTML.
- **The fix:** `safe_token = html.escape(token)` (stdlib) before embedding — converts `"`, `<`, `>`, `&` into HTML entities, making injected markup inert text instead of real HTML.
- **Interview Q&A:**
  - *Q: XSS vs CSRF — what's the actual difference?* → XSS runs the attacker's code *in your page's context* (can read `document.cookie` unless `httpOnly`, steal tokens from `localStorage`). CSRF runs on an unrelated page and never sees your cookie at all — it just causes your browser to send a forged request, relying on cookies being auto-attached. XSS *steals* data; CSRF *forges an action*, blind.

---

## 6. Login Rate Limiting (Brute Force)

- **Why IP-based limiting (existing generic `rate_limit` dependency) isn't enough for login specifically:** an attacker can distribute guesses across many IPs (botnet/proxies), each staying under the per-IP threshold, while hammering one account. IP limiting protects the *server*, not a specific *account*.
- **The fix — per-account failure counter:**
```python
fail_key = f"login_fail:{email}"
if redis_client.get(fail_key) and int(redis_client.get(fail_key)) >= 5:
    raise HTTPException(429, "Too many failed login attempts")
# on wrong password:
fail_count = redis_client.incr(fail_key)
if fail_count == 1:
    redis_client.expire(fail_key, 300)
# on success:
redis_client.delete(fail_key)
```
- Only **failed** attempts increment the counter; success resets it to zero — so a user who mistypes twice then logs in correctly isn't penalized later.
- `expire` only set on the *first* failure (`fail_count == 1`), not every failure — otherwise each new guess would push the window forward, letting a patient attacker (e.g. one guess every 4 min) keep the window alive forever.
- **Honest limit:** this slows brute force, doesn't eliminate it — an attacker pacing 4 guesses/5min stays under threshold indefinitely (~420k guesses/year, vs millions/sec unthrottled). Real hardening layers on top: account lockout, CAPTCHA, alerting.

---

## 7. Cookies vs Authorization Header, and CSRF

- **httpOnly cookies:** browser auto-attaches to every request to that domain; JavaScript (even your own) cannot read them — resistant to XSS token theft. But auto-attachment is exactly what **CSRF** exploits (see below).
- **Authorization header / localStorage:** nothing attaches automatically — your own JS must read and attach the token each time. Resistant to CSRF (an attacker's page can't make your browser add a custom header), but if XSS ever succeeds, a token in `localStorage` is trivially stealable (`document.cookie`-equivalent for JS-readable storage).
- **This app uses Bearer headers → XSS is the bigger concern, not CSRF**, for the main session/JWT system.
- **CSRF, precisely:** attacker never sees or steals your cookie — their page just causes your browser to send a request to your site, and the browser auto-attaches whatever cookie it already holds. Can be triggered without the victim "visiting a shady site" — a malicious ad on a trusted site, an auto-loading `<img>` in an email, a compromised legitimate site, etc.
- **Interview Q&A:**
  - *Q: Why does CSRF need a victim to be logged in elsewhere, but not need them to visit the attacker's "real" site on purpose?* → Any page the browser loads — through an ad network, email client, compromised trusted site — can embed the forged request; the victim never needs to consciously visit anything suspicious.

---

## 8. MFA / 2FA (Conceptual — Not Implemented)

- **Key distinction:** this app's existing OTP flow verifies email *once, at signup* (`is_verified` is a permanent flag, never re-checked). True 2FA requires a **fresh** OTP check on *every login*, not a one-time flag.
- **How it would work:** split login into two steps — (1) verify password, generate+email an OTP, return `mfa_required: true` + a temp marker, **don't** issue a session yet; (2) a separate `/login/verify-mfa` endpoint checks the OTP, and only then creates the session/tokens.
- Deliberately not implemented — login stays single-factor by choice for this project's scope.

---

## 9. Password Policy

- **Implemented:** `password: str = Field(min_length=8)` on `UserCreate` — Pydantic validates at the request boundary, before the route body runs; failure returns `422` automatically.
- Special-character enforcement was tried via a `@field_validator` + regex, then removed by choice (kept to length-only).
```python
@field_validator("password")
@classmethod
def password_must_have_special_char(cls, value):
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", value):
        raise ValueError("Password must contain at least one special character")
    return value
```

---

## 10. Account Lockout vs Rate-Limit Window

- **Distinct concepts:** the `login_fail` counter (Section 6) is a *temporary* sliding window — auto-clears after 5 min, no lasting record. True **lockout** is *persistent* (`is_locked` / `locked_until` on the User model), requiring explicit unlock (support, email link, admin).
- **Tradeoff:** permanent lockout creates a DoS vector — anyone can lock a victim out just by failing login 10 times on purpose, no password needed. Real systems use **escalating temporary** lockouts (5 fails → 1 min, 10 → 1 hr, 20 → 24 hr) instead of permanent, to avoid this.
- Deferred implementation — queued alongside deeper authorization-types work (Section 13).

---

## 11. Token Revocation Strategy at Scale

- **Current design:** Redis session check on every request via `get_current_user` — real revocation (logout actually works), at the cost of a Redis round-trip per request and a hard dependency on Redis being up.
- **Pure JWT alternative:** no lookup, extremely fast/scalable, but no revocation before expiry — logout becomes client-side only ("forget the token locally"), the token itself stays valid server-side.
- **Middle-ground patterns:** short-lived access tokens (pure JWT, no Redis check) + Redis-checked refresh tokens only (fewer total lookups, since refresh happens far less often than regular requests); or a **blacklist** of revoked tokens only (smaller set than tracking every valid session, cheaper when revocation is rare).
- This app currently accepts the per-request Redis-check tradeoff deliberately — a valid choice at reasonable scale, not a mistake.

---

## 12. OAuth2 + OpenID Connect (Google Login)

- **Terminology correction:** what was built is **OIDC** (OpenID Connect), not plain OAuth2. OAuth2 alone = delegated *authorization* ("let this app access my Drive files"). OIDC is layered on top specifically to add *authentication* (the `id_token`, proving identity) — this distinction is a genuine interview differentiator.
- **Full flow:**
  1. `GET /auth/google/login` builds a URL to Google (`client_id`, `redirect_uri`, `scope`, `response_type=code`, `state`) and returns `RedirectResponse(url)` — the browser auto-navigates there (any `302`/`Location` header triggers this, standard browser behavior, nothing OAuth-specific).
  2. User authenticates **on Google's page** — your server never sees the password.
  3. Google redirects the browser back to `redirect_uri` with a one-time `?code=...` (and the echoed `state`).
  4. Server-to-server (your backend, not the browser): `httpx.post(GOOGLE_TOKEN_URL, data={code, client_id, client_secret, redirect_uri, grant_type: "authorization_code"})` — exchanges the code for Google's tokens. The `client_secret` here is what makes this trustworthy; anyone can *see* a `code` in a URL, only your server can redeem it.
  5. Extract `id_token` (a JWT signed by Google's **private** key) from the response.
  6. Verify it: fetch Google's matching **public** key via `PyJWKClient` (pointed at Google's published JWKS URL), `jwt.decode(id_token, signing_key.key, algorithms=["RS256"], audience=GOOGLE_CLIENT_ID)`.
  7. Find-or-create a `User` by the verified email; issue your own `session_id` + access/refresh tokens — identical machinery to password login, so every other route works unchanged for Google users.
- **Why public/private key signing is safe to verify openly:** the public key only lets you *check* a signature, never *create* one — forging a valid token still requires Google's private key, which is never shared.
- **`kid` (key ID):** a JWT's header names which of Google's several rotating keys signed it; `PyJWKClient` looks this up and fetches only the matching key from Google's published JWKS list (`https://www.googleapis.com/oauth2/v3/certs`, a public, no-auth URL).
- **Hardening pass (all live-tested):**
  - **`state` parameter (CSRF-on-the-login-flow protection):** a random value generated in `/login`, stored in an `httpOnly` cookie (`max_age=300`) **and** sent to Google; compared against what Google echoes back in `/callback`. A naive "did we ever issue this state" check (e.g. just in Redis, unbound to a browser) is **not sufficient** — the real attack is an attacker completing their *own* flow and tricking a victim into opening the captured callback URL. Binding `state` to a cookie proves the *same browser* that started the flow is the one finishing it. Proven live: missing cookie → rejected; mismatched `state` → rejected; real matching flow → still works.
  - **Graceful token-exchange failure:** `token_data.get("id_token")` (not `[...]`) + explicit `None` check → clean `400` instead of an unhandled `KeyError`/`500`.
  - **Graceful signature-verification failure:** `try/except jwt.PyJWTError` around `jwt.decode` → clean `401` instead of a crash.
  - **`email_verified` check:** `if not claims.get("email_verified"): raise 401` — without this, an unverified email claim could in rare cases be trusted and matched against an *existing* account, a theoretical account-takeover path.
  - **Removed a debug `print(token_data)`** that was logging real Google access/refresh/ID tokens to the server log in plaintext.
- **Known gaps (noted, not fixed):** `city` stays permanently empty for Google signups (Google doesn't provide it); a Google-only account (`password=""`) attempting normal password login would throw an unhandled `UnknownHashError` → `500` instead of a clean message; `/callback` is synchronous, blocking on the `httpx` call (minor scaling concern — `async def` + `httpx.AsyncClient` would fix it).
- **Interview Q&A:**
  - *Q: Authorization code flow vs implicit flow?* → Code flow keeps secrets/tokens server-side, never exposed to the browser. Implicit flow (deprecated) returned tokens directly in the URL fragment — exposed to history/extensions/JS. This app uses the correct, modern code flow.
  - *Q: What's PKCE, and do you need it here?* → Proof Key for Code Exchange — needed when a client *can't* safely hold a `client_secret` (mobile apps, SPAs). This app is a traditional server with a backend, so plain code-flow-with-secret is appropriate; PKCE would matter if this were a browser-only/mobile client.
  - *Q: Why verify both `iss` and `aud`, not just the signature?* → Signature alone only proves "some trusted key signed this." `iss` confirms it's specifically Google; `aud` confirms it was issued *for your app* — without it, a token legitimately issued to a *different* app could be replayed against yours.
  - *Q: What's the `state` parameter for?* → CSRF protection on the login flow itself (see above) — a commonly-missed piece in naive OAuth implementations.

---

## 13. RBAC (Role-Based Access Control)

- **Why a column alone isn't enough:** `role=Column(String, default="user")` works but allows any string — migrated to a real Postgres `Enum` (`class UserRole(str, enum.Enum): user="user"; admin="admin"`) so the database itself rejects invalid values, not just app-level comparisons.
- **Schema separation (prevents self-escalation):** `role` exists on `UserRead` (output) and the DB model, but is **never** on `UserCreate`/`UserUpdate` — the same mass-assignment defense from Section 3, applied specifically to roles.
- **`require_admin` dependency — reuses `get_current_user` rather than reimplementing token/session logic:**
```python
def require_admin(current=Depends(get_current_user)):
    if current["user"].role != "admin":
        raise HTTPException(403, "Admin Access Required")
    return current["user"]
```
- **Admin-only route + a routing-order bug:** `GET /user/admin` must be registered **before** `GET /user/{id}` — otherwise `/{id}` (a generic path pattern) structurally matches the literal string `"admin"` first, and FastAPI tries (and fails) to convert `"admin"` to `int`, returning `422` instead of ever reaching the intended admin route.
- **Merged ownership-or-admin check** (one route serving both cases, instead of a separate admin route):
```python
if Current["user"].id != id and Current["user"].role != "admin":
    raise HTTPException(403, "Not Authorized")
```
Self-edit passes (`id == id` short-circuits), cross-edit by a regular user fails (both conditions true), admin cross-edit passes (`role != "admin"` is false, so the `and` fails) — all three verified live against a running server.
- **Incidental fix:** `update_user`'s return value was changed from the raw ORM object to a generic `{"message": "updated successfully"}`, closing a password-hash leak (the raw object included the bcrypt hash field).
- **Interview Q&A:**
  - *Q: RBAC vs ABAC — when would you choose one over the other?* → RBAC when permissions map cleanly to a small fixed set of roles. ABAC when access depends on combining multiple dynamic conditions (ownership + department + time) that a role alone can't express. Default to RBAC; reach for ABAC only when RBAC genuinely can't express the rule — building ABAC for two rules ("owner" + "admin") would be premature complexity (YAGNI).

---

## 14. Other Authorization Models (Conceptual Only — Not Implemented)

- **ABAC** — access computed from attributes of user/resource/context combined via rules, not fixed roles. More expressive, harder to reason about/debug.
- **ACL** — direct per-user-per-resource grants (e.g. Google Docs "share with this person"). Precise for one-off grants, doesn't scale to broad policies ("all managers can read all dept docs" would need thousands of rows).
- **ReBAC (Relationship-Based)** — access via a relationship graph, not roles. Tuples of `(object, relation, subject)`, where a subject can itself be another relation (`document:42, viewer, team:eng#member`). Relations can *imply* other relations (`owner` implies `editor` implies `viewer`) — a schema-defined hierarchy, generalized to arbitrary chains. Checking access = graph reachability, not a single row lookup. This is what Google Zanzibar (and open-source OpenFGA/SpiceDB) implement — the real mechanism behind Google Docs sharing/folder-permission-inheritance. The most practically relevant "advanced" model to know for interviews beyond RBAC.
- **DAC (Discretionary)** — the resource *owner* decides who else gets access (Unix file permissions `chmod`/`chown`). This app's ownership check is a primitive, implicit form of DAC.
- **MAC (Mandatory)** — a central system-wide policy decides access, individual owners can't override (classification levels — Confidential/Secret/Top Secret). Rare outside government/military-grade systems.
- **PBAC (Policy-Based)** — close to ABAC, framed as centrally-authored machine-readable policies (AWS IAM policies are a real-world example).
- **Capability-based** — possession of an unforgeable token *is* the authorization, no identity lookup needed. This app's JWT is a hybrid example (holding a valid JWT grants access, though a Redis session check still happens too).
- **Honest assessment for this project's scope:** none of these need implementation — RBAC + ownership is proportionate to "two roles, no sharing features." ReBAC would only become relevant if real document/resource sharing were added later.
- **Interview framing by context:**
  - Standard backend interviews → definitions + tradeoffs (*"RBAC vs ABAC, when would you pick each"*).
  - System design rounds → design-level reasoning (*"design Google Docs' sharing system"* → ReBAC, named by name, is a strong differentiator most candidates miss).
  - Take-home/live coding → almost always RBAC (or basic ACL) — nobody hand-rolls ReBAC/OpenFGA in an interview exercise.
  - Security-focused roles → IDOR, mass assignment, and the specific vulnerabilities actually fixed in Sections 2-3 are common, concrete interview/CTF material.

---

## 15. Quick Reference — Bugs Fixed vs Concepts Covered

| # | Topic | Status |
|---|-------|--------|
| 1 | Password hashing | Fixed |
| 2 | IDOR (get_user, update_user) | Fixed |
| 3 | Mass assignment (role field) | Fixed (schema exclusion) |
| 4 | Refresh token rotation | Fixed |
| 5 | Reflected XSS | Fixed |
| 6 | Login brute-force rate limiting | Implemented |
| 7 | Cookies vs headers, CSRF | Covered (not implemented — N/A for header-based design) |
| 8 | MFA/2FA | Covered conceptually only |
| 9 | Password policy | Implemented (length only) |
| 10 | Account lockout | Covered conceptually, deferred |
| 11 | Token revocation at scale | Covered (tradeoff accepted as-is) |
| 12 | OAuth2/OIDC (Google login) | Fully implemented + hardened + tested |
| 13 | RBAC | Fully implemented + tested |
| 14 | ABAC/ACL/ReBAC/DAC/MAC/PBAC/capability | Covered conceptually only |
