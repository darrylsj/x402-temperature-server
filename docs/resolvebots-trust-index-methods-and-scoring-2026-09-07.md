# ResolveBots Trust Index Methods And Scoring Note

Date: 2026-09-07

This note supports the reader-facing discussion of the ResolveBots x402 Trust Index in *The x402 Handbook*.

ResolveBots is the author's project. It is not an independent standards body, regulator, marketplace operator, or certification authority. The score records what ResolveBots observed from a buyer's point of view during bounded tests, using the buyer policy in force for that run.

## What The Score Is Trying To Capture

ResolveBots separates several claims that early agent-commerce discussions often collapse:

- listed: a discovery source has a record for the resource
- reachable: the resource URL responds
- payable: the unpaid route returns a coherent payment challenge
- paid-tested: a buyer paid or attempted payment and preserved the observed outcome
- fulfilled: the seller returned the promised output after the payment condition
- useful: the output was parseable and valuable for the stated task
- safe: the resource appears compatible with the buyer's policy and risk constraints

The scoring dimensions in the book are practical rather than legal or regulatory: payability, fulfillment, schema clarity, client compatibility, value, failure honesty, seller readiness, and evidence. The score should be read as a field-test summary, not as a guarantee that another buyer will get the same result.

## Operator And Funding Context

ResolveBots, Darrylbots, and JAMES are author-operated projects. Tests described in the book were run from the author's environment and, where paid, used the author's authorized agent-wallet/payment tooling under small caps. That means the record is useful operational evidence, but it is not independent third-party market research.

Where the author also operates, funds, or benefits from a tested endpoint, that relationship should be disclosed in the surrounding evidence note. Tests of public third-party endpoints are still limited by the buyer's configuration, wallet funding, network choice, and run policy.

## Records And Limits

The book links only verified records or dated source notes. Some historical counters from early ResolveBots runs were narrowed or removed in Draft 016/017 because this pass did not recover the denominator-level archive needed to print exact totals as market evidence. That correction does not mean the project failed; it means the printed claim now matches the evidence available for this edition.

Raw request logs, payment payloads, private outputs, credentials, and reusable authorization material should stay out of the public book. Public notes should preserve enough context to explain method, date, scope, policy, and outcome without exposing material that would let someone replay a payment or leak private data.
