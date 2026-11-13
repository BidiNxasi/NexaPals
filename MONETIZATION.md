# Monetization thesis

This is a decision document, not code — there's no payment integration
anywhere in this codebase, deliberately, until the direction below (or a
different one) is actually chosen. Building billing code before that
decision is made would mean guessing at a data model that's expensive to
change later.

## The constraint that shapes everything else

Nexa Pals' core audience is children. That rules out — or at minimum makes
very risky — any model where a kid is the one making a purchase decision.
"Pay to unlock the next level" or "buy gems for XP" is a well-worn pattern
in kids' apps, and it's also the fastest way to burn the trust this product
is currently built on (free, no ads, no catch — that's a real, load-bearing
part of the pitch to parents and schools). So the recommendation below
deliberately keeps the child-facing product free and looks for revenue
somewhere the buyer is an adult making a considered decision.

## Recommendation: three revenue legs, none of which charge a child directly

**1. Keep the core kids' product free, indefinitely.** This isn't just an
ethical stance — it's the actual growth engine. Free-with-no-catch is what
lets a teacher recommend it to a whole class without a budget conversation,
and what lets a parent sign a 10-year-old up without a credit card. Every
other leg below depends on this one staying true.

**2. "Classroom Pro" — sell to schools, not to kids.** The teacher/classroom
feature just built is the natural seam for this. A free classroom already
gives a teacher a roster and progress view; a paid tier (billed to a school,
not a child) could add: more than one classroom per teacher, exportable
progress reports for parent-teacher conferences, curriculum alignment notes,
and priority support. This is the standard shape of the model Google
Classroom, Seesaw, and most classroom-facing edtech use — free for the
individual, paid for the institution that's making a considered, budgeted
purchase. It also fits South Africa's public/private school funding
patterns better than a consumer subscription would.

**3. A paid tier on the future all-ages/adult track.** Once (if) Nexa Pals
expands beyond kids, the adult/career-switcher segment is a much cleaner
buyer: a 25-year-old deciding whether to pay for a certificate or portfolio
review is an ordinary SaaS purchase decision, not a child-monetization
question. This should be built as a genuinely separate product surface (see
the earlier all-ages discussion) with its own pricing, not a paywall bolted
onto the kids' experience.

## In the meantime: grants and sponsorship, not subscriptions

Given the University of the Free State affiliation already in the codebase
and footer, the realistic near-term funding path is grants, university
budget, and CSR sponsorship from South African tech/telecom companies —
not consumer revenue. This is worth pursuing in parallel with (2) and (3),
not instead of them; it's bridge funding while the classroom/adult-tier
legs mature, not a permanent substitute for them. A telecom CSR
partnership is also where the earlier "zero-rated data" idea (from the
market-positioning discussion) would actually get funded from.

## What NOT to do

- Don't put any purchase flow in front of a student account. Even
  "optional cosmetic" purchases (extra avatars, etc.) aimed at kids invite
  the same trust and regulatory risk as pay-to-win mechanics, for the same
  practical reason: the person clicking "buy" and the person whose card it
  is are different people, and that's exactly the pattern child-protection
  regulation exists to catch.
- Don't build the payment integration speculatively. Stripe (or PayFast /
  Yoco / PayGate for South African rand billing) is a day or two of work
  once there's an actual paying customer type to build it for — building it
  now, before choosing between "sell to schools" and "sell to adults,"
  risks building the wrong shape twice.

## If/when this gets greenlit

The smallest correct first step is a `plan` field (free/pro) on `Classroom`
— not on `User` — since the leg that's closest to ready (the classroom
feature just built) is priced per-school, not per-child. The adult-track
paid tier would get its own `plan` field on whatever "all-ages" user
surface gets built, kept deliberately separate from the kids' `User` model
rather than overloading it with billing concerns that only apply to a
different audience.
