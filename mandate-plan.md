PayPal AI Hackathon \| Updated Sat 7 Nov 2026 \| Solo build: Anthony Afonughe

**Hard deadline:** Thu 12 Nov 2026, 12:00 PT = 21:00 Poland time. **Your internal deadline:** submit Wed 11 Nov by 20:00 Poland time. Thursday is for fixing submission errors only.

Mandate is a policy gateway between an AI agent and PayPal. The agent asks Mandate to pay an invoice. Mandate checks fixed rules in code and answers allow, hold for human approval, or block. Every decision is logged.

# 1. Where things stand (Sat 7 Nov)

| **Item**                                                                 | **Status**                                                              |
|--------------------------------------------------------------------------|-------------------------------------------------------------------------|
| Devpost registration                                                     | Done                                                                    |
| PayPal sandbox: US business and personal accounts                        | Done                                                                    |
| Sandbox app "mandate" (Merchant type, linked to the US business account) | Confirm it exists, then copy Client ID and Secret into .env             |
| Starter repo: policy engine (8 checks), 11 passing tests, MIT license    | Done                                                                    |
| AI model                                                                 | Decided: Nebius Token Factory (you have credits). Model still to choose |
| Which PayPal APIs work in your sandbox (Payouts, Invoicing, Orders)      | Unknown. The probe script in Task 1 will tell us                        |
| Project folder                                                           | Move out of OneDrive to C:\dev\Mandate                                  |
| Payment path, gateway, agent, approval UI, video, README                 | Not started                                                             |

# 2. What the official rules mean for your decisions

| **Rule**                   | **What it means for Mandate**                                                                                                                                                                                                                                                                               |
|----------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Deadline and edits         | Submission period ends Thu 12 Nov, 12:00 PT (21:00 Poland). You can save drafts and edit until then. After that, nothing can be changed.                                                                                                                                                                    |
| Eligibility                | Open to adults by country of residence. Excluded: residents of Brazil, Quebec, Russia, Crimea, Cuba, Iran, North Korea. You live in Poland and enter as an individual, so you qualify.                                                                                                                      |
| What to build              | An app that integrates the PayPal developer platform (free sandbox) plus an AI tool, model or platform of your choice. PayPal must be central.                                                                                                                                                              |
| Judging stages             | Stage 1 is pass/fail: does it fit the theme and really use PayPal APIs. Stage 2 scores five equal criteria: Technological Implementation, Design, Potential Impact, Innovation, Presentation. Judging may include automated AI analysis, and judges may score from the description, images and video alone. |
| Working demo, not a mockup | Provide either a hosted demo URL or complete setup and run instructions in the repo. Static or non-functional demos do not count. The Project must work as shown in your video and text.                                                                                                                    |
| Testing access             | The Project must be free to test, with no restrictions, until the Judging Period ends on 15 Dec. If you host it, keep it running until then. Put any test credentials in the README or description.                                                                                                         |
| Repository                 | Public GitHub/GitLab/Bitbucket repo with all source, assets and instructions, and an open-source LICENSE file visible in the About section.                                                                                                                                                                 |
| Video                      | Under 3 minutes, public on YouTube, shows the project running on the device it was built for. No third-party trademarks or copyrighted music. Narration is not required. All materials in English.                                                                                                          |
| Originality                | The Submission must be your original work, solely owned by you. Open-source libraries are fine if you follow their licenses. Third-party APIs (PayPal, Nebius) must be used within their terms.                                                                                                             |
| Prize limits               | A project can win one Grand Prize plus one Sponsor Prize, or one Honorable Mention plus one Sponsor Prize. So pick ONE sponsor prize to aim for. AG Grid pays cash (\$5,000 / \$2,000 / \$1,000). Render pays credits only.                                                                                 |
| Publicity                  | The sponsor may use your name, likeness, voice and country for promotion for three years.                                                                                                                                                                                                                   |
| If you win                 | Prizes need an affidavit and identity checks. Non-US winners may need a W-8BEN form and are responsible for their own taxes and bank fees.                                                                                                                                                                  |

# 3. Scope

## Must have (minimum viable Mandate)

- Gateway the agent talks to (MCP server over Streamable HTTP).

- Policy checks: per-payment cap, payee allow-list, payee-change detection, approval threshold. Already built and tested in mandate/policy.py, along with budget, expiry, duplicate invoice and currency checks.

- A real PayPal sandbox payment for an allowed request.

- Audit log of every request, decision and reason.

- Approval screen for held payments.

- AI agent running on Nebius that reads invoices and requests payments through Mandate.

- Public repo, LICENSE, README that works from a clean clone.

- Video and Devpost submission.

## Should have

- Approval and audit screens built with AG Grid (your one sponsor prize).

- Attack test script that runs every attack and prints pass or fail.

- AI-written plain-language risk summary on the approval screen (same Nebius model).

- Hosted demo on Render, so judges can try it without setup.

## Could have, only if everything above works

- Prompt-injection test: instructions hidden in invoice text.

- Postman collection of the gateway tools.

## Cut

- New features after the freeze. User accounts. Extra payment methods. Tavily or any search tool. Anything not visible in the video.

# 4. Architecture and where the AI sits

| **AI agent (Nebius model)**                                                                                 | **Mandate gateway (plain code, no AI decisions)**                                           | **PayPal sandbox**                                                        |
|-------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------|---------------------------------------------------------------------------|
| Reads an invoice, extracts supplier, payee and amount, and asks to pay by calling the request_payment tool. | Checks the request against the mandate: ALLOW, HOLD or BLOCK. Logs the decision and reason. | Receives only requests that were ALLOWed, or HOLDs that a human approved. |

- **Design rule:** the policy engine is deterministic code, not an LLM. The agent can be fooled by what it reads. The gateway cannot be talked out of its rules.

- **Why AI still counts as meaningful:** the agent loop (reading invoices and deciding to pay) is the core use case Mandate protects, and the approval screen shows an AI-written risk summary. Say this clearly in the form and video, because Stage 1 checks it.

# 5. AI tool: Nebius Token Factory

Nebius runs hosted models behind an OpenAI-compatible API that supports tool/function calling. Rules allow any AI tool, so using the credits you already have is fine.

## Setup

- Create an API key in the Nebius Token Factory console.

- Open the model list in the console and choose a current text model that supports function calling. Models are retired from time to time, so do not rely on an old name from a tutorial. Write the exact model ID down.

- Put these in .env (never in the repo):

> NEBIUS_API_KEY=
>
> NEBIUS_MODEL_ID=
>
> NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/

## How the agent uses it

- Use an OpenAI-compatible client with the base URL, key and model all read from .env, so you can switch provider by changing three lines.

- Give the model one tool: request_payment(invoice_id, supplier_id, payee_email, amount, currency, memo). Set temperature to 0 for repeatable demos.

- Keep demo invoices as fixed sample files: one legitimate, one with a changed payee, one oversized.

- The agent never calls PayPal directly. It only talks to Mandate.

## Cautions

- Test that your chosen model really issues tool calls. If it does not, switch model before building more.

- Check how long your credits last. If the demo is hosted until 15 Dec, add a rate limit so strangers cannot use them up.

- Fallback: if Nebius misbehaves, point the same code at another OpenAI-compatible provider.

- Do not use Tavily. Mandate has no step that needs web search, and adding it would look forced.

# 6. Policy checks and the attack each one stops

| **Check**           | **Attack it stops**                               | **Decision**            |
|---------------------|---------------------------------------------------|-------------------------|
| Expiry              | Replay of an old mandate                          | Block                   |
| Amount and currency | Zero, negative or wrong-currency payment          | Block                   |
| Payee allow-list    | Unknown recipient                                 | Block                   |
| Payee change        | Known supplier, new payee account (invoice fraud) | Hold for human approval |
| Duplicate invoice   | Same invoice paid twice                           | Block                   |
| Per-payment cap     | Oversized payment                                 | Block                   |
| Cumulative budget   | Splitting one big payment into many small ones    | Block when exceeded     |
| Approval threshold  | Large but legitimate payment                      | Hold for human approval |

*If several checks fire, the worst outcome wins: block beats hold, hold beats allow.*

# 7. Day-by-day plan (Poland time)

You start this plan with nothing built beyond the policy engine, so the order matters: get one real payment working first, then wrap it.

## Sat 7 Nov (tonight): foundations

\[ \] Move the project to C:\dev\Mandate (outside OneDrive).

\[ \] Create .env with Client ID, Secret, PAYPAL_PERSONAL_EMAIL, and the Nebius key and model.

\[ \] Claude Code Task 1: PayPal client and probe script. Run the probe yourself.

\[ \] Create the public GitHub repo, push, confirm the MIT license shows in About.

**End of day test:** the probe shows which of Payouts, Invoicing and Orders work, and a token request succeeds.

## Sun 8 Nov: payment path and gateway

\[ \] Task 2: execute a payment through the API that works, plus a small database (mandate, suppliers, payments, audit log, approvals).

\[ \] Task 3: MCP gateway with request_payment, wired to the policy engine (ALLOW pays, HOLD queues, BLOCK logs).

\[ \] Seed a believable small business: 3 to 5 suppliers, a mandate, a few past payments.

**End of day test:** a request sent to the gateway by a script produces a real sandbox payment, a held request and a blocked request, all in the audit log.

## Mon 9 Nov: the AI agent and the screens

\[ \] Task 4: Nebius agent that reads sample invoices and calls request_payment. Confirm tool calls work.

\[ \] Task 5: approval queue and audit log with AG Grid, with approve and reject buttons.

\[ \] Task 6: attack test script (legitimate, changed payee, oversized, unknown supplier, duplicate, budget).

**End of day test:** agent plus gateway plus UI run the whole attack scenario on your PC.

## Tue 10 Nov: polish, README, freeze, record

\[ \] Task 7: README, .env.example, clean-clone test in a new folder, optional Render deploy.

\[ \] Feature freeze at 14:00. After that, bug fixes only.

\[ \] Rehearse the demo twice. Record the video in the evening. Upload to YouTube as Public.

\[ \] Screenshots and architecture diagram for the gallery.

## Wed 11 Nov: finish and submit

\[ \] Morning: fill the Devpost form from mandate-devpost-submission.md. Replace every bracket.

\[ \] Test the repo, demo link and video in a private window.

\[ \] Submit by 20:00. Confirm "My projects" shows Submitted, not draft.

## Thu 12 Nov: safety day

- Only fix errors. Hard stop at 21:00 Poland time. After that, nothing can be edited.

**If you fall behind:** drop the Should-have items from the bottom up. Never drop the video time, the clean-clone test, or the working PayPal payment.

# 8. Working with Claude Code

Give Claude Code one task at a time and check the result before the next one. Put mandate-plan.md (the text copy of this plan) in the project folder, and paste this at the start of the session.

> Read mandate-plan.md and mandate/policy.py first.
>
> We are building "Mandate" for the PayPal AI Hackathon.
>
> Deadline: Thu 12 Nov 2026, 21:00 Poland time. I am working solo.
>
> Rules for this whole project:
>
> \- Do ONLY the task I give you. No extra features, no refactors.
>
> \- Do not change mandate/policy.py unless I ask.
>
> \- Secrets live only in .env. Never print, log or commit PayPal
>
> credentials, tokens or API keys. Never commit .env.
>
> \- Do not run git commit or git push. I will do that.
>
> \- Keep code simple and readable. I must explain it in a video.
>
> \- After each task, list the files you created or changed and
>
> how to run the tests.

| **Task** | **Goal**                                                                                                                                                                  | **You check by**                                           |
|----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------|
| 1        | mandate/paypal_client.py: OAuth token with caching and refresh. scripts/probe_paypal.py: try a 1.00 USD Payout, a draft invoice and an order, print status and a summary. | Run tests, then run the probe. Paste me the summary.       |
| 2        | Payment execution through the API that worked in the probe. Database for mandate, suppliers, payments, audit log and approvals.                                           | A script makes one real sandbox payment and logs it.       |
| 3        | MCP gateway with a request_payment tool, wired to evaluate(): ALLOW pays, HOLD queues for approval, BLOCK logs.                                                           | Three test requests give three different outcomes.         |
| 4        | Nebius agent that reads sample invoices and calls request_payment. Temperature 0. Config from .env.                                                                       | The model issues real tool calls on all sample invoices.   |
| 5        | Approval queue and audit log with AG Grid, plus approve and reject.                                                                                                       | You approve a held payment in the browser and see it paid. |
| 6        | Attack test script and seed data.                                                                                                                                         | Every attack prints pass.                                  |
| 7        | README, .env.example, deploy notes, clean-clone run.                                                                                                                      | A fresh folder runs from the README alone.                 |

- Read what it writes, especially anything that decides whether money moves. Never let it print the secret.

- List Claude Code as a development tool in the Devpost tools field.

# 9. Video storyboard (target 2:40, hard cap 3:00)

Narration is not required by the rules. You can use text-to-speech or captions only. Do not use copyrighted music or show other companies' logos.

| **Time**     | **On screen**                       | **Say or caption**                                                                                              |
|--------------|-------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| 0:00 to 0:15 | Title, then a fake invoice email    | AI agents can now pay invoices. But an agent can be fooled, and one fake invoice can move real money.           |
| 0:15 to 0:35 | Architecture diagram                | Mandate sits between the agent and PayPal. The rules run in code the agent cannot override.                     |
| 0:35 to 1:00 | Mandate settings                    | The business sets budget, cap, approved suppliers and an approval threshold.                                    |
| 1:00 to 1:25 | Legitimate invoice paid             | A normal invoice is within the mandate and is paid through PayPal sandbox.                                      |
| 1:25 to 2:05 | The attack: changed payee           | Same supplier, new account. The agent was convinced. Mandate holds it and flags the change. Show the audit log. |
| 2:05 to 2:25 | Approval screen                     | Above the threshold, a human decides.                                                                           |
| 2:25 to 2:45 | Test script output, repo, live link | Every attack is a test. Open source. Runs from a clean clone.                                                   |

- Show the attack before the fix. That is the before and after moment.

- Zoom the browser to 125 percent. Close personal tabs and notifications. Keep the Client Secret off screen.

- Mention that the agent runs on Nebius and was built with help from Claude Code.

# 10. README outline (judges read this)

- One sentence and a screenshot.

- Problem in three lines.

- Live demo link and video link.

- Architecture diagram.

- Run it yourself: prerequisites, .env.example variables (PayPal sandbox keys, Nebius key and model), install, start, seed data. Commands judges can copy.

- How to reproduce the demo: exact click path and the attack script command.

- PayPal APIs used and where (file names).

- AI tools used and where: Nebius Token Factory model, and Claude Code for development.

- Policy checks table.

- License.

# 11. Risks and fallbacks

| **\#** | **Risk**                                                                               | **Fallback**                                                                                             |
|--------|----------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| R1     | Stage 1: judges decide AI is not meaningful because the policy engine is deterministic | Make the Nebius agent loop and AI risk summary visible. Say it in the form and video.                    |
| R2     | Payouts not available in the sandbox (your accounts were first set in Poland, now US)  | Use Invoicing or Orders. The demo story is the same: pay the invoice.                                    |
| R3     | Nebius model does not issue tool calls reliably                                        | Test early in Task 4. Switch to another model or provider by changing .env.                              |
| R4     | Nebius credits run out, or strangers use them on a hosted demo                         | Rate limit the demo. Offer self-run instructions. Keep a backup recording.                               |
| R5     | LLM behaves differently while recording                                                | Temperature 0, fixed sample invoices, record a second take.                                              |
| R6     | PayPal token expires mid-demo                                                          | Fetch tokens from client credentials in code and refresh automatically.                                  |
| R7     | Free hosting sleeps or goes down before 15 Dec                                         | Open the URL before recording and before submitting. Keep self-run instructions working.                 |
| R8     | Secrets pushed to GitHub                                                               | Use .env, commit only .env.example, regenerate sandbox keys if anything leaks.                           |
| R9     | Running out of time                                                                    | Cut the Should-have list from the bottom. Never cut the video, the clean-clone test or the real payment. |
| R10    | Flasho or other IP mixed into the repo                                                 | Keep this repo separate from anything you plan to assign to a company.                                   |

# 12. Final checklist (Wed 11 Nov)

## Repo

\[ \] Public, LICENSE visible in About.

\[ \] README works from a clean clone.

\[ \] No secrets in files or git history.

\[ \] Tag the final commit "submission-v1". Keep main stable until 15 Dec.

## Demo

\[ \] Live URL (if hosted) opens from another device, or self-run steps are tested.

\[ \] Seeded data present, attack path works.

\[ \] Test credentials or sandbox steps explained for judges.

## Video

\[ \] Under 3:00, YouTube Public, plays in a private window.

\[ \] Shows the project working. No third-party music or logos.

## Devpost

\[ \] Every bracket in the text replaced or deleted.

\[ \] Tools field lists Nebius model, PayPal APIs and Claude Code accurately.

\[ \] Only the sponsor prize you really qualify for is ticked.

\[ \] Status shows Submitted, not draft.
