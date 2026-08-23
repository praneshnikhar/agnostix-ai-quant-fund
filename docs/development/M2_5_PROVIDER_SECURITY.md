# M2.5 Provider Security

- Set `API_PROVIDER_ENCRYPTION_KEY` outside source control. It must be a valid
  Fernet key before provider credentials can be stored.
- Credentials are encrypted before persistence in
  `provider_configurations.secret_ciphertext`; plaintext keys are not stored in
  normal metadata JSON.
- Responses expose only configured/not-configured state and masked suffixes.
- Metadata rejects secret-looking keys recursively. Audit events contain only
  provider configuration IDs and event names.
- Provider errors are normalized to safe codes such as
  `INVALID_CREDENTIALS`, `TIMEOUT`, `PROVIDER_UNAVAILABLE`, and
  `CONFIGURATION_INVALID`.
- Provider routes require signed bearer tokens bound to existing users. Viewer
  roles can read safe metadata; PM/admin can write and test; admin can delete.
- No provider credentials are sent to browser analytics, URLs, or frontend
  direct provider calls. No live trading capability is added.
