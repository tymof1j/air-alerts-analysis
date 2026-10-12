"""Package the verified dashboard build for static hosting without retraining."""
import hashlib
import shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=root/'dashboard/dist'
if not (source/'index.html').is_file():raise SystemExit('Build dashboard first.')
target=root/'site'
if target.exists():shutil.rmtree(target)
shutil.copytree(source,target)
(target/'.nojekyll').touch()
print('Static site packaged:',target)
print('HTML SHA-256:',hashlib.sha256((target/'index.html').read_bytes()).hexdigest())
