# hello-python-docker-action


w .github/workflows/action.yaml

name: Test Docker Action

on:
  push:
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
        uses: s25132/hello-python-docker-action@v1
        with:
          base_sha: HEAD~1
          head_sha: HEAD