"""Run the shop's system with waitress, a real web server that works on Windows (v0.24.0, F22, DEC-026).

    python serve.py          (or double-click start_shop.bat)

"python app.py" stays for development: Flask's own server is not meant for a shop (audit R3).
How it listens comes from instance/config.toml, which setup_shop.py writes:
    [server]
    host = "127.0.0.1"   # this computer only  ("0.0.0.0" = also phones and computers on the shop's network)
    port = 5000
"""
from waitress import serve
from app import app, upgrade_database, CONFIG
from common import network_address   # moved to common.py in v0.27.0: emails' links use it too

ALLOWED_HOSTS = {'127.0.0.1': 'this computer only', '0.0.0.0': 'this computer and the shop\'s network'}


def server_settings(config):
    """(host, port) from the settings, checked. Without a [server] section: this computer only, port 5000."""
    server = config.get('server', {})
    host, port = server.get('host', '127.0.0.1'), server.get('port', 5000)
    if host not in ALLOWED_HOSTS:
        raise SystemExit(f'instance/config.toml: host must be "127.0.0.1" (this computer only) or "0.0.0.0" '
                         f'(also the shop\'s network), not "{host}". Run "python setup_shop.py" to fix it.')
    if not isinstance(port, int) or not 1024 <= port <= 65535:
        raise SystemExit(f'instance/config.toml: port must be a whole number from 1024 to 65535, not {port!r}. '
                         f'Run "python setup_shop.py" to fix it.')
    return host, port


if __name__ == '__main__':
    host, port = server_settings(CONFIG)
    with app.app_context():
        upgrade_database()   # backs up, then runs any missing migrations (v0.23.0)
    # flush=True: show the addresses at once, even when the output goes to a file or another program
    print(f'Inventory & POS is running ({ALLOWED_HOSTS[host]}).', flush=True)
    print(f'  On this computer:  http://127.0.0.1:{port}', flush=True)
    lan = network_address() if host == '0.0.0.0' else None
    if lan:
        print(f'  On other devices:  http://{lan}:{port}', flush=True)
    print('Keep this window open while the shop is using the system. Close it (or press Ctrl+C) to stop.', flush=True)
    serve(app, host=host, port=port, threads=8)
