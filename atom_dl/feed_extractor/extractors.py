from atom_dl.feed_extractor._extractors import *

_ALL_CLASSES = [klass for name, klass in globals().items() if name.endswith('FIE') and name != 'GenericFIE']
# _ALL_CLASSES.append(GenericFIE)
