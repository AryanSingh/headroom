import json

from cutctx_ee.trial import TrialManager

try:
    info = TrialManager().check_trial()
    print("Integration Success:", json.dumps(info))
except Exception as e:
    print("Integration Error:", str(e))
