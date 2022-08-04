from setuptools import setup, find_packages

exec(open('audian/version.py').read())

long_description = """
# AUDIoANalyser

Simple GUI for viewing biosignals.
"""

setup(
    name = 'audian',
    version = __version__,
    author = 'Jan Benda',
    author_email = "jan.benda@uni-tuebingen.de",
    description = 'Simple GUI for viewing biosignals.',
    long_description = long_description,
    long_description_content_type = "text/markdown",
    url = "https://github.com/bendalab/audian",
    license = "GPLv3",
    classifiers = [
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    packages = ['audian'],
    entry_points = {
        'console_scripts': [
            'audian = audian.audian:run',
        ]},
    python_requires = '>=3.4',
    install_requires = ['scipy', 'numpy', 'matplotlib', 'audioio'],
)
