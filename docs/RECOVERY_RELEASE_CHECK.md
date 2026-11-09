# Integrated recovery and multimodal candidate

November 8, 2026. Draft PR1, not merged/deployed. This extends the existing voice/photo increment; it does not establish hosted acceptance.

## Recovery changes

- Early capture first authenticates the provider order state; unapproved/canceled orders do not create a capture journal. APPROVED admission checks exact quote, merchant, USD amount, CAPTURE intent and absence of contradictory payment evidence.
- A validated completed receipt repairs IN_FLIGHT/UNCERTAIN journals atomically with payment verification/audit, preserves request IDs and does not recapture. Holds and customer/caterer approvals stay enforced. Unknown orders still require investigation.
- A late timeout cannot downgrade a journal already reconciled by a webhook. Payment-result booking status comes from committed reconciliation state. Payment success never books the event automatically.
- Login throttling counts failed credentials only. The existing ten-failures-per-60-seconds rule is preserved; blocked requests do not extend the window, success does not erase previous failures, expired entries are pruned and bucket count is bounded at 1024. This remains process-local, one-worker, direct-peer throttling. Behind a proxy, failed attempts may share a bucket; forwarded headers are not newly trusted. Distributed/durable per-user throttling is not implemented.
- Exact backend 403 / Please sign in restores final-review authentication fields, clears stale CSRF/capability state and retains in-page draft/idempotency key. English/Spanish guidance is provided. No automatic submission/retry; other 403 errors stay distinct. Reload/closed-tab draft persistence remains unimplemented.

## Verification performed

124 Python tests passed: 95 multimodal/base tests, 25 payment-recovery tests and 4 sign-in regression tests. Ten JSDOM interface tests passed: prior seven plus English/Spanish session recovery and distinct authorization-failure handling. No paid/provider calls, credentials or server mutations were involved. Mocked transport/DOM tests do not prove native microphone/camera, browser voice quality, provider availability or live concurrency.

Payment supplement was reused from CaterFlow_Backend_Recovery_2026-11-08.zip after matching all three baseline SHA256 hashes. The session-expiry supplement was reconciled manually with the newer multimodal form; its old page was not copied wholesale.

## Concrete controlled sandbox rollout proposal

Target only the existing aizoya-caterflow-sandbox / caterflow-sandbox.aizoya.com, separate from LBK production. Deploy the reviewed PR head, preserve database, private configuration, users and existing request-budget records. Back up the installed code and database before replacement. Install/check optional Pillow in the existing virtual environment and check proxy body/time limits without opening additional ports. Keep public form/media claims unchanged until acceptance.

Keep photo disabled at first. Verify imports, authenticated routes, process health, host/origin/CSRF enforcement, early capture behavior and retained session flow. Then, if approved, enable photo intake with the existing scoped Bedrock identity and make at most one synthetic food-image request; it consumes the existing durable allowance. No new subscription, key, IAM permissions, total AI allowance or dollar ceiling is introduced. A call cap is not a dollar cap. Do not overwrite newer installed code or clear journal/budget rows.

Test on actual iPhone Safari and desktop Chrome, including microphone denial/fallback, camera and gallery supported formats, Spanish/English read-aloud, photo removal/consent, corrections, stale-response behavior and inquiry review. Use user-operated existing sign-ins and synthetic details only. Record exact installed source hashes and provider response; rollback code/config on a material regression while preserving journals and data for reconciliation. Never blindly retry capture.

## Still open

Owner approval for the exact sandbox deployment; native-device acceptance; real Bedrock image behavior; actual signed PayPal webhook delivery; live cancellation/uncertain-write recovery acceptance; dedicated private judge access and bounded AI allowance through Dec21. Legacy inquiry validation is inconsistent with detailed intake and remains separate cleanup. Refund accounting, operator hold resolution, multi-business isolation, video/PDF intake and production payment support remain out of scope. Final Devpost submission is not performed.
