#!/usr/bin/env python3
"""
Setup script for SAI - Smart AI Assistant
"""

from setuptools import setup, find_packages
import os

# Read the contents of README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Core dependencies that are always required
install_requires = [
    'PyQt6>=6.5.0',
    'anthropic>=0.7.0',
    'sounddevice>=0.4.6',
    'speech-recognition>=3.10.0',
    'numpy>=1.24.0',
    'python-dotenv>=1.0.0',
    'pyaudio>=0.2.11',  # For speech_recognition
]

# Optional dependencies for enhanced features
extras_require = {
    'whisper': [
        'openai-whisper>=20231117',
        'webrtcvad>=2.0.10',
        'torch>=2.0.0',
        'scipy>=1.10.0',
    ],
    'dev': [
        'pytest>=7.0.0',
        'black>=23.0.0',
        'flake8>=6.0.0',
    ],
    'all': [
        'openai-whisper>=20231117',
        'webrtcvad>=2.0.10', 
        'torch>=2.0.0',
        'scipy>=1.10.0',
    ]
}

setup(
    name='sai-assistant',
    version='1.0.0',
    author='SAI Development Team',
    author_email='dev@sai-assistant.com',
    description='Smart AI Assistant - Voice-activated overlay with Claude AI integration',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/sai-assistant/sai',
    packages=find_packages(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Multimedia :: Sound/Audio :: Speech',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Topic :: Desktop Environment',
    ],
    python_requires='>=3.8',
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        'console_scripts': [
            'sai=sai.cli:main',
            'sai-setup=sai.setup:main',
        ],
    },
    include_package_data=True,
    package_data={
        'sai': ['*.md', '*.txt'],
    },
    keywords='ai assistant voice overlay claude whisper speech-to-text',
    project_urls={
        'Bug Reports': 'https://github.com/sai-assistant/sai/issues',
        'Source': 'https://github.com/sai-assistant/sai',
        'Documentation': 'https://sai-assistant.com/docs',
    },
)