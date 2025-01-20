import os
from environs import Env
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import locale

# Load environment variables
env = Env()
env.read_env()

class YoutubeConfig(BaseModel):
    """
    Configuration class for the YouTube playlist downloader.

    Attributes:
        thread_count (int): The number of threads to use for downloading.

    """
    url: str = Field(default_factory=lambda: env.str("YOUTUBE_URL", "").strip())
    reverse_playlist: bool = Field(default_factory=lambda: env.bool("YOUTUBE_REVERSE_PLAYLIST", False))
    use_title: bool = Field(default_factory=lambda: env.bool("YOUTUBE_USE_TITLE", False))
    use_uploader: bool = Field(default_factory=lambda: env.bool("YOUTUBE_USE_UPLOADER", False))
    use_playlist_name: bool = Field(default_factory=lambda: env.bool("YOUTUBE_USE_PLAYLIST_NAME", False))
    use_geo_bypass: bool = Field(default_factory=lambda: env.bool("YOUTUBE_USE_GEO_BYPASS", False))
    sync_folder_name: bool = Field(default_factory=lambda: env.bool("YOUTUBE_SYNC_FOLDER_NAME", True))
    use_threading: bool = Field(default_factory=lambda: env.bool("YOUTUBE_USE_THREADING", True))
    thread_count: int = Field(default_factory=lambda: env.int("YOUTUBE_THREAD_COUNT", 1))
    retain_missing_order: bool = Field(default_factory=lambda: env.bool("YOUTUBE_RETAIN_MISSING_ORDER", False))
    name_format: str = Field(default_factory=lambda: env.str("YOUTUBE_NAME_FORMAT", "%(title)s.%(ext)s").strip())
    track_num_in_name: bool = Field(default_factory=lambda: env.bool("YOUTUBE_TRACK_NUM_IN_NAME", False))
    audio_format: str = Field(default_factory=lambda: env.str("YOUTUBE_AUDIO_FORMAT", "bestaudio/best").strip())
    audio_codec: str = Field(default_factory=lambda: env.str("YOUTUBE_AUDIO_CODEC", "mp3").strip())
    audio_quality: str = Field(default_factory=lambda: env.str("YOUTUBE_AUDIO_QUALITY", "0").strip())
    image_format: str = Field(default_factory=lambda: env.str("YOUTUBE_IMAGE_FORMAT", "jpeg").strip())
    lyrics_langs: List[str] = Field(default_factory=lambda: [lang.strip() for lang in env.list("YOUTUBE_LYRICS_LANGS", [])]) # YOUTUBE_LYRICS_LANGS=en,jp,fr
    strict_lang_match: bool = Field(default_factory=lambda: env.bool("YOUTUBE_STRICT_LANG_MATCH", False))
    cookie_file: Optional[str] = Field(default_factory=lambda: env.str("YOUTUBE_COOKIE_FILE", "").strip())
    cookies_from_browser: Optional[str] = Field(default_factory=lambda: env.str("YOUTUBE_COOKIES_FROM_BROWSER", "").strip())
    verbose: bool = Field(default_factory=lambda: env.bool("YOUTUBE_VERBOSE", False))
    include_metadata: dict = Field(default_factory=dict)  
    no_check_certificate: bool = Field(default_factory=lambda: env.bool("NO_CHECK_CERTIFICATE", True))

    @field_validator("thread_count")
    def check_thread_count(cls, v):
        max_cores = os.cpu_count()
        if v > max_cores:
            raise ValueError(f"thread_count ({v}) cannot exceed the number of CPU cores ({max_cores}).")
        if v <= 0:
            raise ValueError("thread_count must be greater than 0.")
        return v
    
    def setup_include_metadata_config(self):
        return {key:True for key in self.get_metadata_map().keys() if key != "url"}
    
    def get_metadata_map(self):
        return {
            "title": ["TIT2"],
            "cover": ["APIC:Front cover"],
            "track": ["TRCK"],
            "artist": ["TPE1"],
            "album": ["TALB"],
            "date": ["TDRC"],
            "url": ["WOAR"],
            "lyrics": ["SYLT", "USLT"]
        }


    def __init__(self, **data):
        super().__init__(**data)
        self.include_metadata = self.setup_include_metadata_config()

        # If user not set confil lyrics_langs program try to get it from OS
        sys_main_lang = locale.getdefaultlocale()[0].split('_')[0]
        langs = [f"{sys_main_lang}"]
        if sys_main_lang != 'en':
            langs.append('en')
        self.lyrics_langs =  self.lyrics_langs if self.lyrics_langs else langs

# Example usage
if __name__ == "__main__":
    try:
        config = YoutubeConfig().model_dump_json()
        print(config)
        # print(config.json(indent=2))
    except ValueError as e:
        print(f"Error loading config: {e}")