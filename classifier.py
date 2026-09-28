import os
import json
import google.generativeai as genai

# --- SECURITY: Load your Gemini API Key ---
# Set this variable in your terminal using: set GEMINI_API_KEY="your_actual_key_here"
# Or just paste it directly below for local testing (but remove it before uploading to GitHub!)
import streamlit as st
API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=API_KEY)

VALID_CATEGORIES = [
    "Testing & Certification", 
    "Manufacturing / Job Work", 
    "Brokerage & Commissions",
    "Logistics & Secure Freight",
    "Repairs & Maintenance",
    "Software & IT Infrastructure",
    "Capital Machinery",
    "Miscellaneous"
]

def predict_category(vendor_text):
    """
    Passes the transaction description to Gemini 1.5 Flash for semantic classification.
    Returns: (Category_String, Confidence_Score)
    """
    if API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        print("⚠️ Warning: Gemini API Key not set. Defaulting to Miscellaneous.")
        return "Miscellaneous", 0.0

    prompt = f"""
    You are an expert Indian Chartered Accountant auditing a diamond manufacturing enterprise.
    Classify the following bank transaction description into EXACTLY ONE of these ledger categories:
    {VALID_CATEGORIES}
    
    Transaction Description: "{vendor_text}"
    
    Respond ONLY with a valid JSON object in this exact format:
    {{
        "category": "The Chosen Category",
        "confidence": 0.95
    }}
    """
    
    try:
        # We use flash for speed, and explicitly force a JSON response
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1 # Low temperature for consistent, analytical responses
            )
        )
        
        # Parse the JSON response securely
        result = json.loads(response.text)
        category = result.get("category", "Miscellaneous")
        confidence = float(result.get("confidence", 0.0))
        
        # Hallucination Guardrail
        if category not in VALID_CATEGORIES:
            category = "Miscellaneous"
            
        return category, confidence

    except Exception as e:
        print(f"Gemini API Error on text '{vendor_text}': {e}")
        return "Miscellaneous", 0.0