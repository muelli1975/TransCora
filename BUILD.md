# TransCora selbst bauen

Python 3.12 mit Tcl/Tk und die in `requirements-build.txt` festgelegten Pakete
verwenden. Der Windows-Build läuft in `.github/workflows/build.yml`.

1. `python -m pip install -r requirements-build.txt`
2. `python scripts/fetch_ffmpeg.py`
3. `python scripts/fetch_bd3d_tools.py` (7-Zip erforderlich)
4. `python scripts/prepare_exiftool.py`
5. `python scripts/build_mvc_decoder.py` unter MSYS2/UCRT64 mit GCC und make.
6. `python scripts/build_cielab.py` (CMake und C++-Compiler erforderlich;
   unter Windows Visual Studio mit C++-Buildwerkzeugen).
7. `python -m unittest discover -s tests -v`
8. `python scripts/build_windows.py`

Das portable Paket enthält den zugehörigen Anwendungscode unter `source/`,
die unveränderten Original-Assets sowie die Versions-, Lizenz- und Hash-Nachweise
der externen Werkzeuge. Die Werkzeuge bleiben eigenständige Prozesse.
Die Build-Skripte laden die festgelegten Versionen ausschließlich während des Builds;
die Anwendung selbst benötigt keinen Netzwerkzugriff.

Der Ordner `source/` ist ein vollständiger Ausgangspunkt zum Neubau. Nach den
Vorbereitungsschritten kann `python run_transcora.py` darin gestartet werden.

## Linux und macOS

Python 3.12 mit Tcl/Tk, FFmpeg/ffprobe, Perl und einen C/C++-Compiler installieren.
Unter Ubuntu/Debian sind `ffmpeg`, `perl`, `build-essential` und `python3-tk`
geeignete Systempakete; unter macOS FFmpeg über Homebrew und Xcode Command Line Tools.

1. `python -m pip install -r requirements-build.txt`
2. `python scripts/prepare_exiftool.py`
3. `python scripts/build_cielab.py`
4. Linux x64 optional: `python scripts/build_mvc_decoder.py` (GCC, make und git).
5. `python -m unittest discover -s tests -v` (Linux ohne Desktop: `xvfb-run -a` davor).
6. `python scripts/build_windows.py` – der Paketbauer erzeugt auf dem jeweiligen
   System das passende ZIP oder tar.gz; der Dateiname des Skripts ist historisch.

Linux/macOS-Pakete enthalten Python/Tk, CIELAB und ExifTool. FFmpeg wird auf diesen
Systemen extern verwendet; ExifTool benötigt System-Perl. BD-3D-Kodierung verwendet
derzeit Windows-FRIM und ist im nativen Linux/macOS-Paket nicht freigegeben.
Der Linux-x64-Build enthält den unabhängigen MVC-Decoder; Apple Silicon nicht.
