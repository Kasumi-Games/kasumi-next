import re
import io
import csv
import random
import aiohttp
from rapidfuzz import process
from PIL import Image, ImageDraw
from bestdori.charts import Chart
from nonebot.adapters import Message
from nonebot.params import CommandArg
from typing import List, Dict, Any, Tuple
from bestdori.render import _utils as utils
from bestdori.render import config as render_config


diff_num = {
    "easy": "0",
    "normal": "1",
    "hard": "2",
    "expert": "3",
    "special": "4",
}

num_to_diff = {
    "0": "easy",
    "1": "normal",
    "2": "hard",
    "3": "expert",
    "4": "special",
}

game_difficulty_to_seconds = {
    "easy": 10,
    "normal": 8,
    "hard": 5,
    "expert": 2,
}


def non_slice_render(chart: Chart) -> Tuple[Image.Image, float]:
    """
    不切片渲染 bestdori 谱面

    参数:
        chart: 谱面对象 `bestdori.charts.Chart`
    """
    chart_data = chart.to_list()
    chart_data = utils.preprocess_chart(chart_data)
    height = utils.get_height(chart_data)
    chart_img, lane_range = utils.get_lanes(height, chart_data)

    chart_data = utils.corrent_chart(chart_data, lane_range)
    simplified_chart = utils.simplify_chart(chart_data)

    draw = ImageDraw.Draw(chart_img)

    bpm_data = utils.get_bpm_data(chart_data)
    beat_data = utils.get_beat_data(chart_data)

    utils.draw_measure_lines(bpm_data, draw, chart_img.width, height)
    utils.draw_double_tap_lines(simplified_chart, draw, height)

    utils.draw_notes(chart_data, chart_img, height)

    utils.draw_bpm_texts(bpm_data, draw, chart_img.width, height)
    utils.draw_beat_texts(beat_data, draw, chart_img.width, height)

    utils.draw_time_texts(draw, height)
    utils.draw_note_num(draw, chart_img.width, height, chart_data)

    _expect_sum_height = (
        chart_img.height // render_config.slice_height * render_config.expect_height
    )
    chart_img = chart_img.resize(
        (
            int(chart_img.width / chart_img.height * _expect_sum_height),
            _expect_sum_height,
        ),
        Image.Resampling.BILINEAR,
    )

    return chart_img, chart_img.height / height


def read_csv_to_dict(file_path: str):
    data_dict = {}
    with open(file_path, "r", encoding="UTF-8") as file:
        csv_reader = csv.reader(file)
        next(csv_reader)
        for row in csv_reader:
            key = row[0]  # 使用第一列作为字典的键
            values = row[1:]  # 使用剩余列作为字典的值
            if key is not None and values is not None and key != "":
                data_dict[key] = [value for value in values if value != ""]
    result = {}
    for key, values in data_dict.items():
        new_values = []
        for value in values:
            new_values.extend(value.split(","))
        result[key] = new_values
    return result


def fuzzy_match(query: str, dictionary: dict, threshold: int = 75):
    query_lower = query.lower()

    # 1. Exact match fast path (case-insensitive)
    for key, value in dictionary.items():
        if any(query_lower == nick.lower() for nick in value):
            return key

    if not is_valid_query(query):
        return None

    # 2. Flatten to single list, one global extract (case-insensitive)
    flat = [(nick.lower(), kid) for kid, nicks in dictionary.items() for nick in nicks]
    if not flat:
        return None
    results = process.extract(query_lower, [n for n, _ in flat], limit=5)

    # 3. Dynamic threshold: lower for CJK queries where one-char typos are common
    effective_threshold = threshold
    if any("一" <= c <= "鿿" or "㐀" <= c <= "䶿" for c in query):
        effective_threshold = max(threshold - 10, 60)

    best_song = None
    best_score = 0
    for matched_str, score, _ in results:
        if score < effective_threshold:
            break
        for nick, sid in flat:
            if nick == matched_str:
                if score > best_score:
                    best_score = score
                    best_song = sid
                elif score == best_score and best_song is not None:
                    if len(dictionary[sid]) > len(dictionary[best_song]):
                        best_song = sid
                break

    return best_song


def get_difficulty(args: Message = CommandArg()) -> str:
    arg = args.extract_plain_text().strip().lower()

    if arg in ["ez", "easy", "简单"]:
        return "easy"
    elif arg in ["nm", "normal", "普通"]:
        return "normal"
    elif arg in ["hd", "hard", "困难"]:
        return "hard"
    elif arg in ["ex", "expert", "专家"]:
        return "expert"
    else:
        return "normal"


def render_to_slices(chart: list, game_difficulty: str) -> Image.Image:
    chart_img, rate = non_slice_render(chart)

    height = chart_img.height
    # 每个切片展示 n s 的谱面
    slice_height = int(
        rate * render_config.pps * game_difficulty_to_seconds[game_difficulty]
    )

    # 随机抽取三段不重复的部分进行切片
    slices = Image.new(
        "RGB", (chart_img.width * 3, slice_height), render_config.bg_color
    )
    for i in range(3):
        start = random.randint(0, height - slice_height)
        cropped = chart_img.crop((0, start, chart_img.width, start + slice_height))
        slices.paste(
            cropped,
            (i * chart_img.width, 0),
            cropped.convert("RGBA").split()[3],
        )
    return slices


# Japanese shinjitai → Simplified Chinese mapping.
# Source: Chu, Nakazawa & Kurohashi (LREC 2012)
# "Chinese Characters Mapping Table of Japanese, Traditional Chinese and Simplified Chinese"
# https://aclanthology.org/L12-1070/
def _load_shinjitai_mapping() -> Dict[str, str]:
    """Load the LREC 2012 kanji mapping table, returning shinjitai→simplified dict."""
    import os as _os

    _path = _os.path.join(_os.path.dirname(__file__), "kanji_mapping_table.txt")
    _mapping: Dict[str, str] = {}
    with open(_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            if _line.startswith("-") or not _line.strip():
                continue
            _parts = _line.rstrip("\n").split("\t")
            if len(_parts) < 3:
                continue
            _kanji = _parts[0]
            _sc_first = _parts[2].split(",")[0]
            if _kanji != _sc_first:
                _mapping[_kanji] = _sc_first
    return _mapping


_SHINJITAI_TO_SIMPLIFIED: Dict[str, str] = _load_shinjitai_mapping()


def _convert_shinjitai(text: str) -> str:
    """Convert Japanese shinjitai kanji to simplified Chinese."""
    result = []
    for ch in text:
        result.append(_SHINJITAI_TO_SIMPLIFIED.get(ch, ch))
    return "".join(result)


def build_enriched_dictionary(
    nickname_dict: Dict[str, List[str]],
    song_raw_data: Dict[str, Dict[str, Any]],
) -> Dict[str, List[str]]:
    """
    Enrich nickname dictionary with auto-generated nicknames from song titles.
    - Strips hiragana/katakana from Japanese titles to extract kanji/English parts
    - Finds unique distinguishing English words from English-titled songs
    - Adds original musicTitle entries for direct title matching
    """
    enriched: Dict[str, List[str]] = {}
    for song_id, nicks in nickname_dict.items():
        enriched[song_id] = list(nicks)

    # Build song_id -> primary title mapping
    id_to_title: Dict[str, str] = {}
    for song_id, data in song_raw_data.items():
        if (
            data.get("musicTitle")
            and isinstance(data["musicTitle"], list)
            and data["musicTitle"]
        ):
            title = get_value_from_list(data["musicTitle"])
            if title:
                id_to_title[song_id] = title

    hiragana = set(chr(c) for c in range(0x3040, 0x309F + 1))
    katakana = set(chr(c) for c in range(0x30A0, 0x30FF + 1))
    kana = hiragana | katakana

    english_words_across_all: Dict[str, int] = {}

    for song_id, title in id_to_title.items():
        # --- Strip kana ---
        stripped = "".join(c for c in title if c not in kana)
        stripped = re.sub(r"[〜～\s_]+", " ", stripped).strip()
        stripped = re.sub(r"[「」『』【】()\[\]{}『』]", "", stripped)
        if stripped and len(stripped) >= 1:
            existing = {n.lower() for n in enriched.get(song_id, [])}
            if stripped.lower() not in existing:
                enriched.setdefault(song_id, []).append(stripped)

        # --- Aggressively clean: no symbols, no spaces, then shinjitai→simplified ---
        raw = "".join(c for c in title if c not in kana)
        raw = re.sub(r"[^\w一-鿿]", "", raw)
        raw_simplified = _convert_shinjitai(raw)
        if raw_simplified and len(raw_simplified) >= 1:
            existing = {n.lower() for n in enriched.get(song_id, [])}
            if raw_simplified.lower() not in existing:
                enriched.setdefault(song_id, []).append(raw_simplified)
        # Also add the unsimplified clean form if different
        if raw and raw != raw_simplified and len(raw) >= 1:
            existing = {n.lower() for n in enriched.get(song_id, [])}
            if raw.lower() not in existing:
                enriched.setdefault(song_id, []).append(raw)

        # --- Collect English words ---
        words = re.findall(r"[a-zA-Z]{2,}", title)
        for w in words:
            english_words_across_all[w.lower()] = (
                english_words_across_all.get(w.lower(), 0) + 1
            )

    # --- Add distinguishing English words ---
    for song_id, title in id_to_title.items():
        words = re.findall(r"[a-zA-Z]{2,}", title)
        unique_words = [
            w for w in words if english_words_across_all.get(w.lower(), 0) <= 2
        ]
        existing = {n.lower() for n in enriched.get(song_id, [])}
        if unique_words:
            distinctive = " ".join(unique_words)
            if distinctive.lower() not in existing:
                enriched.setdefault(song_id, []).append(distinctive)
        # Also add each unique word individually as a standalone nickname
        for w in unique_words:
            if w.lower() not in existing:
                enriched.setdefault(song_id, []).append(w)

    # --- Add original musicTitle entries ---
    for song_id, data in song_raw_data.items():
        if song_id not in enriched:
            enriched[song_id] = []
        if (
            data.get("musicTitle")
            and isinstance(data["musicTitle"], list)
            and data["musicTitle"]
        ):
            existing = {n.lower() for n in enriched[song_id]}
            for t in data["musicTitle"]:
                if t and isinstance(t, str) and t.lower() not in existing:
                    enriched[song_id].append(t)

    return enriched


def num_to_range(num: int):
    """将数字转换为区间

    e.g. 233 -> tuple(200, 300)
    """
    start = num // 100 * 100
    end = start + 100
    return start, end


def get_value_from_list(song_names: List[str]):
    return (
        song_names[3]
        or song_names[0]
        or song_names[2]
        or song_names[1]
        or song_names[4]
    )


def filter_song_data(song_data):
    return {
        k: v
        for k, v in song_data.items()
        if v.get("musicTitle")
        and isinstance(v["musicTitle"], list)
        and v["musicTitle"]
        and v["musicTitle"][0]
        and "[FULL]" not in v["musicTitle"][0]
        and "超高難易度" not in v["musicTitle"][0]
    }


def pil_image_to_bytes(image: Image.Image):
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format="PNG")
    img_byte_arr = img_byte_arr.getvalue()
    return img_byte_arr


def is_valid_query(query: str):
    stripped = query.strip()
    return (
        bool(stripped) and len(stripped) >= 2 and any(char.isalnum() for char in query)
    )


def _get_song_server(song_info: Dict[str, Any]) -> str:
    if (published_at := song_info.get("publishedAt", None)) is None:
        raise ValueError("缺少歌曲发布时间")
    # 根据 publishedAt 数据判断服务器
    if published_at[0] is not None:
        return "jp"
    elif published_at[1] is not None:
        return "en"
    elif published_at[2] is not None:
        return "tw"
    elif published_at[3] is not None:
        return "cn"
    elif published_at[4] is not None:
        return "kr"
    else:
        raise ValueError("无法判断歌曲服务器")


async def get_jacket_image(song_id: int, song_info: Dict[str, Any]) -> bytes:
    jacket_names = song_info.get("jacketImage", [])

    if not jacket_names:
        raise ValueError("No jacket image found")

    quotient, remainder = divmod(song_id, 10)
    if remainder == 0:
        index = song_id
    else:
        index = (quotient + 1) * 10

    jacket_url = "https://bestdori.com/assets/{server}/musicjacket/musicjacket{index:>02d}_rip/assets-star-forassetbundle-startapp-musicjacket-musicjacket{index:>02d}-{jacket_image}-jacket.png".format(
        index=index, jacket_image=jacket_names[0], server=_get_song_server(song_info)
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(jacket_url) as resp:
            return await resp.read()


def flatten_song_data(song_data: Dict[str, Dict[str, Any]]):
    result = []
    for song_id, song_info in song_data.items():
        for diff_number, play_level_dict in song_info["difficulty"].items():
            play_level = play_level_dict.get("playLevel", 0)
            result.append(
                {
                    "song_id": song_id,
                    "song_name": get_value_from_list(song_info["musicTitle"]),
                    "play_level": play_level,  # 1-30+
                    "difficulty": num_to_diff[
                        diff_number
                    ],  # easy, normal, hard, expert, special
                }
            )
    return result


def sort_by_difficulty(
    flattened_song_data: List[Dict[str, Any]],
) -> Dict[int, Dict[str, Any]]:
    result = {}
    for song in flattened_song_data:
        difficulty = song["play_level"]
        if difficulty not in result:
            result[difficulty] = []
        result[difficulty].append(song)
    return result
