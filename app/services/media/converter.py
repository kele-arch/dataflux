# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/media/converter.py
# @Created: 2026/6/22 11:52
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 媒体文件转换器, 依赖 ffmpeg, 支持视频/音频输入, 输出 WAV 格式

import subprocess
from pathlib import Path


class MediaToAudioConverter:
    VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv"}
    AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac"}

    def __init__(self, ffmpeg_path: str = "ffmpeg", sample_rate=16000, channels=1):
        self.ffmpeg_path = ffmpeg_path
        self.sample_rate = sample_rate
        self.channels = channels

    def is_media(self, path: Path) -> bool:
        return path.suffix.lower() in (self.VIDEO_EXTS | self.AUDIO_EXTS)

    def is_video(self, path: Path) -> bool:
        return path.suffix.lower() in self.VIDEO_EXTS

    def is_audio(self, path: Path) -> bool:
        return path.suffix.lower() in self.AUDIO_EXTS

    def to_wav(self, media_path) -> Path:
        """统一转换为 WAV, 返回 WAV 文件路径"""
        path = Path(media_path)
        if path.suffix.lower() == ".wav":
            return path

        wav_path = path.with_suffix(".wav")
        command = [
            self.ffmpeg_path, "-y", "-i", str(path),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(self.sample_rate),
            "-ac", str(self.channels),
            str(wav_path)
        ]
        try:
            subprocess.run(command, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffmpeg 转换失败: {e.stderr.decode()}")
        return wav_path


# 全局转换器单例(无状态,直接实例化)
media_converter = MediaToAudioConverter(
    ffmpeg_path="ffmpeg"
)