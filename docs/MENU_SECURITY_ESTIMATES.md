# Menu, abuse protection and instant value candidate

November 8, 2026. Extends draft PR1; these additions are not deployed until their candidate is approved. Existing sandbox deployment remains 14b9bef5.

## Customer experience

AIZOYA navy/blue/gold on the pilot intake, with La Bandera Kitchen identified as the pilot menu. A bilingual menu link opens https://labanderakitchen.com/menu in a separate tab and preserves the current draft. Reviewed public dish names are supplied to the model as reference context, not stock or recipe truth. A customer may request an unlisted dish; this remains a custom request. No new real model request was made to validate the prompt change.

Current instant value is an editable structured AI draft and focused follow-up, not a priced order. Sending a reviewed inquiry persists it in the existing database for the caterer workspace. Automatic email/SMS notifications are not implemented. Do not promise an immediate confirmed quote, reserved date or notification delivery.

## Layered abuse controls

- Existing login/session, role, exact Origin/Host and CSRF checks remain.
- Durable authenticated per-account limits: AI 3 attempts/60 seconds and 10/day; intake 5 attempts/10 minutes and 20/day. Counts include failures/retries and are not an idempotent write budget. Existing lifetime global AI cap remains unchanged. SQLite transactions serialize admission across processes; expired abuse rows are pruned and total rows capped at 10,000. This does not prevent distributed-account attacks.
- Legacy `/api/inquiry` returns 410 after authentication/CSRF instead of bypassing reviewed intake minimums/consent.
- Turnstile integration is optional pending exact-host widget configuration. Server validates each single-use token using Siteverify and checks success, hostname and action; enabled-but-misconfigured or provider outages fail closed. Login, AI drafting and intake are guarded. PayPal webhook/reconciliation routes are not sent through human challenges.
- Only the opaque token and secret go to Siteverify; no contact, dietary, image or prompt fields are included. Cloudflare may collect its own challenge signals. CSP permits only Cloudflare's challenge origin for required scripts/frames/connections.
- Client requests a fresh token immediately before each guarded request. Cancellation preserves the in-page draft. No automated CAPTCHA completion.
- Turnstile is NOT active merely because code exists. Needs the sandbox-only public sitekey/private secret, service configuration and live acceptance. Do not use published test keys for hosted protection. No DNS change is required.
- Before public intake, add verified proxy per-IP/login/body/concurrency limits (do not trust arbitrary forwarded IPs), monitor rejects without sensitive data, and test legitimate iPhone accessibility. Application limits are not DDoS protection.

## Estimate engine, intentionally disconnected from live pricing

`estimates.py` is a deterministic calculation foundation, not a public API or checkout replacement. Its operator-owned policy supplies menu prices, minimums, service rates/fixed charges, explicit fee tax treatment, jurisdiction rate/source, version and expiry. Customer requests cannot set prices/rates/totals. Unknown zones/add-ons/services, unapproved or expired policy fail closed. Decimal half-up cent rounding, food/add-on lines, service fee, taxable base, tax, estimated total and per-guest figure are returned with policy provenance and ESTIMATE_ONLY status. It never confirms a booking or changes an approved quote.

All calculator fixture prices and tax rates are SYNTHETIC, not approved LBK rates. Current public LBK form says 25+ plates and deliberately locks prices until food, labor, packaging, service and tax are verified. Existing CaterFlow sandbox minimum is 10; do not silently promote it as LBK policy. Before enabling estimates, reconcile the approved catalog, exact address/jurisdiction and sourcing rules, service/delivery/staffing charges, taxable bases, menu minimums, add-ons, margin floors and quote expiry. Use address-scoped tax lookup or verified maintained policies, not AI or a guessed city rate. California mandatory service-charge tax treatment requires care; see CDTFA Publication 115. Owner approval of an exact policy precedes deployment/public pricing.

## Differentiation research

These are vendor-described capabilities, not hands-on competitor tests or proof a feature is absent.

| Alternative | Verified vendor claims | CaterFlow opportunity to validate |
| --- | --- | --- |
| Tripleseat | Context-aware Intelligence/Cohost, lead qualification and availability; Direct Book, configurable menus/packages, taxes/fees and payments | An easier, lower-setup bilingual experience for small independent caterers, with optional speech/photo and visibly reviewed facts |
| Caterease | AI assistant/Horizon Hub, event portals, menu operations, e-signing and payments | A phone-first customer journey connecting menu inspiration to a transparent estimate and operator handoff |
| Total Party Planner | Proposals/e-signatures, online ordering and vision board | Explainable menu alternatives, budget changes and payment recovery rather than an additional general event dashboard |

Sources checked November 8, 2026:
- https://tripleseat.com/articles/why-most-ai-gets-events-wrong/
- https://tripleseat.com/features/direct-book/
- https://support.tripleseat.com/hc/en-us/articles/42203100060951-How-Do-I-Create-a-Menu-in-Settings
- https://caterease.com/features/
- https://totalpartyplanner.com/features/
- https://totalpartyplanner.com/catering-software-pricing/
- https://labanderakitchen.com/menu
- https://labanderakitchen.com/catering/quote
- https://developers.cloudflare.com/turnstile/get-started/server-side-validation/
- https://developers.cloudflare.com/turnstile/plans/
- https://cdtfa.ca.gov/formspubs/pub115/

Prioritized proposed differentiators: instant reviewed event brief; operator-grounded menu options; good/better/best budget comparisons with exact fee/tax breakdown; explain what changes when guest count/menu/service changes; one focused follow-up at a time; bilingual read-aloud and editable transcripts; allergy uncertainty and chef handoff; inquiry receipt/status and private staff notification after a verified connection. None is a verified exclusive market feature. Measure completion, corrections, quote turnaround, gross margin and support effort before claiming advantage.

Technology decision: Turnstile plus server/proxy limits first; one analytics system (PostHog default, Mixpanel alternative) and scrubbed errors next; Postgres/tenant isolation/configuration before multi-business GTM. MongoDB, Crusoe GPU hosting, Meta inference and a Replit migration are deferred until an actual bottleneck or approved benchmark justifies them. Extra vendor count is not differentiation.

## Validation recorded

137 Python tests and 10 JSDOM interface tests passed locally after this increment. Tests cover cross-instance account limits, expiry, daily cap, token failures and hostname/action checks, fail-closed configuration/outage, pre-provider route rejection, retired endpoint, exact estimate arithmetic/rounding, unapproved/expired policies and price injection. No real AI, Turnstile or PayPal request was made by these tests. Browser challenge interaction and hosted acceptance remain pending.
