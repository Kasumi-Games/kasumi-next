import os
import io
import tempfile
import subprocess
from PIL import Image
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.satori import MessageEvent

from .birthday import get_today_birthday as get_today_birthday
from .passive_generator import PassiveGenerator as PassiveGenerator


async def has_no_argument(arg: Message = CommandArg()):
    if arg.extract_plain_text().strip() == "":
        return True
    return False


async def is_qq_bot(event: MessageEvent):
    return event.login.platform in ["qq", "qqguild"]


def _encode(
    input_path: str, output_path: str, sampling_rate: str = "24000", cli: str = "./cli"
):
    subprocess.run([cli, "-i", input_path, "-o", output_path, "-s", sampling_rate])


def encode_to_silk(file: bytes, format: str = "wav") -> bytes:
    """Encode a file into SILK format."""
    with tempfile.NamedTemporaryFile(
        suffix=f".{format}", delete=False
    ) as temp_input_file:
        temp_input_file.write(file)

    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as temp_pcm_file:
        pass

    ffmpeg_cmd = f"ffmpeg -i {temp_input_file.name} -f s16le -acodec pcm_s16le -ar 24000 -ac 1 {temp_pcm_file.name}"
    subprocess.run(
        ffmpeg_cmd,
        input=b"y",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    os.unlink(temp_input_file.name)

    with tempfile.NamedTemporaryFile(suffix=".silk", delete=False) as temp_output_file:
        pass

    _encode(temp_pcm_file.name, temp_output_file.name)

    with open(temp_output_file.name, "rb") as encoded_file:
        encoded_data = encoded_file.read()

    os.unlink(temp_pcm_file.name)
    os.unlink(temp_output_file.name)

    return encoded_data


def encode_with_ntsilk(file: bytes, format: str = "wav", target: str = "silk") -> bytes:
    """Encode a file into any format using NTSilk."""
    with tempfile.NamedTemporaryFile(
        suffix=f".{format}", delete=False
    ) as temp_input_file:
        temp_input_file.write(file)

    with tempfile.NamedTemporaryFile(
        suffix=f".{target}", delete=False
    ) as temp_output_file:
        pass

    subprocess.run(
        ["./ntsilk", "-i", temp_input_file.name, temp_output_file.name], input=b"y"
    )

    os.unlink(temp_input_file.name)

    with open(temp_output_file.name, "rb") as encoded_file:
        encoded_data = encoded_file.read()

    os.unlink(temp_output_file.name)

    return encoded_data


def encode_to_mp3(file: bytes, format: str = "wav") -> bytes:
    """Encode a file into MP3 format."""
    with tempfile.NamedTemporaryFile(
        suffix=f".{format}", delete=False
    ) as temp_input_file:
        temp_input_file.write(file)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_output_file:
        pass

    ffmpeg_cmd = f"ffmpeg -i {temp_input_file.name} -f mp3 -acodec libmp3lame -ar 24000 -ac 1 {temp_output_file.name}"
    subprocess.run(
        ffmpeg_cmd,
        input=b"y",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    os.unlink(temp_input_file.name)

    with open(temp_output_file.name, "rb") as encoded_file:
        encoded_data = encoded_file.read()

    os.unlink(temp_output_file.name)

    return encoded_data


def image_to_bytes(image: Image.Image) -> bytes:
    with io.BytesIO() as output:
        image.save(output, format="JPEG", quality=90)
        return output.getvalue()
