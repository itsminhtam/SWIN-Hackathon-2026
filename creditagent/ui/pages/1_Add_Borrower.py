import sys
import os
from pathlib import Path
import streamlit as st
import pprint

# Allow importing from root directory
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from mock_data.personas import PERSONAS

st.set_page_config(page_title="Add New Borrower", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; text-transform: uppercase; }
</style>
""", unsafe_allow_html=True)

st.markdown("# ADD NEW BORROWER (TAIWAN EXPERT MODEL)")
st.markdown("Configure native Taiwan Credit Card dataset features for your persona.")

with st.form("add_borrower_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### PROFILE")
        b_id = st.text_input("Borrower ID", f"borrower_{len(PERSONAS)+1:03d}")
        name = st.text_input("Name", "Custom Borrower")
        scenario = st.text_input("Scenario", "Custom manual entry")
        expected = st.selectbox("Expected Decision", ["APPROVE", "ESCALATE", "DENY"])
        
        gender = st.selectbox("Gender", ["male", "female"])
        age = st.selectbox("Age Group", ["18-25", "25-35", "35-45", "45+"])
        region = st.selectbox("Region", ["urban", "suburban", "rural"])
        emp_type = st.selectbox("Employment Type", ["employee", "business_owner", "self_employed", "unemployed"])

    with col2:
        st.markdown("### BANK DATA (TAIWAN FEATURES)")
        has_bank = st.checkbox("Has Bank Data?", value=True)
        limit_bal = st.number_input("LIMIT_BAL (Credit Limit Amount)", 0.0, None, 100_000.0)
        
        edu_dict = {1: "Graduate School", 2: "University", 3: "High School", 4: "Others"}
        mar_dict = {1: "Married", 2: "Single", 3: "Others"}
        education = st.selectbox("EDUCATION", [1, 2, 3, 4], format_func=lambda x: f"{x} - {edu_dict[x]}", index=1)
        marriage = st.selectbox("MARRIAGE", [1, 2, 3], format_func=lambda x: f"{x} - {mar_dict[x]}", index=1)
        
        st.info("Payment statuses (PAY_X): 0 = On Time, -1 = Paid fully, 1 = 1 month delay, 2 = 2 months delay, etc.")
        pay_0 = st.slider("PAY_0 (Current Month Delay)", -2, 8, 0)
        pay_2 = st.slider("PAY_2 (Last Month Delay)", -2, 8, 0)
        pay_3 = st.slider("PAY_3 (2 Months Ago Delay)", -2, 8, 0)
        
        bill_amt1 = st.number_input("BILL_AMT1 (Current Bill Statement)", -50_000.0, None, 50_000.0)
        pay_amt1  = st.number_input("PAY_AMT1 (Amount Paid Last Month)", 0.0, None, 5_000.0)

    st.markdown("### ALTERNATIVE DATA")
    col3, col4 = st.columns(2)
    with col3:
        has_utility = st.checkbox("Has Utility Data?", value=True)
        util_on_time = st.slider("Utility On-Time Rate", 0.0, 1.0, 0.95)
        util_months = st.number_input("Utility Months History", 0, 120, 24)
    with col4:
        has_mobile = st.checkbox("Has Mobile Money Data?", value=True)
        mob_vol = st.number_input("Mobile Monthly Volume (VND)", 0, None, 15_000_000, 1_000_000)
        mob_consistency = st.slider("Mobile Consistency Score", 0.0, 1.0, 0.80)

    submitted = st.form_submit_button("SAVE BORROWER PERSONA", type="primary")

if submitted:
    new_persona = {
        "name": name,
        "scenario": scenario,
        "expected_decision": expected,
        "profile": {
            "gender": gender,
            "age_group": age,
            "region": region,
            "employment_type": emp_type
        }
    }
    
    if has_bank:
        # We parse the age category properly roughly
        age_map = {"18-25": 22, "25-35": 30, "35-45": 40, "45+": 50}
        
        new_persona["bank_data"] = {
            "LIMIT_BAL": limit_bal,
            "SEX": 1 if gender == "male" else 2,
            "EDUCATION": education,
            "MARRIAGE": marriage,
            "AGE": age_map[age],
            "PAY_0": pay_0,
            "PAY_2": pay_2,
            "PAY_3": pay_3,
            "BILL_AMT1": bill_amt1,
            "PAY_AMT1": pay_amt1,
        }
    else:
        new_persona["bank_data"] = None
        
    if has_utility:
        new_persona["utility_data"] = {
            "on_time_rate": util_on_time,
            "months_history": util_months
        }
    else:
        new_persona["utility_data"] = None
        
    if has_mobile:
        new_persona["mobile_data"] = {
            "monthly_volume": mob_vol,
            "consistency_score": mob_consistency
        }
    else:
        new_persona["mobile_data"] = None

    PERSONAS[b_id] = new_persona
    
    out = '"""Mock SME personas for demo using Taiwan Credit Card Dataset native variables."""\n\nPERSONAS = ' + pprint.pformat(PERSONAS, indent=4) + '\n'
    
    personas_path = ROOT / "mock_data" / "personas.py"
    with open(personas_path, "w", encoding="utf-8") as f:
        f.write(out)
        
    st.success(f"SUCCESSFULLY ADDED {b_id.upper()}!")
    st.info("You can now navigate back to the Main App (sidebar menu on the left) to run the credit assessment for your custom borrower.")
