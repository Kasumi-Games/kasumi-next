# Season Gacha and Cosmetics Design

## Purpose

This document defines the first implementation scope for seasonal gacha,
cosmetic rewards, and player identity presentation.

The design goal is to make seasonal gacha desirable without letting gacha
replace achievement-based status. Players who pull ★★★★★★ characters should look
visibly different in generated images, while season ranking rewards should
remain clear proof of season participation and placement.

## Design Principles

- Titles are earned status, not gacha rewards.
- A season is the event. Separate event systems can be added later only if they
  are worth the maintenance cost.
- Achievements are deferred until after this update.
- Gacha rewards should be visually visible in common bot output, not hidden in a
  rarely viewed inventory page.
- Season rank rewards and gacha rewards may share the same theme item to keep
  asset workload manageable, but the theme is still an item, not a hard-linked
  season field.
- Duplicate gacha rewards must not convert into ranking Pt.

## Reward Types

| Reward type | Source in this update | Notes |
| --- | --- | --- |
| Titles | Season/event rank and participation | Achievement titles are deferred. |
| Avatar frames | ★★★★★★ character gacha and season rank | No low-rarity frame pool for this update. |
| Themes | ★★★★★★ character gacha and season rank | Same theme item can be awarded by both paths. |
| Character standing art / 立绘 | ★★★★★★ character gacha | This replaces the idea of character cards. |
| Stickers, icons, badges | Out of scope | Leave these for later. |

## Rarity Names

Use star rarity names in player-facing text instead of letter names like N, R,
SR, and UR.

Recommended mapping:

| Old name | Star name | Meaning |
| --- | --- | --- |
| N | ★★★ | baseline rarity, if low-rarity items are added later |
| R | ★★★★ | mid rarity, if low-rarity items are added later |
| SR | ★★★★★ | high rarity, if low-rarity items are added later |
| UR | ★★★★★★ | top rarity and featured seasonal character rarity |

The first implementation only needs ★★★★★★ character rewards. Lower star
rarities can remain unsupported until the gacha pool needs filler items.

## Season as Event

For this project, an event is a season.

Each season should have:

- season id and season number
- season name
- start time and end time
- featured ★★★★★★ characters
- season rank reward definitions

The season should not have a hard-coded `season_theme_id`. Themes are normal
items. Gacha rewards and rank reward definitions can reference theme item ids,
but the season model itself does not own a theme.

This keeps the operation model simple for a solo maintainer: starting a new
season also starts the event, the gacha banner, the ranking period, and the
cosmetic reward period.

## Seasonal Gacha

Each season has a limited gacha banner centered on featured ★★★★★★ characters.

Recommended first scope:

- 2 featured ★★★★★★ characters per season
- each ★★★★★★ character has one standing art / 立绘
- each season has one shared character avatar frame
- the first owned featured ★★★★★★ character grants the shared character avatar
  frame
- the first owned featured ★★★★★★ character grants the configured theme item, if
  it is part of that banner's reward definition
- pulling both ★★★★★★ characters grants only the second character's own rewards
- no additional duo reward in the first version

When a player pulls a ★★★★★★ character, they receive:

1. The character standing art / 立绘.
2. The shared seasonal character avatar frame, only if this is the first
   featured ★★★★★★ character they own from this season.
3. The configured theme item, only if they do not already own it and this is the
   first featured ★★★★★★ character they own from this season.

If the player already owns the configured theme item from another source, they keep one
copy only. The second ★★★★★★ character grants only that character's standing art
unless later designs add duo rewards.

## Duplicate Handling

Duplicated non-stackable gacha rewards should award a new non-ranking currency.

The duplicate currency is called `盆栽`.

Suggested internal id:

```text
bonsai
```

In a later phase, 盆栽 can be used to buy:

- past avatar frames
- past theme items
- possibly future rerun cosmetics

盆栽 should not be usable for:

- season Pt
- rank movement
- direct title purchase

This prevents a gacha-to-ranking loop. Season rank should come from play during
the season, not duplicate conversion.

## Duplicate Compensation

If a non-stackable item is granted to a player who already owns it, convert that
duplicate into 盆栽.

Avatar frame duplicate compensation:

| Rarity | 盆栽 |
| --- | ---: |
| ★★★★★★ | 12 |
| ★★★★★ | 10 |
| ★★★★ | 8 |
| ★★★ | 6 |
| ★★ | 3 |
| ★ | 2 |

Character standing art duplicate compensation:

| Rarity | 盆栽 |
| --- | ---: |
| ★★★★★★ | 60 |
| ★★★★★ | 50 |
| ★★★★ | 40 |
| ★★★ | 30 |
| ★★ | 15 |
| ★ | 10 |

Theme duplicate compensation:

| Rarity | 盆栽 |
| --- | ---: |
| ★★★★★★ | 120 |

All themes should be ★★★★★★. Lower theme rarities are not part of the design.

Avatar frame duplicates should be rare in the first implementation. They can
happen if the same frame is granted from more than one source, such as a future
rerun/shop path, or if a reward script is re-run. Season settlement should award
only the highest rank tier a player qualifies for, not every lower tier, to avoid
creating accidental duplicates.

The shared seasonal character avatar frame is special: pulling the second
featured ★★★★★★ character should not count as a duplicated avatar frame grant.
The second character simply grants standing art only.

## Season Rank Rewards

Rank rewards can use the same theme item as the gacha path. This avoids
requiring two different themes for the same seasonal content.

| Placement | Rewards |
| --- | --- |
| Rank 1 | 1st-place title, champion frame, theme item |
| Rank 2-3 | podium title, podium frame, theme item |
| Top 10 | top-10 title, top-10 frame |
| Top 50 | top-50 title, top-50 frame |
| All participated players | participation title |

Participation should require a minimal season action, not merely existing in the
database.

A player counts as participated if their Pt has changed at least once during the
season. Any nonzero Pt delta should mark the player as participated, whether the
change comes from game results, daily rewards, or other season-counted Pt
sources.

## Title Policy

Titles are not included in any gacha pool.

For this update, titles come only from season/event placement:

- Rank 1 title
- Rank 2-3 title
- Top 10 title
- Top 50 title
- participation title

Achievement titles are intentionally out of scope. They can be added later as a
separate system after the seasonal cosmetic loop is stable.

## Theme Policy

Only one primary theme item needs to be created alongside a season.

The same theme item may be awarded by:

- pulling any featured ★★★★★★ character
- reaching Rank 1
- reaching Rank 2-3

Players who receive the same theme item from multiple sources should own only one
copy. The reward message should still acknowledge the source, for example:

- "You obtained the theme from the ★★★★★★ character."
- "You already own this theme, so the rank reward kept your existing copy."

Past themes can later enter the 盆栽 shop.

## 盆栽 Shop

The player-facing shop is called `流星堂`, matching the BanG Dream! setting.
`盆栽` remains the permanent currency name.

The shop is controlled by the git-tracked
`plugins/ryuseido/shop.json`. Its first permanent catalog contains:

- the existing ★★★–★★★★★ normal-pool standing art
- three replaceable placeholder avatar frames
- the previously unissued `樱色` theme
- up to five current-banner bonus pulls per player and season

Permanent prices are:

| Product | 盆栽 |
| --- | ---: |
| ★★★ standing art | 500 |
| ★★★★ standing art | 900 |
| ★★★★★ standing art | 1,400 |
| Standard shop avatar frame | 1,200 |
| Premium shop avatar frame | 1,800 |
| Permanent theme | 3,000 |
| Current-season bonus pull | 400, limit 5 per season |

Bonus pulls execute immediately, use the current limited banner, and count
toward normal pity and history. No ticket is created, so pulls cannot be
stockpiled across seasons.

Past season-limited themes must not be sold for 盆栽. Rank avatar frames and
titles also remain achievement-only.

## Avatar Frame Policy

Avatar frames come from two places in this update:

1. ★★★★★★ character gacha.
2. Season rank rewards.

The gacha character frame is one shared frame per season, not one frame per
featured character.

Recommended frame categories:

| Category | Source | Example id |
| --- | --- | --- |
| Character frame | ★★★★★★ gacha | `frame_s05_6star_kasumi` |
| Champion frame | Rank 1 | `frame_s05_champion` |
| Podium frame | Rank 2-3 | `frame_s05_podium` |
| Top-10 frame | Top 10 | `frame_s05_top10` |
| Top-50 frame | Top 50 | `frame_s05_top50` |

The rank frames should look more like competitive status. The character frame
should visually match the character standing art and configured theme item.

## Player Info Card

The base render kit should provide a clean `PlayerInfoCard` component.

This component is not a panel and should not include standing art / 立绘. It
renders only the player's compact identity information on a transparent
background. Plugins decide where and how to place it.

The component should include:

- avatar
- equipped avatar frame
- up to two equipped title images
- nickname
- level
- current Pt
- profile description

Recommended kit API:

```python
kit.info_card(
    avatar_image: ImageSource,
    frame_image: ImageSource | None,
    title1_image: ImageSource | None,
    title2_image: ImageSource | None,
    nickname: str,
    level: int,
    current_pt: int,
    description: str,
    width: SizeValue | int,
    height: SizeValue | int,
)
```

No separate `PlayerInfoData` object is needed. Callers should pass the required
values directly to the component factory/method.

`current_pt` and `description` are required. Callers should pass an empty string
for `description` when the player has not set one.

`width` and `height` should use the existing render size objects, such as
`Fixed`, `Fill`, and `Fraction`, via `SizeValue`.

The card should render transparent pixels outside its own text/avatar content.
It should not draw a solid background, border, panel, or decorative container by
itself.

Plugin renderers can use the card in different compositions:

- place it inside a panel and put that panel in the upper right corner
- place it in a large vertical area on the left or right side with standing art
- use it as a horizontal bar near the top of the image
- combine it with theme-specific shapes, backgrounds, or character art

The important design boundary: the base kit owns the clean player information
card, while each plugin owns the surrounding layout and standing art placement.

## Player Description Policy

Players can write a free-form profile description for themselves.

The renderer and command handler should still enforce practical limits:

- maximum length: 100 characters
- no emoji
- no weird symbols or symbol-heavy Unicode characters
- allow common Chinese/Japanese/English text, numbers, spaces, and basic
  punctuation
- normalized line breaks
- safe text rendering with no markup interpretation
- fallback text when the description is empty

The actual visible portion can depend on each renderer's layout. Renderers may
truncate, wrap, or fade text as needed.

Suggested allow-list:

```text
CJK unified ideographs, hiragana, katakana, ASCII letters, ASCII digits,
spaces, and common punctuation: . , ! ? ~ - _ / : ; ' " ( ) [ ] ， 。 ！ ？ 、 ： ；
```

Anything outside the allow-list should be rejected with a short validation
message instead of passed into the renderer.

The description is cosmetic profile text only. It should not affect gameplay,
ranking, rewards, or gacha.

## Suggested Data Model Additions

Existing cosmetic models can support most rewards, but character standing art
and duplicate currency need explicit representation.

Possible cosmetic types:

```text
avatar_frame
title
theme
standing_art
```

Suggested user equipment fields:

```text
equipped_frame
equipped_title
equipped_theme
equipped_standing_art
profile_description
```

Suggested season tracking fields:

```text
season_participated
```

Suggested new currency:

```text
bonsai
```

盆栽 should be permanent unless a later economy design says otherwise.

## Migration Strategy

Many season/cosmetic changes have not been updated to production yet. The backup
data under `.data/.data - backup` still reflects the older production shape. For
example, `.data/.data - backup/monetary/data.db` currently has a `users` table
with `balance`, `star_stickers`, level, XP, and daily fields, rather than the
newer season/cosmetic schema.

When creating migration scripts for this update, edit the existing pending
migration path instead of creating a new chained migration for code that has not
shipped yet.

## First Implementation Scope

Implement now:

- season reward definitions
- title rewards from season placement and participation
- ★★★★★★ character rewards
- standing art ownership
- avatar frame ownership and equipment
- theme ownership and equipment
- 盆栽 duplicate compensation
- transparent `PlayerInfoCard` component in the base render kit
- profile description storage and validation

Defer:

- achievements
- stickers
- icons
- profile badges
- low-rarity cosmetic filler
- duo rewards for collecting both ★★★★★★ characters
- multiple theme variants in the same season
