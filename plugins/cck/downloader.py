import os
import aiohttp
import asyncio
import aiofiles
from pathlib import Path
from nonebot import logger
from typing import List, Dict


class AsyncDownloader:
    def __init__(self, cache_dir: Path, data_dir: Path, max_concurrent_tasks: int = 32):
        self.cache_dir: Path = cache_dir
        self.data_dir: Path = data_dir
        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.headers: Dict[str, str] = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/87.0.4280.67 Safari/537.36 Edg/87.0.664.47"
            ),
            "Referer": "https://bestdori.com/",
            "Host": "bestdori.com",
        }

    async def get_bad_urls(self) -> List[str]:
        """Read the list of bad URLs from the cache."""
        bad_url_file: Path = self.cache_dir / "bad_url.txt"
        if not bad_url_file.exists():
            return []
        async with aiofiles.open(bad_url_file, "r") as file:
            return [line.strip() for line in await file.readlines()]

    async def download_file(self, url: str, folder_name: str, file_name: str) -> None:
        """Download a file from a URL and save it."""
        file_path: Path = self.data_dir / folder_name / file_name

        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)

        async with self.semaphore:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=self.headers) as response:
                        if response.status != 200:
                            logger.error(
                                f"Downloader: Failed to download {url}, status code: {response.status}"
                            )
                            return

                        data: bytes = await response.read()

                        if len(data) == 14559:
                            logger.warning(f"Downloader: Bestdori image missing {url}")
                            async with aiofiles.open(
                                self.cache_dir / "bad_url.txt", "a"
                            ) as bad_file:
                                await bad_file.write(url + "\n")
                        else:
                            async with aiofiles.open(file_path, "wb") as file:
                                await file.write(data)

                            logger.success(
                                f"Downloader: Successfully downloaded {url} ({os.path.getsize(file_path)})"
                            )
            except Exception as e:
                logger.error(f"Downloader: {str(e)}")

    async def download_cards(
        self, resource_ids: List[str], server_mapping: Dict[str, str]
    ) -> None:
        """Download card resources given a list of resource IDs and a server mapping."""
        base_url: str = "https://bestdori.com/assets/{}/characters/resourceset/"
        tasks: List[asyncio.Task] = []

        bad_urls: List[str] = await self.get_bad_urls()

        for resource_id in resource_ids:
            server_id = server_mapping.get(resource_id[:9])
            if server_id:
                url: str = (
                    f"{base_url.format(server_id)}{resource_id[:9]}_rip/{resource_id[10:]}"
                )
                if url not in bad_urls:
                    task: asyncio.Task = self.download_file(
                        url, resource_id[:6], resource_id
                    )
                    tasks.append(task)

        await asyncio.gather(*tasks)
