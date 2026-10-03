# product.md — PolicyDesk in one page

Short summary of the product. The full rules are in `docs/PolicyDesk_SRS.md` (IDs in brackets).
If this page and the SRS disagree, the SRS wins — tell Mouiad about the difference.

## What it is
A web app to sell **car (CAR)** and **home (HOME)** insurance in Malaysia. Fictional company, learning project.
- Currency **MYR/USD** ("RM 1,234.50"), time zone **Asia/Kuala_Lumpur** (store UTC), dates `YYYY-MM-DD`.
- Payments: **Stripe test mode only** (`sk_test_...`), no real money. Emails: **MailHog** (fake inbox).
- One app (**modular monolith**) with clear services inside. No microservices, no message broker in v1.

## Roles [ROLE]
| Role | Can do |
|---|---|
| Guest | See products, get a quick price |
| Customer | Buy for themself; is the policyholder |
| Agent | Sell for customers; earns commission (CAR 10%, HOME 15% of net premium) |
| Underwriter | Approve or decline **REFERRED** quotes |
| Admin | Users, products, rates, settings, audit log, reports, outbox monitor |

## Products and plans [PRD]
- **CAR** plans: `THIRD_PARTY`, `THIRD_PARTY_FIRE_THEFT`, `COMPREHENSIVE`. Add-ons: `WINDSCREEN`, `FLOOD` (COMPREHENSIVE only), `ROADSIDE_HELP`.
- **HOME** plans: `BUILDING`, `CONTENTS`, `BUILDING_AND_CONTENTS`. Add-ons: `FLOOD`, `ACCIDENTAL_DAMAGE`.
- Term 12 months. Start date: today up to 60 days ahead. End date = start + 12 months − 1 day.

## Price steps — the Rating engine [PRD-15..19]
1. Base price from the rate table (product + plan + band).
2. × factors — CAR: car age, driver age, NCD (1 − NCD%). HOME: building type, risk zone.
3. + add-on prices → **net premium**.
4. + service tax **8%** + stamp duty **RM 10.00** → **total payable**. Round half up to 2 decimals after each step.
- Golden examples: CAR = **RM 2,273.41**, HOME = **RM 1,033.19** (SRS section 04). Tests must match exactly.
- The quote saves a **price snapshot** (+ `rating_version`); later rate changes never change old quotes.
- **Referral rules** → quote becomes `REFERRED`: car value > RM 300,000; driver under 21; car older than 15
  years with COMPREHENSIVE; home total sum insured > RM 2,000,000; risk zone HIGH with FLOOD.

## Main objects and statuses
| Object | Statuses | Number |
|---|---|---|
| Quote | `DRAFT → PRICED → (REFERRED → APPROVED/DECLINED) → ACCEPTED`; open → `EXPIRED` after 30 days | `Q-2026-000123` |
| Policy | `PENDING_PAYMENT → ACTIVE → CANCELLED / EXPIRED`; has `version` (optimistic lock) | `PD-CAR-2026-000123` |
| Invoice | `OPEN → PAID / VOID` | `INV-2026-000123` |
| Payment | `PENDING → SUCCEEDED / FAILED`; max 5 tries per invoice | — |
| Refund | `PENDING → PAID` | — |
| Endorsement | `REQUESTED → APPLIED / REJECTED` (change address, car, add/remove add-on) | — |
| Commission | `EARNED → PAID`; cancellation → `CLAWED_BACK` | — |

- Unpaid `PENDING_PAYMENT` policies are cancelled after **3 days** (reason `NOT_PAID`).
- **Cancel:** first 15 days (cooling-off) = full refund; after = pro-rata − **RM 50.00** fee. Examples: RM 1,296.00 / RM 808.81.
- **Renewal:** renewal quote 30 days before end; reminders at 30 and 7 days; new policy starts the day after the old end date.

## The customer journey (wizard `/quotes/new`)
1 Product & plan → 2 Car or Home details → 3 Add-ons → 4 Price (Rating engine; maybe REFERRED) →
5 Policyholder → 6 Review → 7 Pay (Stripe Checkout) → policy **ACTIVE** → policy page
(tabs: Overview, Policyholder, Cover, Payments, Documents, History) → change / cancel / renew.

## Services inside the app [EVT, section 21]
| Service | Owns | Outside world |
|---|---|---|
| Rating engine | raters, rate rows | none (pure calculation, no DB writes) |
| Quotes / Underwriting / Policies | quote, policy, endorsement | none |
| Payments | invoice, payment, refund, webhook_event | **Stripe** via `PaymentGateway` (Stripe / Fake) |
| Email (notifications) | email_log, templates | **SMTP → MailHog** via `EmailSender` (SMTP / Fake) |
| Documents | document (PDF) | file storage via `DocumentStore` |
| Commissions | commission | none |

## Domain events (outbox → worker → handlers)
`QuotePriced`, `QuoteReferred`, `QuoteApproved`, `QuoteDeclined`, `PolicyCreated`, `PaymentSucceeded`,
`PolicyIssued`, `PaymentFailed`, `EndorsementApplied`, `PolicyCancelled`, `RefundRequested`, `RefundPaid`,
`RenewalQuoteCreated`, `PolicyRenewed`, `PolicyExpired`.
- Saved in the same transaction as the change. Each handler runs once (`processed_event`). Delivery is at least once.
- `PolicyCreated` = policy made, waiting for payment. `PolicyIssued` = payment succeeded, policy ACTIVE.

## Stripe (test mode) [PAY]
- Checkout Session (`currency=myr`, amount in sen). Webhook `POST /api/v1/webhooks/stripe`, checked with
  `Stripe-Signature` on the raw body. Every Stripe event id is saved once (`webhook_event`).
- Test cards: `4242 4242 4242 4242` succeeds · `4000 0000 0000 0002` declined · `4000 0025 0000 3155` 3D Secure.
- Dev: `stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe`.

## Data model (SRS section 18) — 23 tables
`user_account`, `customer`, `product`, `plan`, `addon`, `rate`, `setting`, `quote`, `quote_addon`, `policy`,
`policy_addon`, `endorsement`, `invoice`, `payment`, `refund`, `commission`, `document`, `audit_log`,
`outbox_message`, `processed_event`, `webhook_event`, `email_log`, `number_counter`.
(`user` is a reserved word in PostgreSQL, so the table is `user_account`.)

## Build plan (SRS section 20)
| | Milestone | SRS sections |
|---|---|---|
| M0 | Project foundation (ideas from fastapi-orderly, written from scratch) | FND (00), PAT (22) |
| M1 | Data model and migrations | DATA |
| M2 | Login and roles | ROLE, NFR |
| M3 | Rating engine and products | PRD |
| M4 | Quote wizard | QUO, UW |
| M5 | Policyholder and review | HOL, QUO |
| M6 | Payments with Stripe (test mode) | PAY, POL |
| M7 | Policy pages and documents | POL, ISS |
| M8 | Event bus, handlers and Email service | EVT, NOT |
| M9 | Changes, cancel and renew | END, CAN, REN |
| M10 | Agent, admin, reports and hardening | AGT, ADM, REP, NFR |

## Not in version 1
Real payments, real emails to customers, claims, other languages, microservices or Kafka, mobile apps.
