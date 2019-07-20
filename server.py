import hmac
import logging
from concurrent.futures import ThreadPoolExecutor
from ipaddress import ip_address, ip_network

import requests
from flask import Flask, request, abort, json

from app.configuration import Configuration
from app.build import Build
from app.init import global_config
from app.runner import Runner

app = Flask(__name__)

pool = ThreadPoolExecutor(1)


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

    mac = hmac.new(global_config.hook_secret.encode(), msg=request.data, digestmod='sha1')

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
            handle_push_event(res)

    return 'ok'


def handle_push_event(res):
    logging.info('Received push (ref: {})'.format(res['ref']))
    pool.submit(run_build_wrapper, res)


# Runs on pool
def run_build_wrapper(res):
    try:
        run_build(res)
    except Exception:
        logging.error('General error', exc_info=True)


def run_build(res):
    branch = res['ref'].rsplit('/', maxsplit=1)[1]

    tag = None
    if res['ref'].startswith('refs/heads/'):
        branch = res['ref'][len('refs/heads/'):]
    elif res['ref'].startswith('refs/tags/') and 'base_ref' in res:
        branch = res['base_ref'][len('refs/heads/'):]
        tag = res['ref'][len('refs/tags/'):]
    else:
        return

    commit_id = res['head_commit']['id']

    conf = Configuration.from_file('config.yml', branch, commit_id)
    if conf is None:
        return

    build = Build.from_configuration(conf)
    runner = Runner.from_build(build)
    runner.run()


if __name__ == '__main__':
    app.run()
