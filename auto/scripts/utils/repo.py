class GitHubRepo:
    repo = "Datokina/rvx-builds"
    branch = "changelogs"
    backup_branch = "main"

    @classmethod
    def get_repo(cls):
        return cls.repo

    @classmethod
    def get_branch(cls):
        return cls.branch

    @classmethod
    def get_backup_branch(cls):
        return cls.backup_branch
