class GitHubRepo:
    repo = "IMXEren/rvx-builds"
    branch = "changelogs"
    @classmethod
    def get_repo(cls):
        return cls.repo
    @classmethod
    def get_branch(cls):
        return cls.branch
