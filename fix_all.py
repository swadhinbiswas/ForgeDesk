import os
import re

workflows_dir = ".github/workflows"
for filename in os.listdir(workflows_dir):
    if filename.endswith(".yml"):
        filepath = os.path.join(workflows_dir, filename)
        with open(filepath, "r") as f:
            content = f.read()

        # Remove MATURIN_PEP517_ARGS
        content = re.sub(r'\s*MATURIN_PEP517_ARGS:\s*"--manylinux off"\n', '\n', content)
        
        # Remove --manylinux off from maturin build commands
        content = re.sub(r'--manylinux off', '', content)

        # Add patchelf to apt-get install commands
        content = re.sub(r'(sudo apt-get install -y [^\\n]+)', r'\1 patchelf', content)

        with open(filepath, "w") as f:
            f.write(content)

print("Fixed everything via python script.")
