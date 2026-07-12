"""dr3"""

__title__ = 'dr3'
__package__ = 'dr3'
__author__ = 'Soxoj'
__author_email__ = 'soxoj@protonmail.com'


from .__version__ import __version__
from .checking import maigret as search
from .dr3 import main as cli
from .sites import MaigretEngine, MaigretSite, MaigretDatabase
from .notify import QueryNotifyPrint as Notifier
