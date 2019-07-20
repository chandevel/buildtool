import logging
import os
import random
import string

from app.configuration import Configuration
from app.github import Github
from app.init import global_config


class Build:
    def __init__(self, configuration: 'Configuration'):
        self.configuration = configuration

        self.build_id: str = ''.join(random.choice('0123456789abcdef') for _ in range(32))

        self.log_url = global_config.log_url + self.build_id

        self.source_path = os.path.join(configuration.data_path, self.build_id)

        self.github = Github()
        self.github_deploy_id = -1

    @classmethod
    def from_configuration(cls, configuration: 'Configuration'):
        return cls(configuration)

    def notify_started(self):
        self.github_deploy_id = self.github.deploy_create(
            self.configuration.commit_id, self.configuration.environment + ' deployment',
            self.configuration.environment)

        self.github.deploy_status(self.github_deploy_id, 'in_progress', self.log_url, '', 'Build started')

    def notify_error(self):
        self.github.deploy_status(self.github_deploy_id, 'error', self.log_url, '', 'Build error')

    def notify_success(self, env_url):
        self.github.deploy_status(self.github_deploy_id, 'success', self.log_url, env_url, 'Build succeeded')

    def log(self, value):
        logging.info(value)

        os.makedirs(global_config.log_path, exist_ok=True)

        if value and value[-1] != '\n':
            value += '\n'

        with open(os.path.join(global_config.log_path, self.build_id), 'a') as file:
            file.write(value)
