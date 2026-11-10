# Evaluation results

Run: 2026-11-10 11:58 · drafter: rule-based baseline (no API key set) · data: October 2026 snapshot + Nov 4 ranks

## 1. Critic traps

Overclaims caught: **10/10** · clean claims left alone: **5/5**

| Case | What it tests | Expected | Flagged | Pass |
|---|---|---|---|---|
| T01 | The real October overclaim | R2_RELATIONSHIP | R2_RELATIONSHIP | ✅ |
| T02 | Transmission asserted from a placement | R2_RELATIONSHIP | R2_RELATIONSHIP | ✅ |
| T03 | Traced is not verified | R3_COMMUNITY | R3_COMMUNITY | ✅ |
| T04 | Commercial evidence presented as culture | R5_COMMERCIAL_ONLY | R5_COMMERCIAL_ONLY | ✅ |
| T05 | No citation | R1_CITATION | R1_CITATION | ✅ |
| T06 | Invented record id | R1_CITATION | R1_CITATION | ✅ |
| T07 | Seasonal tag called a trend | R6_CALENDAR | R6_CALENDAR | ✅ |
| T08 | Certainty on one snapshot | R7_CERTAINTY | R7_CERTAINTY | ✅ |
| T09 | Established without two Tier 1-2 sources | R4_MOVEMENT | R4_MOVEMENT | ✅ |
| T10 | Adoption worded indirectly | R2_RELATIONSHIP | R2_RELATIONSHIP | ✅ |
| C01 | Clean: correct relationship language | none | none | ✅ |
| C02 | Clean: commercial claim labelled as commercial | none | none | ✅ |
| C03 | Clean: traced community described as traced | none | none | ✅ |
| C04 | Clean: movement that meets the rule called established | none | none | ✅ |
| C05 | Clean: negated adoption | none | none | ✅ |

## 2. Questions (end to end)

Passed: **18/18** · answers that needed a revision loop: 3

| Case | Question | Pass | Failed checks | Revisions | Claims |
|---|---|---|---|---|---|
| Q01 | What's moving in Beauty? | ✅ | — | 0 | 18 |
| Q02 | What connects Gaming and Fashion? | ✅ | — | 0 | 8 |
| Q03 | Has #bulin47 been adopted by football fans? | ✅ | — | 1 | 3 |
| Q04 | Is Painterly Realism a trend? | ✅ | — | 0 | 0 |
| Q05 | Tell me about the cozy gamers community | ✅ | — | 0 | 1 |
| Q06 | What's happening in Food? | ✅ | — | 0 | 21 |
| Q07 | What's moving in Sports? | ✅ | — | 1 | 25 |
| Q08 | Tell me about #garba | ✅ | — | 0 | 5 |
| Q09 | Which communities are verified? | ✅ | — | 0 | 14 |
| Q10 | Tell me about the quiet-life vloggers | ✅ | — | 0 | 1 |
| Q11 | What connects Music and Sports? | ✅ | — | 1 | 4 |
| Q12 | What's moving in Gaming? | ✅ | — | 0 | 25 |
| Q13 | Tell me about #costcofinds | ✅ | — | 0 | 1 |
| Q14 | Is #spookymonth a trend? | ✅ | — | 0 | 1 |
| Q15 | What's the latest on crypto mining rigs? | ✅ | — | 0 | 0 |
| Q16 | Tell me about the comfort & care theme | ✅ | — | 0 | 11 |
| Q17 | What links Beauty and Food? | ✅ | — | 0 | 2 |
| Q18 | Tell me about #dressmaker | ✅ | — | 0 | 5 |
