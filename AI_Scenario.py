import psycopg2
import json
import sys
import urllib.request

# Connect to local database for now - we'll switch to Azure later
conn = psycopg2.connect(
    host="localhost",
    database="Ginnie_Mae_Concentration_Risk",
    user="katherinezeller"
)


# Each scenario type has stress assumptions for:
#   - dq_increase: % of performing loans that become delinquent
#   - cure_rate: % of delinquent loans that return to performing
#   - default_rate: derived (1 - cure_rate)
#   - loss_severity: % of UPB lost on loans that go to foreclosure


SCENARIO_TEMPLATES = {
    "hurricane": {
        "description": "Major hurricane impact",
        "dq_increase_mild": 0.05,
        "dq_increase_moderate": 0.12,
        "dq_increase_severe": 0.25,
        "cure_rate_mild": 0.60,
        "cure_rate_moderate": 0.45,
        "cure_rate_severe": 0.25,
        "loss_severity": 0.15,
        "affected_by": "state"
    },
    "earthquake": {
        "description": "Major earthquake impact",
        "dq_increase_mild": 0.04,
        "dq_increase_moderate": 0.10,
        "dq_increase_severe": 0.20,
        "cure_rate_mild": 0.55,
        "cure_rate_moderate": 0.40,
        "cure_rate_severe": 0.20,
        "loss_severity": 0.20,
        "affected_by": "state"
    },
    "flood": {
        "description": "Severe flooding impact",
        "dq_increase_mild": 0.06,
        "dq_increase_moderate": 0.15,
        "dq_increase_severe": 0.30,
        "cure_rate_mild": 0.55,
        "cure_rate_moderate": 0.40,
        "cure_rate_severe": 0.22,
        "loss_severity": 0.18,
        "affected_by": "state"
    },
    "unemployment": {
        "description": "Unemployment spike",
        "dq_increase_mild": 0.03,
        "dq_increase_moderate": 0.08,
        "dq_increase_severe": 0.15,
        "cure_rate_mild": 0.65,
        "cure_rate_moderate": 0.50,
        "cure_rate_severe": 0.35,
        "loss_severity": 0.10,
        "affected_by": "state"
    },
    "interest_rate_shock": {
        "description": "Rapid interest rate increase",
        "dq_increase_mild": 0.02,
        "dq_increase_moderate": 0.05,
        "dq_increase_severe": 0.10,
        "cure_rate_mild": 0.70,
        "cure_rate_moderate": 0.55,
        "cure_rate_severe": 0.40,
        "loss_severity": 0.08,
        "affected_by": "nationwide"
    },
    "housing_market_crash": {
        "description": "Housing market downturn",
        "dq_increase_mild": 0.04,
        "dq_increase_moderate": 0.10,
        "dq_increase_severe": 0.22,
        "cure_rate_mild": 0.50,
        "cure_rate_moderate": 0.35,
        "cure_rate_severe": 0.15,
        "loss_severity": 0.25,
        "affected_by": "state"
    }
}

STATE_MAP = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC"
}

# NWS alert event types mapped to scenario types
NWS_EVENT_MAP = {
    "Hurricane Warning": ("hurricane", "severe"),
    "Hurricane Watch": ("hurricane", "moderate"),
    "Tropical Storm Warning": ("hurricane", "mild"),
    "Tropical Storm Watch": ("hurricane", "mild"),
    "Flash Flood Warning": ("flood", "severe"),
    "Flood Warning": ("flood", "moderate"),
    "Flash Flood Watch": ("flood", "mild"),
    "Flood Watch": ("flood", "mild"),
    "Earthquake Warning": ("earthquake", "severe"),
    "Tsunami Warning": ("earthquake", "severe"),
    "Severe Thunderstorm Warning": ("flood", "mild"),
    "Storm Surge Warning": ("hurricane", "severe"),
    "Storm Surge Watch": ("hurricane", "moderate"),
}

# NWS state FIPS to abbreviation
FIPS_TO_STATE = {
    "AL": "AL", "AK": "AK", "AZ": "AZ", "AR": "AR", "CA": "CA",
    "CO": "CO", "CT": "CT", "DE": "DE", "FL": "FL", "GA": "GA",
    "HI": "HI", "ID": "ID", "IL": "IL", "IN": "IN", "IA": "IA",
    "KS": "KS", "KY": "KY", "LA": "LA", "ME": "ME", "MD": "MD",
    "MA": "MA", "MI": "MI", "MN": "MN", "MS": "MS", "MO": "MO",
    "MT": "MT", "NE": "NE", "NV": "NV", "NH": "NH", "NJ": "NJ",
    "NM": "NM", "NY": "NY", "NC": "NC", "ND": "ND", "OH": "OH",
    "OK": "OK", "OR": "OR", "PA": "PA", "RI": "RI", "SC": "SC",
    "SD": "SD", "TN": "TN", "TX": "TX", "UT": "UT", "VT": "VT",
    "VA": "VA", "WA": "WA", "WV": "WV", "WI": "WI", "WY": "WY",
    "DC": "DC"
}


def resolve_state(state_input):
    """Convert state name or abbreviation to two-letter code"""
    state_input = state_input.strip().lower()
    if state_input in STATE_MAP:
        return STATE_MAP[state_input]
    elif state_input.upper() in FIPS_TO_STATE.values():
        return state_input.upper()
    return None


def get_portfolio_exposure(state=None):
    """Query the database for portfolio exposure, optionally filtered by state"""
    cur = conn.cursor()
    
    if state:
        cur.execute("""
            SELECT 
                COUNT(*) as total_loans,
                COALESCE(SUM(unpaid_principal_balance), 0) as total_upb,
                SUM(CASE WHEN months_delinquent > 0 THEN 1 ELSE 0 END) as current_dq_loans,
                COALESCE(SUM(CASE WHEN months_delinquent > 0 THEN unpaid_principal_balance ELSE 0 END), 0) as current_dq_upb
            FROM pool_loans
            WHERE property_state = %s
        """, (state,))
    else:
        cur.execute("""
            SELECT 
                COUNT(*) as total_loans,
                COALESCE(SUM(unpaid_principal_balance), 0) as total_upb,
                SUM(CASE WHEN months_delinquent > 0 THEN 1 ELSE 0 END) as current_dq_loans,
                COALESCE(SUM(CASE WHEN months_delinquent > 0 THEN unpaid_principal_balance ELSE 0 END), 0) as current_dq_upb
            FROM pool_loans
        """)
    
    row = cur.fetchone()
    cur.close()
    
    return {
        "total_loans": row[0],
        "total_upb": float(row[1]),
        "current_dq_loans": row[2],
        "current_dq_upb": float(row[3])
    }


def get_total_portfolio():
    """Get total portfolio metrics for percentage calculations"""
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(unpaid_principal_balance), 0) FROM pool_loans")
    total = float(cur.fetchone()[0])
    cur.close()
    return total


def get_top_issuers_in_area(state):
    """Get the most exposed issuers in the affected area"""
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            i.issuer_name,
            COUNT(*) as loan_count,
            SUM(p.unpaid_principal_balance) as issuer_upb
        FROM pool_loans p
        JOIN issuers i ON p.issuer_number = i.issuer_number
        WHERE p.property_state = %s
        GROUP BY i.issuer_name
        ORDER BY issuer_upb DESC
        LIMIT 5
    """, (state,))
    
    results = []
    for row in cur.fetchall():
        results.append({
            "issuer_name": row[0],
            "loan_count": row[1],
            "upb": float(row[2])
        })
    cur.close()
    return results


def get_top_msas_in_area(state):
    """Get the most exposed MSAs in the affected area"""
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            msa,
            COUNT(*) as loan_count,
            SUM(unpaid_principal_balance) as msa_upb
        FROM pool_loans
        WHERE property_state = %s AND msa IS NOT NULL AND msa != ''
        GROUP BY msa
        ORDER BY msa_upb DESC
        LIMIT 5
    """, (state,))
    
    results = []
    for row in cur.fetchall():
        results.append({
            "msa": row[0],
            "loan_count": row[1],
            "upb": float(row[2])
        })
    cur.close()
    return results


def run_scenario(scenario_type, severity, state=None):
    """
    Run a stress scenario and return projected impact
    
    Loss waterfall:
    1. Performing loans x dq_increase = New delinquent loans
    2. New delinquent loans x cure_rate = Loans that recover
    3. New delinquent loans x (1 - cure_rate) = Loans that default
    4. Defaulted UPB x loss_severity = Projected losses
    """
    
    if scenario_type not in SCENARIO_TEMPLATES:
        return {"error": f"Unknown scenario type: {scenario_type}"}
    
    template = SCENARIO_TEMPLATES[scenario_type]
    
    dq_key = f"dq_increase_{severity}"
    cure_key = f"cure_rate_{severity}"
    if dq_key not in template:
        return {"error": f"Unknown severity: {severity}"}
    
    dq_increase = template[dq_key]
    cure_rate = template[cure_key]
    default_rate = 1 - cure_rate
    loss_severity = template["loss_severity"]
    
    if template["affected_by"] == "nationwide":
        exposure = get_portfolio_exposure()
        area_label = "Nationwide"
    else:
        if not state:
            return {"error": "State required for this scenario type"}
        exposure = get_portfolio_exposure(state)
        area_label = state
    
    total_portfolio = get_total_portfolio()
    
    # Loss waterfall calculation
    current_performing_loans = exposure["total_loans"] - exposure["current_dq_loans"]
    current_performing_upb = exposure["total_upb"] - exposure["current_dq_upb"]
    
    projected_new_dq_loans = int(current_performing_loans * dq_increase)
    projected_new_dq_upb = current_performing_upb * dq_increase
    
    projected_total_dq_loans = exposure["current_dq_loans"] + projected_new_dq_loans
    projected_total_dq_upb = exposure["current_dq_upb"] + projected_new_dq_upb
    
    projected_cured_loans = int(projected_new_dq_loans * cure_rate)
    projected_cured_upb = projected_new_dq_upb * cure_rate
    
    projected_default_loans = projected_new_dq_loans - projected_cured_loans
    projected_default_upb = projected_new_dq_upb * default_rate
    
    projected_losses = projected_default_upb * loss_severity
    
    results = {
        "scenario": {
            "type": scenario_type,
            "description": template["description"],
            "severity": severity,
            "affected_area": area_label,
            "assumptions": {
                "dq_increase_rate": f"{dq_increase * 100:.1f}%",
                "cure_rate": f"{cure_rate * 100:.1f}%",
                "default_rate": f"{default_rate * 100:.1f}%",
                "loss_severity": f"{loss_severity * 100:.1f}%"
            }
        },
        "current_state": {
            "total_loans": exposure["total_loans"],
            "total_upb": f"${exposure['total_upb']:,.2f}",
            "pct_of_portfolio": f"{(exposure['total_upb'] / total_portfolio * 100):.2f}%",
            "performing_loans": current_performing_loans,
            "performing_upb": f"${current_performing_upb:,.2f}",
            "current_dq_loans": exposure["current_dq_loans"],
            "current_dq_upb": f"${exposure['current_dq_upb']:,.2f}",
            "current_dq_rate": f"{(exposure['current_dq_loans'] / exposure['total_loans'] * 100):.2f}%" if exposure['total_loans'] > 0 else "0%"
        },
        "loss_waterfall": {
            "step_1_new_dq_loans": projected_new_dq_loans,
            "step_1_new_dq_upb": f"${projected_new_dq_upb:,.2f}",
            "step_2_cured_loans": projected_cured_loans,
            "step_2_cured_upb": f"${projected_cured_upb:,.2f}",
            "step_3_default_loans": projected_default_loans,
            "step_3_default_upb": f"${projected_default_upb:,.2f}",
            "step_4_projected_losses": f"${projected_losses:,.2f}"
        },
        "projected_impact": {
            "total_delinquent_loans": projected_total_dq_loans,
            "total_delinquent_upb": f"${projected_total_dq_upb:,.2f}",
            "projected_dq_rate": f"{(projected_total_dq_loans / exposure['total_loans'] * 100):.2f}%" if exposure['total_loans'] > 0 else "0%",
            "projected_losses": f"${projected_losses:,.2f}",
            "portfolio_impact": f"${projected_losses:,.2f} ({(projected_losses / total_portfolio * 100):.4f}% of total portfolio)"
        }
    }
    
    if state:
        results["top_exposed_issuers"] = get_top_issuers_in_area(state)
        results["top_exposed_msas"] = get_top_msas_in_area(state)
    
    return results


def format_results(results):
    """Pretty print scenario results"""
    
    if "error" in results:
        print(f"\nERROR: {results['error']}")
        return
    
    s = results["scenario"]
    a = s["assumptions"]
    c = results["current_state"]
    w = results["loss_waterfall"]
    p = results["projected_impact"]
    
    print("\n" + "=" * 70)
    print(f"SCENARIO: {s['description'].upper()}")
    print(f"Area: {s['affected_area']} | Severity: {s['severity'].upper()}")
    print("=" * 70)
    
    print(f"\n--- ASSUMPTIONS ---")
    print(f"Delinquency Increase:  {a['dq_increase_rate']} of performing loans become delinquent")
    print(f"Cure Rate:             {a['cure_rate']} of new DQ loans return to performing")
    print(f"Default Rate:          {a['default_rate']} of new DQ loans proceed to default")
    print(f"Loss Severity:         {a['loss_severity']} of defaulted UPB is lost at foreclosure")
    
    print(f"\n--- CURRENT STATE ---")
    print(f"Total Loans:           {c['total_loans']:,}")
    print(f"Total UPB:             {c['total_upb']}")
    print(f"% of Portfolio:        {c['pct_of_portfolio']}")
    print(f"Performing Loans:      {c['performing_loans']:,}")
    print(f"Performing UPB:        {c['performing_upb']}")
    print(f"Currently DQ:          {c['current_dq_loans']:,} loans ({c['current_dq_rate']})")
    print(f"Currently DQ UPB:      {c['current_dq_upb']}")
    
    print(f"\n--- LOSS WATERFALL ---")
    print(f"Step 1 - New DQ:       +{w['step_1_new_dq_loans']:,} loans  |  {w['step_1_new_dq_upb']}")
    print(f"Step 2 - Cured:        -{w['step_2_cured_loans']:,} loans  |  {w['step_2_cured_upb']}")
    print(f"Step 3 - Defaults:      {w['step_3_default_loans']:,} loans  |  {w['step_3_default_upb']}")
    print(f"Step 4 - Losses:                          {w['step_4_projected_losses']}")
    
    print(f"\n--- PROJECTED IMPACT ---")
    print(f"Total DQ Loans:        {p['total_delinquent_loans']:,}")
    print(f"Total DQ UPB:          {p['total_delinquent_upb']}")
    print(f"Projected DQ Rate:     {p['projected_dq_rate']}")
    print(f"Projected Losses:      {p['projected_losses']}")
    print(f"Portfolio Impact:      {p['portfolio_impact']}")
    
    if "top_exposed_issuers" in results:
        print(f"\n--- TOP EXPOSED ISSUERS ---")
        for issuer in results["top_exposed_issuers"]:
            print(f"  {issuer['issuer_name'][:35]:35s}  {issuer['loan_count']:4d} loans  ${issuer['upb']:>15,.2f}")
    
    if "top_exposed_msas" in results:
        print(f"\n--- TOP EXPOSED MSAs ---")
        for msa in results["top_exposed_msas"]:
            print(f"  MSA {msa['msa']}  {msa['loan_count']:4d} loans  ${msa['upb']:>15,.2f}")
    
    print("=" * 70)


# Pulls active alerts from NOAA/NWS API



def fetch_active_weather_alerts():
    """
    Pull active weather alerts from NOAA National Weather Service API
    Free, no API key needed
    https://api.weather.gov
    """
    url = "https://api.weather.gov/alerts/active?status=actual&message_type=alert"
    
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "GinnieMaeRiskAnalytics/1.0 (ajgordon1021@gmail.com)",
            "Accept": "application/geo+json"
        })
        
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
        
        alerts = []
        seen = set()
        
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            event = props.get("event", "")
            
            # Only process events we have scenario mappings for
            if event not in NWS_EVENT_MAP:
                continue
            
            # Extract affected states from the alert
            affected_zones = props.get("geocode", {}).get("UGC", [])
            affected_states = set()
            
            for zone in affected_zones:
                # UGC codes start with 2-letter state abbreviation
                state_code = zone[:2]
                if state_code in FIPS_TO_STATE:
                    affected_states.add(state_code)
            
            # Also try to get state from areaDesc
            area_desc = props.get("areaDesc", "")
            
            scenario_type, severity = NWS_EVENT_MAP[event]
            
            for state in affected_states:
                key = f"{scenario_type}_{severity}_{state}"
                if key not in seen:
                    seen.add(key)
                    alerts.append({
                        "event": event,
                        "scenario_type": scenario_type,
                        "severity": severity,
                        "state": state,
                        "headline": props.get("headline", ""),
                        "description": props.get("description", "")[:200],
                        "urgency": props.get("urgency", ""),
                        "onset": props.get("onset", ""),
                        "expires": props.get("expires", "")
                    })
        
        return alerts
    
    except Exception as e:
        print(f"Error fetching weather alerts: {e}")
        return []


def run_weather_scenarios():
    """
    Automatically fetch active weather alerts and run
    portfolio impact scenarios for affected areas
    """
    print("\n" + "=" * 70)
    print("FETCHING ACTIVE NOAA/NWS WEATHER ALERTS...")
    print("=" * 70)
    
    alerts = fetch_active_weather_alerts()
    
    if not alerts:
        print("\nNo active weather alerts that affect the portfolio.")
        print("Alert types monitored: Hurricane, Tropical Storm, Flood,")
        print("Flash Flood, Earthquake, Tsunami, Storm Surge")
        return
    
    # keep highest severity
    severity_rank = {"severe": 3, "moderate": 2, "mild": 1}
    best_alerts = {}
    
    for alert in alerts:
        key = f"{alert['state']}_{alert['scenario_type']}"
        if key not in best_alerts or severity_rank[alert["severity"]] > severity_rank[best_alerts[key]["severity"]]:
            best_alerts[key] = alert
    
    unique_alerts = list(best_alerts.values())
    
    print(f"\nFound {len(unique_alerts)} relevant alert(s) affecting portfolio states:\n")
    
    for i, alert in enumerate(unique_alerts):
        print(f"  {i+1}. [{alert['urgency']}] {alert['event']} - {alert['state']}")
        print(f"     {alert['headline'][:80]}")
    
    print(f"\n--- RUNNING PORTFOLIO IMPACT SCENARIOS ---")
    
    # Summary comparison table
    print(f"\n{'STATE':6s} {'EVENT':25s} {'SEVERITY':10s} {'LOANS':>8s} {'EXPOSURE':>18s} {'PROJ LOSSES':>18s}")
    print("-" * 90)
    
    for alert in unique_alerts:
        # Check if we have portfolio exposure in this state
        exposure = get_portfolio_exposure(alert["state"])
        if exposure["total_loans"] == 0:
            continue
        
        r = run_scenario(alert["scenario_type"], alert["severity"], alert["state"])
        if "error" not in r:
            w = r["loss_waterfall"]
            c = r["current_state"]
            print(f"{alert['state']:6s} {alert['event'][:25]:25s} {alert['severity']:10s} {c['total_loans']:>8,d} {c['total_upb']:>18s} {w['step_4_projected_losses']:>18s}")
    
    # Run detailed reports for the top impacted states
    print("\n\n--- DETAILED IMPACT REPORTS ---")
    
    for alert in unique_alerts:
        exposure = get_portfolio_exposure(alert["state"])
        if exposure["total_loans"] == 0:
            continue
        
        results = run_scenario(alert["scenario_type"], alert["severity"], alert["state"])
        format_results(results)


#Interactive Mode


if __name__ == "__main__":
    
    \
    if len(sys.argv) == 4:
        scenario_type = sys.argv[1].lower()
        state_input = sys.argv[2]
        severity = sys.argv[3].lower()
        
        state = resolve_state(state_input)
        if not state:
            print(f"Invalid state: {state_input}")
            sys.exit(1)
        
        if scenario_type not in SCENARIO_TEMPLATES:
            print(f"Invalid scenario: {scenario_type}")
            print(f"Options: {', '.join(SCENARIO_TEMPLATES.keys())}")
            sys.exit(1)
        
        if severity not in ("mild", "moderate", "severe"):
            print(f"Invalid severity: {severity}")
            print("Options: mild, moderate, severe")
            sys.exit(1)
        
        results = run_scenario(scenario_type, severity, state)
        format_results(results)
        conn.close()
        sys.exit(0)
    
    # CLI mode for nationwide
    if len(sys.argv) == 3:
        scenario_type = sys.argv[1].lower()
        severity = sys.argv[2].lower()
        
        if scenario_type not in SCENARIO_TEMPLATES:
            print(f"Invalid scenario: {scenario_type}")
            sys.exit(1)
        
        results = run_scenario(scenario_type, severity)
        format_results(results)
        conn.close()
        sys.exit(0)
    
    
    if len(sys.argv) == 2 and sys.argv[1].lower() == "weather":
        run_weather_scenarios()
        conn.close()
        sys.exit(0)
    
    # Interactive mode
    print("\n" + "=" * 70)
    print("GINNIE MAE MF EXPOSURE RISK SCENARIO ENGINE")
    print("=" * 70)
    print("\nTIP: You can also run directly from the command line:")
    print("  python3 scenario_engine.py hurricane FL severe")
    print("  python3 scenario_engine.py interest_rate_shock severe")
    print("  python3 scenario_engine.py weather")
    
    while True:
        print("\nAvailable scenarios:")
        print("  1. Hurricane")
        print("  2. Earthquake")
        print("  3. Flood")
        print("  4. Unemployment spike")
        print("  5. Interest rate shock")
        print("  6. Housing market crash")
        print("  7. Run all scenarios for a state")
        print("  8. Compare states (same scenario)")
        print("  9. Weather-aware auto scenarios (live NOAA alerts)")
        print("  0. Exit")
        
        choice = input("\nSelect scenario (0-9): ").strip()
        
        if choice == "0":
            print("Exiting.")
            break
        
        scenario_map = {
            "1": "hurricane", "2": "earthquake", "3": "flood",
            "4": "unemployment", "5": "interest_rate_shock",
            "6": "housing_market_crash"
        }
        
        if choice in ("1", "2", "3", "4", "6"):
            state_input = input("Enter state (name or abbreviation): ").strip()
            state = resolve_state(state_input)
            if not state:
                print("Invalid state. Try again.")
                continue
            
            severity = input("Severity (mild/moderate/severe): ").strip().lower()
            if severity not in ("mild", "moderate", "severe"):
                print("Invalid severity. Try again.")
                continue
            
            results = run_scenario(scenario_map[choice], severity, state)
            format_results(results)
        
        elif choice == "5":
            severity = input("Severity (mild/moderate/severe): ").strip().lower()
            if severity not in ("mild", "moderate", "severe"):
                print("Invalid severity. Try again.")
                continue
            
            results = run_scenario("interest_rate_shock", severity)
            format_results(results)
        
        elif choice == "7":
            state_input = input("Enter state (name or abbreviation): ").strip()
            state = resolve_state(state_input)
            if not state:
                print("Invalid state. Try again.")
                continue
            
            severity = input("Severity (mild/moderate/severe): ").strip().lower()
            if severity not in ("mild", "moderate", "severe"):
                print("Invalid severity. Try again.")
                continue
            
            for scenario_type in ["hurricane", "earthquake", "flood",
                                   "unemployment", "housing_market_crash"]:
                results = run_scenario(scenario_type, severity, state)
                format_results(results)
        
        elif choice == "8":
            states_input = input("Enter states separated by commas (e.g. FL, TX, CA): ").strip()
            states = []
            for s in states_input.split(","):
                resolved = resolve_state(s.strip())
                if resolved:
                    states.append(resolved)
            
            if not states:
                print("No valid states entered. Try again.")
                continue
            
            scenario_input = input("Scenario (1=Hurricane 2=Earthquake 3=Flood 4=Unemployment 6=Housing crash): ").strip()
            if scenario_input not in scenario_map:
                print("Invalid scenario. Try again.")
                continue
            
            severity = input("Severity (mild/moderate/severe): ").strip().lower()
            if severity not in ("mild", "moderate", "severe"):
                print("Invalid severity. Try again.")
                continue
            
            print(f"\n{'STATE':6s} {'LOANS':>8s} {'EXPOSURE':>18s} {'NEW DQ':>8s} {'DEFAULTS':>8s} {'PROJ LOSSES':>18s}")
            print("-" * 70)
            
            for state in states:
                r = run_scenario(scenario_map[scenario_input], severity, state)
                if "error" not in r:
                    w = r["loss_waterfall"]
                    c = r["current_state"]
                    print(f"{state:6s} {c['total_loans']:>8,d} {c['total_upb']:>18s} {w['step_1_new_dq_loans']:>8,d} {w['step_3_default_loans']:>8,d} {w['step_4_projected_losses']:>18s}")
        
        elif choice == "9":
            run_weather_scenarios()
    
    conn.close()