import io
import csv
import random
import aiohttp
from fuzzywuzzy import process
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


def fuzzy_match(query: str, dictionary: dict):
    max_ratio = 0
    matched_key = None
    for key, value in dictionary.items():
        if query in value:
            return key
        if not is_valid_query(query):
            continue
        _, ratio = process.extractOne(query, value) or (0, 0)
        if ratio > max_ratio:
            max_ratio = ratio
            matched_key = key
    return matched_key


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
    # elif arg == "":
    #     return "normal"
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


def compare_origin_songname(guessed_name: str, song_data: Dict[str, Dict[str, Any]]):
    for key, data in song_data.items():
        if guessed_name in data["musicTitle"]:
            return key
    return None


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
    # 去除空白后非空，且含有至少一个字母数字字符
    return bool(query.strip()) and any(char.isalnum() for char in query)


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
