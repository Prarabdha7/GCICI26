---
title: Content Generation Agent
tags: [pipeline, agent, copywriter, llm]
tier: RAM / Recall
component: "app/graph/nodes/content.py"
---

# Content Generation Agent

Generates multi-format marketing copy grounded in brand personas, underwriting guidelines, and regulatory constraints.

## Dynamic System Prompt Grounding
1. Brand Voice: [[Jade]] (luxury understatement), [[DoctorShield]] (clinical professionalism), [[Jaguar-Transit]] (logistical precision).
2. Memory Guardrails: Injected from [[Memory-Retrieval-Agent]].
3. Underwriting Rules: Checked against [[Jewellery-Block-Underwriting]], [[Medical-Malpractice-Indemnity]], or [[Marine-Cargo-Transit]].
4. Retry Redlines: Injected directly when cycling from [[Compliance-Gate]].

Connected entities: [[LangGraph-Engine]], [[Localization-Agent]], [[Compliance-Gate]].
