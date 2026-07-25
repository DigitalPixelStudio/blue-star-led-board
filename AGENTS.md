# Digital Pixel Forge (DPF) — AGENTS.md

## Team

- **Faisy💨** — Founder, Visionary & Team Leader
- **Jazz🔥** — Elite AI Engineer & Strategic Special Assistant (Lead Architect)
- **Jasmine🔥** — Head AI Model, Field Developer, Git Executor & Local Operations Specialist (this is me!)

## Company

- **Name:** Digital Pixel Forge (DPF)
- **Mission:** Build seamless, production-ready software solutions
- **GitHub Org:** DigitalPixelStudio
- **Repo:** blue-star-led-board

## Tech Stack

- **Framework:** Python 3 + Kivy
- **Build System:** Buildozer (Docker: `kivy/buildozer`)
- **Target:** Android APK (arm64-v8a, API 33, min API 24)
- **CI/CD:** GitHub Actions (Docker-based pipeline)
- **Workflow:** `.github/workflows/build.apk.yml`

## Project Structure

```
├── main.py                    # Kivy app entry point
├── buildozer.spec             # Buildozer Android config
├── .github/workflows/
│   └── build.apk.yml          # GitHub Actions CI pipeline
├── AGENTS.md                  # This file — team context & conventions
└── JASMINE.md                 # Jasmine's memory & preferences
```

## Rules & Conventions

- Commit messages: `feat(ci):`, `fix(ci):`, `feat:`, `fix:` style
- Branch: `main` is the primary branch
- Always test builds via GitHub Actions before declaring success
- Docker build uses `BUILDOZER_WARN_ON_ROOT=0` and `--entrypoint sh` to bypass root warning
- APK artifacts uploaded as `DPF-Universe-APK`

## Notes

- The repo was previously empty — Jasmine created all initial files
- Build takes 15-25 min on GitHub Actions (Docker SDK/NDK download + compile)
- If build fails, check GitHub Actions logs for the exact step failure
