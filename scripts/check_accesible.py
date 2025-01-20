from yt_dlp import YoutubeDL
import time
import os
import asyncio
from functools import partial
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from . import YoutubeConfig

def resolve_redirect_with_selenium(url):
    """Resolves redirects using Selenium to get the final URL.

    This function uses a headless Chrome browser via Selenium to navigate to the
    given URL and follow any redirects. It then returns the final URL after all
    redirects have been resolved.

    Args:
        url (str): The initial URL to resolve.

    Returns:
        str: The final URL after all redirects, or None if an error occurs.

    Raises:
        WebDriverException: If ChromeDriver is not found or an incompatible version
            is installed. Instructions to resolve this are printed to the console.
    """
    # Set up Selenium with a headless browser and a custom User-Agent
    options = Options()
    options.add_argument("--headless")  # Run in headless mode (no GUI)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as e:
        print("\n".join([
            "[ERROR] ChromeDriver not found or incompatible version.",
            "Please ensure you have ChromeDriver installed and it's in your PATH.",
            "You can download it from: https://chromedriver.chromium.org/downloads",
            "Make sure the ChromeDriver version matches your Chrome browser version.",
            "-----------------------------------------------------------",
        ]))
        raise e
    try:
        driver.get(url)
        # Wait for the page to load and retrieve the final URL
        final_url = driver.current_url
        print(f"Resolved URL: {final_url}")
        return final_url
    except Exception as e:
        print(f"[ERROR] Selenium failed to resolve URL '{url}': {e}")
        return None
    finally:
        if driver:
            driver.quit()

_video_cache = {}  # In-memory cache for video accessibility

def __check_video_accessible(url, ydl_opts_full):
    """
    Checks the accessibility of a single video without downloading, using cache.

    Args:
        url (str): The URL of the video to check.
        ydl_opts_full (dict): Options to pass to the YoutubeDL instance.

    Returns:
        tuple: A tuple containing the URL and a boolean indicating accessibility.
    """
    if url in _video_cache:
        return url, _video_cache[url]
    try:
        with YoutubeDL(ydl_opts_full) as ydl_full:
            ydl_full.extract_info(url, download=False)
            _video_cache[url] = True
            return url, True
    except Exception:
        _video_cache[url] = False
        return url, False

async def __fetch_video_urls(url, ydl_opts_flat):
    """
    Asynchronously fetches video URLs from a playlist or single video URL.

    Args:
        url (str): The URL of the playlist or video.
        ydl_opts_flat (dict): Options to pass to the YoutubeDL instance for flat extraction.

    Returns:
        list: A list of video URLs.
    """
    loop = asyncio.get_running_loop()
    try:
        with YoutubeDL(ydl_opts_flat) as ydl:
            info = await loop.run_in_executor(None, partial(ydl.extract_info, url, download=False))
            video_urls = []
            if "entries" in info:
                # Use a list comprehension for faster creation
                video_urls = [f"https://www.youtube.com/watch?v={entry['id']}" for entry in info["entries"] if entry and entry.get("id")]
            elif info.get("id"):
                video_urls.append(url)
            return video_urls
    except Exception as e:
        print(f"Error fetching URLs for {url}: {e}")
        return []

async def __check_videos_async(url):
    """
    Checks video accessibility asynchronously using concurrent processing and caching.

    Args:
        url (str): The URL of the playlist or video to check.

    Returns:
        tuple: A tuple containing two lists: accessible video URLs and inaccessible video URLs.
    """
    config = YoutubeConfig()
    ydl_opts_flat = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
        "noplaylist": False,
        "no_warnings": True,
        "nocheckcertificate": config.no_check_certificate, # Can improve speed in some environments
        "cookie_file": config.cookie_file,
        "cookies_from_browser": config.cookies_from_browser,
    }
    ydl_opts_full = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,  # Important for speed
        "nocheckcertificate": config.no_check_certificate, # Can improve speed in some environments
        "no_warnings": True,
        "cookie_file": config.cookie_file,
        "cookies_from_browser": config.cookies_from_browser,
    }

    accessible_videos = []
    inaccessible_videos = []

    video_urls = await __fetch_video_urls(url, ydl_opts_flat)

    if not video_urls:
        print(f"No videos found for URL: {url}")
        return [], []

    cpu_count = os.cpu_count() or 1
    max_workers = min(61, cpu_count * 8) # Increased max workers aggressively
    print(f"Using {max_workers} workers for checking video accessibility.")

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        loop = asyncio.get_running_loop()
        partial_check = partial(__check_video_accessible, ydl_opts_full=ydl_opts_full)
        futures = [loop.run_in_executor(executor, partial_check, video_url) for video_url in video_urls] # Use list comprehension

        for future in asyncio.as_completed(futures): #  More efficient handling of results
            try:
                url_result, accessible = await future
                if accessible:
                    accessible_videos.append(url_result.replace('www.youtube','music.youtube'))
                else:
                    inaccessible_videos.append(url_result.replace('www.youtube','music.youtube'))
            except Exception as e:  # Handle potential errors during video checking
                print(f"Error checking video: {e}")
                # You might want to log the error, retry, or append the URL to a failed list

    return accessible_videos, inaccessible_videos

def check_videos(url):
    """
    Checks the accessibility of videos at a given URL.

    This function resolves redirects, fetches video URLs from the given URL
    (which can be a single video or a playlist), and then concurrently checks
    the accessibility of each video using yt-dlp.

    Args:
        url (str): The URL of the YouTube video or playlist to check.

    Returns:
        tuple: A tuple containing two lists:
            - A list of accessible video URLs (with 'music.youtube.com').
            - A list of inaccessible video URLs (with 'music.youtube.com').
    """
    start_time = time.time()
    resolved_url = resolve_redirect_with_selenium(url)
    if resolved_url:
        accessible, inaccessible = asyncio.run(__check_videos_async(resolved_url))
    else:
        accessible, inaccessible = [], []
    end_time = time.time()
    print(f"\nTotal Time Taken: {end_time - start_time:.2f} seconds") #34 - 13.98
    return accessible, inaccessible

# Example usage
if __name__ == "__main__":
    playlist_url = "https://music.youtube.com/playlist?list=PLqXAOnFhzzydfXEl6jOl7SJzFF3hmW0_Z&si=F-Cn60OyoU-qxTbk"  # Replace with your playlist or video URL
    accessible, inaccessible = check_videos(playlist_url)

    print("Accessible Videos:")
    for video in accessible:
        print(video)

    print("\nInaccessible Videos:")
    for video in inaccessible:
        print(video)