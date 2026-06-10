import os

# Disable Gemini CLI deprecation warnings/errors during testing
os.environ["AGENTPIPE_IGNORE_DEPRECATION"] = "1"
