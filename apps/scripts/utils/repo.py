class GitHubRepo:
    repo = "IMXEren/rvx-buids"
    branch = "main"
    @classmethod
    def get_repo(cls):
        return cls.repo
    @classmethod
    def get_branch(cls):
        return cls.branch