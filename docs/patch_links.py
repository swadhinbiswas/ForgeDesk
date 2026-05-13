import glob

for filename in glob.glob("src/content/docs/*.md*"):
    with open(filename) as f:
        content = f.read()

    new_content = content.replace("architecture.md", "/architecture/")
    new_content = new_content.replace("getting-started.md", "/getting-started/")
    new_content = new_content.replace("api-complete-reference.md", "/api-complete-reference/")
    new_content = new_content.replace("deployment-security.md", "/deployment-security/")
    new_content = new_content.replace("frontend-integration.md", "/frontend-integration/")

    if new_content != content:
        with open(filename, "w") as f:
            f.write(new_content)
