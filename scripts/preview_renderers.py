import sys
import time
import types
import random
import argparse
import datetime
import subprocess
import importlib.util
from typing import Iterable
from pathlib import Path

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / ".cache" / "render-previews"
PREVIEW_DATA_DIR = ROOT / ".cache" / "render-preview-data"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugins.render import PlayerIdentity


def _ensure_package(name: str, path: Path) -> None:
    package = sys.modules.get(name)
    if package is not None:
        return
    package = types.ModuleType(name)
    package.__path__ = [str(path)]
    sys.modules[name] = package


def _load_module(name: str, path: Path):
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_plugin_module(name: str, relative_path: str):
    sys.modules.setdefault(
        "nonebot_plugin_localstore",
        types.SimpleNamespace(get_data_dir=lambda _name: PREVIEW_DATA_DIR),
    )
    parts = name.split(".")
    for index in range(2, len(parts)):
        package_name = ".".join(parts[:index])
        package_path = ROOT / Path(*parts[:index])
        _ensure_package(package_name, package_path)
    return _load_module(name, ROOT / relative_path)


def _kit(name: str):
    from plugins.render.kits import KITS

    if name not in KITS:
        raise ValueError(f"unknown kit: {name}")
    return KITS[name]()


def _kit_names() -> list[str]:
    from plugins.render.kits import KITS

    return list(KITS)


def _stub_gacha_service() -> None:
    """Stand in for the gacha service layer, which needs a live database.

    The render modules only import service names for their data-assembly
    helpers; the previews build the page-data dataclasses directly, so empty
    placeholders satisfy the imports.
    """

    if "plugins.gacha.service" in sys.modules:
        return
    stub = types.ModuleType("plugins.gacha.service")
    stub.GachaEntry = type("GachaEntry", (), {})
    stub.GachaBanner = type("GachaBanner", (), {})
    stub.GachaResult = type("GachaResult", (), {})
    stub.current_rates = lambda *_args, **_kwargs: ()
    sys.modules["plugins.gacha.service"] = stub


def _placeholder_art(
    label: str,
    size: tuple[int, int],
    fill: tuple[int, int, int, int],
) -> Image.Image:
    """A solid rounded panel with a centered label, for art slots."""

    width, height = size
    image = Image.new("RGBA", size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=24, fill=fill)
    try:
        font = ImageFont.truetype(
            str(ROOT / "plugins" / "blackjack" / "recourses" / "old.ttf"),
            max(24, width // 8),
        )
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label, font=font)
    draw.text(
        (
            (width - (bbox[2] - bbox[0])) // 2,
            (height - (bbox[3] - bbox[1])) // 2 - bbox[1],
        ),
        label,
        font=font,
        fill=(255, 255, 255, 255),
    )
    return image


def _preview_card(label: str, fill: tuple[int, int, int, int]) -> Image.Image:
    width, height = 640, 896
    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=36, fill=fill)
    draw.rounded_rectangle(
        (18, 18, width - 19, height - 19),
        radius=28,
        outline=(255, 255, 255, 230),
        width=8,
    )
    try:
        font = ImageFont.truetype(
            str(ROOT / "plugins" / "blackjack" / "recourses" / "old.ttf"), 120
        )
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label, font=font)
    draw.text(
        (
            (width - (bbox[2] - bbox[0])) // 2,
            (height - (bbox[3] - bbox[1])) // 2 - bbox[1],
        ),
        label,
        font=font,
        fill=(255, 255, 255, 255),
    )
    return image


def preview_blackjack(kit_name: str, output_dir: Path) -> list[Path]:
    render_module = _load_plugin_module(
        "plugins.blackjack.render", "plugins/blackjack/render.py"
    )
    models_module = _load_plugin_module(
        "plugins.blackjack.models", "plugins/blackjack/models.py"
    )

    renderer = object.__new__(render_module.BlackjackRenderer)
    renderer.kit = _kit(kit_name)
    renderer.card_back = _preview_card("?", (55, 55, 65, 255))
    renderer.get_font = lambda size: ImageFont.truetype(
        str(ROOT / "plugins" / "blackjack" / "recourses" / "old.ttf"), size
    )
    identity = PlayerIdentity(nickname="香澄", level=42)

    def card(rank: str, suit: str, fill: tuple[int, int, int, int]):
        item = models_module.Card(suit, rank)
        item._get_image = lambda ace_value=None: _preview_card(rank, fill)
        return item

    dealer = models_module.Hand()
    dealer.add_card(card("A", "cool", (234, 78, 116, 255)))
    dealer.add_card(card("10", "happy", (66, 133, 244, 255)))
    dealer.add_card(card("K", "pure", (76, 175, 80, 255)))

    player = models_module.Hand()
    player.add_card(card("8", "powerful", (255, 124, 85, 255)))
    player.add_card(card("7", "cool", (184, 130, 225, 255)))

    outputs = [
        output_dir / f"blackjack-hand-{kit_name}.png",
        output_dir / f"blackjack-table-{kit_name}.png",
    ]
    renderer.generate_hand(
        dealer,
        second_card_back=True,
        identity=identity,
        detail="庄家回合 · 押注 120 Pt",
    ).save(outputs[0])
    renderer.generate_table(
        dealer,
        player,
        dealer_card_back=True,
        identity=identity,
        detail="押注 120 Pt · 玩家 15 点",
    ).save(outputs[1])
    return outputs


def preview_mines(kit_name: str, output_dir: Path) -> list[Path]:
    random.seed(7)
    models_module = _load_plugin_module(
        "plugins.mines.models", "plugins/mines/models.py"
    )
    field_module = _load_plugin_module(
        "plugins.mines.render.field", "plugins/mines/render/field.py"
    )

    field = models_module.Field(width=5, height=5, mines=4)
    for index in (0, 3, 6, 12, 18):
        field.reveal_block(index)
    field.reveal_all_mines()

    output = output_dir / f"mines-{kit_name}.png"
    identity = PlayerIdentity(nickname="香澄", level=42)
    field_module.render(
        field,
        kit=_kit(kit_name),
        identity=identity,
        detail="押注 120 Pt · 剩 4 雷",
    ).save(output)
    return [output]


def preview_one_stroke(kit_name: str, output_dir: Path) -> list[Path]:
    models_module = _load_plugin_module(
        "plugins.one_stroke.models", "plugins/one_stroke/models.py"
    )
    session_module = _load_plugin_module(
        "plugins.one_stroke.session", "plugins/one_stroke/session.py"
    )
    graph_module = _load_plugin_module(
        "plugins.one_stroke.render.graph", "plugins/one_stroke/render/graph.py"
    )
    leaderboard_module = _load_plugin_module(
        "plugins.one_stroke.render.leaderboard",
        "plugins/one_stroke/render/leaderboard.py",
    )

    nodes = {(r, c) for r in range(4) for c in range(4)}
    path = [
        (0, 0),
        (0, 1),
        (0, 2),
        (0, 3),
        (1, 3),
        (1, 2),
        (1, 1),
        (1, 0),
        (2, 0),
        (2, 1),
        (2, 2),
        (2, 3),
        (3, 3),
    ]
    edges = {frozenset((a, b)) for a, b in zip(path, path[1:])}
    graph = models_module.Graph(
        rows=4, cols=4, nodes=nodes, edges=edges, start_node=path[0]
    )
    session = session_module.GameSession(
        user_id="preview",
        channel_id="preview",
        difficulty_name="普通",
        reward=120,
        graph=graph,
    )
    for next_node in path[1:7]:
        edge = frozenset((session.current_pos, next_node))
        session.drawn_edges.add(edge)
        session.current_pos = next_node
        session.visited_nodes.add(next_node)

    board_output = output_dir / f"one-stroke-{kit_name}.png"
    leaderboard_output = output_dir / f"one-stroke-leaderboard-{kit_name}.png"
    identity = PlayerIdentity(nickname="香澄", level=42)
    graph_module.render(
        session,
        kit=_kit(kit_name),
        identity=identity,
        detail="难度 普通 · 奖励 120 Pt",
    ).save(board_output)
    leaderboard_module.render_leaderboard(
        [("kasumi", 12.34), ("arisa", 16.78), ("tae", 20.12)],
        [("a very very long player name", 23.45), ("rimi", 25.67)],
        [("saaya", 31.23)],
        kit=_kit(kit_name),
    ).save(leaderboard_output)
    return [board_output, leaderboard_output]


def _avatar() -> Image.Image:
    return _placeholder_art("香", (128, 128), (234, 78, 116, 255))


def preview_profile(kit_name: str, output_dir: Path) -> list[Path]:
    profile_module = _load_plugin_module(
        "plugins.inventory.render.profile", "plugins/inventory/render/profile.py"
    )

    data = profile_module.ProfileData(
        identity=PlayerIdentity(nickname="香澄", level=42, avatar=_avatar()),
        current_pt=12345,
        description="今天也在世界的角落里唱歌。欢迎来到我的资料页！",
        star_stickers=2680,
        bonsai=12,
        season_name="星之鼓动",
        season_rank=42,
        equipped=(("头像框", "星之鼓动"), ("称号", "星辰收藏家")),
        xp_in_level=320,
        xp_level_span=1000,
    )
    output = output_dir / f"profile-{kit_name}.png"
    profile_module.render_profile(data, kit=_kit(kit_name)).save(output)
    return [output]


def preview_gacha(kit_name: str, output_dir: Path) -> list[Path]:
    _stub_gacha_service()
    banner_module = _load_plugin_module(
        "plugins.gacha.render.banner", "plugins/gacha/render/banner.py"
    )
    pull_module = _load_plugin_module(
        "plugins.gacha.render.pull", "plugins/gacha/render/pull.py"
    )
    from plugins.render import PullRevealItem

    banner = banner_module.BannerPageData(
        banner_name="星之鼓动 招募",
        season_name="星之鼓动",
        featured_name="星空下的约定 香澄",
        featured_rarity=6,
        featured_art=None,
        bundle_names=("星之鼓动 头像框", "星之鼓动 主题"),
        rates=((6, 0.03), (5, 0.12), (4, 0.35), (3, 0.50)),
        single_cost=120,
        ten_cost=1200,
        pity_count=17,
        hard_pity=100,
    )

    names = (
        "初始之音 未来", "舞台之上 心羽", "星屑的轨迹 铃", "彩虹彼端 奏",
        "月光食堂 绘名", "放学后茶会 澪", "风之驿站 真琴", "雨停信号 雫",
        "闪耀节拍 香澄", "星空下的约定 香澄",
    )
    rarities = (3, 4, 2, 6, 5, 3, 4, 3, 5, 6)
    fills = (
        (234, 78, 116, 255), (66, 133, 244, 255), (76, 175, 80, 255),
        (255, 124, 85, 255), (184, 130, 225, 255), (255, 193, 7, 255),
        (0, 150, 136, 255), (96, 125, 139, 255), (233, 30, 99, 255),
        (63, 81, 181, 255),
    )
    pulls = tuple(
        PullRevealItem(
            name=name,
            rarity=rarity,
            is_new=index in (0, 3, 9),
            featured=index in (3, 9),
            image=_placeholder_art(name[:1], (480, 600), fills[index]),
            note="+120" if index == 9 else "",
        )
        for index, (name, rarity) in enumerate(zip(names, rarities))
    )
    pull = pull_module.PullPageData(
        banner_name="星之鼓动 招募",
        pulls=pulls,
        pity_after=3,
        hard_pity=100,
        bonus_grants=("星之鼓动 头像框",),
    )

    outputs = [
        output_dir / f"gacha-banner-{kit_name}.png",
        output_dir / f"gacha-pull-{kit_name}.png",
    ]
    banner_module.render_banner(banner, kit=_kit(kit_name)).save(outputs[0])
    pull_module.render_pull(pull, kit=_kit(kit_name)).save(outputs[1])
    return outputs


def preview_checkin(kit_name: str, output_dir: Path) -> list[Path]:
    checkin_module = _load_plugin_module(
        "plugins.daily.render.checkin", "plugins/daily/render/checkin.py"
    )

    data = checkin_module.CheckinData(
        nickname="香澄",
        reward_pt=120,
        balance=12625,
        offseason=False,
        streak=6,
        window_done=6,
        window_total=7,
        next_bonus_day=7,
        bonus_stickers=5,
        streak_bonus=0,
        old_level=41,
        new_level=42,
        level_stickers=10,
        task=checkin_module.CheckinTask(
            name="每日演出",
            description="完成 1 场协力演出",
            reward=2,
            done=False,
        ),
        unread_mails=2,
    )
    output = output_dir / f"checkin-{kit_name}.png"
    checkin_module.render_checkin(data, kit=_kit(kit_name)).save(output)
    return [output]


def preview_mailbox(kit_name: str, output_dir: Path) -> list[Path]:
    inbox_module = _load_plugin_module(
        "plugins.mailbox.render.inbox", "plugins/mailbox/render/inbox.py"
    )
    models_module = _load_plugin_module(
        "plugins.mailbox.models", "plugins/mailbox/models.py"
    )

    now = datetime.datetime.now()
    mails = [
        models_module.ServiceMail(
            id=3,
            title="赛季结算奖励",
            content="本赛季的 Pt 结算已完成，感谢参与！",
            star_kakeras=0,
            star_stickers=200,
            sender_id="system",
            created_at=now - datetime.timedelta(hours=2),
            expire_time=now + datetime.timedelta(days=7),
            is_broadcast=True,
            is_read=False,
            read_at=None,
        ),
        models_module.ServiceMail(
            id=2,
            title="维护补偿",
            content="感谢耐心等待，奉上补偿贴纸。",
            star_kakeras=0,
            star_stickers=50,
            sender_id="system",
            created_at=now - datetime.timedelta(days=1),
            expire_time=now + datetime.timedelta(days=6),
            is_broadcast=True,
            is_read=False,
            read_at=None,
        ),
        models_module.ServiceMail(
            id=1,
            title="欢迎来到星之鼓动",
            content="新季节开始了，记得每日签到。",
            star_kakeras=0,
            star_stickers=0,
            sender_id="system",
            created_at=now - datetime.timedelta(days=3),
            expire_time=now + datetime.timedelta(days=4),
            is_broadcast=True,
            is_read=True,
            read_at=now - datetime.timedelta(days=2),
        ),
    ]
    output = output_dir / f"mailbox-{kit_name}.png"
    inbox_module.render_inbox(mails, kit=_kit(kit_name)).save(output)
    return [output]


def _help_entries():
    entries_module = _load_plugin_module(
        "plugins.help.entries", "plugins/help/entries.py"
    )
    command = entries_module.HelpCommand
    entry = entries_module.HelpEntry
    return (
        entry(
            name="猜谱面",
            description="看局部谱面猜歌曲",
            category="游戏",
            usage=(
                ("/猜谱面", "开始一局"),
                ("/猜谱面 <难度>", "按难度开始一局"),
            ),
            examples=("/猜谱面", "/猜谱面 expert"),
            commands=(
                command(command="/猜谱面", summary="开始一局", aliases=("bdc",)),
            ),
            params=(("难度", ("easy", "normal", "hard", "expert")),),
        ),
        entry(
            name="一笔画",
            description="在网格上一笔连通所有边",
            category="游戏",
            usage=(("/一笔画", "开始一局"),),
            examples=("/一笔画",),
            commands=(command(command="/一笔画", summary="开始一局"),),
        ),
        entry(
            name="签到",
            description="每日签到领取 Pt 与贴纸",
            category="日常",
            usage=(("/签到", "领取今日奖励"),),
            examples=("/签到",),
            commands=(command(command="/签到", summary="领取今日奖励"),),
        ),
        entry(
            name="红包",
            description="发 Pt 红包给群友拼手气",
            category="日常",
            usage=(("/发红包 <总额> <份数>", "发出一个红包"),),
            examples=("/发红包 1000 10",),
            commands=(command(command="/发红包", summary="发出一个红包"),),
        ),
        entry(
            name="资料",
            description="查看自己的名片与资产",
            category="查询",
            usage=(("/资料", "查看资料页"),),
            examples=("/资料",),
            commands=(command(command="/资料", summary="查看资料页"),),
        ),
        entry(
            name="赛季排行",
            description="查看本赛季 Pt 天梯",
            category="查询",
            usage=(("/赛季排行", "查看 Pt 榜"),),
            examples=("/赛季排行",),
            commands=(command(command="/赛季排行", summary="查看 Pt 榜"),),
        ),
    )


def preview_help(kit_name: str, output_dir: Path) -> list[Path]:
    board_module = _load_plugin_module(
        "plugins.help.render.board", "plugins/help/render/board.py"
    )
    detail_module = _load_plugin_module(
        "plugins.help.render.detail", "plugins/help/render/detail.py"
    )

    entries = _help_entries()
    outputs = [
        output_dir / f"help-board-{kit_name}.png",
        output_dir / f"help-detail-{kit_name}.png",
    ]
    board_module.render_board(entries, kit=_kit(kit_name)).save(outputs[0])
    detail_module.render_detail(entries[0], kit=_kit(kit_name)).save(outputs[1])
    return outputs


def preview_season_rank(kit_name: str, output_dir: Path) -> list[Path]:
    rank_module = _load_plugin_module(
        "plugins.inventory.render.season_rank",
        "plugins/inventory/render/season_rank.py",
    )

    top = (
        ("花园多惠", 98210),
        ("牛込里美", 95432),
        ("山吹沙绫", 90123),
        ("市谷有咲", 87654),
        ("户山香澄", 84521),
    )
    data = rank_module.SeasonRankData(
        season_name="星之鼓动",
        rows=tuple(
            rank_module.SeasonRankRow(rank=index + 1, name=name, points=points)
            for index, (name, points) in enumerate(top)
        ),
        nearby=(
            rank_module.SeasonRankRow(rank=41, name="美竹兰", points=12400),
            rank_module.SeasonRankRow(rank=42, name="香澄", points=12345),
            rank_module.SeasonRankRow(rank=43, name="青叶摩卡", points=12200),
        ),
        viewer_name="香澄",
        viewer_rank=42,
        viewer_points=12345,
    )
    output = output_dir / f"season-rank-{kit_name}.png"
    rank_module.render_season_rank(data, kit=_kit(kit_name)).save(output)
    return [output]


def preview_red_envelope(kit_name: str, output_dir: Path) -> list[Path]:
    envelope_module = _load_plugin_module(
        "plugins.red_envelope.render.envelope",
        "plugins/red_envelope/render/envelope.py",
    )

    create = envelope_module.EnvelopeCreateData(
        channel_index=7,
        title="新年快乐，星之鼓动！",
        total_amount=2000,
        total_count=10,
        creator=PlayerIdentity(nickname="香澄", level=42, avatar=_avatar()),
    )
    completion = envelope_module.EnvelopeCompletionData(
        channel_index=7,
        title="新年快乐，星之鼓动！",
        total_amount=2000,
        total_count=10,
        creator_name="香澄",
        duration_text="2 分 14 秒",
        lucky_king_name="山吹沙绫",
        lucky_king_amount=388,
        claims=tuple(
            envelope_module.ClaimRow(name=name, amount=amount, is_lucky_king=index == 1)
            for index, (name, amount) in enumerate(
                (("户山香澄", 245), ("山吹沙绫", 388), ("花园多惠", 176), ("牛込里美", 152))
            )
        ),
    )
    outputs = [
        output_dir / f"red-envelope-create-{kit_name}.png",
        output_dir / f"red-envelope-done-{kit_name}.png",
    ]
    envelope_module.render_create(create, kit=_kit(kit_name)).save(outputs[0])
    envelope_module.render_completion(completion, kit=_kit(kit_name)).save(outputs[1])
    return outputs


def preview_guess_chart(kit_name: str, output_dir: Path) -> list[Path]:
    reveal_module = _load_plugin_module(
        "plugins.guess_chart.render.reveal",
        "plugins/guess_chart/render/reveal.py",
    )

    data = reveal_module.GuessChartRevealData(
        outcome="win",
        song_name="Returns",
        band_name="Poppin'Party",
        difficulty="expert",
        play_level=27,
        bpm=195,
        notes=1001,
        pool_size=420,
        hints_used=1,
        jacket=None,
        winner=PlayerIdentity(nickname="香澄", level=42, avatar=_avatar()),
        base_amount=120,
        final_amount=240,
        birthday_names=("户山香澄",),
        multiplier=2,
        owner_name="香澄",
    )
    output = output_dir / f"guess-chart-{kit_name}.png"
    reveal_module.render_reveal(data, kit=_kit(kit_name)).save(output)
    return [output]


def preview_cck(kit_name: str, output_dir: Path) -> list[Path]:
    reveal_module = _load_plugin_module(
        "plugins.cck.render.reveal", "plugins/cck/render/reveal.py"
    )

    data = reveal_module.CckRevealData(
        outcome="win",
        character_name="户山香澄",
        card_id="2060",
        card_image=_preview_card("香澄", (234, 78, 116, 255)),
        card_title="星空下的约定",
        rarity=5,
        card_type="limited",
        difficulty="normal",
        winner=PlayerIdentity(nickname="山吹沙绫", level=38),
        winner_attempt=2,
        base_amount=100,
        final_amount=100,
        owner_name="山吹沙绫",
    )
    output = output_dir / f"cck-{kit_name}.png"
    reveal_module.render_reveal(data, kit=_kit(kit_name)).save(output)
    return [output]


_TARGETS = (
    "blackjack",
    "mines",
    "one-stroke",
    "profile",
    "gacha",
    "checkin",
    "mailbox",
    "help",
    "season-rank",
    "red-envelope",
    "guess-chart",
    "cck",
)

_PREVIEW_BY_TARGET = {
    "blackjack": preview_blackjack,
    "mines": preview_mines,
    "one-stroke": preview_one_stroke,
    "profile": preview_profile,
    "gacha": preview_gacha,
    "checkin": preview_checkin,
    "mailbox": preview_mailbox,
    "help": preview_help,
    "season-rank": preview_season_rank,
    "red-envelope": preview_red_envelope,
    "guess-chart": preview_guess_chart,
    "cck": preview_cck,
}


def render_targets(
    targets: Iterable[str], kits: Iterable[str], output_dir: Path
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for kit_name in kits:
        for target in targets:
            outputs.extend(_PREVIEW_BY_TARGET[target](kit_name, output_dir))
    return outputs


def _expand_targets(target: str) -> list[str]:
    if target == "all":
        return list(_TARGETS)
    return [target]


def _expand_kits(kit: str) -> list[str]:
    if kit == "all":
        return _kit_names()
    if kit == "both":
        return ["bangdream", "minimal"]
    return [kit]


def _watch_files() -> list[Path]:
    return [
        Path(__file__),
        ROOT / "plugins" / "blackjack" / "render.py",
        ROOT / "plugins" / "mines" / "render" / "field.py",
        ROOT / "plugins" / "one_stroke" / "render" / "graph.py",
        ROOT / "plugins" / "one_stroke" / "render" / "leaderboard.py",
        ROOT / "plugins" / "inventory" / "render" / "profile.py",
        ROOT / "plugins" / "inventory" / "render" / "season_rank.py",
        ROOT / "plugins" / "gacha" / "render" / "banner.py",
        ROOT / "plugins" / "gacha" / "render" / "pull.py",
        ROOT / "plugins" / "daily" / "render" / "checkin.py",
        ROOT / "plugins" / "mailbox" / "render" / "inbox.py",
        ROOT / "plugins" / "help" / "render" / "board.py",
        ROOT / "plugins" / "help" / "render" / "detail.py",
        ROOT / "plugins" / "red_envelope" / "render" / "envelope.py",
        ROOT / "plugins" / "guess_chart" / "render" / "reveal.py",
        ROOT / "plugins" / "cck" / "render" / "reveal.py",
    ]


def _snapshot(paths: Iterable[Path]) -> dict[Path, int]:
    return {path: path.stat().st_mtime_ns for path in paths if path.exists()}


def _open_paths(paths: Iterable[Path]) -> None:
    for path in paths:
        subprocess.run(["open", str(path)], check=False)


def run_once(args: argparse.Namespace) -> list[Path]:
    targets = _expand_targets(args.target)
    kits = _expand_kits(args.kit)
    outputs = render_targets(targets, kits, args.output_dir)
    for path in outputs:
        print(path)
    if args.open:
        _open_paths(outputs)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render local game previews without loading NoneBot plugins."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=["all", *_TARGETS],
    )
    parser.add_argument(
        "--kit",
        default="bangdream",
        choices=[*_kit_names(), "both", "all"],
        help="Render with one kit, 'both' for bangdream+minimal, or 'all' kits.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated preview PNGs.",
    )
    parser.add_argument("--open", action="store_true", help="Open generated PNGs.")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Regenerate when previewed render files change.",
    )
    args = parser.parse_args()

    if not args.watch:
        run_once(args)
        return

    watched = _watch_files()
    previous = _snapshot(watched)
    run_once(args)
    print("Watching render files. Press Ctrl+C to stop.")
    while True:
        time.sleep(0.5)
        current = _snapshot(watched)
        if current == previous:
            continue
        previous = current
        for name in list(sys.modules):
            if name.startswith(
                (
                    "plugins.blackjack",
                    "plugins.mines",
                    "plugins.one_stroke",
                    "plugins.inventory",
                    "plugins.gacha",
                    "plugins.daily",
                    "plugins.mailbox",
                    "plugins.help",
                    "plugins.red_envelope",
                    "plugins.guess_chart",
                    "plugins.cck",
                )
            ):
                sys.modules.pop(name, None)
        print("Change detected. Regenerating...")
        run_once(args)


if __name__ == "__main__":
    main()
