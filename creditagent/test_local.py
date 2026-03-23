import sys, os
from pathlib import Path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from agents.react_orchestrator import ReActOrchestrator
from api.main import CreditAssessmentResult

orc = ReActOrchestrator()
try:
    res = orc.run("borrower_001")
    # Try parsing through the Pydantic model directly
    try:
        model_instance = CreditAssessmentResult(**res)
        print("Pydantic Validation PASS")
    except Exception as parse_e:
        print("Pydantic Validation ERROR:")
        print(parse_e)
except Exception as e:
    import traceback
    traceback.print_exc()
