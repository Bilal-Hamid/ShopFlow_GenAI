# Security Review — Authentication Module

**Project:** ShopFlow (backend)
**Scope:** Authentication / authorization module only
**Date:** 2026-07-21
**Reviewer:** Automated security review (Claude Code, `/security-review`)

## Files in scope

- `backend/app/api/routes/auth.py`
- `backend/app/schemas/auth.py`
- `backend/app/services/auth_service.py`
- `backend/app/services/token_store.py`
- `backend/app/core/security.py`
- `backend/app/api/cookies.py`
- `backend/app/api/deps.py` (auth/authz dependencies)
- `backend/app/core/config.py` (auth-relevant config)
- `backend/app/models/user.py` (auth-relevant fields)

Other modules (products, cart, orders, reviews, merchant, admin, payments, webhooks) were **not** reviewed, per the request.

---

## Executive summary

The authentication module is **well implemented**. No directly exploitable, high-confidence vulnerability (RCE, authentication bypass, privilege escalation, injection) was found. Core primitives are sound:

- JWT verification pins the accepted algorithm to a single configured value (`algorithms=[settings.jwt_algorithm]`), which defeats the classic `alg:none` bypass and RS256→HS256 confusion attacks.
- Passwords are hashed with **Argon2** (`argon2.PasswordHasher`), and verification never crashes on malformed hashes.
- Refresh tokens use **server-side family rotation with reuse detection** in Redis, and burn the whole token family on replay.
- Login is **timing-equalized** against a dummy hash so latency does not leak whether an account exists.
- RBAC role checks read the role **from the database**, not from the (tamperable) token, so token manipulation cannot elevate privileges.
- Tokens are stored in **httpOnly cookies** (never in JSON bodies or `localStorage`); the refresh cookie is path-scoped to `/auth`.
- All database access uses **parameterized SQLAlchemy** queries — no string-built SQL, no `eval`/`pickle`/`yaml` in scope.

The findings below are **LOW/MEDIUM severity, defense-in-depth / hardening items**. None met the bar of a concrete, attacker-triggerable exploit under a secure default configuration. They are documented because the review explicitly asked for any security weaknesses present, but they should be prioritized accordingly — the module has no critical exposure.

| # | Finding | Severity | Category | Status |
|---|---------|----------|----------|--------|
| 1 | User enumeration via registration endpoint | Low–Medium | Information disclosure (CWE-204) | Real, low impact |
| 2 | JWT secret length / algorithm not constrained in config | Low | Weak-crypto hardening | Config-dependent |
| 3 | Cookie auth relies solely on SameSite; no CSRF token | Low | CSRF hardening (CWE-352) | Config-dependent |

> **Note on methodology:** Candidate findings were run through an adversarial false-positive filter. All three fell below the "high-confidence exploitable vulnerability" threshold — Finding 1 was assessed as a genuine but low-impact information leak; Findings 2 and 3 depend on operator misconfiguration of trusted environment values and are hardening recommendations rather than exploitable defects under the secure defaults. They are retained here as advisory items, not blocking issues.

---

## Finding 1 — User enumeration via registration endpoint

- **File / lines:** [auth_service.py:24-30](backend/app/services/auth_service.py#L24-L30) (consumed by [auth.py](backend/app/api/routes/auth.py))
- **Severity:** Low–Medium
- **Category:** Information disclosure / user enumeration (CWE-204)
- **Confidence this is a real (if low-impact) weakness:** Medium

### Description
`register_user` returns HTTP `409` with the detail message `"An account with this email already exists."` when the normalized email already exists, versus a `201` for a new email:

```python
existing = await db.scalar(select(User.id).where(User.email == normalized_email))
if existing is not None:
    raise ProblemException(
        status_code=409,
        detail="An account with this email already exists.",
        title="Conflict",
    )
```

The login path was deliberately hardened against enumeration (generic `"Incorrect email or password."` message plus dummy-hash timing equalization in `authenticate_user`), but the registration endpoint re-opens the same oracle through its status code and message.

### Impact / exploit scenario
An attacker scripts `POST /auth/register` against a list of candidate email addresses. A `409` confirms the address already has an account (useful for targeted phishing and credential-stuffing shortlists); a `201` confirms it did not. No authentication is required. The public rate limit (100 req/min per IP) slows but does not prevent enumeration, since it can be spread across IPs. Impact is limited to disclosing *which* emails are registered — no credentials, PII, or access are exposed.

### Suggested action
Decouple account existence from the immediate response. Return a neutral response (e.g. `202`/`200` "if this email is new, check your inbox to verify") and complete registration via an out-of-band email-verification link, so the synchronous response never reveals prior existence. If an async verification flow is out of scope, treat this as an explicitly accepted, documented risk. This weakness is partly intrinsic to a globally-unique-email schema.

---

## Finding 2 — JWT secret length and algorithm are not constrained in config

- **File / lines:** [config.py:31-32](backend/app/core/config.py#L31-L32); consumed at [security.py:60,82,89](backend/app/core/security.py#L60)
- **Severity:** Low (hardening)
- **Category:** Weak-crypto / secure configuration
- **Confidence this is an exploitable defect:** Low (depends on operator misconfiguration)

### Description
Two config-driven weaknesses in the token trust anchor:

```python
jwt_secret_key: str = Field(min_length=16)
jwt_algorithm: str = "HS256"
```

1. `jwt_secret_key` enforces only `min_length=16`. For HMAC-SHA256 the recommended key strength is ≥256 bits (~32+ random bytes). The surrounding comment already advises "≥32 chars", but the code permits a shorter (potentially lower-entropy) value.
2. `jwt_algorithm` is a free-form string with no allow-list. A misconfiguration such as `JWT_ALGORITHM=none` would cause tokens to be minted and accepted unsigned.

### Impact / exploit scenario
These require **operator misconfiguration via trusted environment values**, which is why they are hardening items rather than directly exploitable flaws:
- A short/low-entropy secret could, in principle, be brute-forced offline from a captured token, enabling forgery of access tokens for any `sub`/`role` (including `admin`).
- Setting the algorithm to `none` would allow forged unsigned tokens.

Note the decode path is already **correctly defensive**: `jwt.decode(..., algorithms=[settings.jwt_algorithm])` pins verification to the single server-configured algorithm, so an attacker cannot smuggle `alg:none` or perform algorithm-confusion against a correctly configured HS256 deployment.

### Suggested action
Defense-in-depth only:
- Raise the enforced minimum for `jwt_secret_key` to ≥32 characters and document a high-entropy random value requirement.
- Constrain `jwt_algorithm` to a `Literal` allow-list of safe algorithms (e.g. `Literal["HS256", "HS384", "HS512"]`) so `none` and asymmetric-confusion values cannot be configured.
- Keep the existing `algorithms=[...]` pinning in `decode_token`.

---

## Finding 3 — Cookie authentication relies solely on SameSite; no CSRF token

- **File / lines:** [cookies.py:18-38](backend/app/api/cookies.py#L18-L38); [config.py:38](backend/app/core/config.py#L38)
- **Severity:** Low (hardening)
- **Category:** Cross-site request forgery (CWE-352)
- **Confidence this is an exploitable defect under defaults:** Low

### Description
Authentication is carried entirely in cookies, and there is no CSRF token, double-submit cookie, or `Origin`/`Referer` check in the auth or dependency layer. The only CSRF barrier is the SameSite cookie attribute:

```python
cookie_samesite: Literal["lax", "strict", "none"] = "lax"
```

The default of `lax` is a valid CSRF mitigation — it strips the cookie from cross-site state-changing (POST/PUT/DELETE) requests — so under the secure default the app is **not** CSRF-exploitable. The value is operator-configurable to `none`, which cross-site SPA deployments sometimes require and which would silently remove the sole CSRF defense.

### Impact / exploit scenario
If an operator sets `cookie_samesite="none"` (a trusted config value), a malicious page could drive a victim's browser to issue authenticated cross-site requests against cookie-authenticated state-changing endpoints, with no CSRF token to stop it. Under the default `lax`, there is no practical CSRF exposure.

### Suggested action
Before ever allowing `SameSite=none`, add a CSRF defense that does not depend on SameSite — a double-submit cookie plus an `X-CSRF-Token` header, or strict `Origin`/`Referer` validation on unsafe methods. Alternatively, forbid `cookie_samesite="none"` via config validation unless a CSRF mechanism is enabled.

---

## Items examined and cleared (no finding)

- **JWT verification** ([security.py:86-95](backend/app/core/security.py#L86-L95)): signature + expiry enforced, algorithm pinned to a single value, `type` claim checked — resists `alg:none` and RS/HS confusion.
- **Privilege escalation via role:** self-registration cannot request `admin` (blocked at the schema layer); `require_roles`/`get_current_user` read the role from the DB, not the token, so tampering/staleness cannot elevate access.
- **Refresh rotation / reuse detection:** `token_store` uses atomic Redis operations to distinguish valid-vs-reused refresh tokens and burns the whole family on replay; deleted / soft-deleted users cannot refresh.
- **Password hashing:** Argon2 via `PasswordHasher`; verification never crashes on malformed hashes.
- **Data exposure in responses:** `UserResponse` excludes `password_hash`; no tokens are returned in JSON bodies (cookies only).
- **Injection:** all DB access is via parameterized SQLAlchemy `select(...)`; no string-built SQL, `eval`, `pickle`, or `yaml` deserialization in scope.

---

## Overall assessment

The authentication module demonstrates strong secure-by-default design. **No blocking security issue was identified.** The three findings above are advisory hardening items — the highest-value one being Finding 1 (registration user enumeration), which is worth addressing if/when an email-verification flow is introduced. As instructed, no vulnerabilities were resolved as part of this review; this report is for triage only.
