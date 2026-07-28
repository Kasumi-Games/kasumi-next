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


def sync_seasons_config(now: int | None = None) -> list[Season]:
    config = load_seasons_config()
    timezone = config.get("timezone", DEFAULT_TIMEZONE)
    seasons = []
    session = get_session()

    _validate_seasons_config(config)
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
        config_hash = hashlib.sha256(metadata_json.encode("utf-8")).hexdigest()
        if row.settled_at:
            if row.config_hash and row.config_hash != config_hash:
                logger.warning(
                    f"Ignoring config changes for settled season {row.season_key}"
                )
            seasons.append(row)
            continue
        row.season_number = int(entry["number"])
        row.name = entry["name"]
        authored_start = _parse_time(entry["starts_at"])
        if entry.get("start_on_deployment") and row.opened_at:
            row.start_time = row.opened_at
        else:
            row.start_time = authored_start
        row.end_time = _parse_time(entry["ends_at"])
        row.timezone = timezone
        row.metadata_json = metadata_json
        row.config_hash = config_hash
        seasons.append(row)

    _prune_scrapped_seasons(session, {entry["season_key"] for entry in config.get("seasons", [])})
    session.commit()
    refresh_season_statuses(now=now)
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
        elif season.status == "settling":
            status = "settling"
        elif season.start_time <= now < season.end_time and season.opened_at:
            status = "open"
        elif now < season.start_time:
            status = "planned"
        elif now < season.end_time and not season.opened_at:
            status = "planned"
        else:
            status = "ended"
        if season.status != status:
            season.status = status
            changed = True
    if changed:
        session.commit()


def activate_due_seasons(now: int | None = None) -> int:
    """Record the one-time transition from planned configuration to open."""

    now = int(time.time()) if now is None else now
    seasons = get_due_seasons(now=now)
    session = get_session()
    for season in seasons:
        if get_season_metadata(season).get("start_on_deployment"):
            season.start_time = now
        season.opened_at = now
        season.status = "open"
        logger.info(f"Season opened: {season.season_key}")
    if seasons:
        session.commit()
    return len(seasons)


def get_due_seasons(now: int | None = None) -> list[Season]:
    """Return due seasons without exposing them to commands yet."""

    now = int(time.time()) if now is None else now
    sync_seasons_config(now=now)
    candidates = (
        get_session()
        .query(Season)
        .filter(
            Season.end_time > now,
            Season.opened_at == 0,
            Season.settled_at == 0,
        )
        .order_by(Season.start_time.asc())
        .all()
    )
    return [
        season
        for season in candidates
        if season.start_time <= now
        or get_season_metadata(season).get("start_on_deployment")
    ]


def get_current_season(now: int | None = None) -> Optional[Season]:
    now = int(time.time()) if now is None else now
    sync_seasons_config(now=now)
    session = get_session()
    return (
        session.query(Season)
        # A settled season is over even inside its time window: an early
        # (admin) settlement must close the Pt scope and the gacha banner
        # immediately, not at the configured end date.
        .filter(
            Season.start_time <= now,
            Season.end_time > now,
            Season.opened_at > 0,
            Season.settled_at == 0,
        )
        .order_by(Season.start_time.desc())
        .first()
    )


def get_current_season_bounds(now: int | None = None) -> tuple[int, int] | None:
    """Return the inclusive/exclusive time range for the open season.

    Game plugins keep their own databases, so their records are associated with
    a season by their existing completion timestamp rather than a cross-database
    foreign key.  ``None`` deliberately means that no season is open; callers
    can then avoid presenting off-season games as next season's records.
    """

    season = get_current_season(now=now)
    if season is None:
        return None
    return season.start_time, season.end_time


def get_next_season(now: int | None = None) -> Season | None:
    """Return the next configured, unsettled season after ``now``."""

    now = int(time.time()) if now is None else now
    sync_seasons_config(now=now)
    return (
        get_session()
        .query(Season)
        .filter(
            Season.end_time > now,
            Season.opened_at == 0,
            Season.settled_at == 0,
        )
        .order_by(Season.start_time.asc())
        .first()
    )


def get_season_by_key(season_key: str) -> Season | None:
    sync_seasons_config()
    return get_session().query(Season).filter(Season.season_key == season_key).first()


def get_latest_season(now: int | None = None) -> Season | None:
    now = int(time.time()) if now is None else now
    sync_seasons_config(now=now)
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
    now = int(time.time()) if now is None else now
    sync_seasons_config(now=now)
    session = get_session()
    previous_candidates = (
        session.query(Season)
        .filter(Season.start_time <= now)
        .order_by(Season.start_time.desc())
        .all()
    )
    previous = next(
        (
            season
            for season in previous_candidates
            if season.end_time <= now or season.settled_at
        ),
        None,
    )
    next_season = (
        session.query(Season)
        .filter(
            Season.end_time > now,
            Season.opened_at == 0,
            Season.settled_at == 0,
        )
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


def get_season_starting_points(season_id: str | int) -> int:
    season = (
        get_session().query(Season).filter(Season.id == int(season_id)).first()
    )
    if season is None:
        return 0
    return int(get_season_metadata(season).get("starting_points", 0))


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
    now = int(time.time()) if now is None else now
    sync_seasons_config(now=now)
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


def settle_season(
    season_key: str,
    now: int | None = None,
    *,
    force: bool = False,
) -> int:
    now = int(time.time()) if now is None else now
    season = get_season_by_key(season_key)
    if season is None:
        raise ValueError(f"unknown season: {season_key}")
    if season.settled_at:
        raise ValueError(f"{season.name} 已经结算")
    if now < season.start_time:
        raise ValueError(f"{season.name} 尚未开始，不能结算")
    if now < season.end_time and not force:
        raise ValueError("赛季尚未到结束时间；提前结算必须显式使用 --force")

    session = get_session()
    if not season.opened_at:
        season.opened_at = season.start_time
    season.status = "settling"
    session.commit()
    try:
        ranking_rows = _season_point_query(season.id).all()
        metadata = get_season_metadata(season)
        reward_tiers = metadata.get("reward_tiers", [])
        participation_tier = _participation_tier(metadata)
        participated_user_ids = _participated_user_ids(season.id)
        existing_rankings = {
            row.user_id: row
            for row in session.query(SeasonRanking)
            .filter(SeasonRanking.season_id == season.id)
            .all()
        }
        existing_rewards = {
            row.user_id
            for row in session.query(SeasonReward.user_id)
            .filter(SeasonReward.season_id == season.id)
            .all()
        }
        created_rewards = 0

        for idx, row in enumerate(ranking_rows, start=1):
            ranking = existing_rankings.get(row.user_id)
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
                if _ensure_reward_record(
                    season,
                    row.user_id,
                    idx,
                    row.quantity,
                    tier,
                    now,
                    existing_rewards,
                ):
                    created_rewards += 1
            else:
                ranking.reward_summary_json = "{}"

        ranked_user_ids = {row.user_id for row in ranking_rows}
        if participation_tier:
            for user_id in sorted(participated_user_ids - ranked_user_ids):
                if _ensure_reward_record(
                    season,
                    user_id,
                    0,
                    0,
                    participation_tier,
                    now,
                    existing_rewards,
                ):
                    created_rewards += 1

        season.settled_at = now
        season.status = "settled"
        session.commit()
    except Exception:
        session.rollback()
        failed_season = (
            session.query(Season).filter(Season.season_key == season_key).first()
        )
        if failed_season is not None and not failed_season.settled_at:
            failed_season.status = (
                "open" if now < failed_season.end_time else "ended"
            )
            session.commit()
        raise

    logger.info(
        f"Season settled: {season.season_key}, rankings={len(ranking_rows)}, rewards={created_rewards}"
    )
    dispatch_pending_season_rewards(season_id=season.id)
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


def settlement_preview(season_key: str) -> dict[str, int | str]:
    """Return the immutable facts an operator should inspect before settling."""

    season = get_season_by_key(season_key)
    if season is None:
        raise ValueError(f"unknown season: {season_key}")
    ranking_rows = _season_point_query(season.id).all()
    metadata = get_season_metadata(season)
    reward_tiers = metadata.get("reward_tiers", [])
    participation_tier = _participation_tier(metadata)
    participated_user_ids = _participated_user_ids(season.id)
    rewarded_user_ids: set[str] = set()
    for rank, row in enumerate(ranking_rows, start=1):
        if _reward_tier_for_rank(reward_tiers, rank) is not None:
            rewarded_user_ids.add(row.user_id)
        elif participation_tier and row.user_id in participated_user_ids:
            rewarded_user_ids.add(row.user_id)
    if participation_tier:
        rewarded_user_ids.update(participated_user_ids)
    pending = (
        get_session()
        .query(SeasonReward)
        .filter(SeasonReward.season_id == season.id, SeasonReward.mail_id == 0)
        .count()
    )
    return {
        "season_key": season.season_key,
        "status": season.status,
        "rankings": len(ranking_rows),
        "participants": len(participated_user_ids),
        "reward_mails": len(rewarded_user_ids),
        "pending_mails": pending,
    }


def _ensure_reward_record(
    season: Season,
    user_id: str,
    rank: int,
    points: int,
    tier: dict[str, Any],
    now: int,
    existing_user_ids: set[str],
) -> bool:
    session = get_session()
    if user_id in existing_user_ids:
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
    existing_user_ids.add(user_id)
    return True


def dispatch_pending_season_rewards(season_id: int | None = None) -> int:
    """Deliver durable reward records through an idempotent mailbox boundary.

    The ranking/reward transaction commits before this dispatcher runs.
    Mailbox ``external_key`` makes a retry return the original mail if the
    process died after the mailbox commit but before ``mail_id`` was saved.
    Failures stay as ``mail_id == 0`` and are retried by the lifecycle job.
    """

    session = get_session()
    query = session.query(SeasonReward.id).filter(SeasonReward.mail_id == 0)
    if season_id is not None:
        query = query.filter(SeasonReward.season_id == season_id)
    reward_ids = [row[0] for row in query.order_by(SeasonReward.id.asc()).all()]
    delivered = 0

    from ..mailbox.service import MailService

    for reward_id in reward_ids:
        reward = (
            session.query(SeasonReward)
            .filter(SeasonReward.id == reward_id, SeasonReward.mail_id == 0)
            .first()
        )
        if reward is None:
            continue
        season = session.query(Season).filter(Season.id == reward.season_id).first()
        if season is None:
            logger.error(f"Season reward {reward.id} has no season")
            continue
        tier = json.loads(reward.reward_json or "{}")
        attachments = [
            ItemAmount(item_id=item["item_id"], quantity=int(item["quantity"]))
            for item in tier.get("items", [])
        ]
        if reward.rank > 0:
            content = (
                f"{season.name} 已结束！你以 {reward.points} Pt 获得第 {reward.rank} 名。\n"
                "奖励已经放在这封邮件里了，感谢参与本赛季。"
            )
        else:
            content = (
                f"{season.name} 已结束！你完成了本赛季参与。\n"
                "奖励已经放在这封邮件里了，感谢参与本赛季。"
            )
        try:
            mail_id = MailService().send_mail(
                recipient_id=reward.user_id,
                title=f"{season.name} {tier.get('title', '赛季奖励')}",
                content=content,
                attachments=attachments,
                expire_days=30,
                sender_id="season",
                external_key=f"season_reward:{season.id}:{reward.user_id}",
            )
            reward.mail_id = mail_id
            session.commit()
            delivered += 1
        except Exception:
            session.rollback()
            logger.opt(exception=True).error(
                f"Season reward delivery failed: reward_id={reward_id}"
            )
    return delivered


def _season_point_query(season_id: int):
    return (
        get_session()
        .query(UserItem)
        .join(
            SeasonParticipation,
            (SeasonParticipation.season_id == season_id)
            & (SeasonParticipation.user_id == UserItem.user_id),
        )
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


def _validate_seasons_config(config: dict[str, Any]) -> None:
    try:
        offseason_points = int(
            config.get(
                "offseason_starting_points",
                DEFAULT_OFFSEASON_STARTING_POINTS,
            )
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("offseason_starting_points must be an integer") from exc
    if offseason_points < 0:
        raise ValueError("offseason_starting_points cannot be negative")

    seen_keys: set[str] = set()
    seen_numbers: set[int] = set()
    timeline: list[tuple[int, int, str]] = []
    for entry in config.get("seasons", []):
        try:
            season_key = str(entry["season_key"]).strip()
            season_number = int(entry["number"])
            start_time = _parse_time(entry["starts_at"])
            end_time = _parse_time(entry["ends_at"])
            starting_points = int(entry.get("starting_points", 0))
            snapshot_interval = int(
                entry.get("snapshot_interval_minutes", 60)
            )
        except KeyError as exc:
            raise ValueError(f"season config missing field: {exc.args[0]}") from exc
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"invalid numeric value in season {entry.get('season_key', '?')}"
            ) from exc

        if not season_key:
            raise ValueError("season_key cannot be empty")
        if season_key in seen_keys:
            raise ValueError(f"duplicate season_key: {season_key}")
        if season_number <= 0 or season_number in seen_numbers:
            raise ValueError(f"invalid or duplicate season number: {season_number}")
        if start_time >= end_time:
            raise ValueError(f"season {season_key} must end after it starts")
        if starting_points < 0:
            raise ValueError(f"season {season_key} starting_points cannot be negative")
        if snapshot_interval <= 0:
            raise ValueError(
                f"season {season_key} snapshot_interval_minutes must be positive"
            )

        snapshot_ranks = [int(rank) for rank in entry.get("snapshot_ranks", [10, 50])]
        if (
            any(rank <= 0 for rank in snapshot_ranks)
            or len(snapshot_ranks) != len(set(snapshot_ranks))
        ):
            raise ValueError(
                f"season {season_key} snapshot_ranks must be unique positive integers"
            )

        tiers = list(entry.get("reward_tiers", []))
        tier_keys: set[str] = set()
        ranges: list[tuple[int, int, str]] = []
        for tier in tiers:
            tier_key = _validate_reward_tier(season_key, tier, needs_range=True)
            if tier_key in tier_keys:
                raise ValueError(
                    f"season {season_key} duplicate reward tier: {tier_key}"
                )
            tier_keys.add(tier_key)
            ranges.append(
                (int(tier["from_rank"]), int(tier["to_rank"]), tier_key)
            )
        participation = entry.get("participation_reward")
        if participation:
            tier_key = _validate_reward_tier(
                season_key, participation, needs_range=False
            )
            if tier_key in tier_keys:
                raise ValueError(
                    f"season {season_key} duplicate reward tier: {tier_key}"
                )
        ranges.sort()
        for previous, current in zip(ranges, ranges[1:], strict=False):
            if current[0] <= previous[1]:
                raise ValueError(
                    f"season {season_key} reward tiers overlap: "
                    f"{previous[2]} and {current[2]}"
                )

        seen_keys.add(season_key)
        seen_numbers.add(season_number)
        timeline.append((start_time, end_time, season_key))

    timeline.sort()
    for previous, current in zip(timeline, timeline[1:], strict=False):
        if current[0] < previous[1]:
            raise ValueError(
                f"season timelines overlap: {previous[2]} and {current[2]}"
            )


def _validate_reward_tier(
    season_key: str,
    tier: dict[str, Any],
    *,
    needs_range: bool,
) -> str:
    tier_key = str(tier.get("tier_key", "")).strip()
    if not tier_key:
        raise ValueError(f"season {season_key} reward tier needs tier_key")
    if needs_range:
        try:
            from_rank = int(tier["from_rank"])
            to_rank = int(tier["to_rank"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"season {season_key} tier {tier_key} has invalid rank range"
            ) from exc
        if from_rank <= 0 or to_rank < from_rank:
            raise ValueError(
                f"season {season_key} tier {tier_key} has invalid rank range"
            )
    for item in tier.get("items", []):
        try:
            quantity = int(item["quantity"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"season {season_key} tier {tier_key} has invalid quantity"
            ) from exc
        if quantity <= 0:
            raise ValueError(
                f"season {season_key} tier {tier_key} quantity must be positive"
            )
    return tier_key


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
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError(f"season timestamp needs an explicit UTC offset: {value}")
    return int(parsed.timestamp())
