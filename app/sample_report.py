"""Static sample report used by the /sample route to preview the UI without
running the pipeline (no API keys required)."""

SAMPLE_REPORT = {
    "status": "complete",
    "warning": None,
    "cards": [
        {
            "display_name": "Amoxicillin 500mg",
            "raw_text": "Amoxi 500",
            "package_image_url": "https://dailymed.nlm.nih.gov/dailymed/image.cfm?setid=amoxicillin-sample&type=img",
            "what_its_for": "A penicillin-type antibiotic used to treat a range of bacterial infections.",
            "dosage": {
                "as_written": "500mg",
                "frequency_as_written": "TID x 7d",
                "general_reference": "250\u2013500mg every 8 hours",
                "source": "openfda",
            },
            "side_effects": ["Nausea", "Diarrhea", "Rash", "Headache"],
            "safety_source": "openfda",
            "generic_alternatives": ["Amoxicillin trihydrate", "Co-amoxiclav"],
            "purchase_links": {"tata_1mg": "#", "pharmeasy": "#", "netmeds": "#"},
            "needs_verification": False,
            "verification_reason": None,
        },
        {
            "display_name": "Paracetamol 650mg",
            "raw_text": "Dolo 650",
            "package_image_url": None,
            "what_its_for": "Reduces fever and relieves mild to moderate pain.",
            "dosage": {
                "as_written": "650mg",
                "frequency_as_written": "SOS, max 3/day",
                "general_reference": "500\u20131000mg every 4\u20136 hours",
                "source": "openfda",
            },
            "side_effects": ["Nausea", "Liver strain at high doses"],
            "safety_source": "openfda",
            "generic_alternatives": ["Acetaminophen"],
            "purchase_links": {"tata_1mg": "#", "pharmeasy": "#", "netmeds": "#"},
            "needs_verification": False,
            "verification_reason": None,
        },
        {
            "display_name": "Pantoprazole",
            "raw_text": "Pan-D",
            "package_image_url": None,
            "what_its_for": None,
            "dosage": {
                "as_written": "1 tab",
                "frequency_as_written": "before breakfast",
                "general_reference": None,
                "source": None,
            },
            "side_effects": [],
            "safety_source": None,
            "generic_alternatives": [],
            "purchase_links": None,
            "needs_verification": True,
            "verification_reason": "Low OCR confidence on brand name",
        },
    ],
    "disclaimers": [
        "This is informational only. Confirm dosage and interactions with your pharmacist or doctor before use.",
        "General dosing shown is standard reference information, not a personal recommendation \u2014 your actual "
        "prescribed dose may differ.",
    ],
}
