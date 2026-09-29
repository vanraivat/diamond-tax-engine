import json
import streamlit as st
import google.generativeai as genai

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

def process_vendors_batch(vendors):
    """Processes all unique vendors in a single, stable bulk API call."""
    if not vendors:
        return {}
        
    prompt = f"""
    You are an expert Indian Chartered Accountant auditing a diamond enterprise. 
    Classify these transaction descriptions into EXACTLY ONE of these categories:
    {VALID_CATEGORIES}
    
    Transactions to classify:
    {json.dumps(vendors)}
    
    Respond ONLY with a valid JSON object mapping the exact description to the category:
    {{"Vendor A": "Category", "Vendor B": "Category"}}
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        # Standard synchronous call - incredibly stable on Streamlit Cloud
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )
        
        result = json.loads(response.text)
        
        # Map them back safely, enforcing guardrails
        final_mapping = {}
        for vendor in vendors:
            cat = result.get(vendor, "Miscellaneous")
            final_mapping[vendor] = cat if cat in VALID_CATEGORIES else "Miscellaneous"
            
        return final_mapping

    except Exception as e:
        # If it fails, print the exact error to the screen so we can see it!
        st.error(f"🚨 AI Engine Error: {e}")
        return {vendor: "Miscellaneous" for vendor in vendors}