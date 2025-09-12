"""
Secure Token Provider for Compiled Version
Uses runtime decryption with multiple layers
"""
import hashlib
import base64
from datetime import datetime

class SecureTokenProvider:
    def __init__(self):
        # Multi-layer encrypted token
        self._encrypted_data = self._get_encrypted_token()
        self._key = self._generate_runtime_key()
    
    def _get_encrypted_token(self):
        """Get the encrypted token data (will be replaced during build)"""
        # This will be replaced during the PyInstaller build process
        return "BUILD_TIME_ENCRYPTED_TOKEN_PLACEHOLDER"
    
    def _generate_runtime_key(self):
        """Generate decryption key at runtime"""
        # Use app-specific data to generate key
        app_id = "WebCorder"
        date_seed = datetime.now().strftime("%Y-%m")  # Changes monthly
        return hashlib.sha256(f"{app_id}_{date_seed}".encode()).hexdigest()[:16]
    
    def get_github_token(self):
        """Decrypt and return GitHub token"""
        try:
            if self._encrypted_data == "BUILD_TIME_ENCRYPTED_TOKEN_PLACEHOLDER":
                # Development mode - return None
                return None
            
            # Production mode - decrypt token
            decrypted = self._decrypt_token(self._encrypted_data, self._key)
            return decrypted
        except:
            return None
    
    def _decrypt_token(self, encrypted_data, key):
        """Decrypt the token using XOR + Base64"""
        try:
            # Base64 decode
            decoded = base64.b64decode(encrypted_data)
            
            # XOR decrypt
            result = ""
            for i, byte in enumerate(decoded):
                result += chr(byte ^ ord(key[i % len(key)]))
            
            return result
        except:
            return None

# Global instance
_token_provider = SecureTokenProvider()

def get_secure_github_token():
    """Get the securely stored GitHub token"""
    return _token_provider.get_github_token()
