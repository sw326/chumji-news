# Web product reconciliation

## Baseline

The root `chumji-news` application is the surviving product and visual system.
The retired `chumji-ops/apps/web` preview is comparison evidence only. A
feature is not imported merely because it existed in that fork.

## Audit result

The root application has the stronger bookmark flow: a complete per-user
article index, cursor pagination, search, category filtering, sorting, delete
undo, OTP resend cooldown, and news-list restoration. The ops fork used an
unbounded full-row query and lacked the later recovery behavior. Its bookmark
implementation is therefore not ported.

The ops navigation's larger touch targets were useful, but its six primary
tabs mixed unfinished market, alerts, and operations prototypes into the news
product. The root navigation keeps only News, Prices, and Scraps while adopting
a larger minimum touch area.

## Reconciliation changes

- serialize bookmark writes per article to prevent duplicate rapid clicks;
- expose pending state to bookmark and delete buttons;
- show a recoverable error when a detail-card bookmark request fails;
- retain the root app's search, filter, sort, undo, OTP, and pagination flows;
- add deterministic source-contract tests to prevent retired routes or weaker
  bookmark behavior from returning accidentally.

The market data jobs remain under `operations/`. A future market UI must be
designed as a new root-app feature and pass an explicit product-quality review;
it must not restore the retired web fork wholesale.
