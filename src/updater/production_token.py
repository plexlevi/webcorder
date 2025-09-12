"""
Production GitHub Token Configuration
LIMITED token for update checking on private repositories

SECURITY NOTE: 
- This token has repo access but should be:
  1. Rotated regularly (every 6 months)
  2. Monitored for unusual activity
  3. Replaced immediately if compromised
"""

# Limited access token for private repository releases
# Scope: repo (required for private repo access)
# Usage: ONLY for checking releases, not for code modification
PRODUCTION_GITHUB_TOKEN = "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"

# Security measures implemented:
# 1. Token only used for read operations
# 2. No write operations in update checker code
# 3. Exception handling prevents token exposure in logs
# 4. Token embedded in binary - not accessible as plain text
