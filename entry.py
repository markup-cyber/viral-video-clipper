import os, sys
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
def main():
    frozen = getattr(sys, "frozen", False)
    base = sys._MEIPASS if frozen else os.path.dirname(os.path.abspath(__file__))
    app = os.path.join(base, "app.py")

    # Make outputs/ land next to the exe, and allow ffmpeg.exe dropped next to the exe
    cwd = os.path.dirname(sys.executable) if frozen else base
    os.chdir(cwd)
    os.environ["PATH"] = cwd + os.pathsep + base + os.pathsep + os.environ.get("PATH", "")

    import streamlit.web.cli as stcli
    sys.argv = ["streamlit", "run", app,
                "--global.developmentMode=false",
                "--server.port=8501",
                "--server.headless=false",
                "--server.fileWatcherType=none"]
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
