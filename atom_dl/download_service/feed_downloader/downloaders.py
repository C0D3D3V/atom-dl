from atom_dl.download_service.feed_downloader._downloaders import *

_ALL_CLASSES = [klass for name, klass in globals().items() if name.endswith('FD') and name != 'GenericFD']
# _ALL_CLASSES.append(GenericFD)
