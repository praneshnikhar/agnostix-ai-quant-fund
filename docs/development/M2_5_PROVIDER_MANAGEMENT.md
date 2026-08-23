# M2.5 Provider Management Manual Smoke Test

This procedure is developer-only. Do not use production credentials in local
tests, and do not run it in CI.

1. Generate and set `API_PROVIDER_ENCRYPTION_KEY`; start PostgreSQL and apply
   migrations with the normal Alembic workflow. Do not auto-apply migrations
   from application startup.
2. Create or use an existing `User` row and create a signed bearer token with
   `app.core.auth.issue_access_token(user_id)`. Send it as
   `Authorization: Bearer <token>`.
3. Configure Ollama at `POST /provider-configurations/ai` with its base URL and
   default model. Run `/ai/{id}/test`, then `/ai/{id}/models/discover`.
4. Configure OpenRouter similarly with an API key and model. Test and discover
   models. Confirm responses contain only masked credential suffixes.
5. Configure Alpaca at `POST /provider-configurations/data` with API key,
   secret key, and `market_data_feed` set to `iex` or `sip`. Test the provider.
   Confirm capabilities remain data/news/security metadata and trading is not
   enabled by this configuration.
6. Inspect PostgreSQL and audit events. Confirm only ciphertext exists in
   `secret_ciphertext`, no plaintext appears in metadata or event payloads, and
   connection errors are normalized.
7. Resolve an AI configured model through the existing ModelGateway
   configuration seam. Confirm research agents still receive only the gateway
   contract, never credentials.

Live provider tests are opt-in and must never be part of normal CI.
