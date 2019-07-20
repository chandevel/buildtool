import logging
import os.path
import shutil

from git import Repo, GitCommandError

from app.build import Build


class BuildContext:
    def __init__(self, build: Build):
        self.build: Build = build

        self.path = self.build.source_path

        self.repo = None

        self.tag = None

    def gather(self):
        try:
            # Create if nonexistent
            os.makedirs(self.path)
            logging.info('[BuildContext] Fetching code for commit {}'.format(self.build.configuration.commit_id))
            self.repo = Repo.clone_from(self.build.configuration.git_url, self.path, depth=10)
            self.repo.git.checkout(self.build.configuration.commit_id)

            logging.info('[BuildContext] Checked out')
        except GitCommandError as e:
            logging.error('[BuildContext] Error gathering code %s %s', e.stdout, e.stderr)
            raise Exception('Error gathering code ' + e.stdout + ' ' + e.stderr) from e

    def process(self):
        tagref = next((tag for tag in self.repo.tags if tag.commit == self.repo.head.commit), None)
        if tagref:
            self.tag = str(tagref)

        for key in self.build.configuration.keys:
            from_file = key.from_file
            to_file = key.to_file

            shutil.copy(
                os.path.join(from_file),
                os.path.join(self.path, to_file)
            )

    def clean(self):
        shutil.rmtree(self.path, ignore_errors=True)
