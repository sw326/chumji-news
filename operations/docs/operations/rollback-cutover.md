# Rollback And Cutover Rules

This repository starts as a scaffold. No rollback, cutover, or service activation is approved by its existence.

## Cutover Approval

Before cutover, record:

- The current live source of truth.
- The exact target revision.
- The affected service, scheduler, and live path.
- The validation checklist.
- The rollback plan.
- The human approval and timestamp.

## Rollback Approval

Before rollback, record:

- The production symptom or incident.
- The revision or configuration being restored.
- Expected user-visible impact.
- The command plan.
- The human approval and timestamp.

## Prohibited Without Approval

- Loading or unloading LaunchAgents or LaunchDaemons.
- Editing cron or scheduler state.
- Redirecting webhooks, DNS, gateways, or production traffic.
- Replacing live app directories or production environment variables.
