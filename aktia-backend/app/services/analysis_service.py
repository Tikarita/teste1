def analyze_radiograph(image_bytes: bytes):

    return {
        "quality_score": 82,
        "status": "attention",
        "findings": [
            {
                "category": "sharpness",
                "score": 75,
                "status": "attention",
                "confidence": 0.89,
                "description": "Possível redução de nitidez."
            },
            {
                "category": "exposure",
                "score": 92,
                "status": "approved",
                "confidence": 0.95,
                "description": "Exposição adequada."
            }
        ],
        "recommendation": "A imagem apresenta qualidade aceitável, porém requer atenção à nitidez."
    }