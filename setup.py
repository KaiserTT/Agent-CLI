"""Setup script for the Agent CLI package."""

from setuptools import setup, find_packages

setup(
    name="agent_cli",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'agent=agent_cli.cli:main',
        ],
    },
    install_requires=[
        'openai>=1.0.0',
    ],
    author="KaiserTT",
    author_email="kaisertan015@gmail.com",
    description="A command line tool for interacting with LLM providers",
    keywords="cli, ai, llm, chat",
    python_requires='>=3.8',
)