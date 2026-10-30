"""One public Next.js process and a private loopback FastAPI process."""
import os
import signal
import subprocess
import sys
import time


def main():
    from app.server_config import local_mode, public_origin
    from app.auth import configured
    from app.storage import initialize
    if local_mode():
        print('Refusing public container startup with DASHBOARD_LOCAL_MODE=true.',file=sys.stderr);return 1
    if not public_origin() or not configured():
        print('Set the dashboard owner, password hash and HTTPS PUBLIC_ORIGIN in host secrets before startup.',file=sys.stderr);return 1
    try: initialize()
    except Exception:
        print('Database initialization failed. Check the host database binding and TLS configuration.',file=sys.stderr);return 1
    children=[]
    def stop(*args):
        for child in children:
            if child.poll() is None:child.terminate()
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    try:
        children.append(subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--workers','1'],env={**os.environ,'AUTO_INIT_DB':'false'}))
        children.append(subprocess.Popen(['node','/app/frontend/server.js'],cwd='/app/frontend',env={**os.environ,'HOSTNAME':'0.0.0.0'}))
        while all(child.poll() is None for child in children):time.sleep(.5)
        return next((child.returncode for child in children if child.poll() is not None),1) or 1
    finally:
        stop()
        for child in children:
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()


if __name__=='__main__':sys.exit(main())
