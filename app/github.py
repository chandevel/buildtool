import requests

from app.init import global_config


class Github:
    def __init__(self):
        self.base = 'https://api.github.com'
        self.repo_path = global_config.github_repo_path
        self.token = global_config.github_token

    def deploy_create(self, ref: str, desc: str, environment: str):
        res = self.call_api('/repos/' + self.repo_path + '/deployments', {
            'ref': ref,
            'auto_merge': False,
            'payload': {},
            'description': desc,
            'environment': environment
        })
        return res['id']

    def deploy_status(self, deploy_id: int, state: str, log_url: str, env_url: str, desc: str):
        self.call_api('/repos/' + self.repo_path + '/deployments/' + str(deploy_id) + '/statuses', {
            'state': state,
            'log_url': log_url,
            'description': desc,
            'environment_url': env_url,
            'auto_inactive': False
        })

    def call_api(self, path, data):
        r = requests.post(self.base + path, headers={
            'Authorization': 'token ' + self.token,
            'Accept': 'application/vnd.github.flash-preview+json, application/vnd.github.ant-man-preview+json '
        }, json=data)
        r.raise_for_status()
        return r.json()
