# TransCora selbst bauen

Python 3.12 mit Tcl/Tk und die in `requirements-build.txt` festgelegten Pakete
verwenden. Der Windows-Build läuft in `.github/workflows/build.yml`.

1. `python -m pip install -r requirements-build.txt`
2. `python scripts/fetch_ffmpeg.py`
3. `python scripts/fetch_bd3d_tools.py` (7-Zip erforderlich)
4. `python scripts/prepare_exiftool.py`
5. `python scripts/build_mvc_decoder.py` unter MSYS2/UCRT64 mit GCC und make.
6. `python -m unittest discover -s tests -v`
7. `python scripts/build_windows.py`

Das portable Paket enthält den zugehörigen Anwendungscode unter `source/`,
die unveränderten Original-Assets sowie die Versions-, Lizenz- und Hash-Nachweise
der externen Werkzeuge. Die Werkzeuge bleiben eigenständige Prozesse.
Die Build-Skripte laden die festgelegten Versionen ausschließlich während des Builds;
die Anwendung selbst benötigt keinen Netzwerkzugriff.

Der Ordner `source/` ist ein vollständiger Ausgangspunkt zum Neubau. Nach den
Vorbereitungsschritten kann `python run_transcora.py` darin gestartet werden.
