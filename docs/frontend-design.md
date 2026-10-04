# TripWise Frontend Direction

## Tokens

- `atlas` `#14213D`: primary ink and navigation.
- `lagoon` `#1E6F6D`: planning/weather status and active route.
- `sun` `#F4C95D`: selective highlight, never a background wash.
- `coral` `#F07167`: primary action and overspend state.
- `paper` `#F8F7F2`: quiet application ground.
- `mist` `#DDE8E7`: secondary surfaces and rules.

Headings use Fraunces, chosen for the stamped character of old guidebooks; interface copy and tabular numbers use Manrope. Both have local system fallbacks and are loaded from Google Fonts only when the browser can reach it.

## Layout

Desktop pages use an offset map grid: a fixed route ribbon at left, a wide content track, and occasional narrow annotation columns. Content remains left aligned. Mobile turns the ribbon into a horizontally scrollable sequence directly below the trip identity.

```text
┌──────── route ribbon ────────┬──────── current trip view ───────────────────┐
│  TripWise                    │  destination / date            action         │
│  Overview ●                  │                                              │
│  Plan     ○                  │  one dominant module       annotation         │
│  Route    ○                  │  supporting ledger rows                         │
│  Expenses ○                  │                                              │
└──────────────────────────────┴──────────────────────────────────────────────┘
```

```text
mobile
┌──────────────────────────────┐
│ TripWise          menu       │
│ Sri Lanka / 3 days           │
│ overview—plan—route—expenses │
│                              │
│ dominant module              │
│ ledger rows                  │
└──────────────────────────────┘
```

## Principles

- Route lines, plotted dots, coordinates, and ledger rules encode progress or financial relationships; they are not decorative filler.
- One bold motif—the route ribbon—carries identity. Cards, shadows, and motion remain restrained.
- Currency uses tabular figures, direct labels, and exact totals.
- Empty states always point to the next action.
- Focus, contrast, reduced motion, and touch targets are part of the visual system.

## Uniqueness Review

The first pass leaned toward a warm travel-journal palette that would have reproduced a common generated cream/terracotta aesthetic. It was replaced with coastal mineral blue, lagoon green, signal coral, and a deliberately small sun-yellow accent. The map-grid/ribbon structure comes from the trip workflow itself and would not transfer unchanged to a generic admin product.
