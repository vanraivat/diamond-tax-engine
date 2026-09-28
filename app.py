import streamlit as st
import pandas as pd
import io
import classifier
import loopholes
from database import Session, Client, Transaction, AuditFlag
from exporter import generate_ca_audit_workbook # The missing import

st.set_page_config(page_title="Diamond Enterprise Tax Engine", layout="wide")
st.title("💎 Enterprise Ledger & Tax Engine")

# --- DATABASE INIT ---
session = Session()

default_client = session.query(Client).filter_by(gstin="27AAACD1234E1Z5").first()
if not default_client:
    default_client = Client(company_name="Bharat Diamond Corp", gstin="27AAACD1234E1Z5")
    session.add(default_client)
    session.commit()

# --- HELPER: EXCEL/TALLY INGELSTION & SANITIZATION ---
def standardize_columns(df):
    vendor_col = next((c for c in df.columns if str(c).lower() in ['vendor', 'particulars', 'description', 'narration', 'party']), 'Vendor')
    amount_col = next((c for c in df.columns if str(c).lower() in ['amount', 'debit', 'withdrawal', 'value']), 'Amount')
    date_col = next((c for c in df.columns if str(c).lower() in ['date', 'txn date', 'transaction date']), 'Date')
    
    df = df.rename(columns={vendor_col: 'Vendor', amount_col: 'Amount', date_col: 'Date'})
    
    def clean_amount(val):
        if pd.isna(val): return 0.0
        val = str(val).replace(',', '').replace('₹', '').replace('$', '').strip()
        try: return float(val)
        except: return 0.0
        
    df['Amount'] = df['Amount'].apply(clean_amount)
    
    if 'Extracted_Text' not in df.columns: df['Extracted_Text'] = df['Vendor']
    if 'Payment_Mode' not in df.columns: df['Payment_Mode'] = 'Bank Transfer'
    return df

# --- UI: FILE UPLOAD ---
st.header("1. Upload Bank Statement or Tally Export")
uploaded_file = st.file_uploader("Upload corporate statement (CSV, XLSX, XLS)", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    if st.button("Process & Save to Database"):
        with st.spinner('Sanitizing data, running AI, and saving to SQLite...'):
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
                
            df = standardize_columns(df)
            
            for index, row in df.iterrows():
                processed_row = row.to_dict()
                
                cat, conf = classifier.predict_category(processed_row["Vendor"])
                processed_row['Category'] = cat 
                
                flags = loopholes.run_rules_engine(
                    processed_row, 
                    processed_row['Extracted_Text'],
                    db_session=session,
                    client_id=default_client.id
                )
                
                new_tx = Transaction(
                    client_id=default_client.id,
                    date=processed_row["Date"],
                    vendor=processed_row["Vendor"],
                    amount=processed_row["Amount"],
                    payment_mode=processed_row.get("Payment_Mode", "Unknown"),
                    ledger_category=cat,
                    currency="USD" if "$" in processed_row['Extracted_Text'] else "INR"
                )
                session.add(new_tx)
                session.flush() 
                
                for flag in flags:
                    if "✅" in flag: continue 
                    severity = "WARNING"
                    if "🔴" in flag: severity = "CRITICAL"
                    elif "🟢" in flag: severity = "OPPORTUNITY"
                    
                    new_flag = AuditFlag(transaction_id=new_tx.id, flag_description=flag, severity=severity)
                    session.add(new_flag)
            
            session.commit()
            st.success("Successfully processed and saved to database!")

# --- UI: DATABASE & EXPORT ---
st.header("2. Audit Dashboard & Working Papers")
st.write("Review flagged transactions. Edit the 'CA Status' and 'CA Notes' columns, then click Save.")

all_transactions = session.query(Transaction).all()

if all_transactions:
    display_data = []
    for tx in all_transactions:
        tx_flags = session.query(AuditFlag).filter_by(transaction_id=tx.id).all()
        flag_texts = [f.flag_description for f in tx_flags]
        
        display_data.append({
            "ID": tx.id,
            "Date": tx.date,
            "Vendor": tx.vendor,
            "Raw_Amount": tx.amount, 
            "Amount": f"₹{tx.amount:,.2f}",
            "AI Category": tx.ledger_category,
            "Audit Risks": " | ".join(flag_texts) if flag_texts else "Clean",
            "CA Status": tx.ca_status if tx.ca_status else "Pending Review",
            "CA Notes": tx.ca_notes if tx.ca_notes else ""
        })
        
    db_df = pd.DataFrame(display_data)
    import plotly.express as px

    # --- VISUAL ANALYTICS DASHBOARD ---
    st.markdown("### 📊 Executive Financial & Risk Overview")
    
    # We use the 'Raw_Amount' column we preserved earlier for accurate math
    plot_df = db_df.copy()
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        # Chart 1: Expenditure by AI Ledger Category
        cat_df = plot_df.groupby('AI Category')['Raw_Amount'].sum().reset_index()
        fig_cat = px.bar(
            cat_df, 
            x='AI Category', 
            y='Raw_Amount', 
            title='Total Expenditure by AI Category',
            labels={'Raw_Amount': 'Amount (₹)', 'AI Category': 'Ledger Head'},
            color='AI Category',
            template='plotly_white'
        )
        st.plotly_chart(fig_cat, use_container_width=True)

    with col_chart2:
        # Chart 2: Audit Resolution Status (Donut Chart)
        status_df = plot_df['CA Status'].value_counts().reset_index()
        status_df.columns = ['Status', 'Count']
        
        # Color mapping to make Critical/Pending red and Approved green
        color_map = {
            "Pending Review": "#EF553B", # Red
            "Auto-Approved": "#00CC96",  # Green
            "Approved": "#00CC96",       # Green
            "Rejected": "#636EFA"        # Blue
        }
        
        fig_status = px.pie(
            status_df, 
            values='Count', 
            names='Status', 
            title='Audit Resolution Status',
            hole=0.4,
            color='Status',
            color_discrete_map=color_map
        )
        st.plotly_chart(fig_status, use_container_width=True)
        
    st.markdown("### 📝 Transaction Ledger & Overrides")
    
    # Interactive Human-in-the-Loop Grid
    view_columns = ["ID", "Date", "Vendor", "Amount", "AI Category", "Audit Risks", "CA Status", "CA Notes"]
    
    edited_df = st.data_editor(
        db_df[view_columns], 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "CA Status": st.column_config.SelectboxColumn(
                "CA Status",
                help="Override AI risk flags",
                options=["Pending Review", "Approved", "Rejected", "Auto-Approved"],
                required=True
            ),
            "CA Notes": st.column_config.TextColumn(
                "CA Notes",
                help="Add statutory justification for overrides"
            )
        }
    )
    
    # Save & Export Mechanics
    col1, col2 = st.columns([1, 4])
    
    with col1:
        if st.button("💾 Save Adjustments to DB", use_container_width=True):
            with st.spinner("Updating database..."):
                for index, row in edited_df.iterrows():
                    tx = session.query(Transaction).filter_by(id=row["ID"]).first()
                    if tx:
                        tx.ca_status = row["CA Status"]
                        tx.ca_notes = row.get("CA Notes", "")
                session.commit()
            st.success("Overrides permanently saved!")
            st.rerun() 
            
    with col2:
        export_df = db_df.copy()
        export_df['CA Status'] = edited_df['CA Status']
        export_df['CA Notes'] = edited_df['CA Notes']
        
        client_meta = {"company_name": default_client.company_name, "gstin": default_client.gstin}
        excel_report = generate_ca_audit_workbook(client_meta, export_df)
    
        st.download_button(
            label="📥 Download Statutory Audit Working Papers (.xlsx)",
            data=excel_report,
            file_name=f"Tax_Audit_Report_{default_client.company_name.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("The database is currently empty. Upload a CSV or Excel file to populate it.")

st.markdown("---")
st.caption("*Disclaimer: This engine provides automated preliminary audit flags under Indian corporate tax laws. It does not constitute statutory audit certification or binding legal advice.*")