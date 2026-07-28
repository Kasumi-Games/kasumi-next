import io
import os
import asyncio
import tempfile
import subprocess

from PIL import Image
from nonebot.params import CommandArg
from nonebot.adapters import Message
from nonebot.adapters.satori import MessageEvent

from .birthday import get_today_birthday as get_today_birthday
from .passive_generator import PassiveGenerator as PassiveGenerator

NTSILK_TIMEOUT_SECONDS = 30


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


async def encode_with_ntsilk(
    file: bytes,
    format: str = "wav",
    target: str = "silk",
) -> bytes:
    """Encode a file with NTSilk without blocking the event loop."""
    with tempfile.NamedTemporaryFile(
        suffix=f".{format}", delete=False
    ) as temp_input_file:
        temp_input_file.write(file)
        input_path = temp_input_file.name

    with tempfile.NamedTemporaryFile(
        suffix=f".{target}", delete=False
    ) as temp_output_file:
        output_path = temp_output_file.name

    try:
        process = await asyncio.create_subprocess_exec(
            "./ntsilk",
            "-i",
            input_path,
            output_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            async with asyncio.timeout(NTSILK_TIMEOUT_SECONDS):
                _, stderr = await process.communicate(input=b"y")
        except TimeoutError as error:
            process.kill()
            await process.communicate()
            raise RuntimeError(
                f"NTSilk encoding timed out after {NTSILK_TIMEOUT_SECONDS}s"
            ) from error
        if process.returncode != 0:
            detail = stderr.decode(errors="replace").strip()[-500:]
            raise RuntimeError(
                f"NTSilk encoding failed with exit code {process.returncode}: {detail}"
            )
        return await asyncio.to_thread(_read_bytes, output_path)
    finally:
        for path in (input_path, output_path):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as file:
        return file.read()


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
        image = image.convert("RGB")
        image.save(output, format="JPEG")
        return output.getvalue()
