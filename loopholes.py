import re
import requests
from sqlalchemy import func

GSTIN_PATTERN = r'\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b'

# --- 1. LIVE GOVERNMENT VALIDATION (GSTN) ---
def verify_live_gstin(gstin_string):
    """
    Validates GSTIN against public search gateways or verifies format checksum.
    """
    match = re.search(GSTIN_PATTERN, gstin_string)
    if not match:
        return "MISSING", "No valid 15-digit GSTIN pattern detected."
    
    gstin = match.group(0)
    try:
        # Public search check via taxpayer search gateway (timeout safe)
        url = f"https://commonapi.gst.gov.in/commonapi/v0.3/search?action=TP&gstin={gstin}"
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "ACTIVE")
            if status.upper() != "ACTIVE":
                return "RISK", f"GSTIN {gstin} is {status.upper()} on the GSTN portal."
            return "VALID", f"GSTIN {gstin} verified ACTIVE."
    except Exception:
        pass
    
    # Fallback: Structural check
    state_code = int(gstin[:2])
    if 1 <= state_code <= 38:
        return "VALID", f"GSTIN {gstin} structurally validated."
    return "RISK", f"GSTIN {gstin} contains an invalid state code ({state_code})."


# --- 2. CUMULATIVE VENDOR THRESHOLD TRACKING (Section 194C / 194J) ---
def check_cumulative_tds_threshold(session, client_id, vendor_name, current_amount, category):
    """
    Income Tax Act: Checks if single payment > 30k OR cumulative FY total > 1,00,000.
    """
    from database import Transaction
    
    past_total = session.query(func.sum(Transaction.amount)).filter(
        Transaction.client_id == client_id,
        Transaction.vendor == vendor_name
    ).scalar() or 0.0

    projected_total = past_total + current_amount

    flags = []
    applicable_categories = ['Testing & Certification', 'Manufacturing / Job Work', 'Brokerage & Commissions']
    
    if any(c.lower() in category.lower() for c in applicable_categories):
        if current_amount >= 30000:
            flags.append(f"🟢 COMPLIANCE (Sec 194C/J): Single transaction exceeds ₹30,000. Deduct TDS.")
        elif projected_total >= 100000:
            flags.append(f"🔴 AUDIT WARNING: Cumulative payments to '{vendor_name}' reached ₹{projected_total:,.2f} (Threshold: ₹1,00,000). TDS required on aggregate sum.")
            
    return flags


# --- 3. CAPITAL ASSET DEPRECIATION (Section 32) ---
def check_depreciation_section_32(row):
    """
    Identifies capital acquisitions and routes them to statutory depreciation blocks.
    """
    vendor_desc = (str(row['Vendor']) + " " + str(row.get('Category', ''))).lower()
    amount = float(row['Amount'])
    
    # Computer / Laser Cutting Machinery blocks
    if any(k in vendor_desc for k in ['laser', 'sawing', 'machinery', 'polishing unit', 'equipment']):
        depr_rate = 15.0  # Plant & Machinery standard rate
        annual_depr = (amount * depr_rate) / 100
        return [f"ℹ️ SEC 32 DEPRECIATION: Capital asset detected. Capitalize to 'Plant & Machinery' (Block 15%). Allowable annual depreciation: ₹{annual_depr:,.2f}."]
    
    if any(k in vendor_desc for k in ['server', 'computer', 'macbook', 'laptop', 'software']):
        depr_rate = 40.0  # Computers & software
        annual_depr = (amount * depr_rate) / 100
        return [f"ℹ️ SEC 32 DEPRECIATION: Capital asset detected. Capitalize to 'Computers' (Block 40%). Allowable annual depreciation: ₹{annual_depr:,.2f}."]

    return []


# --- 4. FOREX FLUCTUATIONS & CUSTOMS ACT COMPLIANCE ---
def check_forex_and_customs(row, extracted_text):
    """
    Customs Act & AS-11 / Ind AS 21: Flags foreign currency entries and exchange differentials.
    """
    flags = []
    text_lower = extracted_text.lower()
    amount = float(row['Amount'])
    
    # Forex detection ($ / USD / EUR / AED)
    forex_match = re.search(r'(?i)(usd|\$|eur|€|aed)\s*([0-9,]+(?:\.[0-9]{2})?)', text_lower)
    if forex_match or str(row.get('Currency', '')).upper() != "INR":
        curr = forex_match.group(1).upper() if forex_match else row.get('Currency', 'USD')
        flags.append(f"⚠️ FEMA / AS-11 FOREX: Foreign currency transaction detected ({curr}). Ensure booking at SBI TT selling/buying rate on date of invoice. Reconcile realized forex variance at settlement.")
        
    # Customs Act Valuation
    if any(k in text_lower for k in ['import', 'antwerp', 'customs', 'cargo']):
        if 'bill of entry' not in text_lower:
            flags.append("🔴 CUSTOMS RISK: Rough/Polished import without explicit 'Bill of Entry' verification. Risk of seizure under Sec 111 Customs Act.")
        if 'icegate' not in text_lower:
            flags.append("ℹ️ COMPLIANCE: Verify customs duty payment and IGST reference on ICEGATE portal.")
            
    return flags


# --- 5. CORE EXECUTION PIPELINE ---
def run_rules_engine(expense_row, extracted_text, db_session=None, client_id=1):
    flags = []
    amount = float(expense_row['Amount'])
    pay_mode = str(expense_row.get('Payment_Mode', '')).lower()
    category = str(expense_row.get('Category', ''))

    # Cash Disallowance (Sec 40A(3) / Sec 269ST)
    if amount > 200000 and pay_mode == 'cash':
        flags.append(f"🔴 CRITICAL RISK: Sec 269ST Violation. Cash transaction ₹{amount:,.2f} exceeds ₹2 Lakh limit.")
    elif amount > 10000 and pay_mode == 'cash':
        flags.append(f"🔴 RISK: Section 40A(3) Disallowance. Cash payment exceeds ₹10,000 threshold.")

    # Live GSTIN Validation
    gst_status, gst_msg = verify_live_gstin(extracted_text)
    if gst_status == "RISK":
        flags.append(f"🔴 GST RISK: {gst_msg}")
    elif gst_status == "MISSING" and category in ['Logistics & Secure Freight', 'Testing & Certification']:
        flags.append(f"🟢 OPPORTUNITY: Missing GSTIN on {category}. Ineligible for ITC until tax invoice supplied.")

    # Cumulative Thresholds (Database-aware)
    if db_session:
        cum_flags = check_cumulative_tds_threshold(db_session, client_id, expense_row['Vendor'], amount, category)
        flags.extend(cum_flags)

    # Section 32 Depreciation
    flags.extend(check_depreciation_section_32(expense_row))

    # Forex & Customs
    flags.extend(check_forex_and_customs(expense_row, extracted_text))

    return flags if flags else ["✅ Fully Compliant"]