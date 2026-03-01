# summarize-changed-files-agent

## Example workflow configuration

`.github/workflows/action.yaml`:

```yaml
name: Summarize Changed Files Agent 

on:
  push:
  workflow_dispatch:
    inputs:
      base_sha:
        description: "Base commit SHA (older)"
        required: true
      head_sha:
        description: "Head commit SHA (newer)"
        required: true

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Print changed Python files
        uses: s25132/summarize-changed-files-agent@v1
        with:
          base_sha: HEAD~1
          head_sha: HEAD
```

## Documentation

[GitHub Copilot SDK Getting Started](https://github.com/github/copilot-sdk/blob/main/docs/getting-started.md)