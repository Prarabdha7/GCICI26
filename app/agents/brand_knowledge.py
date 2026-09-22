"""Brand and jurisdiction knowledge — ported from src/config.py.

Single source of truth for brand voices, colors, risk factors, disclaimers
and per-jurisdiction regulatory schedules. Imported by prompts, fallback
generators, compliance checks and video assembly. No secrets here.
"""

from __future__ import annotations

BRANDS: dict[str, dict] = {
    "jade": {
        "id": "jade",
        "name": "Jade",
        "parent": "JA Assure",
        "niche": "Jewellers Block Insurance",
        "tagline": "Bespoke protection for fine jewellery, precious gems, and goldsmiths",
        "audiences": ["Retail Jewellers", "Gem Traders", "Goldsmiths", "Auction Houses", "Watch Dealers"],
        "territories": ["Singapore", "Hong Kong", "Malaysia", "Thailand", "Indonesia"],
        "voice": "Prestigious, discreet, meticulous, security-first, heritage-aware",
        "colors": {
            "primary": "#0A3B2C",
            "secondary": "#D4AF37",
            "background": "#051F17",
            "text": "#FDFBF7",
            "accent": "#2DD4BF",
        },
        "risk_factors": ["Burglary / safe cracking", "Smash-and-grab retail robbery", "Exhibition transit", "Memo goods loss"],
        "compliance_disclaimer": "Jade Jewellers Block is underwritten by licensed insurance partners and administered by JA Assure Pte Ltd. Terms and conditions apply.",
    },
    "jaguar_transit": {
        "id": "jaguar_transit",
        "name": "Jaguar Transit",
        "parent": "JA Assure",
        "niche": "High-Value Goods Transit Insurance",
        "tagline": "Unbroken chain-of-custody protection for luxury logistics and high-value cargo",
        "audiences": ["Specialized Couriers", "Bullion & Cash Handlers", "Luxury Watch & Art Logistics", "Freight Forwarders"],
        "territories": ["Singapore", "Malaysia", "Hong Kong", "Indonesia", "Thailand"],
        "voice": "Vigilant, operational, logistics-savvy, resilient, real-time risk conscious",
        "colors": {
            "primary": "#1E293B",
            "secondary": "#F59E0B",
            "background": "#0F172A",
            "text": "#F8FAFC",
            "accent": "#38BDF8",
        },
        "risk_factors": ["Hijacking & road theft", "Port & tarmac storage delays", "Disputed chain-of-custody", "High-value loss in transit"],
        "compliance_disclaimer": "Jaguar Transit policies are underwritten by authorized insurers and managed by JA Assure. Coverage limits depend on declared route telemetry and policy terms.",
    },
    "doctorshield": {
        "id": "doctorshield",
        "name": "DoctorShield",
        "parent": "JA Assure",
        "niche": "Medical Malpractice & Professional Indemnity",
        "tagline": "Doctor-first medical defence and legal protection across Southeast Asia",
        "audiences": ["Private Clinic Physicians", "Specialist Surgeons", "Aesthetic Practitioners", "Dental Specialists"],
        "territories": ["Singapore", "Malaysia", "Hong Kong", "Thailand", "Indonesia"],
        "voice": "Empathetic, legally rigorous, doctor-first advocate, reassuring, peer-to-peer",
        "colors": {
            "primary": "#0F172A",
            "secondary": "#06B6D4",
            "background": "#082F49",
            "text": "#FFFFFF",
            "accent": "#38BDF8",
        },
        "risk_factors": ["Disciplinary inquiries (SMC / MMC / HKMC)", "Informed consent litigation", "Diagnostic delay allegations", "Data privacy & clinic cyber risks"],
        "compliance_disclaimer": "DoctorShield is distributed by JA Assure. Specific coverage, retroactive dates, and exclusions are subject to formal underwriting criteria.",
    },
}

# Canonical display-name lookup (repo uses "Jade" / "Jaguar Transit" / "DoctorShield").
BRAND_BY_NAME: dict[str, dict] = {
    "jade": BRANDS["jade"],
    "jaguar transit": BRANDS["jaguar_transit"],
    "jaguar_transit": BRANDS["jaguar_transit"],
    "doctorshield": BRANDS["doctorshield"],
    "doctor shield": BRANDS["doctorshield"],
}


def get_brand(brand: str) -> dict:
    """Case-insensitive brand lookup, defaults to Jade."""
    return BRAND_BY_NAME.get((brand or "").strip().lower(), BRANDS["jade"])


JURISDICTIONS: dict[str, dict] = {
    "Singapore": {
        "regulator": "Monetary Authority of Singapore (MAS)",
        "framework": "Insurance Act 1966 & MAS Notice 318 / Notice 321",
        "mandatory_warnings": "This material is for informational purposes and does not constitute insurance or financial advice.",
        "prohibited_terms": ["100% covered", "zero risk", "instant guaranteed payout", "no questions asked", "unlimited coverage"],
    },
    "Malaysia": {
        "regulator": "Bank Negara Malaysia (BNM)",
        "framework": "Financial Services Act 2013 & Fair Treatment of Financial Consumers (FTFC)",
        "mandatory_warnings": "Maklumat ini adalah untuk tujuan maklumat am sahaja dan tidak membentuk nasihat kewangan rasmi.",
        "prohibited_terms": ["dijamin 100%", "tanpa risiko", "tuntutan serta-merta tanpa soalan", "pampasan tanpa had"],
    },
    "Hong Kong": {
        "regulator": "Insurance Authority (HKIA)",
        "framework": "Insurance Authority Guideline 27 & Code of Conduct for Licensed Insurance Intermediaries",
        "mandatory_warnings": "本資料僅供參考，並不構成任何要約或保險建議。受條款及細則約束。",
        "prohibited_terms": ["保證賠償", "零風險", "100%賠足", "無條件理賠"],
    },
    "Thailand": {
        "regulator": "Office of Insurance Commission (OIC)",
        "framework": "Non-Life Insurance Act B.E. 2535 and Market Conduct Regulations",
        "mandatory_warnings": "เอกสารนี้มีวัตถุประสงค์เพื่อการประชาสัมพันธ์เท่านั้น โปรดศึกษารายละเอียดความคุ้มครอง",
        "prohibited_terms": ["คุ้มครอง 100% ไม่มีเงื่อนไข", "เคลมได้ทันทีโดยไม่ต้องตรวจ", "ไม่มีความเสี่ยง"],
    },
    "Indonesia": {
        "regulator": "Otoritas Jasa Keuangan (OJK)",
        "framework": "POJK Nomor 22/POJK.04/2023 tentang Pelindungan Konsumen Sektor Jasa Keuangan",
        "mandatory_warnings": "Informasi ini hanya untuk edukasi dan bukan merupakan nasihat asuransi formal. Syarat & ketentuan berlaku.",
        "prohibited_terms": ["dijamin pasti cair", "tanpa risiko sama sekali", "klaim 100% tanpa syarat"],
    },
}

LANGUAGE_TO_JURISDICTION: dict[str, str] = {
    "en": "Singapore",
    "ms": "Malaysia",
    "zh": "Hong Kong",
    "th": "Thailand",
    "id": "Indonesia",
}
