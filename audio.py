"""音源ファイルの長さを読む（標準ライブラリだけ）。Ogg Vorbis / Ogg Opus / WAV。

DTXMania は譜面の最後のチップで演奏を終えるので、音源の長さが分かれば
「歌が残っているのに結果画面になる」のを終端の無音チップで防げる（dtx.render の end_time）。
"""
from __future__ import annotations

import struct
import wave
from pathlib import Path

_TAIL = 256 * 1024   # 最後のページを探す範囲


def _ogg_pages(data: bytes):
    """data 内の Ogg ページを (先頭位置, granule, 本体) で列挙する。"""
    pos = 0
    while True:
        pos = data.find(b'OggS', pos)
        if pos < 0 or pos + 27 > len(data):
            return
        nseg = data[pos + 26]
        head_end = pos + 27 + nseg
        if head_end > len(data):
            return
        body_len = sum(data[pos + 27:head_end])
        granule = struct.unpack_from('<q', data, pos + 6)[0]
        yield pos, granule, data[head_end:head_end + body_len]
        pos = head_end + body_len


def ogg_duration(path: Path) -> float | None:
    """Ogg（Vorbis / Opus）の長さ（秒）。読めなければ None。"""
    try:
        size = path.stat().st_size
        with path.open('rb') as f:
            head = f.read(64 * 1024)
            f.seek(max(0, size - _TAIL))
            tail = f.read(_TAIL)
    except OSError:
        return None
    rate = None
    pre_skip = 0
    for _pos, _g, body in _ogg_pages(head):
        if body.startswith(b'\x01vorbis') and len(body) >= 16:
            rate = struct.unpack_from('<I', body, 12)[0]
        elif body.startswith(b'OpusHead') and len(body) >= 12:
            pre_skip = struct.unpack_from('<H', body, 10)[0]
            rate = 48000   # Opus の granule は常に 48 kHz
        if rate:
            break
    if not rate:
        return None
    last = None
    for _pos, granule, _body in _ogg_pages(tail):
        if granule >= 0:
            last = granule
    if last is None:
        return None
    return max(0.0, (last - pre_skip) / rate)


def wav_duration(path: Path) -> float | None:
    try:
        with wave.open(str(path), 'rb') as w:
            return w.getnframes() / (w.getframerate() or 1)
    except (OSError, wave.Error, EOFError):
        return None


def duration(path: Path) -> float | None:
    if path.suffix.lower() == '.ogg':
        return ogg_duration(path)
    if path.suffix.lower() == '.wav':
        return wav_duration(path)
    return None


def write_silence(path: Path, seconds: float = 0.05, rate: int = 44100) -> Path:
    """終端用の無音 WAV（16 bit モノラル）。"""
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b'\x00\x00' * int(rate * seconds))
    return path
