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

    async def download_file(self, url: str, folder_name: str, file_name: str, 
                          max_retries: int = 3, retry_delay: float = 1.0) -> None:
        """Download a file from a URL and save it with retry mechanism.
        
        Args:
            url: The URL to download from
            folder_name: Target folder name
            file_name: Target file name
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Delay between retries in seconds (default: 1.0)
        """
        file_path: Path = self.data_dir / folder_name / file_name

        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)

        async with self.semaphore:
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(60)) as session:
                        async with session.get(url, headers=self.headers) as response:
                            if response.status != 200:
                                logger.error(
                                    f"Downloader: Failed to download {url}, status code: {response.status}"
                                )
                                return

                            data: bytes = await response.read()

                            if len(data) == 14559 or len(data) == 14084:
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
                                return
                except (aiohttp.ClientError, asyncio.TimeoutError, IOError) as e:
                    last_error = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Downloader: 下载失败 (尝试 {attempt + 1}/{max_retries}) - URL: {url} - 错误: {str(e)}"
                        )
                        await asyncio.sleep(retry_delay)
                    continue
                except Exception as e:
                    logger.error(f"Downloader: 未知错误 - URL: {url} - 错误类型: {type(e).__name__} - 详情: {str(e)}")
                    return

            if last_error:
                error_type = type(last_error).__name__
                logger.error(f"Downloader: 下载失败 (超过最大重试次数 {max_retries}) - URL: {url} - 最后错误: {error_type}: {str(last_error)}")

    async def download_cards(
        self, urls: List[str], folder_name: str, file_names: List[str]
    ) -> None:
        """Download card resources from given URLs."""
        tasks: List[asyncio.Task] = []
        
        for url, file_name in zip(urls, file_names):
            if not url.lower().endswith('.png'):
                continue
                
            task: asyncio.Task = self.download_file(url, folder_name, file_name)
            tasks.append(task)

        await asyncio.gather(*tasks)

    async def download_svgs(
        self, urls: List[str], folder_name: str, file_names: List[str]
    ) -> None:
        """Download SVG resources from given URLs."""
        tasks: List[asyncio.Task] = []
        
        for url, file_name in zip(urls, file_names):
            if not url.lower().endswith('.svg'):
                continue
                
            task: asyncio.Task = self.download_file(url, folder_name, file_name)
            tasks.append(task)

        await asyncio.gather(*tasks)
