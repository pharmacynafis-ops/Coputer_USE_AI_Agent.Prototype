import os
import sys
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from request_classifier import RequestClassifier
from server import save_step_log


def test_classification_logging():
    rc = RequestClassifier()
    classification = rc.classify('Create a new file for a feature')
    entry = {
        'session_id': 'test_session',
        'type': 'classification',
        'classification': classification,
        'timestamp': time.time()
    }
    # Invoke save_step_log to persist
    save_step_log(entry)
    # Verify file exists
    assert os.path.exists('steps_log.json')
    # Basic check: last entry matches type
    import json
    with open('steps_log.json', 'r', encoding='utf-8') as f:
        logs = json.load(f)
    assert logs[-1]['type'] == 'classification'


if __name__ == '__main__':
    test_classification_logging()
    print('Integration logging test passed')
