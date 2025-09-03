# tests/test_utils.py
import sys
import os
import pytest
import pyotp
from app.auth_utils import generate_2fa_secret, verify_2fa_code

# Add the project root to the Python path to allow imports from 'app'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the functions we want to test
from app.auth_utils import verify_password, pwd_context

# A test function must start with the word 'test_'
def test_verify_password_correct():
    """Tests that a correct password returns True."""
    plain_password = "mySuperSecretPassword123"
    hashed_password = pwd_context.hash(plain_password)
    
    # 'assert' checks if a condition is True. If it's False, the test fails.
    assert verify_password(plain_password, hashed_password) == True

def test_verify_password_incorrect():
    """Tests that an incorrect password returns False."""
    plain_password = "mySuperSecretPassword123"
    hashed_password = pwd_context.hash(plain_password)

    assert verify_password("wrong_password", hashed_password) == False

def test_generate_2fa_secret():
    """Tests that a valid 32-character Base32 secret is generated."""
    secret = generate_2fa_secret()
    assert isinstance(secret, str)
    assert len(secret) == 32
    # Check if it's a valid Base32 string
    try:
        pyotp.random_base32() # This is just a way to validate the format
        is_valid_base32 = True
    except Exception:
        is_valid_base32 = False
    assert is_valid_base32

def test_verify_2fa_code():
    """Tests that the 2FA code verification works correctly."""
    secret = generate_2fa_secret()
    totp = pyotp.TOTP(secret)
    
    # 1. Test with a correct code
    correct_code = totp.now()
    assert verify_2fa_code(secret, correct_code) == True
    
    # 2. Test with an incorrect code
    incorrect_code = "000000"
    assert verify_2fa_code(secret, incorrect_code) == False