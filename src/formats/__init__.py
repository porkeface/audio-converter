"""音频格式处理模块"""

from .base import AudioFormat
from .ncm import NCMFormat

__all__ = ['AudioFormat', 'NCMFormat']
