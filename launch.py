"""Create an isolated environment once, install Qt, and launch the desktop UI."""
from pathlib import Path
import os
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parent

def main():
    if not (3,10)<=sys.version_info[:2]<(3,14):
        print('ORVEXA requires Python 3.10–3.13 (recommended: Python 3.12).')
        return 1
    directory=ROOT/'.venv'
    python=directory/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    try:
        if not python.exists():
            print('Creating .venv for ORVEXA…',flush=True)
            venv.create(directory,with_pip=True)
        check=subprocess.run([str(python),'-c',"import importlib.metadata; assert importlib.metadata.version('PySide6-Essentials') == '6.8.3'"],
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if check.returncode:
            print('Installing Qt (first launch only; internet connection required)…',flush=True)
            pip_check=subprocess.run([str(python),'-m','pip','--version'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if pip_check.returncode:
                subprocess.run([str(python),'-m','ensurepip','--upgrade'],cwd=ROOT,check=True)
            subprocess.run([str(python),'-m','pip','install','--disable-pip-version-check','-r',str(ROOT/'requirements.txt')],cwd=ROOT,check=True)
        return subprocess.call([str(python),str(ROOT/'main.py')],cwd=ROOT)
    except (OSError,subprocess.CalledProcessError) as exc:
        print('Unable to launch ORVEXA:',exc)
        print('See README.md. On Linux, python3-venv and Qt/X11 system libraries may be required.')
        return 1

if __name__=='__main__':
    raise SystemExit(main())
