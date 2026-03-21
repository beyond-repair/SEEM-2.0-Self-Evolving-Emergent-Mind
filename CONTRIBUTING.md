# Contributing to SEEM 1.7 – Self-Evolving Emergent Mind

Thank you for considering contributing to SEEM!  
This project aims to build the first truly sovereign, self-evolving AGI seed — a local-first epistemic engine that grows more valuable the longer you own it.

We welcome contributions of all kinds: code, documentation, benchmarks, experiments, issue reports, design ideas, and even hardware-specific optimizations.

## Code of Conduct

By participating, you agree to our [Code of Conduct](./CODE_OF_CONDUCT.md) (standard Contributor Covenant — be respectful, inclusive, and constructive).

## How to Contribute

1. **Find an Issue**  
   Look at the [Issues tab](https://github.com/AtomicDreamLabs/SEEM-1.7/issues) — we tag good first issues with `good-first-issue` and high-impact ones with `help-wanted` or `research`.

2. **Discuss First**  
   For large changes (new tier, major refactor, new math), open a discussion or comment on an existing issue to align before writing code.

3. **Fork & Branch**  
   - Fork the repo  
   - Create a branch: `git checkout -b feature/resonator-hrn` or `fix/shacl-latency`  
   - Make your changes

4. **Run Tests & Lint**  
   ```bash
   # Install dev dependencies
   pip install -r requirements-dev.txt

   # Run tests
   pytest

   # Lint & format
   ruff check --fix
   black .
