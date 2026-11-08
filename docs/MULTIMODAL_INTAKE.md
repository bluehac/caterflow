# Voice, photo and read-aloud intake — review candidate

Implemented November 8, 2026. Not deployed or live-provider verified.

Customer outcome: turn spoken, typed or photographed food inspiration into an editable catering request; hear the result and correct it before sending. Preserve separate caterer quote, customer quote approval, payment verification and booking confirmation.

## Implemented

- Browser speech recognition on explicit Speak, editable transcript, selected English/Spanish, stop/abort on navigation and language change. Browser service may receive audio; no app audio recording or storage. Unsupported browsers retain typed input and keyboard-dictation guidance. This is not ElevenLabs or continuous realtime voice AI.
- Device/browser read-aloud of explanations, AI suggestions, one deterministic follow-up question, final inquiry review, and exact displayed quote/payment state. Voice availability and pronunciation vary; no extra model-generated financial explanation. Stop audio control on intake. Text remains available.
- Explicit camera capture hint and photo-picker inputs. JPEG/PNG/WebP browser preprocessing to JPEG up to 1280px; unsupported HEIC/video is rejected with a smaller-supported-photo prompt. Camera capture behavior depends on browser/device.
- Photo preview, remove and explicit transmission consent. Authenticated customer + CSRF required before expanded body read. Feature flag CATERFLOW_PHOTO_ENABLED defaults off. Existing AI enabled/configuration and durable call budget are also required.
- Server accepts only bounded base64, decodes JPEG/PNG, rejects malformed/animated/excessive dimensions, strips metadata by re-encoding. Max decoded input 400,000 bytes; max HTTP AI body 550,000 bytes; other routes retain 8,192-byte cap. Require a buffering reverse proxy with bounded body/time limits.
- One model call with text/image content. Photo is untrusted inspiration, never an instruction or evidence of recipe, allergens, safety, portions, availability or price. Photo-only output cannot establish event/dietary facts. Photo-inspired menu notes get an uncertainty label. Customer can reject/correct suggestions; no automatic order/event/payment/booking writes.
- Stale model responses are discarded after text edits, photo changes or language/navigation changes. Explicit acceptance fills the existing editable form. Large labeled service-choice buttons retain the normal validated select field.

## Local verification

95 Python tests passed (original 86 plus 9 new photo/HTTP cases); 7 executable JSDOM tests passed. Provider, recognition and speech synthesis are mocked; JSDOM is not a browser or iPhone test. New tests cover consent, metadata removal, malformed images, size/dimensions, disabled flag/role, existing shared attempt budget, photo-only fact suppression, authentication before expanded-body read, route size isolation, transcript editing, review gate, stale results, camera attribute, photo consent, visual choices and language selection.

Run Python tests after installing optional photo support: `pip install -r requirements-vision.txt`, then `python3 -m unittest discover -s tests -v`. Dev DOM tests: `npm ci && npm test`. Node is not a runtime requirement. Pillow 13.0.0 and Node 24.22.1 were used locally.

## Release and acceptance gates

1. Resolve existing payment recovery, login throttling and judge-access blockers separately; this increment does not fix them.
2. Approve sandbox deployment of this exact candidate; install/check Pillow, keep current secrets and budget intact, configure bounded reverse-proxy upload size and timeouts. No new provider account, subscription or permission is implied.
3. Verify selected Bedrock model supports image content through the installed SDK. Run a bounded synthetic food-image call under existing authorization; failure consumes its attempt and must not trigger automatic retries.
4. Test actual iPhone Safari and desktop Chrome: microphone permission accepted/denied, unsupported voice fallback, camera/gallery JPEG and HEIC behavior, Spanish/English voices, interrupted speech, removal/revocation, photo failure, correction and full form submission. Test with actual users who prefer audio; no accessibility certification is claimed.
5. Review deployed logs/provider invocation logging and retention. The app does not persist photo/audio, but browser/provider retention policies are outside that statement. Transcripts/accepted text may become stored inquiry details; synthetic data only in this sandbox.
6. Recheck all approval/payment/booking invariants, genuine signed webhook delivery, dedicated judge accounts and adequate bounded AI availability through Dec21. Update demo/story only after hosted verification.

## Deferred

Video analysis, PDFs, SMS/WhatsApp integrations, automatic language detection, paid STT/TTS services, ElevenLabs production integration, realtime voice streaming, user-configurable multi-business menus and merchant integrations. These remain roadmap work, not implemented features.

## Evidence and product hypothesis

TARGET: customers who prefer speaking or pictures can prepare a correct, reviewed inquiry with less reading/correction than the prior form. No measured time reduction, conversion gain, recognition accuracy or 10x advantage exists yet. Compare the same synthetic scenarios on actual devices, including denied permissions and correction, and record task completion, field accuracy, elapsed time, corrections and provider cost. Novelty alone is not evidence of usefulness.
