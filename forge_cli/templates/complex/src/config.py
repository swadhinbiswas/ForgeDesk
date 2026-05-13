"""
Configuration module.
"""

import os

APP_NAME = "{{PROJECT_NAME}}"
DEBUG = os.environ.get("DEBUG", "1") == "1"

# Add any additional constants or config classes here
