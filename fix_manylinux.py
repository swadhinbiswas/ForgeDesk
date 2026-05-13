import os
import re

workflows_dir = ".github/workflows"
for filename in os.listdir(workflows_dir):
    if filename.endswith(".yml"):
        filepath = os.path.join(workflows_dir, filename)
        with open(filepath) as f:
            content = f.read()

        # Change --manylinux 2014 to --manylinux auto
        content = re.sub(r"--manylinux 2014", "--manylinux auto", content)

        # Add MATURIN_PEP517_ARGS: "--manylinux off" to env blocks
        # First, check if there is an env: block at the top level
        if "env:" in content and "MATURIN_PEP517_ARGS" not in content:
            content = re.sub(
                r"(env:\n(?:  .*\n)+)", r'\1  MATURIN_PEP517_ARGS: "--manylinux off"\n', content
            )

        with open(filepath, "w") as f:
            f.write(content)
