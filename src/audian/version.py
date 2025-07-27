__version__= '2.4'
"""Current version of the audian package."""

__year__ = '2025'
"""Current year for copyright messages."""

__pdoc__ = {}
__pdoc__['__version__'] = True
__pdoc__['__year__'] = True


from platformdirs import PlatformDirs

audian_dirs = PlatformDirs('audian', 'janscience')
