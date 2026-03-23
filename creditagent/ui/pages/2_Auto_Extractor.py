import sys
import os
from pathlib import Path
import streamlit as st
import pprint

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from tools.data_extractor import extract_persona_data
from mock_data.personas import PERSONAS

st.set_page_config(page_title="Auto Data Extractor", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; text-transform: uppercase; }
</style>
""", unsafe_allow_html=True)

st.markdown("# AI DATA EXTRACTOR AGENT")
st.markdown("Automate data entry by pasting unstructured text (e.g., an interview transcript, an email, or raw notes) and our AI Extractor Agent will automatically parse the structured financial data for you.")

st.info("💡 **Example input:** 'We have a new applicant, Alice. She is a 28 year old self-employed woman living in a rural area. She has no bank account. She wants a loan of 40,000,000 VND. She has been paying her utility bills on time 95% of the time for the past 36 months, and her mobile money volume is roughly 25,000,000 VND each month with a consistency rating of 0.88.'")

raw_text = st.text_area("Unstructured Borrower Information", height=250, placeholder="Paste or type raw borrower data here...")

if st.button("EXTRACT AND SAVE PERSONA", type="primary"):
    if not raw_text.strip():
        st.warning("Please enter some text first.")
    else:
        with st.spinner("🤖 Agent is reading and extracting data..."):
            try:
                extracted_data = extract_persona_data(raw_text)
                b_id = f"borrower_{len(PERSONAS)+1:03d}"
                PERSONAS[b_id] = extracted_data
                
                # Save back to file
                out = '"""Mock SME personas for demo using Taiwan Credit Card Dataset native variables."""\n\nPERSONAS = ' + pprint.pformat(PERSONAS, indent=4) + '\n'
                personas_path = ROOT / "mock_data" / "personas.py"
                with open(personas_path, "w", encoding="utf-8") as f:
                    f.write(out)
                
                st.success(f"✅ SUCCESSFULLY EXTRACTED AND ADDED {b_id.upper()}!")
                st.json(extracted_data)
                st.info("You can now navigate back to the Main App (sidebar menu on the left) to run the assessment on this parsed borrower.")
            except Exception as e:
                st.error(f"❌ Extraction failed: {str(e)}\n\nPlease try rephrasing the text, or verify your API key configuration.")
