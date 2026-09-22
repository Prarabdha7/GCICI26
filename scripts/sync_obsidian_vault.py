"""Synchronize and populate the Obsidian Second Brain Vault with rich bidirectional graph topology."""

from __future__ import annotations

import logging
from pathlib import Path
import sqlite3
import sys

# Ensure repository root is on sys.path
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.integrations.obsidian import _build_excalidraw_json, _safe_slug

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("sync_obsidian_vault")


def get_vault_dir() -> Path:
    if settings.obsidian_vault_dir:
        v = Path(settings.obsidian_vault_dir).expanduser()
        if v.exists() and v.is_dir():
            return v
    candidate = BASE_DIR / "GCICI"
    if candidate.exists() and candidate.is_dir():
        return candidate
    fallback = BASE_DIR / "vault"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def generate_knowledge_base(vault_dir: Path) -> None:
    """Creates the core interconnected markdown notes for the Second Brain Knowledge Graph."""
    notes: dict[str, str] = {
        # =========================================================================
        # CENTRAL MAP OF CONTENT (MOC)
        # =========================================================================
        "JA-Assure-Second-Brain.md": """---
title: JA Assure — AI Second Brain & Knowledge Graph OS
tags: [hub, architecture, memory, knowledge-graph]
tier: RAM / Recall / Disk
last_updated: 2026-09-22
---

# JA Assure — AI Second Brain & Knowledge Graph OS

Welcome to the centralized **Second Brain** for JA Assure's multi-agent autonomous marketing system. This vault forms an interactive topological graph mapping brand underwriting constraints, statutory regulations, cyclic agent execution nodes, and self-healing memory feedback.

```
                    ┌─────────────────────────┐
                    │ JA-Assure-Second-Brain  │
                    └────────────┬────────────┘
         ┌───────────────────────┼──────────────────────┐
         ▼                       ▼                      ▼
  [[Brands/Index]]     [[Compliance/Index]]    [[Pipeline/Index]]
         │                       │                      │
         ▼                       ▼                      ▼
[[Underwriting/Rules]]  [[Regulators/MAS-318]]  [[Memory/3-Tier-OS]]
```

## 🏛️ Brand Ecosystem & Underwriting
- [[Jade]]: Lloyd's-backed commercial insurance for luxury horology & diamond block merchants.
- [[DoctorShield]]: Medical malpractice & clinical legal defence for surgeons and private practices.
- [[Jaguar-Transit]]: High-value multi-modal freight, marine cargo, and cold-chain logistics indemnity.

## ⚖️ Regulatory Guardrails & Jurisdictions
- [[Universal-Rubric]]: Core prohibitions, truth-in-advertising, and self-healing redlines.
- [[MAS-Notice-318]]: Monetary Authority of Singapore direct marketing restrictions.
- [[BNM-FTFC]]: Bank Negara Malaysia fair treatment and bilingual requirements.
- [[HKIA-Guideline-27]]: Hong Kong Insurance Authority statutory disclaimers.
- [[OIC-Thailand]]: Thailand Non-Life Insurance Act B.E. 2535 standards.
- [[OJK-Indonesia]]: Indonesia OJK POJK 22/2023 financial consumer protections.

## ⚙️ Multi-Agent Cyclic Pipeline (Project 1: Brain)
- [[LangGraph-Engine]]: Cyclic state machine orchestrating content research, drafting, and evaluation.
- [[Memory-Retrieval-Agent]]: Injects historical human rejection memory before first draft.
- [[Market-Research-Agent]]: Live keyless competitor intelligence via DuckDuckGo and Crawl4AI.
- [[Content-Agent]]: Multi-format copywriting grounded in persona and underwriting rules.
- [[Localization-Agent]]: Multi-jurisdiction linguistic and cultural adaptation.
- [[Compliance-Gate]]: Automated statutory rubric auditing with minimal redline repair.
- [[Circuit-Breaker]]: Diverts stubborn retries (`retry_count > 3`) to [[Manual-Intervention]].
- [[Video-Assembly-Veo]]: 3-tier video pipeline (Veo generative AI → Pexels stock → ColorClip).
- [[Image-Generation]]: Gemini native image models with Pollinations keyless fallback.
- [[Publisher-Worker]]: Automated publishing dispatcher (Buffer / Ayrshare).

## 🧠 Memory Hierarchy & DSPy Optimization
- [[3-Tier-Memory-OS]]: Virtual memory hierarchy (RAM Context → Mem0 Buffer → Archival Disk).
- [[Tier-1-RAM-Context]]: Active LLM token budget and persona guidelines.
- [[Tier-2-Mem0-Buffer]]: Dynamic semantic recall buffer of past human edits and rejections.
- [[Tier-3-Archival-Vault]]: Persistent Obsidian markdown repository on disk.
- [[DSPy-GEPA-Evolution]]: Genetic-Pareto Prompt Optimizer treating prompts as trainable parameters.

## 📡 Omnichannel Distribution
- [[LinkedIn]]: B2B decision makers, brokers, and risk managers.
- [[Instagram]]: Visual lifestyle, luxury showcases, and carousel education.
- [[TikTok]]: Dynamic video reels and short-form risk awareness.
- [[Carousel-Format]]: Multi-slide educational breakdown format.
- [[Video-Reel]]: 1080x1920 high-fidelity vertical video reels.
""",

        # =========================================================================
        # BRANDS
        # =========================================================================
        "Brands/Jade.md": """---
title: Jade — Luxury Jewellery & Diamond Block Insurance
tags: [brand, luxury, jewellery, horology, underwriting]
tier: Archival
brand_code: JADE
linked_rubric: "[[MAS-Notice-318]]"
underwriting_spec: "[[Jewellery-Block-Underwriting]]"
---

# Jade — Luxury Jewellery Block

**Target Demographic**: High-net-worth jewelers, diamond bourses, antique dealers, and luxury horology boutiques in Singapore, Hong Kong, and Southeast Asia.

## Underwriting Boundaries
- **Premises Security**: Vault-grade physical safes with dual-key electronic biometric verification.
- **Hand-Carry Transit**: Armoured courier and attended hand-carry options up to S$5,000,000 per consignment.
- **Unattended Vehicle Exclusion**: Strictly enforced under [[MAS-Notice-318]]. Never assert zero-deductible or unconditional unattended loss protection in public marketing.
- **Deductible Structure**: Scaled by risk audit index, typically 1.0% to 2.5% of sum insured.

## Connected Marketing & Graph Links
- System Hub: [[JA-Assure-Second-Brain]]
- Primary Underwriting Spec: [[Jewellery-Block-Underwriting]]
- Regulatory Compliance: [[MAS-Notice-318]] and [[Universal-Rubric]]
- Key Channel: [[LinkedIn]] and [[Instagram]]
- Content Agent Persona: [[Content-Agent]]
- Memory Rules: [[DSPy-GEPA-Evolution]]
""",

        "Brands/DoctorShield.md": """---
title: DoctorShield — Medical Malpractice & Clinical Indemnity
tags: [brand, medical, indemnity, malpractice, underwriting]
tier: Archival
brand_code: DOCTORSHIELD
linked_rubric: "[[HKIA-Guideline-27]]"
underwriting_spec: "[[Medical-Malpractice-Indemnity]]"
---

# DoctorShield — Medical Malpractice & Clinical Indemnity

**Target Demographic**: Specialist surgeons, aesthetic medical clinics, dental specialists, and private medical practitioners across Singapore, Malaysia, and Hong Kong.

## Underwriting Boundaries
- **Retroactive Cover**: Continuous claims-made protection backdated to inception of specialist medical registry.
- **Regulatory Scrutiny**: Under [[HKIA-Guideline-27]] and SMC ethical codes, promotional material must never promise immunity from malpractice lawsuits or dismiss patient rights.
- **Inquiry Defence**: Includes full legal representation before Medical Council disciplinary tribunals and coroners' inquests.
- **Good Samaritan Endorsement**: Worldwide cover for voluntary emergency clinical assistance.

## Connected Marketing & Graph Links
- System Hub: [[JA-Assure-Second-Brain]]
- Primary Underwriting Spec: [[Medical-Malpractice-Indemnity]]
- Regulatory Compliance: [[HKIA-Guideline-27]], [[BNM-FTFC]], and [[Universal-Rubric]]
- Primary Channel: [[LinkedIn]]
- Content Agent Persona: [[Content-Agent]]
- Active Learned Rules: [[Tier-2-Mem0-Buffer]]
""",

        "Brands/Jaguar-Transit.md": """---
title: Jaguar Transit — High-Value Multi-Modal Cargo Indemnity
tags: [brand, logistics, transit, cargo, underwriting]
tier: Archival
brand_code: JAGUAR_TRANSIT
linked_rubric: "[[Universal-Rubric]]"
underwriting_spec: "[[Marine-Cargo-Transit]]"
---

# Jaguar Transit — High-Value Goods Transit

**Target Demographic**: Cross-border freight forwarders, high-value bullion shippers, electronics exporters, and cold-chain pharmaceutical distributors throughout ASEAN.

## Underwriting Boundaries
- **Multi-Modal Transit**: Seamless cover across maritime sea lanes, air cargo, and cross-border road transit.
- **Real-Time Telemetry Endorsements**: IoT container temperature and GPS geofence tracking lower active premiums.
- **General Average Waiver**: Expedited deposit release preventing cargo arrest at major ports.
- **Perils Covered**: Maritime piracy, port strikes, refrigeration equipment breakdown, armed overland hijacking. Never advertise zero risk or physical invulnerability.

## Connected Marketing & Graph Links
- System Hub: [[JA-Assure-Second-Brain]]
- Primary Underwriting Spec: [[Marine-Cargo-Transit]]
- Regulatory Compliance: [[Universal-Rubric]] and [[BNM-FTFC]]
- Primary Channels: [[LinkedIn]], [[TikTok]], and [[Video-Reel]]
- Video Engine: [[Video-Assembly-Veo]]
""",

        # =========================================================================
        # UNDERWRITING
        # =========================================================================
        "Underwriting/Jewellery-Block-Underwriting.md": """---
title: Jewellery Block Underwriting Guidelines
tags: [underwriting, jewellery, luxury, risk-management]
tier: Archival
brand: "[[Jade]]"
---

# Jewellery Block Underwriting Guidelines

Bespoke risk assessment criteria governing marketing claims for [[Jade]].

## Mandatory Underwriting Safeguards
1. **Public Alarm Details**: Marketing assets MUST NOT disclose alarm frequencies, seismic sensor brands, or vault safe grades.
2. **Attended Transit Condition**: Theft from unattended personal motor vehicles is an absolute policy exclusion under [[MAS-Notice-318]].
3. **Consignment Audits**: Showroom stock balances must maintain electronic dual-verification inventory.

Connected entities: [[Jade]], [[Universal-Rubric]], [[MAS-Notice-318]], [[JA-Assure-Second-Brain]].
""",

        "Underwriting/Medical-Malpractice-Indemnity.md": """---
title: Medical Malpractice Indemnity Underwriting
tags: [underwriting, medical, liability, malpractice]
tier: Archival
brand: "[[DoctorShield]]"
---

# Medical Malpractice Indemnity Underwriting

Clinical liability parameters governing promotional communications for [[DoctorShield]].

## Core Underwriting Principles
1. **No Legal Immunity Claims**: Insurance provides defense and financial indemnity; it does not confer legal immunity or exemption from standard of care.
2. **Tribunal Defence Coverage**: Explicit coverage for legal counsel costs in Medical Disciplinary Board inquiries.
3. **Cosmetic & Aesthetic Procedures**: High-risk clinical procedures require specialized rider disclosures.

Connected entities: [[DoctorShield]], [[HKIA-Guideline-27]], [[Universal-Rubric]], [[JA-Assure-Second-Brain]].
""",

        "Underwriting/Marine-Cargo-Transit.md": """---
title: Marine Cargo & Freight Transit Underwriting
tags: [underwriting, cargo, freight, logistics]
tier: Archival
brand: "[[Jaguar-Transit]]"
---

# Marine Cargo & Freight Transit Underwriting

Logistics indemnity constraints governing assets for [[Jaguar-Transit]].

## Core Underwriting Principles
1. **No Physical Invulnerability Claims**: Marketing must highlight financial reimbursement and telemetry monitoring, never physical indestructibility.
2. **Cold-Chain Temperature Excursion**: Sensor-driven parametric triggers require verifiable data logger calibration.
3. **War & Strike Clauses**: Institute Cargo Clauses (A/B/C) distinctions must be preserved.

Connected entities: [[Jaguar-Transit]], [[Universal-Rubric]], [[BNM-FTFC]], [[JA-Assure-Second-Brain]].
""",

        # =========================================================================
        # COMPLIANCE & REGULATORS
        # =========================================================================
        "Compliance/Universal-Rubric.md": """---
title: Universal Global Marketing Compliance Rubric
tags: [compliance, rubric, legal, guardrails]
tier: Archival
rubric_source: "compliance_rubric.md"
---

# Universal Global Marketing Compliance Rubric

The master statutory rulebook loaded directly into [[Compliance-Gate]] on every pipeline execution.

## 1. Universal Prohibitions (All Brands)
- **No Absolute Guarantees**: Assets MUST NOT contain phrases guaranteeing claim approval, full payouts, or immediate coverage.
- **Accurate Representation of Risk**: Assets MUST NOT imply that buying insurance prevents theft, accidents, or lawsuits.
- **No Unsubstantiated Superlatives**: Marketers shall not use 'fastest', 'cheapest', or 'best in Asia' without audited empirical proof.

## 2. Banned Phrases
`100% guaranteed`, `always approved`, `cheap`, `loophole`, `immune`, `foolproof`, `100% covered`, `zero risk`, `guaranteed payout`, `no questions asked`, `unlimited coverage`.

## 3. Mandatory Disclaimers
Every approved asset MUST include at least one approved statutory disclaimer:
> *"Terms, conditions, and exclusions apply. Subject to formal policy wording and underwriting approval. This is general information only and does not constitute financial advice."*

## 4. Self-Healing Redlines
When violations occur, [[Compliance-Gate]] proposes minimal redlines, replacing banned terms with claim-safe alternatives and appending required disclaimers.

Connected Jurisdictions:
- [[MAS-Notice-318]] (Singapore)
- [[BNM-FTFC]] (Malaysia)
- [[HKIA-Guideline-27]] (Hong Kong)
- [[OIC-Thailand]] (Thailand)
- [[OJK-Indonesia]] (Indonesia)
""",

        "Compliance/MAS-Notice-318.md": """---
title: MAS Notice 318 & 321 — Market Conduct Guidelines (Singapore)
tags: [compliance, jurisdiction, singapore, mas]
tier: Archival
jurisdiction: Singapore
regulator: Monetary Authority of Singapore
cited_as: MAS-1
---

# MAS Notice 318 / 321 — Market Conduct (Singapore)

Issued by the Monetary Authority of Singapore (MAS) under the Insurance Act 1966.

## Mandatory Marketing Requirements
1. **Clause 4.2 (No Guarantees)**: Marketers shall not use unqualified words like 'guaranteed', '100% covered', or 'zero risk'.
2. **Clause 3.1 (Substantiation of Superlatives)**: Comparative claims require empirical, audited evidence.
3. **Clause 5.3 (Clear Exclusions)**: Any post advertising claim indemnification must state that terms, conditions, and policy exclusions apply.
4. **Mandatory Singapore Disclaimer**:
   > *"This material is for informational purposes only and does not constitute insurance or financial advice."*

Connected entities: [[Jade]], [[DoctorShield]], [[Universal-Rubric]], [[Compliance-Gate]].
""",

        "Compliance/BNM-FTFC.md": """---
title: BNM Fair Treatment of Financial Consumers (Malaysia)
tags: [compliance, jurisdiction, malaysia, bnm]
tier: Archival
jurisdiction: Malaysia
regulator: Bank Negara Malaysia
cited_as: BNM-1
---

# BNM FTFC — Fair Treatment of Financial Consumers (Malaysia)

Regulatory framework enforced by Bank Negara Malaysia under the Financial Services Act 2013.

## Core Directives
1. **Plain Language**: Marketing must avoid misleading legal jargon and present balanced policy limitations.
2. **Bahasa Malaysia Clarity**: When targeting Malaysian consumers, provide formal bilingual warnings.
3. **Mandatory Malaysian Warning**:
   > *"Maklumat ini adalah untuk tujuan maklumat am sahaja dan tidak membentuk nasihat kewangan rasmi. Tertakluk kepada terma dan syarat."*
4. **Prohibited Phrases**: `dijamin 100%`, `tanpa risiko`, `pasti lulus`.

Connected entities: [[Jaguar-Transit]], [[DoctorShield]], [[Universal-Rubric]], [[Compliance-Gate]].
""",

        "Compliance/HKIA-Guideline-27.md": """---
title: HKIA Guideline 27 & Intermediaries Code (Hong Kong)
tags: [compliance, jurisdiction, hongkong, hkia]
tier: Archival
jurisdiction: Hong Kong
regulator: Hong Kong Insurance Authority
cited_as: HKIA-1
---

# HKIA Guideline 27 — Code of Conduct (Hong Kong)

Enforced by the Hong Kong Insurance Authority for market representations and medical indemnity.

## Core Directives
1. **No Misleading Offer Language**: Advertisements must not create unreasonable expectations of coverage.
2. **Mandatory Traditional Chinese Disclaimer**:
   > *"本資料僅供參考，並不構成任何要約或保險建議。受條款及細則約束。"*
3. **Prohibited Terms**: `保證賠償`, `零風險`, `100%賠足`.

Connected entities: [[DoctorShield]], [[Jade]], [[Universal-Rubric]], [[Compliance-Gate]].
""",

        "Compliance/OIC-Thailand.md": """---
title: OIC Non-Life Insurance Act B.E. 2535 (Thailand)
tags: [compliance, jurisdiction, thailand, oic]
tier: Archival
jurisdiction: Thailand
regulator: Office of Insurance Commission
cited_as: OIC-1
---

# OIC Standards — Thailand

Direct marketing rules under the Thai Non-Life Insurance Act B.E. 2535.

## Directives
1. **Mandatory Thai Disclaimer**:
   > *"เอกสารนี้มีวัตถุประสงค์เพื่อการประชาสัมพันธ์เท่านั้น โปรดศึกษารายละเอียดความคุ้มครองและข้อยกเว้นในกรมธรรม์ประกันภัย"*
2. **Prohibited Terms**: `คุ้มครอง 100% ไม่มีเงื่อนไข`.

Connected entities: [[Jaguar-Transit]], [[Universal-Rubric]], [[Compliance-Gate]].
""",

        "Compliance/OJK-Indonesia.md": """---
title: OJK POJK 22/2023 Consumer Protection (Indonesia)
tags: [compliance, jurisdiction, indonesia, ojk]
tier: Archival
jurisdiction: Indonesia
regulator: Otoritas Jasa Keuangan
cited_as: OJK-1
---

# OJK POJK 22/2023 — Indonesia

Consumer protection regulations by Otoritas Jasa Keuangan (OJK).

## Directives
1. **Mandatory Bahasa Indonesia Disclaimer**:
   > *"Informasi ini hanya untuk edukasi dan bukan merupakan nasihat asuransi formal. Syarat & ketentuan berlaku."*
2. **Prohibited Terms**: `dijamin pasti cair`, `tanpa risiko sama sekali`.

Connected entities: [[Jaguar-Transit]], [[Universal-Rubric]], [[Compliance-Gate]].
""",

        # =========================================================================
        # PIPELINE NODES (PROJECT 1: THE BRAIN)
        # =========================================================================
        "Pipeline/LangGraph-Engine.md": """---
title: LangGraph Orchestration & Cyclic State Machine
tags: [pipeline, langgraph, architecture, state-machine]
tier: Archival
component: "app/graph/graph.py"
---

# LangGraph Orchestration & Cyclic State Machine

The core intelligence coordinating the multi-agent content generation workflow.

```
START ──> Memory Retrieval ──> Market Research ──> Content Agent ──> Localization
                                                        ▲                  │
                                                        │ (retry <= 3)     ▼
                 Persist (Pending) <── Compliant <── Compliance Gate <── Media Assembly
                                            │
                                            ▼ (retry > 3)
                                  Manual Intervention
```

## Cyclic vs Linear Pipeline
Unlike naive prompt chains, the content pipeline incorporates an active feedback loop. When [[Compliance-Gate]] discovers regulatory violations, it routes execution back to [[Content-Agent]] with specific rubric violations attached.

## Circuit Breaker
When `retry_count > 3`, the [[Circuit-Breaker]] fires, terminating the loop and diverting the generation to [[Manual-Intervention]].

Connected Pipeline Nodes:
- [[Memory-Retrieval-Agent]]
- [[Market-Research-Agent]]
- [[Content-Agent]]
- [[Localization-Agent]]
- [[Compliance-Gate]]
- [[Circuit-Breaker]]
- [[Publisher-Worker]]
""",

        "Pipeline/Memory-Retrieval-Agent.md": """---
title: Memory Retrieval Agent
tags: [pipeline, agent, memory, feedback]
tier: RAM / Recall
component: "app/graph/nodes/memory_retrieval.py"
---

# Memory Retrieval Agent

Fetches the last 5 human edits and rejections from [[Tier-2-Mem0-Buffer]] before [[Content-Agent]] drafts copy.

## Key Attributes
- Runs exactly once at pipeline initiation.
- Grounds agent generation in historical operational feedback.
- Prevents repeating previous marketing errors.

Connected entities: [[LangGraph-Engine]], [[Tier-2-Mem0-Buffer]], [[Content-Agent]].
""",

        "Pipeline/Market-Research-Agent.md": """---
title: Market Research Agent
tags: [pipeline, agent, research, scraping]
tier: RAM / Recall
component: "app/graph/nodes/market_research.py"
---

# Market Research Agent

Gathers real-time competitor intelligence and underwriting news via DuckDuckGo search and Crawl4AI web extraction.

## Features
- Keyless live research (zero API quota restrictions).
- Extracts competitor hooks, industry risks, and regional insurance trends.
- Grounds [[Content-Agent]] in current market realities.

Connected entities: [[LangGraph-Engine]], [[Content-Agent]].
""",

        "Pipeline/Content-Agent.md": """---
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
""",

        "Pipeline/Localization-Agent.md": """---
title: Localization Agent
tags: [pipeline, agent, localization, multilingual]
tier: RAM / Recall
component: "app/graph/nodes/localization.py"
---

# Localization Agent

Adapts draft copy to target jurisdictions across Southeast Asia.

## Supported Locales
- **Singapore**: English (business standard) with [[MAS-Notice-318]] disclaimers.
- **Malaysia**: English & Bahasa Malaysia with [[BNM-FTFC]] disclaimers.
- **Hong Kong**: Traditional Chinese (繁體中文) with [[HKIA-Guideline-27]] disclaimers.
- **Thailand**: Thai (ภาษาไทย) with [[OIC-Thailand]] disclaimers.
- **Indonesia**: Bahasa Indonesia with [[OJK-Indonesia]] disclaimers.

Connected entities: [[Content-Agent]], [[Compliance-Gate]], [[Video-Assembly-Veo]].
""",

        "Pipeline/Compliance-Gate.md": """---
title: Compliance Gate Node
tags: [pipeline, agent, compliance, rubric, guardrail]
tier: Archival
component: "app/graph/nodes/compliance_gate.py"
---

# Compliance Gate Node

The statutory gatekeeper evaluating every marketing draft against [[Universal-Rubric]].

## Operational Policy
- Grounded in `compliance_rubric.md` read from disk on every invocation.
- Increments `retry_count`.
- Proposes minimal redlines replacing prohibited superlatives.
- Routes compliant drafts to persistent queue; routes failed drafts to [[Content-Agent]] or [[Circuit-Breaker]].

Connected entities: [[LangGraph-Engine]], [[Universal-Rubric]], [[Circuit-Breaker]].
""",

        "Pipeline/Circuit-Breaker.md": """---
title: Circuit Breaker & Retry Routing Policy
tags: [pipeline, safety, routing, circuit-breaker]
tier: Archival
component: "app/graph/routing.py"
---

# Circuit Breaker & Retry Routing Policy

Prevents infinite retry loops in cyclic state machine execution.

## Policy
```python
if status == "compliant":
    return "persist_node"
elif retry_count <= max_compliance_retries:
    return "content_node"
else:
    return "manual_intervention_node"
```

Connected entities: [[LangGraph-Engine]], [[Compliance-Gate]], [[Manual-Intervention]].
""",

        "Pipeline/Video-Assembly-Veo.md": """---
title: Video Assembly & Veo Generative Video Engine
tags: [pipeline, video, veo, media, reels]
tier: Archival
component: "app/media/assembly.py"
---

# Video Assembly & 3-Tier Fallback

Generates vertical 1080x1920 MP4 video reels for [[TikTok]] and [[Instagram]].

## 3-Tier Robust Architecture
1. **Tier 1: Google Veo** — Generative video prompted directly from script keywords.
2. **Tier 2: Pexels Stock Clip** — Real stock footage keyed off script topics (`app/media/stock_video.py`).
3. **Tier 3: ColorClip Safety Net** — Brand-tinted MoviePy ColorClip fallback with subtitles and Edge-TTS voiceover.

Connected entities: [[LangGraph-Engine]], [[TikTok]], [[Instagram]], [[Video-Reel]].
""",

        "Pipeline/Image-Generation.md": """---
title: Image Generation Engine
tags: [pipeline, image, gemini, pollinations, media]
tier: Archival
component: "app/llm/client.py"
---

# Image Generation Engine

Renders hero images and carousel slides.

## Architecture
- **Primary**: Gemini native image-output models (`gemini-3.1-flash-image`).
- **Keyless Fallback**: Pollinations free REST image API when Gemini quota/billing is unavailable.
- Prompting: Derived strictly from copy topics — never artificially injected with brand names to prevent topic drift.

Connected entities: [[LangGraph-Engine]], [[Instagram]], [[Carousel-Format]].
""",

        "Pipeline/Publisher-Worker.md": """---
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
""",

        "Pipeline/Manual-Intervention.md": """---
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
""",

        # =========================================================================
        # MEMORY HIERARCHY
        # =========================================================================
        "Memory/3-Tier-Memory-OS.md": """---
title: 3-Tier Virtual Memory Hierarchy OS
tags: [memory, architecture, hierarchy, second-brain]
tier: RAM / Recall / Disk
---

# 3-Tier Virtual Memory Hierarchy OS

Modeled after modern operating system memory hierarchies to balance latency, recall precision, and durability.

```
┌───────────────────────────────────────────────────────────┐
│ Tier 1: RAM Working Context (Prompt Token Window)        │
├───────────────────────────────────────────────────────────┤
│ Tier 2: Mem0 Recall Buffer (Dynamic Semantic Retrieval)   │
├───────────────────────────────────────────────────────────┤
│ Tier 3: Archival Disk Vault (Obsidian Markdown Second Brain) │
└───────────────────────────────────────────────────────────┘
```

- [[Tier-1-RAM-Context]]: Active prompt window holding brand persona and task instructions.
- [[Tier-2-Mem0-Buffer]]: Dynamic semantic buffer storing human corrections and rejection notes.
- [[Tier-3-Archival-Vault]]: Persistent disk knowledge base formatted as Markdown notes in this vault.
- [[DSPy-GEPA-Evolution]]: Evolutionary prompt optimizer tuning constraints across generations.

Connected Hub: [[JA-Assure-Second-Brain]].
""",

        "Memory/Tier-1-RAM-Context.md": """---
title: Tier 1 — RAM Working Context
tags: [memory, tier-1, ram, tokens]
tier: RAM
---

# Tier 1 — RAM Working Context

The volatile LLM token context budget (typically 4,000–8,192 tokens) allocated during prompt evaluation.

Connected entities: [[3-Tier-Memory-OS]], [[Content-Agent]].
""",

        "Memory/Tier-2-Mem0-Buffer.md": """---
title: Tier 2 — Mem0 Recall Buffer
tags: [memory, tier-2, mem0, semantic-recall]
tier: Recall
---

# Tier 2 — Mem0 Recall Buffer

Dynamic semantic cache of recent human interventions, rubric violations, and regulatory penalties.

Connected entities: [[3-Tier-Memory-OS]], [[Memory-Retrieval-Agent]], [[Manual-Intervention]].
""",

        "Memory/Tier-3-Archival-Vault.md": """---
title: Tier 3 — Archival Disk Vault
tags: [memory, tier-3, archival, disk, obsidian]
tier: Disk
---

# Tier 3 — Archival Disk Vault

The durable on-disk knowledge graph maintained in this Obsidian vault. Contains underwriting boundaries, statutory rubrics, and run logs.

Connected entities: [[3-Tier-Memory-OS]], [[JA-Assure-Second-Brain]].
""",

        "Memory/DSPy-GEPA-Evolution.md": """---
title: DSPy Genetic-Pareto Prompt Evolution (GEPA)
tags: [memory, dspy, gepa, prompt-optimization]
tier: RAM / Recall
---

# DSPy Genetic-Pareto Prompt Evolution (GEPA)

Optimization engine treating prompts as trainable parameters. Discovers Pareto-optimal prompts balancing regulatory compliance (score >= 95) with engagement click-through rates.

Connected entities: [[3-Tier-Memory-OS]], [[Content-Agent]], [[Compliance-Gate]].
""",

        # =========================================================================
        # CHANNELS
        # =========================================================================
        "Channels/LinkedIn.md": """---
title: LinkedIn Channel Specifications
tags: [channel, linkedin, b2b]
tier: Archival
---

# LinkedIn Channel

Primary distribution channel for B2B risk managers, luxury boutique owners, and medical practitioners.

Connected Brands: [[Jade]], [[DoctorShield]], [[Jaguar-Transit]].
Connected Hub: [[JA-Assure-Second-Brain]].
""",

        "Channels/Instagram.md": """---
title: Instagram Channel Specifications
tags: [channel, instagram, social, visual]
tier: Archival
---

# Instagram Channel

Visual storytelling platform featuring luxury jewellery showcases, aesthetic clinical procedures, and educational carousels.

Connected Formats: [[Carousel-Format]], [[Video-Reel]], [[Image-Generation]].
Connected Brands: [[Jade]], [[DoctorShield]].
""",

        "Channels/TikTok.md": """---
title: TikTok Channel Specifications
tags: [channel, tiktok, video, reels]
tier: Archival
---

# TikTok Channel

High-engagement short-form video platform for dynamic logistics coverage, heist defense explanations, and surgical liability mythbusting.

Connected Formats: [[Video-Reel]], [[Video-Assembly-Veo]].
Connected Brands: [[Jaguar-Transit]], [[Jade]].
""",

        "Channels/Video-Reel.md": """---
title: Video Reel Format Specifications
tags: [channel, format, video, reel]
tier: Archival
---

# Video Reel Format

9:16 vertical 1080x1920 video with dynamic synchronized subtitles and multilingual voiceover.

Produced by: [[Video-Assembly-Veo]].
""",

        "Channels/Carousel-Format.md": """---
title: Carousel Multi-Slide Format Specifications
tags: [channel, format, carousel, instagram]
tier: Archival
---

# Carousel Multi-Slide Format

Multi-slide educational graphics format breaking down complex insurance exclusions and compliance guidelines.

Rendered by: [[Image-Generation]].
""",

        # =========================================================================
        # COMPATIBILITY NOTES (MATCHING EXISTING SYSTEM DEFAULTS)
        # =========================================================================
        "Jade-Luxury-Underwriting.md": """---
title: Jade Luxury Jewellery Block Underwriting
brand: Jade
tags: [underwriting, jade, luxury, jewellery, mas318]
links: [[MAS-Notice-318]], [[DSPy-GEPA-Evolution]], [[Jade]]
last_updated: 2026-09-22
tier: Archival
---

# Jade — Luxury Jewellery & Diamond Block Underwriting

Comprehensive underwriting specification for [[Jade]] luxury insurance.

See full brand documentation at [[Jade]] and underwriting rules at [[Jewellery-Block-Underwriting]].
Governed by [[MAS-Notice-318]] and evaluated by [[Compliance-Gate]].
""",

        "MAS-Notice-318-Regulatory-Rubric.md": """---
title: MAS Notice 318 Market Conduct Guidelines
jurisdiction: Singapore
tags: [regulation, compliance, mas318, legal, guardrails]
links: [[Jade-Luxury-Underwriting]], [[DoctorShield-Medical-Liability]], [[MAS-Notice-318]]
last_updated: 2026-09-22
tier: Archival
---

# MAS Notice 318 — Market Conduct Guidelines

Detailed regulatory breakdown for Monetary Authority of Singapore requirements.

See comprehensive statute at [[MAS-Notice-318]] and universal rubric at [[Universal-Rubric]].
""",

        "DoctorShield-Medical-Liability.md": """---
title: DoctorShield Medical Malpractice & Liability
brand: DoctorShield
tags: [medical, malpractice, doctorshield, hkia, bnm]
links: [[MAS-Notice-318]], [[DSPy-GEPA-Evolution]], [[DoctorShield]]
last_updated: 2026-09-22
tier: Archival
---

# DoctorShield — Medical Malpractice & Clinical Indemnity

Specialized legal defence and indemnity for medical specialists.

See full brand profile at [[DoctorShield]] and underwriting parameters at [[Medical-Malpractice-Indemnity]].
""",

        "Jaguar-Transit-Marine-Cargo.md": """---
title: Jaguar Transit Cross-Border Marine & Cargo
brand: Jaguar Transit
tags: [logistics, freight, marine-cargo, supply-chain, bnm]
links: [[MAS-Notice-318]], [[Jaguar-Transit]]
last_updated: 2026-09-22
tier: Archival
---

# Jaguar Transit — Multi-Modal Freight & Cargo Indemnity

Protection against maritime, aviation, and cross-border overland cargo hazards.

See full brand profile at [[Jaguar-Transit]] and underwriting parameters at [[Marine-Cargo-Transit]].
""",

        "DSPy-GEPA-Lessons-Learned.md": """---
title: DSPy GEPA Prompt Evolution & Learned Constraints
system: Memory Engine
tags: [dspy, gepa, machine-learning, prompt-optimization, self-healing]
links: [[Jade-Luxury-Underwriting]], [[MAS-Notice-318]], [[DSPy-GEPA-Evolution]]
last_updated: 2026-09-22
tier: RAM / Recall
---

# DSPy Genetic-Pareto Prompt Optimizer (GEPA)

Closed-loop feedback engine treating system prompts as trainable parameters.

See full architecture at [[DSPy-GEPA-Evolution]] and memory hierarchy at [[3-Tier-Memory-OS]].
""",
    }

    for rel_path, content in notes.items():
        fp = vault_dir / rel_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content.strip() + "\n", encoding="utf-8")
        log.info("Wrote knowledge note: %s", rel_path)


def export_runs_from_database(vault_dir: Path) -> None:
    """Exports any existing content queue items from SQLite as rich linked execution run notes with Excalidraw diagrams."""
    db_path = BASE_DIR / "ja_assure.db"
    if not db_path.exists():
        log.info("No ja_assure.db found to export runs from.")
        return

    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute(
            """
            SELECT id, brand, platform, status, retry_count, content_type, topic, COALESCE(final_content, draft_content, '')
            FROM content_queue
            ORDER BY id ASC
            """
        )
        rows = cur.fetchall()
        con.close()
    except Exception as e:
        log.warning("Could not query content_queue: %s", e)
        return

    runs_folder = vault_dir / "JA-Assure-Runs"
    runs_folder.mkdir(parents=True, exist_ok=True)

    for r in rows:
        cid, brand, platform, status, retry_count, content_type, topic, text = r
        brand_val = brand or "Jade"
        plat_val = platform or "linkedin"
        brand_slug = _safe_slug(brand_val)
        plat_slug = _safe_slug(plat_val)
        stat_slug = _safe_slug(status or "pending")

        brand_link = "Jaguar-Transit" if "jaguar" in brand_val.lower() else ("DoctorShield" if "doctor" in brand_val.lower() else "Jade")
        plat_link = "LinkedIn" if "link" in plat_val.lower() else ("Instagram" if "insta" in plat_val.lower() else ("TikTok" if "tik" in plat_val.lower() else plat_val.capitalize()))

        slug = f"run-{cid:03d}-{brand_slug}-{plat_slug}"
        note_path = runs_folder / f"{slug}.md"
        excal_path = runs_folder / f"{slug}.excalidraw"

        note_content = [
            "---",
            f"title: JA Assure Run #{cid} ({brand_val} - {plat_link})",
            f"tags: [run, brand/{brand_slug}, channel/{plat_slug}, status/{stat_slug}]",
            f'brand: "[[{brand_link}]]"',
            f'channel: "[[{plat_link}]]"',
            'hub: "[[JA-Assure-Second-Brain]]"',
            'gate: "[[Compliance-Gate]]"',
            'orchestrator: "[[LangGraph-Engine]]"',
            f"run_id: {cid}",
            "tier: Archival",
            "---",
            "",
            f"# JA Assure Run #{cid} — {brand_val} on {plat_link}",
            "",
            "> Automated LangGraph cyclic execution log linked to the [[JA-Assure-Second-Brain]].",
            "",
            "## Network Topology Links",
            f"- **Target Brand**: [[{brand_link}]]",
            f"- **Distribution Channel**: [[{plat_link}]]",
            "- **State Machine Orchestrator**: [[LangGraph-Engine]]",
            "- **Compliance Gatekeeper**: [[Compliance-Gate]]",
            "- **Memory Feedback Buffer**: [[Tier-2-Mem0-Buffer]]",
            "",
            "## Execution Telemetry",
            f"- **Content Queue ID**: `#{cid}`",
            f"- **Status**: `{status}`",
            f"- **Retry Count**: `{retry_count}`",
            f"- **Content Type**: `{content_type or 'post'}`",
            f"- **Topic**: `{topic or 'Autonomous Underwriting Focus'}`",
            "",
            "## Execution Flow Diagram",
            f"![[{excal_path.name}]]",
            "",
            "## Generated Copy Preview",
            "```text",
            (text or "Content generated via LangGraph cyclic pipeline.").strip()[:600],
            "```",
            "",
            "## Active Regulatory Constraints",
            "Evaluated against [[Universal-Rubric]] and [[MAS-Notice-318]].",
        ]

        note_path.write_text("\n".join(note_content) + "\n", encoding="utf-8")

        include_video = plat_val.lower() in {"tiktok", "instagram"} or (content_type or "").lower() == "video"
        is_manual = status == "manual_intervention"
        excal_path.write_text(_build_excalidraw_json(include_video=include_video, manual=is_manual), encoding="utf-8")
        log.info("Exported database run: %s", note_path.name)


def main() -> None:
    vault_dir = get_vault_dir()
    log.info("Starting Obsidian Vault Synchronization at: %s", vault_dir)

    # 1. Generate Core Knowledge Base
    generate_knowledge_base(vault_dir)

    # 2. Export database runs
    export_runs_from_database(vault_dir)

    # 3. Clean up default Welcome.md if present
    welcome_file = vault_dir / "Welcome.md"
    if welcome_file.exists():
        try:
            welcome_file.unlink()
            log.info("Removed default Welcome.md placeholder.")
        except Exception:
            pass

    log.info("Obsidian Vault Synchronization completed successfully! All notes & links generated.")


if __name__ == "__main__":
    main()
