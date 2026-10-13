"""Run the Dual check through the actual packaged application's entry point."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import os


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--application',type=Path,required=True)
    parser.add_argument('--folder',type=Path,default=Path('work/dual-package-test'))
    args=parser.parse_args()
    folder=args.folder.resolve();folder.mkdir(parents=True,exist_ok=True)
    report=folder/'report.json'
    result=subprocess.run([str(args.application.resolve()),'--self-test-dual',str(report),str(folder)],
                          timeout=120,**({'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}))
    content=json.loads(report.read_text('utf-8')) if report.is_file() else {'ok':False,'error':'No application report'}
    print(json.dumps(content,indent=2))
    if result.returncode or not content.get('ok'):raise SystemExit(1)


if __name__=='__main__':
    main()
