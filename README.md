> Hackathon development build. Synthetic test details and PayPal sandbox only.

# AIZOYA CaterFlow

Owner: Franklyn Rosario, MBA-ITM. AIZOYA OS 2.6 governs; OS 2.7 remains candidate.
Working title; trademark clearance incomplete. Synthetic customer details only.

## Verified state — reconciled November 7, 2026 (Pacific)

- Isolated HTTPS sandbox deployed at https://caterflow-sandbox.aizoya.com. This is separate from the public La Bandera Kitchen website.
- Detailed bilingual inquiry persisted through the customer browser; caterer quote revision and customer approval verified. Twelve optional detail fields are preserved.
- Actual PayPal sandbox order/capture succeeded November 4. App refresh retained payment verification; provider API log showed capture 201 and authenticated order reads 200. 
- Caterer booking confirmation was verified November 6 and survived browser refresh. Actual signature-verified webhook delivery remains unverified. Registration and OAuth are verified; registration alone is not delivery evidence.
- Hosted Amazon Bedrock Claude Sonnet 4.6 drafting is enabled. Real English and Spanish calls passed through the installed adapter and signed-in browser. Suggestions stayed separate from form fields until explicit customer acceptance, remained editable, and did not create events or alter quotes. Allergy notes require caterer review and do not promise safety.
- All 86 local tests passed after the payment-hold fix. Four focused regression tests also passed against installed server modules using mocked providers and temporary databases. The server now rejects payment-operation admission and completed-operation replay while a quote is on hold. These tests do not prove real webhook delivery or all concurrency cases.

**Development prototype.** Source is released under MIT. Public video, judge-access instructions and final submission remain outstanding. The current hosted AI attempt limit is deliberately small and operator-controlled; it is a request cap, not an account-wide dollar cap. Actual signed webhook delivery and outage fallback remain unverified.

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

