# Github Contribution Guide

_This guide outlines our github contribution process for our NZ Solar Map project._

## In Brief

* **Sync:**
    * `git pull origin main` before you start.
* **Branch Strategy:**
    * Develop in git branches. Don't git push to `main`.
    * Push your branch to GitHub.
* **Deploy:**
    * Open PR on [GitHub](https://github.com/rewiring-nz/solar-estimates).
    * Wait for CI Green Check.
    * Request review.
    * Merge.

## 1. Prerequisites and Assumptions

Before starting, we assume the following:

* **Command Line Proficiency:** You are comfortable running commands in a terminal/shell.
* **Local Development:** You have cloned the repository and are working on your own local computer.
* **Git Installed:** You have Git configured on your machine.
* **Shell Environment:** These instructions use **Bash** syntax. If you are using Windows PowerShell or CMD, you may need to adjust commands slightly.

!!! tip "Using Visual Studio Code"
    We recommend using **Visual Studio Code**. Its built-in Source Control tab provides a high-quality visual interface for staging changes and resolving merge conflicts.

## 2. The Development Process

### Step A: Sync your Local Environment

Always start by ensuring your local `main` branch is up to date with the official repository.
```bash
git checkout main
git pull origin main
```

### Step B: Create a Feature Branch

To protect the project history and ensure the stability of the `main` branch, **never work directly on `main`**. Create a branch named after the specific feature, fix, or analysis you are performing.

```bash
git checkout -b feature/my-council-analysis
```

### Step C: Develop and Test Locally

1. Perform your work in your preferred editor.
2. **Test the Pipeline:** Run your custom command using `docker compose run` (as detailed in the "Customizing the Pipeline" guide) to ensure your changes work within the Docker environment.
3. **Test the Docs:** Run `docker compose up docs` and visit `http://localhost:8000` to preview documentation changes and ensure formatting renders correctly.

### Step D: Commit and Push

Once your changes are tested and you are satisfied, stage them and push the branch to GitHub.

```bash
git add .
git commit -m "Update documentation for council data sourcing"
git push origin feature/my-council-analysis
```

## 3. Managing the Pull Request (GitHub Web UI)

Once your branch is pushed, the rest of the integration process happens on the GitHub website:

1. Navigate to the [solar-estimates repository](https://github.com/rewiring-nz/solar-estimates).
2. Look for the yellow notification bar: **"feature/my-council-analysis had recent pushes..."**
3. Click **Compare & pull request**.
4. Provide a clear title and a brief description of what you changed or the data you analyzed.
5. Click **Create pull request**.
6. **Status Checks:** Wait for the automated checks (CI) to finish. A green checkmark confirms that the Docker build and MkDocs site are still functional.
7. Once the checks pass and any review is complete, click **Merge pull request** and then **Delete branch** to keep the repository clean.

## 3. Managing the Pull Request (GitHub Web UI)

Once your branch is pushed, the rest of the integration process happens on the GitHub website:

1. Navigate to the [solar-estimates repository](https://github.com/rewiring-nz/solar-estimates).
2. Look for the yellow notification bar: **"feature/my-council-analysis had recent pushes..."**
3. Click **Compare & pull request**.
4. Provide a clear title and a brief description of what you changed or the data you analyzed.
5. Click **Create pull request**.
6. **Status Checks:** Wait for the automated checks (CI) to finish. A green checkmark confirms that the Docker build and MkDocs site are still functional.
7. **Request Review:** In the right-hand sidebar, click **Reviewers** and select a teammate to review your work. 
    * _Note: For low-impact documentation changes, you may proceed without a formal review._
8. Once the checks pass and any review is complete, click **Merge pull request** and then **Delete branch** to keep the repository clean.

## 4. Troubleshooting

| Issue | Likely Cause(s) | Fix |
| :--- | :--- | :--- |
| **Push Rejected** | • Branch protection is active on `main`.<br>• The remote branch has moved ahead of your local copy. | • Switch to a feature branch: `git checkout -b new-name`.<br>• Run `git pull origin main` to sync before pushing. |
| **Merge Blocked** | • Required status checks (CI) failed.<br>• There are merge conflicts with `main`. | • Click **Details** in the GitHub PR to see the error logs.<br>• Merge `main` into your branch locally (`git merge main`) and resolve conflicts in your editor. |
| **Docker Path Errors**| • Bash vs. Windows path syntax mismatch.<br>• Data files are located outside the `src/data` volume. | • Use forward slashes `/` in all Docker-related commands.<br>• Ensure your source data is inside the mapped project directories. |

---

## Maintainer: Configuration & Permissions

Rules for our workflow are found in :

* [Branch Protection Rules](https://github.com/rewiring-nz/solar-estimates/settings/branches): `Settings` > `Branches` > `Branch protection rules`.
* [Actions & CI/CD Settings](https://github.com/rewiring-nz/solar-estimates/settings/actions): `Settings` > `Actions` > `General`.
* [Collaborators & Teams](https://github.com/rewiring-nz/solar-estimates/settings/access): `Settings` > `Collaborators and teams`.

!!! tip "Admin Access Required"
    Only users with **Admin** permissions can see the `Settings` tab. If you cannot see it, contact the repository owner to update your permission level.