import psycopg2
import json
import urllib.request
import csv
import os
from datetime import datetime, timedelta


conn = psycopg2.connect(
    host="localhost",
    database="Ginnie_Mae_Concentration_Risk",
    user="katherinezeller"
)



# 1. FEMA DISASTER DATA
# https://www.fema.gov/api/open


def fetch_fema_disasters(start_year=2015, state=None):
    """
    Pull federally declared disasters from FEMA API
    Filters to housing-relevant disaster types
    """
    
    base_url = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"
    
    # Filter to major disaster types that affect housing
    filters = [
        f"declarationDate gt '{start_year}-01-01T00:00:00.000z'",
        "incidentType in ('Hurricane','Flood','Earthquake','Severe Storm(s)','Tornado','Fire','Typhoon','Coastal Storm')"
    ]
    
    if state:
        filters.append(f"stateCode eq '{state}'")
    
    filter_str = " and ".join(filters)
    
    url = f"{base_url}?$filter={urllib.parse.quote(filter_str)}&$orderby={urllib.parse.quote('declarationDate desc')}&$top=200"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "GinnieMaeRiskAnalytics/1.0"
        })
        
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
        
        disasters = []
        seen = set()
        
        for record in data.get("DisasterDeclarationsSummaries", []):
            # Deduplicate by disaster number and state
            disaster_num = record.get("disasterNumber")
            state_code = record.get("stateCode", "")
            key = f"{disaster_num}_{state_code}"
            
            if key in seen:
                continue
            seen.add(key)
            
            disasters.append({
                "disaster_number": disaster_num,
                "state": state_code,
                "declaration_date": record.get("declarationDate", "")[:10],
                "incident_type": record.get("incidentType", ""),
                "declaration_title": record.get("declarationTitle", ""),
                "incident_begin": record.get("incidentBeginDate", "")[:10] if record.get("incidentBeginDate") else "",
                "incident_end": record.get("incidentEndDate", "")[:10] if record.get("incidentEndDate") else "",
                "declaration_type": record.get("declarationType", "")
            })
        
        return disasters
    
    except Exception as e:
        print(f"Error fetching FEMA data: {e}")
        return []


def display_fema_disasters(disasters):
    """Display FEMA disasters in a readable format"""
    
    print(f"\n{'DATE':12s} {'TYPE':20s} {'STATE':6s} {'TITLE'}")
    print("-" * 80)
    
    for d in disasters[:30]:
        print(f"{d['declaration_date']:12s} {d['incident_type'][:20]:20s} {d['state']:6s} {d['declaration_title'][:40]}")
    
    if len(disasters) > 30:
        print(f"\n... and {len(disasters) - 30} more")
    
    print(f"\nTotal disasters found: {len(disasters)}")




# Compares portfolio performance before and after a disaster event in a specific state


def analyze_disaster_impact(state, disaster_date_str, months_before=3, months_after=6):
    """
    Analyze how a disaster affected delinquency rates in a state
    
    Requires multiple months of disclosure data loaded into pool_loans
    with different as_of_date values.
    
    Returns pre-disaster vs post-disaster delinquency metrics.
    """
    cur = conn.cursor()
    
    disaster_date = datetime.strptime(disaster_date_str, "%Y-%m-%d")
    
    # Calculate date windows
    pre_start = (disaster_date - timedelta(days=months_before * 30)).strftime("%Y%m")
    pre_end = disaster_date.strftime("%Y%m")
    post_start = disaster_date.strftime("%Y%m")
    post_end = (disaster_date + timedelta(days=months_after * 30)).strftime("%Y%m")
    
    # Check what months of data we have
    cur.execute("""
        SELECT DISTINCT as_of_date 
        FROM pool_loans 
        WHERE property_state = %s
        ORDER BY as_of_date
    """, (state,))
    
    available_months = [row[0] for row in cur.fetchall()]
    
    if len(available_months) < 2:
        cur.close()
        return {
            "error": f"Need multiple months of data to analyze impact. Currently have {len(available_months)} month(s): {available_months}",
            "available_months": available_months,
            "recommendation": "Download additional monthly disclosure files from ginniemae.gov and load them using load_data.py"
        }
    
    # Pre-disaster metrics
    cur.execute("""
        SELECT 
            as_of_date,
            COUNT(*) as total_loans,
            SUM(CASE WHEN months_delinquent > 0 THEN 1 ELSE 0 END) as dq_loans,
            ROUND(SUM(CASE WHEN months_delinquent > 0 THEN 1 ELSE 0 END)::DECIMAL / 
                COUNT(*) * 100, 4) as dq_rate,
            COALESCE(SUM(unpaid_principal_balance), 0) as total_upb,
            COALESCE(SUM(CASE WHEN months_delinquent > 0 THEN unpaid_principal_balance ELSE 0 END), 0) as dq_upb
        FROM pool_loans
        WHERE property_state = %s
            AND as_of_date <= %s
        GROUP BY as_of_date
        ORDER BY as_of_date
    """, (state, pre_end))
    
    pre_data = []
    for row in cur.fetchall():
        pre_data.append({
            "as_of_date": row[0],
            "total_loans": row[1],
            "dq_loans": row[2],
            "dq_rate": float(row[3]),
            "total_upb": float(row[4]),
            "dq_upb": float(row[5])
        })
    
    # Post-disaster metrics
    cur.execute("""
        SELECT 
            as_of_date,
            COUNT(*) as total_loans,
            SUM(CASE WHEN months_delinquent > 0 THEN 1 ELSE 0 END) as dq_loans,
            ROUND(SUM(CASE WHEN months_delinquent > 0 THEN 1 ELSE 0 END)::DECIMAL / 
                COUNT(*) * 100, 4) as dq_rate,
            COALESCE(SUM(unpaid_principal_balance), 0) as total_upb,
            COALESCE(SUM(CASE WHEN months_delinquent > 0 THEN unpaid_principal_balance ELSE 0 END), 0) as dq_upb
        FROM pool_loans
        WHERE property_state = %s
            AND as_of_date > %s
        GROUP BY as_of_date
        ORDER BY as_of_date
    """, (state, pre_end))
    
    post_data = []
    for row in cur.fetchall():
        post_data.append({
            "as_of_date": row[0],
            "total_loans": row[1],
            "dq_loans": row[2],
            "dq_rate": float(row[3]),
            "total_upb": float(row[4]),
            "dq_upb": float(row[5])
        })
    
    cur.close()
    
    return {
        "state": state,
        "disaster_date": disaster_date_str,
        "pre_disaster": pre_data,
        "post_disaster": post_data,
        "available_months": available_months
    }



# Tracks individual loans over time to determine
# actual outcomes


def calculate_historical_cure_rate(state=None):
    """
    Calculate the actual cure rate by tracking loans that were 
    delinquent in one month and checking their status in subsequent months.
    
    Requires multiple months of disclosure data.
    """
    cur = conn.cursor()
    
    state_filter = ""
    params = []
    if state:
        state_filter = "AND a.property_state = %s"
        params.append(state)
    
    # Find loans that were delinquent in an earlier month and check if they cured (became current) in a later month
    cur.execute(f"""
        SELECT 
            COUNT(DISTINCT a.cusip) as total_dq_loans,
            COUNT(DISTINCT CASE WHEN b.months_delinquent = 0 THEN a.cusip END) as cured_loans,
            COUNT(DISTINCT CASE WHEN b.months_delinquent > a.months_delinquent THEN a.cusip END) as worsened_loans,
            COUNT(DISTINCT CASE WHEN b.current_month_liquidation = 'Y' THEN a.cusip END) as liquidated_loans
        FROM pool_loans a
        JOIN pool_loans b ON a.cusip = b.cusip AND b.as_of_date > a.as_of_date
        WHERE a.months_delinquent > 0
        {state_filter}
    """, params)
    
    row = cur.fetchone()
    cur.close()
    
    if not row or row[0] == 0:
        return {
            "error": "Need multiple months of data to calculate cure rates",
            "recommendation": "Load additional monthly disclosure files"
        }
    
    total_dq = row[0]
    cured = row[1]
    worsened = row[2]
    liquidated = row[3]
    
    return {
        "state": state or "All States",
        "total_delinquent_loans_tracked": total_dq,
        "cured": cured,
        "cure_rate": f"{(cured / total_dq * 100):.2f}%",
        "worsened": worsened,
        "worsen_rate": f"{(worsened / total_dq * 100):.2f}%",
        "liquidated": liquidated,
        "liquidation_rate": f"{(liquidated / total_dq * 100):.2f}%"
    }


def calculate_historical_loss_severity(state=None):
    """
    Calculate actual loss severity from loans that were removed
    from pools due to foreclosure (removal_reason = 3) or 
    loss mitigation (removal_reason = 4).
    
    Loss severity = 1 - (recovery / original balance)
    Since we don't have recovery amounts in disclosure data,
    we estimate using the UPB at time of removal vs original balance.
    """
    cur = conn.cursor()
    
    state_filter = ""
    params = []
    if state:
        state_filter = "AND property_state = %s"
        params.append(state)
    
    cur.execute(f"""
        SELECT 
            removal_reason,
            COUNT(*) as loan_count,
            SUM(original_principal_balance) as total_original_balance,
            SUM(unpaid_principal_balance) as total_upb_at_removal,
            AVG(original_principal_balance) as avg_original_balance,
            AVG(unpaid_principal_balance) as avg_upb_at_removal
        FROM pool_loans
        WHERE removal_reason IS NOT NULL 
            AND removal_reason > 0
            {state_filter}
        GROUP BY removal_reason
        ORDER BY removal_reason
    """, params)
    
    removal_reasons = {
        1: "Mortgagor Payoff",
        2: "Repurchase of DQ Loan",
        3: "Foreclosure",
        4: "Loss Mitigation",
        5: "Substitution",
        6: "Other"
    }
    
    results = []
    for row in cur.fetchall():
        reason_code = row[0]
        results.append({
            "removal_reason": removal_reasons.get(reason_code, f"Code {reason_code}"),
            "loan_count": row[1],
            "total_original_balance": float(row[2]) if row[2] else 0,
            "total_upb_at_removal": float(row[3]) if row[3] else 0,
            "avg_original_balance": float(row[4]) if row[4] else 0,
            "avg_upb_at_removal": float(row[5]) if row[5] else 0
        })
    
    cur.close()
    return {
        "state": state or "All States",
        "removal_breakdown": results
    }



# Combines all data sources into a single report
# with recommended assumption updates


def generate_calibration_report(state=None):
    """
    Generate a comprehensive calibration report that recommends
    evidence-based assumptions for the scenario engine
    """
    
    print("\n" + "=" * 70)
    print("CALIBRATION REPORT — EVIDENCE-BASED ASSUMPTION ANALYSIS")
    if state:
        print(f"State: {state}")
    print("=" * 70)
    
    # 1. FEMA disaster history
    print("\n\n--- SECTION 1: FEMA DISASTER HISTORY ---")
    disasters = fetch_fema_disasters(start_year=2019, state=state)
    if disasters:
        display_fema_disasters(disasters)
        
        # Summarize by type
        type_counts = {}
        for d in disasters:
            t = d["incident_type"]
            type_counts[t] = type_counts.get(t, 0) + 1
        
        print(f"\nDisaster frequency by type:")
        for t, c in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {t}: {c}")
    else:
        print("No FEMA disasters found for this filter.")
    
    # 2. Current portfolio snapshot
    print("\n\n--- SECTION 2: CURRENT PORTFOLIO DELINQUENCY ---")
    cur = conn.cursor()
    
    state_filter = ""
    params = []
    if state:
        state_filter = "WHERE property_state = %s"
        params.append(state)
    
    cur.execute(f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN months_delinquent = 0 THEN 1 ELSE 0 END) as current,
            SUM(CASE WHEN months_delinquent = 1 THEN 1 ELSE 0 END) as dq_30,
            SUM(CASE WHEN months_delinquent = 2 THEN 1 ELSE 0 END) as dq_60,
            SUM(CASE WHEN months_delinquent = 3 THEN 1 ELSE 0 END) as dq_90,
            SUM(CASE WHEN months_delinquent >= 4 THEN 1 ELSE 0 END) as dq_120plus,
            SUM(unpaid_principal_balance) as total_upb
        FROM pool_loans
        {state_filter}
    """, params)
    
    row = cur.fetchone()
    total = row[0]
    
    print(f"Total Loans:    {row[0]:,}")
    print(f"Current:        {row[1]:,} ({row[1]/total*100:.2f}%)")
    print(f"30-Day DQ:      {row[2]:,} ({row[2]/total*100:.2f}%)")
    print(f"60-Day DQ:      {row[3]:,} ({row[3]/total*100:.2f}%)")
    print(f"90-Day DQ:      {row[4]:,} ({row[4]/total*100:.2f}%)")
    print(f"120+ Day DQ:    {row[5]:,} ({row[5]/total*100:.2f}%)")
    print(f"Total UPB:      ${row[6]:,.2f}")
    print(f"Overall DQ Rate: {((total - row[1])/total*100):.2f}%")
    
    # 3. Removal/liquidation analysis
    print("\n\n--- SECTION 3: LOAN REMOVAL ANALYSIS ---")
    loss_data = calculate_historical_loss_severity(state)
    
    if loss_data.get("removal_breakdown"):
        print(f"\n{'REASON':25s} {'COUNT':>8s} {'ORIG BALANCE':>18s} {'UPB AT REMOVAL':>18s}")
        print("-" * 75)
        for r in loss_data["removal_breakdown"]:
            print(f"{r['removal_reason']:25s} {r['loan_count']:>8,d} ${r['total_original_balance']:>15,.2f} ${r['total_upb_at_removal']:>15,.2f}")
    else:
        print("No loan removals found in current data.")
    
    # 4. Historical trend analysis
    print("\n\n--- SECTION 4: HISTORICAL DELINQUENCY TRENDS ---")
    cur.execute(f"""
        SELECT DISTINCT as_of_date FROM pool_loans ORDER BY as_of_date
    """)
    months = [row[0] for row in cur.fetchall()]
    
    if len(months) > 1:
        print(f"Data available for {len(months)} months: {', '.join(months)}")
        
        cure_data = calculate_historical_cure_rate(state)
        if "error" not in cure_data:
            print(f"\nHistorical Cure Rate Analysis:")
            print(f"  DQ Loans Tracked: {cure_data['total_delinquent_loans_tracked']:,}")
            print(f"  Cured:            {cure_data['cured']:,} ({cure_data['cure_rate']})")
            print(f"  Worsened:         {cure_data['worsened']:,} ({cure_data['worsen_rate']})")
            print(f"  Liquidated:       {cure_data['liquidated']:,} ({cure_data['liquidation_rate']})")
    else:
        print(f"Only 1 month of data available ({months[0] if months else 'none'}).")
        print("To calculate historical trends and calibrate assumptions,")
        print("download additional months from ginniemae.gov:")
        print("  https://www.ginniemae.gov/data_and_reports/disclosure/Pages/disclosuredata.aspx")
        print("\nRecommended: Download at least 24 months of mfplmon4 files")
        print("and load each using load_data.py. The as_of_date field")
        print("(L42 in the layout) differentiates monthly snapshots.")
    
    cur.close()
    
    # 5. Recommendations
    print("\n\n--- SECTION 5: ASSUMPTION RECOMMENDATIONS ---")
    
    if len(months) > 6:
        print("\nSufficient historical data available for calibration.")
        print("Recommended next steps:")
        print("  1. Run disaster impact analysis for specific historical events")
        print("  2. Calculate state-specific cure rates and loss severity")
        print("  3. Update scenario_engine.py SCENARIO_TEMPLATES with calibrated values")
    else:
        print("\nInsufficient historical data for full calibration.")
        print("Current assumptions are illustrative estimates.")
        print("\nTo calibrate with evidence-based numbers:")
        print("  1. Download 24+ months of mfplmon4 files from ginniemae.gov")
        print("  2. Load each month using load_data.py (update filepath per month)")
        print("  3. Re-run this calibration report")
        print("  4. Run analyze_disaster_impact() for specific events")
        print("  5. Update scenario_engine.py with calculated rates")
        print("\nKey events to analyze:")
        
        if disasters:
            # Show the biggest disasters as calibration targets
            major = [d for d in disasters if d["declaration_type"] == "DR"][:5]
            for d in major:
                print(f"  - {d['declaration_title']} ({d['state']}, {d['declaration_date']})")
    
    print("\n" + "=" * 70)



# When sufficient historical data exists, automatically calculate and update assumptions


def auto_calibrate():
    """
    Automatically calculate evidence-based assumptions from
    historical data and output updated SCENARIO_TEMPLATES
    that can be pasted into scenario_engine.py
    """
    cur = conn.cursor()
    
    # Check how much historical data we have
    cur.execute("SELECT COUNT(DISTINCT as_of_date) FROM pool_loans")
    num_months = cur.fetchone()[0]
    
    if num_months < 12:
        print(f"\nAuto-calibration requires at least 12 months of data.")
        print(f"Currently have {num_months} month(s).")
        print("Download more monthly disclosure files and reload.")
        cur.close()
        return
    
    print("\n" + "=" * 70)
    print("AUTO-CALIBRATION — CALCULATING EVIDENCE-BASED ASSUMPTIONS")
    print("=" * 70)
    
    # Get overall cure rate
    cure_data = calculate_historical_cure_rate()
    if "error" not in cure_data:
        overall_cure = float(cure_data["cure_rate"].replace("%", "")) / 100
    else:
        overall_cure = 0.50  # fallback
    
    # Get loss severity from foreclosure data
    loss_data = calculate_historical_loss_severity()
    foreclosure_severity = 0.15  # fallback
    for r in loss_data.get("removal_breakdown", []):
        if r["removal_reason"] == "Foreclosure" and r["total_original_balance"] > 0:
            # Estimate severity as remaining UPB / original balance (simplified - actual would need recovery amount)
            foreclosure_severity = 1 - (r["total_upb_at_removal"] / r["total_original_balance"])
    
    # Get state-by-state delinquency rates for baseline
    cur.execute("""
        SELECT 
            property_state,
            COUNT(*) as total,
            SUM(CASE WHEN months_delinquent > 0 THEN 1 ELSE 0 END) as dq,
            ROUND(SUM(CASE WHEN months_delinquent > 0 THEN 1 ELSE 0 END)::DECIMAL / COUNT(*) * 100, 4) as dq_rate
        FROM pool_loans
        GROUP BY property_state
        HAVING COUNT(*) >= 10
        ORDER BY dq_rate DESC
    """)
    
    state_dq = {}
    for row in cur.fetchall():
        state_dq[row[0]] = {
            "total": row[1],
            "dq": row[2],
            "dq_rate": float(row[3])
        }
    
    cur.close()
    
    # Calculate calibrated assumptions
    avg_dq_rate = sum(s["dq_rate"] for s in state_dq.values()) / len(state_dq) if state_dq else 0.5
    
    print(f"\n--- CALCULATED METRICS ---")
    print(f"Overall Cure Rate:      {overall_cure*100:.2f}%")
    print(f"Foreclosure Severity:   {foreclosure_severity*100:.2f}%")
    print(f"Avg State DQ Rate:      {avg_dq_rate:.4f}%")
    print(f"Months of Data:         {num_months}")
    
    # Generate calibrated scenario templates
    print(f"\n--- CALIBRATED SCENARIO TEMPLATES ---")
    print("Copy this into scenario_engine.py to replace estimated assumptions:\n")
    
    # Scale factors based on historical severity patterns
    print(f"""
SCENARIO_TEMPLATES = {{
    "hurricane": {{
        "description": "Major hurricane impact",
        "dq_increase_mild": {round(avg_dq_rate/100 * 3, 4)},
        "dq_increase_moderate": {round(avg_dq_rate/100 * 8, 4)},
        "dq_increase_severe": {round(avg_dq_rate/100 * 16, 4)},
        "cure_rate_mild": {round(min(overall_cure + 0.10, 0.80), 2)},
        "cure_rate_moderate": {round(overall_cure, 2)},
        "cure_rate_severe": {round(max(overall_cure - 0.20, 0.10), 2)},
        "loss_severity": {round(foreclosure_severity, 2)},
        "affected_by": "state"
    }},
    # ... (additional scenarios would be generated similarly)
}}
    """)
    
    print("\nNOTE: These values are derived from the historical data in your database.")
    print("They should be reviewed and validated against published research before")
    print("use in production. The auto-calibration provides a data-driven starting")
    print("point, not a final answer.")




if __name__ == "__main__":
    import sys
    
    # CLI mode
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        
        if cmd == "fema":
            state = sys.argv[2].upper() if len(sys.argv) > 2 else None
            disasters = fetch_fema_disasters(state=state)
            display_fema_disasters(disasters)
        
        elif cmd == "report":
            state = sys.argv[2].upper() if len(sys.argv) > 2 else None
            generate_calibration_report(state)
        
        elif cmd == "cure":
            state = sys.argv[2].upper() if len(sys.argv) > 2 else None
            result = calculate_historical_cure_rate(state)
            print(json.dumps(result, indent=2))
        
        elif cmd == "severity":
            state = sys.argv[2].upper() if len(sys.argv) > 2 else None
            result = calculate_historical_loss_severity(state)
            print(json.dumps(result, indent=2))
        
        elif cmd == "calibrate":
            auto_calibrate()
        
        elif cmd == "impact":
            if len(sys.argv) < 4:
                print("Usage: python3 calibration_agent.py impact STATE YYYY-MM-DD")
                sys.exit(1)
            state = sys.argv[2].upper()
            date = sys.argv[3]
            result = analyze_disaster_impact(state, date)
            if "error" in result:
                print(f"\n{result['error']}")
                print(f"{result.get('recommendation', '')}")
            else:
                print(json.dumps(result, indent=2))
        
        else:
            print("Unknown command. Available commands:")
            print("  python3 calibration_agent.py fema [STATE]")
            print("  python3 calibration_agent.py report [STATE]")
            print("  python3 calibration_agent.py cure [STATE]")
            print("  python3 calibration_agent.py severity [STATE]")
            print("  python3 calibration_agent.py calibrate")
            print("  python3 calibration_agent.py impact STATE YYYY-MM-DD")
        
        conn.close()
        sys.exit(0)
    
    # Interactive mode
    print("\n" + "=" * 70)
    print("CALIBRATION AGENT — EVIDENCE-BASED ASSUMPTION CALCULATOR")
    print("=" * 70)
    
    while True:
        print("\nOptions:")
        print("  1. View FEMA disaster history")
        print("  2. Generate full calibration report")
        print("  3. Calculate historical cure rates")
        print("  4. Analyze loan removal/loss severity")
        print("  5. Analyze specific disaster impact")
        print("  6. Auto-calibrate assumptions")
        print("  0. Exit")
        
        choice = input("\nSelect (0-6): ").strip()
        
        if choice == "0":
            break
        
        elif choice == "1":
            state = input("Filter by state (or press Enter for all): ").strip().upper()
            disasters = fetch_fema_disasters(state=state if state else None)
            display_fema_disasters(disasters)
        
        elif choice == "2":
            state = input("State (or press Enter for all): ").strip().upper()
            generate_calibration_report(state if state else None)
        
        elif choice == "3":
            state = input("State (or press Enter for all): ").strip().upper()
            result = calculate_historical_cure_rate(state if state else None)
            if "error" in result:
                print(f"\n{result['error']}")
                print(f"{result.get('recommendation', '')}")
            else:
                print(f"\nCure Rate Analysis ({result['state']}):")
                print(f"  DQ Loans Tracked: {result['total_delinquent_loans_tracked']:,}")
                print(f"  Cured:            {result['cured']:,} ({result['cure_rate']})")
                print(f"  Worsened:         {result['worsened']:,} ({result['worsen_rate']})")
                print(f"  Liquidated:       {result['liquidated']:,} ({result['liquidation_rate']})")
        
        elif choice == "4":
            state = input("State (or press Enter for all): ").strip().upper()
            result = calculate_historical_loss_severity(state if state else None)
            if result.get("removal_breakdown"):
                print(f"\n{'REASON':25s} {'COUNT':>8s} {'ORIG BALANCE':>18s} {'UPB AT REMOVAL':>18s}")
                print("-" * 75)
                for r in result["removal_breakdown"]:
                    print(f"{r['removal_reason']:25s} {r['loan_count']:>8,d} ${r['total_original_balance']:>15,.2f} ${r['total_upb_at_removal']:>15,.2f}")
            else:
                print("No removal data found.")
        
        elif choice == "5":
            state = input("State: ").strip().upper()
            date = input("Disaster date (YYYY-MM-DD): ").strip()
            result = analyze_disaster_impact(state, date)
            if "error" in result:
                print(f"\n{result['error']}")
                print(f"{result.get('recommendation', '')}")
            else:
                print(json.dumps(result, indent=2))
        
        elif choice == "6":
            auto_calibrate()
    
    conn.close()