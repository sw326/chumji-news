# Manifests

Manifests in this directory are examples only. They describe intended service and job shape without installing, enabling, or changing any live runtime.

Rules:

- Store SecretRef names only.
- Do not store secret values or copied `.env` content.
- Keep live paths out of examples unless they are explicitly marked as placeholders.
- Treat every manifest as inactive until cutover approval is recorded.

