import aiohttp
from typing import Optional, Dict, List


async def call_synthesize_api(
    text: str,
    length_scale: Optional[float] = 1.0,
    language: Optional[str] = "Auto",
    sdp_ratio: Optional[float] = 0.5,
    noise_scale: Optional[float] = 0.6,
    noise_scale_w: Optional[float] = 0.667,
    speaker_id: Optional[int] = 4,
    style_text: Optional[str] = None,
    style_weight: Optional[float] = 0.7,
    url: Optional[str] = "http://127.0.0.1:4371/synthesize",
) -> bytes:
    """调用 Bert VITS API 生成语音

    Args:
        text (str): 要转化为语音的文本.
        length_scale (Optional[float]): 语速调节. Defaults to 1.0.
        language (Optional[str]): 语言. Defaults to "Auto".
        sdp_ratio (Optional[float]): SDP/DP混合比. Defaults to 0.5.
        noise_scale (Optional[float]): 感情调节. Defaults to 0.6.
        noise_scale_w (Optional[float]): 音素长度. Defaults to 0.667.
        speaker_id (Optional[int]): 说话人. Defaults to 4.
        style_text (Optional[str]): 情感辅助文本. 使用辅助文本的语意来辅助生成对话(语言保持与主文本相同). 注意: 不要使用指令式文本(如: 开心), 要使用带有强烈情感的文本(如: 我好快乐！！！). Defaults to None.
        style_weight (Optional[float]): 主文本和辅助文本的bert混合比率，0表示仅主文本，1表示仅辅助文本. Defaults to 0.7.
        url (Optional[str]): 请求地址. Defaults to "http://127.0.0.1:4371/synthesize".

    Raises:
        Exception: 请求失败时返回错误信息.

    Returns:
        bytes: API 的响应数据，即 wav 格式的 bytes 对象，或者在请求失败时返回错误信息.
    """

    input_data = {
        "length_scale": length_scale,
        "language": language,
        "sdp_ratio": sdp_ratio,
        "noise_scale": noise_scale,
        "noise_scale_w": noise_scale_w,
        "speaker_id": speaker_id,
        "text": text,
        "style_text": style_text,
        "style_weight": style_weight,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=input_data) as response:
            if response.status == 200:
                return await response.read()
            else:
                response.raise_for_status()


async def call_speaker_api(
    url: str = "http://127.0.0.1:4371/speakers",
) -> Dict[str, str]:
    """调用 Bert VITS API 获取说话人列表

    Args:
        url (str): 请求地址. Defaults to "http://127.0.0.1:4371/speakers".

    Raises:
        Exception: 请求失败时返回错误信息.

    Returns:
        Dict[str, str]: 说话人列表，或者在请求失败时返回错误信息.
    """

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            else:
                response.raise_for_status()


def match_character(string: str, characters: Dict[str, List[str]]) -> Optional[str]:
    """匹配角色

    Args:
        string (str): 要匹配的字符串.
        characters (Dict[str, List[str]]): 角色名列表.

    Returns:
        Optional[str]: 匹配到的角色名，或者匹配失败时返回 None.
    """

    for name, aliases in characters.items():
        if string in aliases:
            return name
    return None
