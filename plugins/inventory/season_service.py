"""Season metadata, lifecycle, snapshots, and settlement."""

import json
import time
import hashlib
from typing import Any
from typing import Optional
from pathlib import Path
from datetime import datetime

from nonebot.log import logger

from .models import SEASON_SCOPE_TYPE
from .models import OFFSEASON_SCOPE_TYPE
from .models import SEASON_POINT_ITEM_ID
from .models import Item
from .models import Season
from .models import UserItem
from .models import ItemAmount
from .models import SeasonReward
from .models import SeasonRanking
from .models import SeasonRankSnapshot
from .models import SeasonParticipation
from .database import get_session

SEASONS_PATH = Path(__file__).with_name("seasons.json")
DEFAULT_TIMEZONE = "UTC+8"
DEFAULT_OFFSEASON_STARTING_POINTS = 100


def load_seasons_config() -> dict[str, Any]:
    with open(SEASONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def sync_seasons_config() -> list[Season]:
    config = load_seasons_config()
    timezone = config.get("timezone", DEFAULT_TIMEZONE)
    seasons = []
    session = get_session()

    _validate_reward_items(config)

    for entry in config.get("seasons", []):
        season_key = entry["season_key"]
        row = session.query(Season).filter(Season.season_key == season_key).first()
        if row is None:
            row = (
                session.query(Season)
                .filter(Season.season_number == int(entry["number"]))
                .first()
            )
            if row is None:
                row = Season(season_key=season_key)
                session.add(row)
            else:
                row.season_key = season_key

        metadata_json = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        row.season_number = int(entry["number"])
        row.name = entry["name"]
        row.start_time = _parse_time(entry["starts_at"])
        row.end_time = _parse_time(entry["ends_at"])
        row.timezone = timezone
        row.metadata_json = metadata_json
        row.config_hash = hashlib.sha256(metadata_json.encode("utf-8")).hexdigest()
        seasons.append(row)

    _prune_scrapped_seasons(session, {entry["season_key"] for entry in config.get("seasons", [])})
    session.commit()
    refresh_season_statuses()
    return seasons


def _prune_scrapped_seasons(session, config_keys: set[str]) -> None:
    """Delete database seasons that were scrapped from the config before running.

    Only seasons that never happened are touched: a row is removed when its key
    is gone from ``seasons.json``, it never left the ``planned`` state, and it
    has no rankings, rewards, or participation. Anything a player interacted
    with stays, even if its config disappears — that is a data problem to solve
    by hand, not silently.
    """

    orphans = (
        session.query(Season)
        .filter(~Season.season_key.in_(config_keys))
        .all()
        if config_keys
        else session.query(Season).all()
    )
    for season in orphans:
        if season.status not in ("planned", ""):
            continue
        if season.settled_at:
            continue
        has_history = any(
            session.query(model).filter(model.season_id == season.id).first()
            is not None
            for model in (SeasonRanking, SeasonReward, SeasonParticipation)
        )
        if has_history:
            continue
        session.delete(season)


def refresh_season_statuses(now: int | None = None) -> None:
    now = int(time.time()) if now is None else now
    session = get_session()
    changed = False
    for season in session.query(Season).all():
        if season.settled_at:
            status = "settled"
        elif season.start_time <= now < season.end_time:
            status = "open"
        elif now < season.start_time:
            status = "planned"
        else:
            status = "ended"
        if season.status != status:
            season.status = status
            changed = True
    if changed:
        session.commit()


def get_current_season(now: int | None = None) -> Optional[Season]:
    sync_seasons_config()
    now = int(time.time()) if now is None else now
    session = get_session()
    return (
        session.query(Season)
        .filter(Season.start_time <= now, Season.end_time > now)
        .order_by(Season.start_time.desc())
        .first()
    )


def get_season_by_key(season_key: str) -> Season | None:
    sync_seasons_config()
    return get_session().query(Season).filter(Season.season_key == season_key).first()


def get_latest_season(now: int | None = None) -> Season | None:
    sync_seasons_config()
    now = int(time.time()) if now is None else now
    session = get_session()
    return (
        session.query(Season)
        .filter(Season.start_time <= now)
        .order_by(Season.start_time.desc())
        .first()
    )


def get_season_name(season_id: str | int) -> str:
    session = get_session()
    season = session.query(Season).filter(Season.id == int(season_id)).first()
    if season is None:
        return f"赛季 {season_id}"
    return season.name


def get_point_scope(now: int | None = None) -> tuple[str, str, Season | None]:
    season = get_current_season(now=now)
    if season is not None:
        return SEASON_SCOPE_TYPE, str(season.id), season
    return OFFSEASON_SCOPE_TYPE, get_offseason_scope_id(now=now), None


def get_offseason_scope_id(now: int | None = None) -> str:
    sync_seasons_config()
    now = int(time.time()) if now is None else now
    session = get_session()
    previous = (
        session.query(Season)
        .filter(Season.end_time <= now)
        .order_by(Season.end_time.desc())
        .first()
    )
    next_season = (
        session.query(Season)
        .filter(Season.start_time > now)
        .order_by(Season.start_time.asc())
        .first()
    )
    prev_key = previous.season_key if previous else "before-first-season"
    next_key = next_season.season_key if next_season else "after-last-season"
    return f"{prev_key}_to_{next_key}"


def get_offseason_starting_points() -> int:
    config = load_seasons_config()
    return int(
        config.get("offseason_starting_points", DEFAULT_OFFSEASON_STARTING_POINTS)
    )


def get_season_metadata(season: Season) -> dict[str, Any]:
    if not season.metadata_json:
        return {}
    return json.loads(season.metadata_json)


def mark_participated(user_id: str, season_id: int, now: int | None = None) -> None:
    now = int(time.time()) if now is None else now
    session = get_session()
    row = (
        session.query(SeasonParticipation)
        .filter(
            SeasonParticipation.season_id == season_id,
            SeasonParticipation.user_id == user_id,
        )
        .first()
    )
    if row is None:
        row = SeasonParticipation(
            season_id=season_id,
            user_id=user_id,
            first_participated_at=now,
            last_participated_at=now,
        )
        session.add(row)
        session.flush()
        return
    row.last_participated_at = now


def get_active_ranking(limit: int = 50, season: Season | None = None) -> list[UserItem]:
    season = season or get_current_season()
    if season is None:
        return []
    return _season_point_query(season.id).limit(limit).all()


def get_user_season_rank(user_id: str, season: Season | None = None) -> tuple[int, int]:
    season = season or get_current_season()
    if season is None:
        return 0, 0
    rows = _season_point_query(season.id).all()
    for idx, row in enumerate(rows, start=1):
        if row.user_id == user_id:
            return idx, row.quantity
    return len(rows) + 1, 0


def capture_rank_snapshots(now: int | None = None) -> int:
    now = int(time.time()) if now is None else now
    season = get_current_season(now=now)
    if season is None:
        return 0

    metadata = get_season_metadata(season)
    interval = int(metadata.get("snapshot_interval_minutes", 60)) * 60
    captured_at = now - (now % interval) if interval > 0 else now
    ranks = metadata.get("snapshot_ranks", [10, 50])
    rows = _season_point_query(season.id).all()
    session = get_session()
    created = 0

    for rank in ranks:
        rank = int(rank)
        existing = (
            session.query(SeasonRankSnapshot)
            .filter(
                SeasonRankSnapshot.season_id == season.id,
                SeasonRankSnapshot.captured_at == captured_at,
                SeasonRankSnapshot.rank == rank,
            )
            .first()
        )
        if existing is not None:
            continue
        target = rows[rank - 1] if len(rows) >= rank else None
        session.add(
            SeasonRankSnapshot(
                season_id=season.id,
                captured_at=captured_at,
                rank=rank,
                user_id=target.user_id if target else "",
                points=target.quantity if target else None,
            )
        )
        created += 1

    if created:
        session.commit()
    return created


def settle_due_seasons(now: int | None = None) -> int:
    sync_seasons_config()
    now = int(time.time()) if now is None else now
    session = get_session()
    seasons = (
        session.query(Season)
        .filter(Season.end_time <= now, Season.settled_at == 0)
        .order_by(Season.end_time.asc())
        .all()
    )
    settled = 0
    for season in seasons:
        settle_season(season.season_key, now=now)
        settled += 1
    return settled


def settle_season(season_key: str, now: int | None = None) -> int:
    now = int(time.time()) if now is None else now
    season = get_season_by_key(season_key)
    if season is None:
        raise ValueError(f"unknown season: {season_key}")

    session = get_session()
    ranking_rows = _season_point_query(season.id).all()
    metadata = get_season_metadata(season)
    reward_tiers = metadata.get("reward_tiers", [])
    participation_tier = _participation_tier(metadata)
    participated_user_ids = _participated_user_ids(season.id)
    created_rewards = 0

    for idx, row in enumerate(ranking_rows, start=1):
        ranking = (
            session.query(SeasonRanking)
            .filter(
                SeasonRanking.season_id == season.id,
                SeasonRanking.user_id == row.user_id,
            )
            .first()
        )
        if ranking is None:
            ranking = SeasonRanking(season_id=season.id, user_id=row.user_id)
            session.add(ranking)
        ranking.final_points = row.quantity
        ranking.rank = idx

        tier = _reward_tier_for_rank(reward_tiers, idx)
        if row.user_id in participated_user_ids:
            tier = _merge_reward_tiers(tier, participation_tier)
        if tier:
            reward_json = json.dumps(tier, ensure_ascii=False, sort_keys=True)
            ranking.reward_summary_json = reward_json
            if _ensure_reward_mail(season, row.user_id, idx, row.quantity, tier, now):
                created_rewards += 1
        else:
            ranking.reward_summary_json = "{}"

    ranked_user_ids = {row.user_id for row in ranking_rows}
    if participation_tier:
        for user_id in sorted(participated_user_ids - ranked_user_ids):
            if _ensure_reward_mail(season, user_id, 0, 0, participation_tier, now):
                created_rewards += 1

    season.settled_at = now
    season.status = "settled"
    session.commit()
    logger.info(
        f"Season settled: {season.season_key}, rankings={len(ranking_rows)}, rewards={created_rewards}"
    )
    return len(ranking_rows)


def grant_featured_character_reward(
    user_id: str,
    season_key: str,
    character_id: str,
    *,
    idempotency_key: str | None = None,
):
    season = get_season_by_key(season_key)
    if season is None:
        raise ValueError(f"unknown season: {season_key}")
    metadata = get_season_metadata(season)
    character = _featured_character(metadata, character_id)
    if character is None:
        raise ValueError(f"unknown featured character: {character_id}")

    from .service import grant_item
    from .service import get_quantity

    featured = metadata.get("featured_characters", [])
    owned_before = any(
        get_quantity(user_id, _standing_art_item_id(entry)) > 0
        for entry in featured
        if _standing_art_item_id(entry)
    )
    results = [
        grant_item(
            user_id,
            _standing_art_item_id(character),
            1,
            "season_gacha_featured_character",
            source_type="season_gacha",
            source_id=f"{season.season_key}:{character_id}",
            idempotency_key=idempotency_key,
        )
    ]
    if owned_before:
        return results

    frame_item_id = metadata.get("gacha_character_frame_item_id")
    theme_item_id = metadata.get("gacha_theme_item_id")
    for item_id in (frame_item_id, theme_item_id):
        if item_id:
            results.append(
                grant_item(
                    user_id,
                    item_id,
                    1,
                    "season_gacha_first_featured_character",
                    source_type="season_gacha",
                    source_id=f"{season.season_key}:{character_id}",
                    idempotency_key=idempotency_key,
                )
            )
    return results


def list_settled_rankings(season: Season, limit: int = 50) -> list[SeasonRanking]:
    return (
        get_session()
        .query(SeasonRanking)
        .filter(SeasonRanking.season_id == season.id)
        .order_by(SeasonRanking.rank.asc())
        .limit(limit)
        .all()
    )


def list_snapshots(season: Season) -> list[SeasonRankSnapshot]:
    return (
        get_session()
        .query(SeasonRankSnapshot)
        .filter(SeasonRankSnapshot.season_id == season.id)
        .order_by(SeasonRankSnapshot.captured_at.asc(), SeasonRankSnapshot.rank.asc())
        .all()
    )


def _ensure_reward_mail(
    season: Season,
    user_id: str,
    rank: int,
    points: int,
    tier: dict[str, Any],
    now: int,
) -> bool:
    session = get_session()
    existing = (
        session.query(SeasonReward)
        .filter(SeasonReward.season_id == season.id, SeasonReward.user_id == user_id)
        .first()
    )
    if existing is not None:
        return False

    reward_json = json.dumps(tier, ensure_ascii=False, sort_keys=True)
    reward = SeasonReward(
        season_id=season.id,
        user_id=user_id,
        tier_key=tier["tier_key"],
        rank=rank,
        points=points,
        reward_json=reward_json,
        created_at=now,
    )
    session.add(reward)
    session.flush()

    from ..mailbox.service import MailService

    attachments = [
        ItemAmount(item_id=item["item_id"], quantity=int(item["quantity"]))
        for item in tier.get("items", [])
    ]
    if rank > 0:
        content = (
            f"{season.name} 已结束！你以 {points} Pt 获得第 {rank} 名。\n"
            "奖励已经放在这封邮件里了，感谢参与本赛季。"
        )
    else:
        content = (
            f"{season.name} 已结束！你完成了本赛季参与。\n"
            "奖励已经放在这封邮件里了，感谢参与本赛季。"
        )
    mail_id = MailService().send_mail(
        recipient_id=user_id,
        title=f"{season.name} {tier.get('title', '赛季奖励')}",
        content=content,
        attachments=attachments,
        expire_days=30,
        sender_id="season",
    )
    reward.mail_id = mail_id
    return True


def _season_point_query(season_id: int):
    return (
        get_session()
        .query(UserItem)
        .filter(
            UserItem.item_id == SEASON_POINT_ITEM_ID,
            UserItem.scope_type == SEASON_SCOPE_TYPE,
            UserItem.scope_id == str(season_id),
        )
        .order_by(UserItem.quantity.desc(), UserItem.user_id.asc())
    )


def _reward_tier_for_rank(
    tiers: list[dict[str, Any]], rank: int
) -> dict[str, Any] | None:
    for tier in tiers:
        if int(tier["from_rank"]) <= rank <= int(tier["to_rank"]):
            return tier
    return None


def _participation_tier(metadata: dict[str, Any]) -> dict[str, Any] | None:
    if tier := metadata.get("participation_reward"):
        return tier
    for tier in metadata.get("reward_tiers", []):
        if tier.get("tier_key") == "participation":
            return tier
    return None


def _participated_user_ids(season_id: int) -> set[str]:
    rows = (
        get_session()
        .query(SeasonParticipation.user_id)
        .filter(SeasonParticipation.season_id == season_id)
        .all()
    )
    return {row[0] for row in rows}


def _merge_reward_tiers(
    rank_tier: dict[str, Any] | None, participation_tier: dict[str, Any] | None
) -> dict[str, Any] | None:
    if rank_tier is None:
        return participation_tier
    if participation_tier is None:
        return rank_tier
    items = list(rank_tier.get("items", []))
    existing_item_ids = {item.get("item_id") for item in items}
    for item in participation_tier.get("items", []):
        if item.get("item_id") not in existing_item_ids:
            items.append(item)
    merged = dict(rank_tier)
    merged["items"] = items
    merged["participation_tier_key"] = participation_tier.get("tier_key")
    return merged


def _featured_character(
    metadata: dict[str, Any], character_id: str
) -> dict[str, Any] | None:
    for character in metadata.get("featured_characters", []):
        if str(character.get("character_id")) == character_id:
            return character
    return None


def _standing_art_item_id(character: dict[str, Any]) -> str:
    return character.get("standing_art_item_id") or character.get("item_id", "")


def _validate_reward_items(config: dict[str, Any]) -> None:
    session = get_session()
    known_item_ids = {row.item_id for row in session.query(Item.item_id).all()}
    missing = []
    for season in config.get("seasons", []):
        for item_id in (
            season.get("gacha_character_frame_item_id"),
            season.get("gacha_theme_item_id"),
        ):
            if item_id and item_id not in known_item_ids:
                missing.append(item_id)
        for character in season.get("featured_characters", []):
            item_id = _standing_art_item_id(character)
            if item_id and item_id not in known_item_ids:
                missing.append(item_id)
        if banner := season.get("gacha_banner"):
            for entry in banner.get("entries", []):
                item_id = entry.get("item_id")
                if item_id and item_id not in known_item_ids:
                    missing.append(item_id)
        for tier in season.get("reward_tiers", []):
            for item in tier.get("items", []):
                if item["item_id"] not in known_item_ids:
                    missing.append(item["item_id"])
        if tier := season.get("participation_reward"):
            for item in tier.get("items", []):
                if item["item_id"] not in known_item_ids:
                    missing.append(item["item_id"])
    if missing:
        raise ValueError(
            f"Unknown season reward item ids: {', '.join(sorted(set(missing)))}"
        )


def _parse_time(value: str) -> int:
    return int(datetime.fromisoformat(value).timestamp())
