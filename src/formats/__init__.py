"""音频格式处理模块"""

from .base import AudioFormat
from .ncm import NCMFormat
from .mflac import MflacFormat

__all__ = ['AudioFormat', 'NCMFormat', 'MflacFormat']
