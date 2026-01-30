# hello-python-docker-action


w .github/workflows/action.yaml

name: Test Docker Action

on:
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run hello python docker action
        uses: s25132/hello-python-docker-action@v1
        with:
          name: "World"