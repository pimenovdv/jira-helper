import gitlab
gl = gitlab.Gitlab("https://gitlab.com")
# we don't have token but we can fetch public repo branches
project = gl.projects.get('gitlab-org/gitlab-foss')
branches = project.branches.list(per_page=1)
if branches:
    b = branches[0]
    print(dir(b))
    print(b.attributes)
