from setuptools import setup, find_packages

setup(
    name="ScreenHUD-Alarm",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "python-dotenv",
        "pydantic",
        "setuptools",
        "OperaPowerRelay @ git+https://github.com/OperavonderVollmer/OperaPowerRelay@main"
    ],
    python_requires=">=3.7",
    author="Opera von der Vollmer",
    description="Alarm plugin for Opera's ScreenHUD",
    url="https://github.com/OperavonderVollmer/ScreenHUD-Alarm", 
    license="MIT",
)
