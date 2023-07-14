class GitHubURLs:
    default_repo = "IMXEren/rvx-builds"
    default_branch = "main"

    def __init__(self, repo_full=default_repo, repo_branch=default_branch):
        self.repo = repo_full
        self.branch = repo_branch
    
    def get_patches_py(self):
        return f"https://raw.githubusercontent.com/{self.repo}/{self.branch}/src/patches.py"
    
    def get_config_py(self):
        return f"https://raw.githubusercontent.com/{self.repo}/{self.branch}/src/config.py"
    
    def get_extras_json(self):
        return f"https://raw.githubusercontent.com/{self.repo}/{self.branch}/apps/json/extras.json"
    
    def get_rv_json(self):
        return f"https://raw.githubusercontent.com/revanced/revanced-patches/main/patches.json"
    
    def get_rvx_json(self):
        return f"https://raw.githubusercontent.com/inotia00/revanced-patches/revanced-extended/patches.json"
