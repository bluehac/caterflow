> Hackathon development build. Synthetic test details and PayPal sandbox only.

# AIZOYA CaterFlow

Owner: Franklyn Rosario, MBA-ITM. AIZOYA OS 2.6 governs; OS 2.7 remains candidate.
Working title; trademark clearance incomplete. Synthetic customer details only.

## From catering inquiry to confirmed booking

CaterFlow connects bilingual, customer-reviewed AI intake to a caterer-prepared quote, customer approval, PayPal sandbox payment verification and a separate caterer booking decision.

- [Public showcase and judge guide](https://caterflow.aizoya.com) · [53-second illustrated walkthrough](https://www.youtube.com/watch?v=w0jjRP7LZ84)
- [Hosted bilingual sandbox](https://caterflow-sandbox.aizoya.com/catering) uses synthetic data only. Full testing requires separate provisioned customer and caterer accounts. Private judge access is pending.
- [Release candidate](https://github.com/bluehac/caterflow/pull/1) is a draft PR; do not assume the default branch matches the hosted runtime.

## Verified evidence — November 8, 2026

137 Python tests and 10 simulated DOM tests passed locally; 49 overlapping tests passed against installed modules with temporary data and mocked providers. Prior signed-in English and Spanish Bedrock drafting and actual PayPal sandbox capture/readback were verified. A subsequent synthetic image request produced a validated review-required draft; image recognition quality was not established. Actual signed webhook delivery and native iPhone media acceptance remain unverified.

AI suggestions require explicit customer review. AI does not set prices, move money, confirm bookings, or establish ingredient or allergy safety. Refund/reversal reconciliation, operator hold resolution, and business isolation are commercial launch gates.

## Pilot and revenue hypotheses

Start with owner-operated caterers managing custom quotes across texts, email and spreadsheets. Recruit five design partners and measure quote turnaround, onboarding, support and willingness to pay. Proposed $99 Starter and $199 Team pricing at a 50/50 mix yields $149 per business/month; 100 paying businesses imply $178,800 modeled ARR. No paid subscriptions or retention are verified.

## Run locally

Requires Python 3.11+; Node.js is needed for workspace JavaScript tests. Core runtime uses the Python standard library. Optional Bedrock runtime requires boto3 (`pip install -r requirements-ai.txt`); use an isolated virtual environment and an authorized scoped runtime identity. No credentials belong in source, chat or command arguments.

From this directory:

```sh
python3 -m unittest discover -s tests -v
python3 manage.py customer demo-customer
python3 manage.py caterer demo-caterer
python3 app.py
```

Account provisioning prompts privately for a password of at least 12 characters. Open `http://127.0.0.1:8080/catering` for the customer form or `http://127.0.0.1:8080/` for the workspace. Submit synthetic details, then switch to the caterer to approve a quote and back to the customer to approve it. No payment controls are enabled by default.

The database persists locally; sessions expire after one hour. The server binds only to loopback and enforces its exact Host and Origin. Local HTTP cookies omit Secure solely for loopback. Do not expose the development server through a tunnel or public host.

## Private local sandbox configuration

The operator utility `sandbox_config.py` supports hidden terminal entry into a new owner-only file outside this source directory. Prepare a private directory first. For example, on your own development computer:

```sh
mkdir -p "$HOME/.config/aizoya/caterflow"
chmod 700 "$HOME/.config/aizoya/caterflow"
python3 sandbox_config.py configure --file "$HOME/.config/aizoya/caterflow/sandbox.json"
```

Enter only values from the CaterFlow sandbox app: Client ID, Secret, seller merchant ID, and registered webhook ID. Never use live credentials. Webhook registration requires an approved HTTPS runtime endpoint. The isolated hosted sandbox has one registered; a separate local operator must use their own authorized endpoint. Do not invent a webhook ID to complete setup.

Once configured, this optional command requests a sandbox OAuth token and reports only whether client authentication succeeded:

```sh
python3 sandbox_config.py check --file "$HOME/.config/aizoya/caterflow/sandbox.json"
```

It does not create or capture a payment. OAuth success does not prove seller ownership, webhook delivery, or the end-to-end workflow. The check returns no token. Invalid permissions, symlinks, unknown fields, conflicting environment values and overwriting an existing file are rejected.

The app reads the file only if `CATERFLOW_SECRET_FILE` explicitly points to it. This does not enable checkout. Payment routes additionally require `CATERFLOW_PAYPAL_ENABLED=true`; leave it unset until the controlled sandbox test is ready. The API base is fixed to `https://api-m.sandbox.paypal.com`.

## AI configuration boundary

`CATERFLOW_AI_ENABLED=true`, `CATERFLOW_BEDROCK_MODEL_ID`, `CATERFLOW_AWS_REGION`, and `CATERFLOW_AI_MAX_CALLS` are required. Leave AI disabled until a scoped runtime identity and workload authorization are in place. The durable 1–100 call cap includes failed attempts, but is not an account-wide dollar cap. SDK calls have one total attempt, 5-second connection timeout and 20-second read timeout. Customer language is validated as en/es and passed to the prompt; language correctness is not deterministically guaranteed.

## Payment and release limitations

- Prices are synthetic guests × per-guest price in USD. Tax, delivery, deposits, service fees and refunds are not implemented.
- Single-business authorization only. This is not a verified multi-merchant SaaS platform.
- Approved quote financial fields are frozen by database triggers. Audit rows are append-only for normal SQL access, but a database administrator can replace the database; this is not independently tamper-evident storage.
- Persisted provider request IDs and operation states block automatic retries after uncertain create/capture outcomes. Complete operator recovery tooling remains open, especially when an order ID is unknown.
- Pending/denied/refunded/reversed verified events place a conservative review hold and clear booking confirmation. A server-side guard rejects create/capture admission and completed-operation replay while held; an already-admitted concurrent request is not cancelled by this guard. Delayed completion cannot clear that hold automatically. Refund accounting and an operator resolution workflow remain open.
- Inquiry retries deduplicate within the page request key; cross-reload draft recovery remains incomplete.
- Browser visual/accessibility QA, concurrent operation tests, actual cancellation/decline/pending behavior and live webhook verification remain open.
- Proposed Next.js/Supabase/Vercel stack is not provisioned. Current code is the preserved local Python reference application.
- Source is licensed under MIT; see LICENSE. Deployment, new terms, spending, external communications and final submission remain subject to their separate authorization boundaries.

