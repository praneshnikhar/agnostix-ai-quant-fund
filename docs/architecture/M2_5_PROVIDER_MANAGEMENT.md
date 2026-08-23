# M2.5 Provider Management Architecture

Provider management is a configuration and credential boundary, not a new
runtime provider abstraction.

AI configurations resolve through the existing single ModelGateway registry,
with canonical `provider + model` targets. Data configurations resolve through
the existing M1 adapter boundary and retain the flow:

`Alpaca adapter → normalization → validation → freshness → persistence → MarketSnapshot`.

`provider_configurations` stores safe metadata, explicit scope, status, and
Fernet ciphertext in a dedicated column. `provider_model_configurations` stores
configured or discovered model targets. No secret is returned through API
responses or audit events.

The current identity model has users and roles but no organization service.
Platform and owner-bound user scopes are implemented; organization scope is
schema-ready and explicitly rejected until organization identity exists.

Alpaca remains data/news/security-metadata infrastructure. Its configuration
does not enable trading and no live-trading endpoint was added.
