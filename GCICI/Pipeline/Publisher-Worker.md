---
title: Publisher Worker & Social Media Dispatcher
tags: [pipeline, worker, publisher, buffer, ayrshare]
tier: Archival
component: "worker/publisher.py"
---

# Publisher Worker (Project 2: The Hands)

Background worker polling approved queue items and dispatching to social media.

## Integrations
- **Buffer**: GraphQL createPost integration.
- **Ayrshare**: Multi-network social posting API.
- **Mock Dispatcher**: Labeled keyless simulation mode for dry-run verification.

Connected entities: [[LangGraph-Engine]], [[LinkedIn]], [[Instagram]], [[TikTok]].
