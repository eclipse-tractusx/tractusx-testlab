# Overview

Tractus-X TestLab is a test authoring and execution library for Eclipse Tractus-X dataspaces.

## How It Works

1. Write a YAML test definition describing your test scenario, listed in a TCK manifest
2. Run it with `testlab run index.yaml`
3. TestLab compiles the manifest into a sealed package, validating it first — nothing
   executes that has not compiled
4. TestLab executes each step, manages mock services, and reports results
