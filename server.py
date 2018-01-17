import hmac
from concurrent.futures import ThreadPoolExecutor
from ipaddress import ip_address, ip_network

import requests
import yaml
from flask import Flask, request, abort, json

from app import run as run_build

app = Flask(__name__)

pool = ThreadPoolExecutor(1)

hook_secret = None


def run_build_on_pool(branch):
    pool.submit(run_build, branch)


def check_origin():
    src_ip = ip_address(u'{}'.format(request.remote_addr))
    whitelist = requests.get('https://api.github.com/meta').json()['hooks']

    whitelist += ['127.0.0.1']

    for valid_ip in whitelist:
        if src_ip in ip_network(valid_ip):
            break
    else:
        abort(403)


def check_secret(provided_secret):
    if not provided_secret:
        abort(403)

    sha_name, signature = provided_secret.split('=')
    if sha_name != 'sha1':
        abort(501)

    mac = hmac.new(hook_secret.encode(), msg=request.data, digestmod='sha1')

    if not hmac.compare_digest(str(mac.hexdigest()), str(signature)):
        abort(403)


@app.route('/hook', methods=['POST'])
def hook():
    res = request.get_json()
    if not res:
        abort(400)

    # check_origin()
    check_secret(request.headers['X-Hub-Signature'])

    event = request.headers['X-GitHub-Event']
    if event in ('ping', 'push'):
        if event == 'ping':
            return json.dumps({
                'msg': 'pong'
            })
        elif event == 'push':
            branch = res['ref'].rsplit('/', maxsplit=1)[1]
            print('got push for branch {}'.format(branch))
            run_build_on_pool(branch)

    return 'ok'


def init():
    global hook_secret

    with open('config.yml', 'r') as f:
        r = yaml.load(f)
        hook_secret = r['hook_secret']


init()

if __name__ == '__main__':
    app.run()
