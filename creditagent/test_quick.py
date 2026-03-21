"""Quick end-to-end test of the orchestrator."""
import sys
sys.path.insert(0, ".")

from agents.orchestrator import OrchestratorAgent

o = OrchestratorAgent()

print("=== borrower_002 (thin-file, no bank) ===")
r = o.run("borrower_002")
print(f"Name           : {r['borrower_name']}")
print(f"Scenario       : {r['scenario']}")
print(f"Financial Score: {r['financial_score']}")
print(f"Alt Score      : {r['alternative_score']}")
print(f"Composite Score: {r['composite_score']}")
print(f"Risk Tier      : {r['risk_tier']}")
print(f"DECISION       : {r['decision']}")
print(f"Is_underbanked : {r['is_underbanked']}")
print(f"Processing     : {r['processing_time_ms']}ms")
print()

print("=== borrower_001 (strong traditional) ===")
r2 = o.run("borrower_001")
print(f"Decision: {r2['decision']} | Score: {r2['composite_score']} | {r2['risk_tier']}")
print()

print("=== borrower_003 (borderline) ===")
r3 = o.run("borrower_003")
print(f"Decision: {r3['decision']} | Score: {r3['composite_score']} | {r3['risk_tier']}")
print()

print("=== borrower_004 (high risk) ===")
r4 = o.run("borrower_004")
print(f"Decision: {r4['decision']} | Score: {r4['composite_score']} | {r4['risk_tier']}")
