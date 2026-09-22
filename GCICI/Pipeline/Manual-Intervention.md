---
title: Manual Intervention & Human Review Queue
tags: [pipeline, human-in-the-loop, review, safety]
tier: Archival
component: "app/graph/nodes/manual_intervention.py"
---

# Manual Intervention Queue

Human-in-the-loop review dashboard where marketing directors review, edit, approve, or reject drafts.

## Closed-Loop Memory
Every human rejection or edit stores a memory record in [[Tier-2-Mem0-Buffer]], improving future drafts.

Connected entities: [[Circuit-Breaker]], [[Tier-2-Mem0-Buffer]], [[LangGraph-Engine]].
