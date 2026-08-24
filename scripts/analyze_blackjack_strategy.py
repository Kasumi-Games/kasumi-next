"""Print a strategy table and validate it against a production-faithful simulation.

Run from the repository root, for example:

    python scripts/analyze_blackjack_strategy.py --rounds 1000000 --seed 20260815

The displayed opening table assumes enough Pt remains to fund a double or a
split.  Pass ``--no-extra-stake`` to calculate the table the live plugin falls
back to when those actions cannot be afforded.
"""

from __future__ import annotations

import sys
import argparse
import importlib.util
from types import ModuleType
from pathlib import Path

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

# ``python scripts/...`` sets sys.path to ``scripts/`` rather than the repo.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BLACKJACK_DIR = REPOSITORY_ROOT / "plugins" / "blackjack"


def _load_strategy_module() -> ModuleType:
    """Load pure blackjack modules without starting the NoneBot plugin.

    Importing ``plugins.blackjack`` executes the bot's plugin registration,
    which is useful in production but makes a command-line analysis require a
    running NoneBot configuration.  Loading these three source modules under a
    private package still exercises the exact production ``models.py``,
    ``rules.py`` and ``strategy.py`` files.
    """

    package_name = "_blackjack_strategy_analysis"
    package = ModuleType(package_name)
    package.__path__ = [str(BLACKJACK_DIR)]
    sys.modules[package_name] = package
    for module_name in ("rules", "models", "strategy"):
        qualified_name = f"{package_name}.{module_name}"
        spec = importlib.util.spec_from_file_location(
            qualified_name, BLACKJACK_DIR / f"{module_name}.py"
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load {qualified_name}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified_name] = module
        spec.loader.exec_module(module)
    return sys.modules[f"{package_name}.strategy"]


_strategy = _load_strategy_module()
DEALER_UPCARDS = _strategy.DEALER_UPCARDS
PAIR_VALUES = _strategy.PAIR_VALUES
OptimalStrategy = _strategy.OptimalStrategy
StrategyConfig = _strategy.StrategyConfig
dealer_label = _strategy.dealer_label
pair_label = _strategy.pair_label

CHART_FONT = (
    REPOSITORY_ROOT
    / "plugins/render/kits/bangdream/resources/Fonts/old.ttf"
)
ACTION_NAMES = {"H": "补", "S": "停", "D": "双", "R": "降", "P": "分"}
ACTION_COLORS = {
    "H": (77, 129, 222),
    "S": (66, 159, 124),
    "D": (218, 143, 62),
    "R": (203, 91, 102),
    "P": (151, 101, 201),
}


def _table(headers: list[str], rows: list[tuple[str, list[str]]]) -> str:
    body = ["| " + " | ".join(headers) + " |"]
    body.append("|" + "|".join("---" for _ in headers) + "|")
    body.extend("| " + label + " | " + " | ".join(cells) + " |" for label, cells in rows)
    return "\n".join(body)


def _decision_row(strategy: OptimalStrategy, label: str, hard: int, aces: int) -> tuple[str, list[str]]:
    return (
        label,
        [
            strategy.first_action_decision(
                hard, aces, upcard, upcard in (1, 10), True
            )[1].value
            for upcard in DEALER_UPCARDS
        ],
    )


def _after_hit_row(strategy: OptimalStrategy, label: str, hard: int, aces: int) -> tuple[str, list[str]]:
    return (
        label,
        [
            strategy.after_hit_decision(hard, aces, upcard, upcard in (1, 10))[1].value
            for upcard in DEALER_UPCARDS
        ],
    )


def render_report(strategy: OptimalStrategy, rounds: int, seed: int) -> str:
    exact = strategy.exact_result()
    simulation = strategy.simulate(rounds, seed)
    upcards = ["你的牌 / 庄家明牌", *[dealer_label(card) for card in DEALER_UPCARDS]]

    hard_rows = [_decision_row(strategy, str(total), total, 0) for total in range(5, 21)]
    soft_rows = [
        _decision_row(strategy, f"A,{card}", 1 + card, 1)
        for card in range(2, 10)
    ]
    pair_rows = [
        (
            pair_label(pair),
            [
                strategy.opening_decision(pair, pair, upcard)[1].value
                for upcard in DEALER_UPCARDS
            ],
        )
        for pair in PAIR_VALUES
    ]
    post_hit_hard_rows = [
        _after_hit_row(strategy, str(total), total, 0) for total in range(4, 21)
    ]
    post_hit_soft_rows = [
        _after_hit_row(strategy, f"A,{card}", 1 + card, 1)
        for card in range(2, 10)
    ]
    ci_low, ci_high = simulation.confidence_interval_95
    config = strategy.config
    return f"""# BlackKasumi 最优策略表

此表针对当前插件的真实规则：每张牌均有放回抽取、庄家 17 点停牌、庄家开局 BlackKasumi 立即结算、自然 BlackKasumi 支付 `int(1.5 × 下注)`、投降损失 `ceil(下注 / 2)`；分牌后不能双倍下注，但每手首回合都能投降。

计算参数：初始下注 `{config.bet_amount} Pt`；额外下注 {'可用' if config.allow_extra_stake else '不可用'}。当额外下注不可用时，线上插件会拒绝双倍和分牌，应该使用本报告对应的结果。下表只适用于庄家未在开局直接结算之后的行动阶段；若明牌为 A 或 10，这也意味着庄家没有 BlackKasumi。

图例：`H` 补牌，`S` 停牌，`D` 双倍，`R` 投降，`P` 分牌。

## 开局：硬牌

{_table(upcards, hard_rows)}

## 开局：软牌

{_table(upcards, soft_rows)}

## 开局：对子

`10,10` 包含任意两张点数为 10 的牌（10/J/Q/K）；插件按点数相同判定可分牌。

{_table(upcards, pair_rows)}

## 已补过至少一张牌

此时插件只允许补牌或停牌，不能双倍、分牌或投降。

### 硬牌

{_table(upcards, post_hit_hard_rows)}

### 软牌

{_table(upcards, post_hit_soft_rows)}

## 精确值与模拟核对

| 指标 | 精确动态规划 | 模拟（{simulation.rounds:,} 局，seed={simulation.seed}） |
|---|---:|---:|
| 每初始下注净收益 | {exact.net_per_initial_bet:.6%} | {simulation.net_per_initial_bet:.6%} |
| 每总下注净收益 | {exact.net_per_total_staked:.6%} | {simulation.net_per_total_staked:.6%} |
| 每局总下注倍数 | {exact.expected_total_stake:.8f} | {simulation.expected_total_stake:.8f} |

模拟的每初始下注收益 95% 置信区间为 `[{ci_low:.6%}, {ci_high:.6%}]`；精确值应落在该区间附近。模拟会复用插件的 `Shoe` 和 `Hand`：包括每次发牌的 suit 随机数消耗、庄家/玩家的实际发牌顺序，以及普通手爆牌或投降后不再补完庄家牌这一控制流。

开局动作计数：`{simulation.opening_actions}`
"""


def render_strategy_image(strategy: OptimalStrategy, output: Path) -> None:
    """Export all opening tables as a high-resolution PNG image."""

    tables = [
        (
            "硬牌",
            "对子优先看“对子”表",
            [
                (str(total), [strategy.first_action_cell(total, 0, upcard) for upcard in DEALER_UPCARDS])
                for total in range(5, 21)
            ],
        ),
        (
            "软牌",
            "A 默认按 11 计算",
            [
                (f"A,{card}", [strategy.first_action_cell(1 + card, 1, upcard) for upcard in DEALER_UPCARDS])
                for card in range(2, 10)
            ],
        ),
        (
            "对子",
            "10,10 包含任意两张 10/J/Q/K；分牌按两手合计结算",
            [
                (pair_label(pair), [strategy.opening_cell(pair, pair, upcard) for upcard in DEALER_UPCARDS])
                for pair in PAIR_VALUES
            ],
        ),
    ]
    width, padding, label_width, cell_width, cell_height = 1440, 56, 138, 118, 92
    title_height, section_gap = 160, 52
    height = (
        padding * 2
        + title_height
        + sum(48 + cell_height * (len(rows) + 1) for _, _, rows in tables)
        + section_gap * 2
        + 120
    )
    image = Image.new("RGB", (width, height), (249, 245, 250))
    draw = ImageDraw.Draw(image)
    fonts = {
        "title": ImageFont.truetype(str(CHART_FONT), 58),
        "section": ImageFont.truetype(str(CHART_FONT), 34),
        "label": ImageFont.truetype(str(CHART_FONT), 27),
        "action": ImageFont.truetype(str(CHART_FONT), 30),
        "rate": ImageFont.truetype(str(CHART_FONT), 20),
    }

    draw.rectangle(
        (padding, padding, width - padding, padding + 116), fill=(64, 46, 81)
    )
    _center_text(
        draw, (padding, padding, width - padding, padding + 72), "BlackKasumi 最优策略", fonts["title"], (255, 255, 255)
    )
    _center_text(
        draw,
        (padding, padding + 67, width - padding, padding + 108),
        "每格：最优动作 / 最终净收益为正的精确胜率 · 标准注 100 Pt",
        fonts["rate"],
        (234, 218, 240),
    )

    y = padding + title_height
    for title, note, rows in tables:
        draw.text((padding, y), title, font=fonts["section"], fill=(57, 45, 69))
        draw.text((padding + 120, y + 10), note, font=fonts["rate"], fill=(115, 98, 124))
        y += 48
        labels = ["你的牌", *[dealer_label(card) for card in DEALER_UPCARDS]]
        for column, label in enumerate(labels):
            x = padding if column == 0 else padding + label_width + (column - 1) * cell_width
            cell_w = label_width if column == 0 else cell_width
            draw.rectangle(
                (x + 3, y + 3, x + cell_w - 3, y + cell_height - 3),
                fill=(235, 225, 238),
            )
            _center_text(draw, (x, y, x + cell_w, y + cell_height), label, fonts["label"], (80, 62, 89))
        y += cell_height
        for row_label, cells in rows:
            draw.rectangle(
                (padding + 3, y + 3, padding + label_width - 3, y + cell_height - 3),
                fill=(255, 255, 255),
            )
            _center_text(draw, (padding, y, padding + label_width, y + cell_height), row_label, fonts["label"], (80, 62, 89))
            for column, cell in enumerate(cells):
                action = cell.action.value
                color = ACTION_COLORS[action]
                x = padding + label_width + column * cell_width
                fill = tuple((value + 255 * 3) // 4 for value in color)
                draw.rectangle(
                    (x + 3, y + 3, x + cell_width - 3, y + cell_height - 3),
                    fill=fill,
                    outline=color,
                    width=2,
                )
                _center_text(draw, (x, y + 8, x + cell_width, y + 51), ACTION_NAMES[action], fonts["action"], color)
                _center_text(draw, (x, y + 48, x + cell_width, y + cell_height - 5), f"胜 {cell.outcomes.win_rate:.1%}", fonts["rate"], (85, 70, 93))
            y += cell_height
        y += section_gap

    draw.text((padding, height - 68), "补=补牌　停=停牌　双=双倍　降=投降　分=分牌", font=fonts["label"], fill=(80, 62, 89))
    draw.text((padding, height - 34), "投降的净收益必为负，因此胜率为 0%。", font=fonts["rate"], fill=(115, 98, 124))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)


def _center_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int],
) -> None:
    left, top, right, bottom = box
    text_box = draw.textbbox((0, 0), text, font=font)
    x = left + (right - left - (text_box[2] - text_box[0])) // 2
    y = top + (bottom - top - (text_box[3] - text_box[1])) // 2 - text_box[1]
    draw.text((x, y), text, font=font, fill=color)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bet", type=int, default=100, help="initial bet in Pt")
    parser.add_argument("--rounds", type=int, default=1_000_000)
    parser.add_argument("--seed", type=int, default=20260815)
    parser.add_argument("--no-extra-stake", action="store_true")
    parser.add_argument("--output", type=Path, help="write the Markdown report here")
    parser.add_argument("--image", type=Path, help="write the PNG strategy chart here")
    args = parser.parse_args()

    strategy = OptimalStrategy(
        StrategyConfig(args.bet, allow_extra_stake=not args.no_extra_stake)
    )
    if args.image is not None:
        render_strategy_image(strategy, args.image)
        print(f"Wrote {args.image}")
    if args.output is not None:
        report = render_report(strategy, args.rounds, args.seed)
        args.output.write_text(report + "\n", encoding="utf-8")
        print(f"Wrote {args.output}")
    elif args.image is None:
        print(render_report(strategy, args.rounds, args.seed))


if __name__ == "__main__":
    main()
