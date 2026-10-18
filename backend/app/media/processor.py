import os
import subprocess
import logging
import json
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import imageio_ffmpeg

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".mp3", ".wav", ".m4a", ".ogg", ".aac"}

def get_ffmpeg_binary() -> str:
    """Return path to ffmpeg binary, preferring imageio-ffmpeg static binary or system ffmpeg."""
    try:
        binary = imageio_ffmpeg.get_ffmpeg_exe()
        if binary and os.path.exists(binary):
            return binary
    except Exception as e:
        logger.warning(f"Could not retrieve imageio_ffmpeg binary: {e}")
    return "ffmpeg"

def get_ffprobe_binary() -> str:
    """Return path to ffprobe binary."""
    # Check if ffprobe is in Python Scripts or PATH
    python_scripts_ffprobe = Path(r"C:\Users\hp\AppData\Local\Programs\Python\Python313\Scripts\ffprobe.exe")
    if python_scripts_ffprobe.exists():
        return str(python_scripts_ffprobe)
    return "ffprobe"

def inspect_media(file_path: Path) -> Dict[str, Any]:
    """
    Inspect media file using ffprobe.
    Returns details on video/audio streams, codecs, and durations.
    """
    if not file_path.exists():
        return {
            "valid": False,
            "error": "File does not exist.",
            "has_video": False,
            "has_audio": False,
            "duration": 0.0
        }

    ffprobe_bin = get_ffprobe_binary()
    cmd = [
        ffprobe_bin,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path)
    ]

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(proc.stdout)
        
        streams = data.get("streams", [])
        fmt = data.get("format", {})
        
        has_video = any(s.get("codec_type") == "video" for s in streams)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
        
        duration = 0.0
        if "duration" in fmt and fmt["duration"]:
            try:
                duration = float(fmt["duration"])
            except ValueError:
                duration = 0.0
        if duration == 0.0 and video_stream and "duration" in video_stream:
            try:
                duration = float(video_stream["duration"])
            except ValueError:
                pass
        if duration == 0.0 and audio_stream and "duration" in audio_stream:
            try:
                duration = float(audio_stream["duration"])
            except ValueError:
                pass

        return {
            "valid": True,
            "has_video": has_video,
            "has_audio": has_audio,
            "duration": round(duration, 2),
            "format": fmt.get("format_name", ""),
            "video_codec": video_stream.get("codec_name") if video_stream else None,
            "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
            "width": video_stream.get("width") if video_stream else None,
            "height": video_stream.get("height") if video_stream else None,
            "error": None
        }
    except Exception as e:
        logger.warning(f"ffprobe inspection failed on {file_path}: {e}")
        # Basic fallback
        ext = file_path.suffix.lower()
        is_audio = ext in [".mp3", ".wav", ".m4a", ".ogg", ".aac"]
        dur = get_audio_duration(file_path) if ext == ".wav" else 0.0
        return {
            "valid": True,
            "has_video": not is_audio,
            "has_audio": is_audio,
            "duration": dur,
            "format": ext.replace(".", ""),
            "video_codec": None,
            "audio_codec": None,
            "error": None
        }

def validate_media_file(file_path: Path) -> Tuple[bool, str]:
    """Validate that the file exists and is an allowable audio/video type."""
    if not file_path.exists():
        return False, "File does not exist."
    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return False, f"Unsupported file format: {file_path.suffix}. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
    if file_path.stat().st_size == 0:
        return False, "File is empty (0 bytes)."
    return True, "Valid media file"

def validate_media_pair(video_path: Optional[Path], audio_path: Optional[Path]) -> Dict[str, Any]:
    """
    Validate input media according to Mode A (Paired) or Mode B (Single).
    - Mode A: video file + optional external audio file.
      Video does NOT require audio if external audio is provided!
    - Mode B: video or audio only.
    - Duration mismatches are flagged safely without artificially shifting timestamps.
    """
    if not video_path and not audio_path:
        return {
            "valid": False,
            "status": "error",
            "message": "No media file provided.",
            "mode": "unknown"
        }

    vid_info = inspect_media(video_path) if video_path and video_path.exists() else None
    aud_info = inspect_media(audio_path) if audio_path and audio_path.exists() else None

    # MODE A: Paired Video + Audio
    if vid_info and aud_info:
        vid_dur = vid_info["duration"]
        aud_dur = aud_info["duration"]
        
        dur_diff = abs(vid_dur - aud_dur)
        status = "valid"
        msg = f"Paired media verified: Video ({vid_dur:.1f}s, {vid_info.get('video_codec', 'video')}) + External Audio ({aud_dur:.1f}s, {aud_info.get('audio_codec', 'audio')})."
        
        if dur_diff > 1.5:
            status = "warning"
            msg = (
                f"Paired media verified with duration discrepancy: Video is {vid_dur:.1f}s, Audio is {aud_dur:.1f}s "
                f"(Δ {dur_diff:.1f}s). Original audio/video timestamps are strictly preserved without artificial shifting."
            )

        return {
            "valid": True,
            "status": status,
            "message": msg,
            "mode": "paired",
            "video_detected": vid_info["has_video"],
            "audio_detected": aud_info["has_audio"],
            "video_duration": vid_dur,
            "audio_duration": aud_dur,
            "video_codec": vid_info.get("video_codec"),
            "audio_codec": aud_info.get("audio_codec")
        }

    # MODE B: Video only
    if vid_info and not aud_info:
        vid_dur = vid_info["duration"]
        has_internal_audio = vid_info["has_audio"]
        
        if not has_internal_audio:
            # Video without audio and no external audio supplied
            return {
                "valid": False,
                "status": "error",
                "message": "The supplied video contains no audio stream. Please provide an external audio file (Mode A paired media) for transcription.",
                "mode": "single",
                "video_detected": True,
                "audio_detected": False,
                "video_duration": vid_dur,
                "audio_duration": 0.0,
                "video_codec": vid_info.get("video_codec")
            }

        return {
            "valid": True,
            "status": "valid",
            "message": f"Single video media verified ({vid_dur:.1f}s). Audio stream detected ({vid_info.get('audio_codec', 'audio')}) and ready for extraction.",
            "mode": "single",
            "video_detected": True,
            "audio_detected": True,
            "video_duration": vid_dur,
            "audio_duration": vid_dur,
            "video_codec": vid_info.get("video_codec"),
            "audio_codec": vid_info.get("audio_codec")
        }

    # MODE B: Audio only
    if aud_info and not vid_info:
        aud_dur = aud_info["duration"]
        return {
            "valid": True,
            "status": "valid",
            "message": f"Single audio media verified ({aud_dur:.1f}s, {aud_info.get('audio_codec', 'audio')}).",
            "mode": "single",
            "video_detected": False,
            "audio_detected": True,
            "video_duration": 0.0,
            "audio_duration": aud_dur,
            "audio_codec": aud_info.get("audio_codec")
        }

    return {"valid": False, "status": "error", "message": "Invalid media state.", "mode": "unknown"}

def prepare_playback_media(video_path: Optional[Path], audio_path: Optional[Path], output_mp4_path: Path) -> Optional[Path]:
    """
    Ensure a browser-compatible MP4 (H.264 / AAC) with +faststart exists for seamless video playback and evidence seeking.
    If video has no audio and separate audio is provided (e.g. AMI Corner.avi + Mix-Headset.wav),
    FFmpeg muxes them together with ultrafast preset so the user hears audio while watching synchronized video in the browser.
    """
    if not video_path or not video_path.exists():
        return None

    # If it is already a web-compatible MP4 with H.264 and AAC, return it directly
    info = inspect_media(video_path)
    if (
        video_path.suffix.lower() == ".mp4" and 
        info.get("video_codec") in ["h264", "avc1"] and 
        (info.get("audio_codec") in ["aac", "mp3"] or not audio_path)
    ):
        return video_path

    # Otherwise transmux/transcode with ultrafast preset
    ffmpeg_bin = get_ffmpeg_binary()
    output_mp4_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [ffmpeg_bin, "-y"]
    cmd.extend(["-i", str(video_path)])
    
    if audio_path and audio_path.exists():
        cmd.extend(["-i", str(audio_path)])
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            str(output_mp4_path)
        ])
    else:
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-an",
            "-movflags", "+faststart",
            str(output_mp4_path)
        ])

    try:
        logger.info(f"Generating web playback MP4 for {video_path.name}...")
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        if output_mp4_path.exists() and output_mp4_path.stat().st_size > 0:
            logger.info(f"Web playback MP4 created: {output_mp4_path} ({output_mp4_path.stat().st_size} bytes)")
            return output_mp4_path
    except Exception as e:
        logger.warning(f"Failed to create playback MP4: {e}. Falling back to original video_path.")
    
    return video_path

def extract_and_convert_audio(media_path: Path, output_wav_path: Path) -> Tuple[bool, float, Optional[str]]:
    """
    Extract audio from media file, convert to 16kHz 16-bit mono WAV, and return (success, duration_seconds, error).
    """
    ffmpeg_bin = get_ffmpeg_binary()
    output_wav_path.parent.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(media_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(output_wav_path)
    ]

    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        duration = get_audio_duration(output_wav_path)
        return True, duration, None
    except subprocess.CalledProcessError as e:
        err = e.stderr or str(e)
        logger.error(f"FFmpeg error: {err}")
        return False, 0.0, f"FFmpeg failed to extract audio: {err[:300]}"
    except Exception as e:
        logger.error(f"Audio extraction error: {e}")
        return False, 0.0, str(e)

def get_audio_duration(wav_path: Path) -> float:
    """Read duration of WAV file in seconds."""
    import wave
    try:
        with wave.open(str(wav_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration = frames / float(rate)
            return round(duration, 2)
    except Exception as e:
        logger.warning(f"Could not compute wave duration: {e}")
        return 0.0
