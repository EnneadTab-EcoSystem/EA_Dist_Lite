# Transplant instructions

This directory is a **ready-to-push** greenfield tree for
`https://github.com/EnneadTab-EcoSystem/enneadtab-logger`.

When that repo exists and this agent (or a human) has push access:

```bash
git clone https://github.com/EnneadTab-EcoSystem/enneadtab-logger.git
cd enneadtab-logger
# copy contents of this folder (not the parent docs/proposals path) to repo root
cp -a README.md CHANGELOG.md pyproject.toml src docs .gitignore .
git add .
git commit -m "chore: initial enneadtab-logger scaffold (usage lane)"
git push -u origin main   # or open PR if main is protected
```

Do **not** publish under SenZhang-Plus.
