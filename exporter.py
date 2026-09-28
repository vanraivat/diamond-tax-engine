import io
import pandas as pd

def generate_ca_audit_workbook(client_info, transactions_df):
    """
    Generates a multi-tab Excel workbook:
    1. Executive Summary & Audit Trail
    2. Critical Exceptions & Tax Risks
    3. Full Audited Ledger
    """
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # --- STYLES & CELL FORMATS ---
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#1B365D', 'font_color': '#FFFFFF',
            'border': 1, 'align': 'center', 'valign': 'vcenter'
        })
        crit_header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#8B0000', 'font_color': '#FFFFFF',
            'border': 1, 'align': 'center', 'valign': 'vcenter'
        })
        metric_title_fmt = workbook.add_format({'bold': True, 'bg_color': '#E9ECEF', 'border': 1})
        metric_val_fmt = workbook.add_format({'align': 'right', 'border': 1, 'num_format': '#,##0.00'})
        metric_int_fmt = workbook.add_format({'align': 'right', 'border': 1, 'num_format': '#,##0'})
        currency_fmt = workbook.add_format({'num_format': '₹#,##0.00', 'border': 1})
        cell_fmt = workbook.add_format({'border': 1, 'valign': 'vcenter'})
        
        # Risk highlight formats
        crit_row_fmt = workbook.add_format({'bg_color': '#FCE8E6', 'font_color': '#A51D24', 'border': 1})
        opp_row_fmt = workbook.add_format({'bg_color': '#E6F4EA', 'font_color': '#137333', 'border': 1})

        # --- SHEET 1: EXECUTIVE SUMMARY ---
        summary_ws = workbook.add_worksheet('Audit Summary')
        summary_ws.hide_gridlines(2)
        summary_ws.set_column('B:B', 32)
        summary_ws.set_column('C:C', 24)

        # Title Block
        title_fmt = workbook.add_format({'bold': True, 'font_size': 16, 'font_color': '#1B365D'})
        summary_ws.write('B2', 'PRELIMINARY TAX AUDIT & COMPLIANCE REPORT', title_fmt)
        summary_ws.write('B3', f"Entity: {client_info.get('company_name', 'Bharat Diamond Corp')}")
        summary_ws.write('B4', f"GSTIN: {client_info.get('gstin', '27AAACD1234E1Z5')}")
        summary_ws.write('B5', f"Assessment Period: FY 2026-27")

        # Metric Calculations
        total_txns = len(transactions_df)
        total_val = transactions_df['Raw_Amount'].sum() if 'Raw_Amount' in transactions_df.columns else 0.0
        critical_flags = transactions_df['Audit Risks'].str.contains('🔴', na=False).sum()
        opp_flags = transactions_df['Audit Risks'].str.contains('🟢', na=False).sum()
        clean_txns = (transactions_df['Audit Risks'] == 'Clean').sum()

        summary_ws.write('B7', 'Audit Metrics', header_fmt)
        summary_ws.write('C7', 'Values', header_fmt)
        
        metrics = [
            ('Total Transactions Audited', total_txns, metric_int_fmt),
            ('Cumulative Transaction Value', total_val, metric_val_fmt),
            ('Critical Regulatory Violations (🔴)', critical_flags, metric_int_fmt),
            ('Unclaimed ITC / Deductions (🟢)', opp_flags, metric_int_fmt),
            ('Fully Compliant Entries (Clean)', clean_txns, metric_int_fmt)
        ]
        
        for idx, (label, val, fmt) in enumerate(metrics, start=8):
            summary_ws.write(f'B{idx}', label, metric_title_fmt)
            summary_ws.write(f'C{idx}', val, fmt)

        summary_ws.write('B15', 'Statutory Disclaimer:', workbook.add_format({'bold': True, 'font_size': 9}))
        summary_ws.write('B16', 'This electronic workpaper contains automated tax analytics under the Income Tax Act 1961,', workbook.add_format({'font_size': 9}))
        summary_ws.write('B17', 'CGST Act 2017, Customs Act 1962, and RBI FEMA guidelines. Subject to independent CA review.', workbook.add_format({'font_size': 9}))

        # --- SHEET 2: CRITICAL EXCEPTIONS & TAX RISKS ---
        exceptions_df = transactions_df[transactions_df['Audit Risks'].str.contains('🔴', na=False)].copy()
        exceptions_ws = workbook.add_worksheet('Tax Exceptions')
        
        headers = ['ID', 'Date', 'Vendor', 'Amount (INR)', 'Ledger Head', 'Statutory Violation / Risk Description', 'CA Disposition']
        for col_idx, h in enumerate(headers):
            exceptions_ws.write(0, col_idx, h, crit_header_fmt)
            
        row_idx = 1
        for _, r in exceptions_df.iterrows():
            exceptions_ws.write(row_idx, 0, r['ID'], cell_fmt)
            exceptions_ws.write(row_idx, 1, r['Date'], cell_fmt)
            exceptions_ws.write(row_idx, 2, r['Vendor'], cell_fmt)
            exceptions_ws.write(row_idx, 3, r['Raw_Amount'], currency_fmt)
            exceptions_ws.write(row_idx, 4, r['AI Category'], cell_fmt)
            exceptions_ws.write(row_idx, 5, r['Audit Risks'], crit_row_fmt)
            exceptions_ws.write(row_idx, 6, r.get('CA Status', 'Pending Review'), cell_fmt)
            row_idx += 1

        exceptions_ws.set_column('A:A', 8)
        exceptions_ws.set_column('B:B', 12)
        exceptions_ws.set_column('C:C', 30)
        exceptions_ws.set_column('D:D', 18)
        exceptions_ws.set_column('E:E', 25)
        exceptions_ws.set_column('F:F', 55)
        exceptions_ws.set_column('G:G', 18)

        # --- SHEET 3: FULL AUDITED LEDGER ---
        ledger_ws = workbook.add_worksheet('Audited Ledger')
        for col_idx, h in enumerate(headers):
            ledger_ws.write(0, col_idx, h, header_fmt)

        row_idx = 1
        for _, r in transactions_df.iterrows():
            flag_fmt = cell_fmt
            if '🔴' in str(r['Audit Risks']):
                flag_fmt = crit_row_fmt
            elif '🟢' in str(r['Audit Risks']):
                flag_fmt = opp_row_fmt

            ledger_ws.write(row_idx, 0, r['ID'], cell_fmt)
            ledger_ws.write(row_idx, 1, r['Date'], cell_fmt)
            ledger_ws.write(row_idx, 2, r['Vendor'], cell_fmt)
            ledger_ws.write(row_idx, 3, r['Raw_Amount'], currency_fmt)
            ledger_ws.write(row_idx, 4, r['AI Category'], cell_fmt)
            ledger_ws.write(row_idx, 5, r['Audit Risks'], flag_fmt)
            ledger_ws.write(row_idx, 6, r.get('CA Status', 'Clean'), cell_fmt)
            row_idx += 1

        ledger_ws.set_column('A:A', 8)
        ledger_ws.set_column('B:B', 12)
        ledger_ws.set_column('C:C', 30)
        ledger_ws.set_column('D:D', 18)
        ledger_ws.set_column('E:E', 25)
        ledger_ws.set_column('F:F', 55)
        ledger_ws.set_column('G:G', 18)

    return output.getvalue()