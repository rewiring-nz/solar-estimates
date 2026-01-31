# Website Maintenance Guide

_This guide describes how the website infrastructure is setup._

**Last updated:** Jan 2026

**Target site:** https://rewiring-nz.github.io/solar-estimates/

## Publish pipeline

```mermaid
graph TD
    subgraph Local Development
        A[docs/*.md] --Guides / Howtos --> D{ }
        B[src/*.py Docstrings] --> Y{ }
        X[reference.md] --> Y --API Reference--> D
        C[mkdocs.yml] -- Navigation / Style --> D
        D --docker compose up docs--> K
    end
    K(http://localhost:8080) ~~~ E

    subgraph Github Pages
        E[.github/workflows/deploy.yml] --> F
        D -- git push main --> F{GitHub
          Actions}
        F --> G(rewiring-nz.github.io/solar-estimates)
    end
```
_Diagram: Doc toolchain workflow_

## Documentation Sources

| Source | Description |
| :---- | :---- |
| docs/\*.md | Standard documentation is in markdown. |
| src/\*.py | The "API Reference" section is automatically extracted from Python docstrings in mkdocs format. |
| docs/developer/reference.md | New python files need to be added in order to extract docs-as-code. |
| mkdocs.yml | Navigation and Style: New files need to be added to the nav section of this config. |

### Local Preview

Before publishing, you can preview with:
```bash
# Change to project's root directory
#
# Start local web server
docker compose up docs

# View in a browser at: http://localhost:8000
```
### Publish Workflow

1. **The Trigger**: A `git push` to `main` triggers `/.github/workflows/deploy.yml`.  
2. **The Build**: Actions runs mkdocs gh-deploy, pushing HTML to the `gh-pages` branch.  
3. **The Hosting**: GitHub Pages watches gh-pages and refreshes the live site at https://rewiring-nz.github.io/solar-estimates/

## Technology Stack

* **MkDocs**: The static site generator that converts Markdown to HTML.  
* **Material for MkDocs**: The theme providing the UI/UX and search.  
* **mkdocstrings**: A plugin that inspects Python source code to generate the API reference.  
* **GitHub Actions**: The CI/CD engine that automates the build process.  
* **GitHub Pages**: The hosting service that serves the final files.
