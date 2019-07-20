import datetime
import json
import os.path
import re
import shutil


class Artifact:
    def __init__(self, from_file, to_file):
        self.from_file = from_file
        self.to_file = to_file


class Key:
    def __init__(self, from_file, to_file):
        self.from_file = from_file
        self.to_file = to_file


class Artifacts:
    def __init__(self, build, repo):
        from app.build import Build
        from app.repo import BuildContext

        self.build: 'Build' = build
        self.repo: 'BuildContext' = repo

        self.version_code = None

    def process_artifacts(self):
        conf = self.build.configuration
        os.makedirs(conf.output_path, exist_ok=True)

        if conf.mode == 'hash':
            self.version_code = conf.commit_id[:8]
        elif conf.mode == 'tags':
            self.version_code = self.repo.tag

        for artifact in conf.artifacts:
            from_file = artifact.from_file
            to_file = artifact.to_file.replace('%v', self.version_code)

            try:
                shutil.copy(
                    os.path.join(self.repo.path, from_file),
                    os.path.join(conf.output_path, to_file)
                )
            except FileNotFoundError as e:
                self.build.log('BUILD FAILED, NO ARTIFACTS')
                self.build.log(str(e))
                raise e

    def process_version(self):
        message = '<h2>Clover update ready</h2>A new Clover version is available.'

        changelog, version_code_from_commit_message = \
            self.get_data_from_git_message(self.repo.repo.head.commit.message)
        if changelog:
            message += '\n\nChangelog:\n' + changelog

        message = message.replace('\n', '<br>')

        conf = self.build.configuration
        os.makedirs(os.path.dirname(conf.version_out), exist_ok=True)
        with open(conf.version_out, 'w') as f:
            url = conf.version_url.replace('%v', self.version_code)

            message = {
                'type': 'update',
                'date': datetime.datetime.today().strftime('%Y-%m-%dT%H:%M:%S'),
                'message_html': message,

                'apk': {
                    conf.version_flavor: {
                        'url': url
                    }
                }
            }

            if conf.mode == 'hash':
                message['hash'] = conf.commit_id[:8]
            elif conf.mode == 'tags':
                # Is different from 'v1.2.3', it's the android code (10203).
                message['code'] = version_code_from_commit_message

            version = {
                'api_version': 1,
                'messages': [message],
                'check_interval': 432000000
            }

            json.dump(version, f, indent=4)

        return url

    def get_data_from_git_message(self, message):
        changelog = ''

        m = re.search(r'^CHANGELOG:[\r\n]([\s\S]+)[\r\n]{2}', message, re.M)
        if m:
            changelog = m.group(1)

        version_code = None
        m = re.search(r'^VERSIONCODE:[\r\n]([\d]+)[\r\n]', message, re.M)
        if m:
            version_code = int(m.group(1))

        return changelog, version_code
