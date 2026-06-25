from headroom_ee.trial import TrialManager
import json

try:
    info = TrialManager().check_trial()
    print("Integration Success:", json.dumps(info))
except Exception as e:
    print("Integration Error:", str(e))
