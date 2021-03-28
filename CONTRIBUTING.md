# Contributing to Killer

First off, thanks for taking the time to contribute! 😊

If you want to contribute with a feature request, please send it on the [issues tab](https://github.com/ntaraujo/killer/issues)

If you want to make this feature, but are not shure if it would be accepted, go to the [discussions tab](https://github.com/ntaraujo/killer/discussions)

Also, in any moment of your developing, feel free to tell us the step you are, the difficults, ask for advices or any in the same
[discussions tab](https://github.com/ntaraujo/killer/discussions), in the right category

Are objectives of this project:
* An lightweight app, when talking about memory and cpu usage
* A well designed app, with colors and shapes coherence
* An app with features not given by the default Windows Task Manager, or at least with no easy access
* An efficient app for improving performance by killing undesired processes
* An intuitive app

Are not objectives of this project:
* A complete solution, with more features than can be reconciled with the design
* Another Task Manager, taking the place of the default Windows Task Manager
* An app just for advanced users, without intuitive paths to the features

# Starting

Python, PIP and GIT needs to be installed and Python 3.8 inside a venv is recommended
```sh
git clone https://github.com/ntaraujo/killer.git
cd killer
pip install -r requirements.txt
cd src
python main.py
```
If it works, you are ready for making changes to the source code.

# About the current used tools

1. [Python](https://www.python.org): A programming language to work quickly
2. [Kivy](https://kivy.org): A cross-platform Python framework for NUI development
3. [KivyMD](https://kivymd.readthedocs.io): A collection of material design compliant widgets for use with Kivy
4. [Psutil](https://psutil.readthedocs.io): A cross-platform library for retrieving information on running processes and system utilization in Python
5. [Pillow](https://pillow.readthedocs.io): The Python imaging library
6. [pywin32](https://github.com/mhammond/pywin32): Python extensions for Windows
7. [PyInstaller](https://www.pyinstaller.org): Bundles Python applications and all its dependencies into a single package
8. [Inno Setup](https://jrsoftware.org/isinfo.php): A free installer for Windows programs

# About the current files

```
killer - the project
  |
  data - images used by PyInstaller, Inno Setup and GitHub
  |
  src - the important files
    |
    icons - pre-saved icons of Windows processes to be used
    | |
    | Killer.exe.png - icon for the main.py window
    |
    main.kv - most of the app design (view)
    |
    main.py - the jack of all trades (control)
    |
    utils.py - functions which can be in another file not main.py (model)
```
