import json
import streamlit as st
import google.generativeai as genai

# Safely load the API key whether running locally or on the cloud
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    API_KEY = "YOUR_ACTUAL_GEMINI_API_KEY"

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
    """Processes unique vendors using an ID-based mapping for 100% accuracy."""
    if not vendors:
        return {}
        
    # 1. Map exact vendor strings to numerical IDs
    vendor_dict = {i: vendor for i, vendor in enumerate(vendors)}
    
    # 2. Build a payload using only the IDs
    payload = [{"id": k, "description": v} for k, v in vendor_dict.items()]
        
    prompt = f"""
    You are an expert Indian Chartered Accountant auditing a diamond enterprise. 
    Classify these transaction descriptions into EXACTLY ONE of these categories:
    {VALID_CATEGORIES}
    
    Transactions:
    {json.dumps(payload)}
    
    Respond ONLY with a valid JSON array of objects in this exact format:
    [
        {{"id": 0, "category": "Capital Machinery"}},
        {{"id": 1, "category": "Miscellaneous"}}
    ]
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )
        
        result = json.loads(response.text)
        
        # 3. Reconstruct the mapping by linking the returned IDs back to the exact strings
        final_mapping = {}
        for item in result:
            v_id = item.get("id")
            cat = item.get("category", "Miscellaneous")
            
            if v_id in vendor_dict:
                vendor_string = vendor_dict[v_id]
                final_mapping[vendor_string] = cat if cat in VALID_CATEGORIES else "Miscellaneous"
                
        # 4. Fallback for any missing items
        for v in vendors:
            if v not in final_mapping:
                final_mapping[v] = "Miscellaneous"
                
        return final_mapping

    except Exception as e:
        st.error(f"🚨 AI Engine Error: {e}")
        return {vendor: "Miscellaneous" for vendor in vendors}