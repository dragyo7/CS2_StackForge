# Feature: Authentication & Community Foundation

**Status:** Implemented (local-dev host mode + real PBKDF2-HMAC-SHA256 auth endpoints)

## Implemented Capabilities
- `POST /api/auth/signup`, `POST /api/auth/login` (with 5-minute failed-attempt rate limiting), `POST /api/auth/logout`, `GET /api/auth/me`.
- Password hashing via standard-library `hashlib.pbkdf2_hmac("sha256", ..., 260_000)` with per-user random salt and constant-time comparison (`hmac.compare_digest`).
- Bearer session tokens stored as SHA-256 hashes in `user_sessions` (`14`-day expiry).
- Landing page (`LandingAuthView.tsx`) with sign-up, sign-in, and explicit local-dev host mode toggle.

## Honest Scope Status
- Single-community local-dev host mode remains usable without mandatory login so 10-man organizing works immediately; full multi-tenant RBAC enforcement across communities, password-reset email delivery, and Steam OpenID login remain deferred.
