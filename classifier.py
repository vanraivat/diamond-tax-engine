import os
import json
import asyncio
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

async def classify_batch_async(vendor_batch):
    """Processes a batch of up to 20 vendors concurrently via Gemini."""
    prompt = f"""
    You are an expert Indian Chartered Accountant auditing a diamond enterprise. 
    Classify these transaction descriptions into EXACTLY ONE of these categories:
    {VALID_CATEGORIES}
    
    Transactions to classify:
    {json.dumps(vendor_batch)}
    
    Respond ONLY with a valid JSON object mapping the exact description to the category:
    {{"Vendor A": "Category", "Vendor B": "Category"}}
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.0 # Zero creativity for maximum classification consistency
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini API Error on batch: {e}")
        return {vendor: "Miscellaneous" for vendor in vendor_batch}

async def process_vendors_concurrently(vendors):
    """Splits vendors into batches and processes them via async tasks."""
    batch_size = 20
    # Create chunks of 20 vendors
    batches = [vendors[i:i + batch_size] for i in range(0, len(vendors), batch_size)]
    
    # Fire all chunks at Google's servers simultaneously
    tasks = [classify_batch_async(batch) for batch in batches]
    results = await asyncio.gather(*tasks)
    
    final_mapping = {}
    for res in results:
        # Enforce hallucination guardrails on the returned batch
        for vendor, category in res.items():
            final_mapping[vendor] = category if category in VALID_CATEGORIES else "Miscellaneous"
            
    return final_mapping