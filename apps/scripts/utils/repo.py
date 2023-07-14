class GitHubRepo:
    repo = "repo"
    branch = "branch"
    @classmethod
    def get_repo(cls):
        return cls.repo
    @classmethod
    def get_branch(cls):
        return cls.branch
