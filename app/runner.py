import logging

from app.build import Build
from app.artifact import Artifacts
from app.executor import BuildExecutor
from app.repo import BuildContext


class Runner:
    @classmethod
    def from_build(cls, build: Build):
        return cls(build)

    def __init__(self, build: Build):
        self.build = build

    def run(self):
        logging.getLogger().setLevel(logging.DEBUG)

        self.build.log('[runner] Starting build (build id: {}, env: {})'.format(
            self.build.build_id, self.build.configuration.environment))

        self.build.notify_started()
        repo = None
        try:
            repo = BuildContext(self.build)
            repo.gather()
            repo.process()

            url = self.run_build(repo)
            self.build.notify_success(url)
        except Exception as e:
            if repo:
                logging.info('[runner] cleaning up repo')
                repo.clean()

            self.build.log(str(e))
            self.build.notify_error()
            raise e

    def run_build(self, repo):
        conf = self.build.configuration
        # Cancel if we require tags, but no tags were found for this commit.
        if conf.mode == 'tags' and not repo.tag:
            logging.error('[runner] No tag found for git ref, aborting')
            return

        if conf.dry_run:
            logging.info('[runner] dry_run execute_build')
        else:
            build_executor = BuildExecutor.from_configuration(self.build)
            build_executor.setup()
            build_executor.run()

        artifacts = Artifacts(self.build, repo)

        artifacts.process_artifacts()
        return artifacts.process_version()
