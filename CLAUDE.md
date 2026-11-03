# Working rules for Claude

These rules were set by the project owner and apply to all work on this project.

## 1. Work locally

- All work happens in the local folder `D:\aysha_garments`.
- Do not create or change project files anywhere else as the final location.

## 2. Push only when told

- Repository: https://github.com/Tajmalookcs/aysha_garments
- Do not push to GitHub until the owner explicitly asks for it.
- A previous request to push does not cover later work. Each push needs its own request.

## 3. Plan first, then wait for approval

For every build:

1. Give the owner a plan: what will be built, which files will change, and any decisions needed.
2. Stop and wait for the owner's approval.
3. Build only what was approved.
4. Record the plan and its outcome in `docs/BUILD_PLANS.md`.

If the work needs to go beyond the approved plan, stop and ask first.

## 4. Keep documents accurate

- Project facts go in `docs/PROJECT_BRIEF.md`. Do not fill in details the owner has not confirmed; list them as open questions.
- Keep the folder structure and status in `README.md` up to date.

## 5. Project layout

- `docs/` holds project documents.
- `media/` holds client documents. It is ignored by Git and must never be pushed.
- `reference/` holds official FBR and PRAL documents. Do not edit them.

## 6. Public repository

The repository is public. Never commit tax numbers, CNICs, IP addresses, tokens, passwords, or personal contact details.

## 7. FBR facts

- Never invent FBR API details, tax rates, SROs, HS codes or scenario codes.
- FBR facts must trace to an official document. If unconfirmed, say so and ask.

## 8. Earlier projects

Earlier projects are only a reference for FBR rules. This project has its own design and code.
