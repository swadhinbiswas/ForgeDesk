with open("forge/api/__init__.py", "r") as f:
    text = f.read()

text = text.replace("from .os_integration import OsIntegrationAPI", "from .os_integration import OSIntegrationAPI")
text = text.replace("    \"OsIntegrationAPI\",", "    \"OSIntegrationAPI\",")

with open("forge/api/__init__.py", "w") as f:
    f.write(text)
