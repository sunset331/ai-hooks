# ai-hooks example: basic project setup

This directory shows what a minimal project looks like after `ai-init`.

## Usage

```bash
# Setup a demo project
mkdir -p /tmp/demo && cd /tmp/demo
git init
ai-init .

# Make some commits
echo "# hello" > README.md
git add README.md && git commit -m "initial commit"

echo "print('hello')" > main.py
git add main.py && git commit -m "add main script"

# See the state
cat .ai/STATUS.md
sqlite3 .ai/project.db "SELECT id, type, substr(payload,1,40) FROM events"

# Diagnose
ai-doctor .
```

## Expected structure after setup

```
demo/
├── .ai/
│   ├── project.db
│   ├── STATUS.md
│   ├── MEMORY.md
│   ├── DECISIONS.md
│   ├── CHECKLIST.md
│   └── WORKFLOW.md
├── .claude/
│   ├── settings.json
│   └── skills/ai-review/SKILL.md
├── .gitignore
└── README.md
```
