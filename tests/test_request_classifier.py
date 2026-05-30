import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from request_classifier import RequestClassifier


def test_classifier_basic_categories():
    rc = RequestClassifier()
    r1 = rc.classify("Create a file with a login handler")
    assert isinstance(r1, dict)
    assert 'category' in r1 and 'confidence' in r1

    r2 = rc.classify("There is an exception and a traceback in server.py")
    assert isinstance(r2, dict)
    assert 'category' in r2 and 'confidence' in r2

    r3 = rc.classify("How do I secure passwords in the database?")
    assert isinstance(r3, dict)
    assert 'category' in r3 and 'confidence' in r3


if __name__ == '__main__':
    test_classifier_basic_categories()
    print('RequestClassifier basic tests passed')
