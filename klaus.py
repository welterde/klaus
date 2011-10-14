import sys
import os

from jinja2 import Environment, FileSystemLoader
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash

from repo import Repo
from utils import timesince, pygmentize, force_unicode, guess_is_binary, guess_is_image, extract_author_name, subpaths, get_commit, listdir, get_blob



KLAUS_ROOT = os.path.join(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(KLAUS_ROOT, 'templates')

try:
    KLAUS_VERSION = ' ' + open(os.path.join(KLAUS_ROOT, '.git/refs/heads/master')).read()[:7]
except IOError:
    KLAUS_VERSION = ''

app = application = Flask(__name__, template_folder=TEMPLATE_DIR)
app.jinja_env.filters['u'] = force_unicode
app.jinja_env.filters['timesince'] = timesince
app.jinja_env.filters['shorten_id'] = lambda id: id[:7] if len(id) in {20, 40} else id
app.jinja_env.filters['shorten_message'] = lambda msg: msg.split('\n')[0]
app.jinja_env.filters['pygmentize'] = pygmentize
app.jinja_env.filters['is_binary'] = guess_is_binary
app.jinja_env.filters['is_image'] = guess_is_image
app.jinja_env.filters['shorten_author'] = extract_author_name
app.jinja_env.globals['KLAUS_VERSION'] = KLAUS_VERSION
app.debug = bool(os.environ.get('KLAUS_DEBUG', 'False'))

if os.path.isfile(os.path.join(os.environ.get('KLAUS_BASE_PATH', ''), 'projects.list')):
    app.repos={}
    f=open(os.path.join(os.environ.get('KLAUS_BASE_PATH', ''), 'projects.list'), 'r')
    for line in f.readlines():
        app.repos[line.strip().rstrip(os.sep)] = os.environ.get('KLAUS_BASE_PATH', '') + os.environ.get('KLAUS_BASE_PATH_SUFFIX', '') + line.strip()
    f.close()
else:
    app.repos = {repo.rstrip(os.sep): (os.environ.get('KLAUS_BASE_PATH', '') + repo) for repo in os.environ.get('KLAUS_REPOS', '').split()}

def get_repo(name):
    try:
        return Repo(name, app.repos[name])
    except KeyError:
        g.err_msg='No repository named "%s"' % name
        abort(404)

# now load some stuff..
@app.url_value_preprocessor
def pull_stuff(endpoint, values):
    if not values:
        return
    g.repo = values.pop('repo', None)
    # load repo if there is an repo
    if g.repo:
        g.repo = get_repo(g.repo)
        g.commit_id = values.pop('commit_id', None)
        g.commit, isbranch = get_commit(g.repo, g.commit_id)
        g.branches = g.repo.get_branch_names(exclude=[g.commit_id])
        if isbranch:
            g.branch=g.commit_id
        else:
            g.branch='master'
        
        # load path and subpaths if there is an path
        g.path = values.get('path', '')
        g.subpaths = subpaths(g.path)
        g.directory, g.filename = os.path.split(g.path.strip('/'))
    

# adds repo to url_for if it is there
@app.url_defaults
def add_repo(endpoint, values):
    if 'repo' in values or not g.repo:
        return
    if app.url_map.is_endpoint_expecting(endpoint, 'repo'):
        values['repo'] = g.repo.name

@app.url_defaults
def add_commit_id(endpoint, values):
    if 'commit_id' in values or not g.commit_id:
        return
    if app.url_map.is_endpoint_expecting(endpoint, 'commit_id'):
        values['commit_id'] = g.commit_id

@app.errorhandler(404)
def view_page_not_found(error):
    return render_template('page_not_found.html'), 404

@app.route('/')
def view_repo_list():
    repos = []
    for name in app.repos.iterkeys():
        repo = get_repo(name)
        refs = [repo[ref] for ref in repo.get_refs()]
        refs.sort(key=lambda obj:getattr(obj, 'commit_time', None), reverse=True)
        if len(refs) > 0:
            repos.append((name, refs[0].commit_time))
    if 'by-last-update' in request.args:
        repos.sort(key=lambda x: x[1], reverse=True)
    else:
        repos.sort(key=lambda x: x[0])
    return render_template("repo_list.html", repos=repos)

@app.route('/<path:repo>/tree/<string:commit_id>/')
@app.route('/<path:repo>/tree/<string:commit_id>/<path:path>')
def view_history(path=None):
    tree=listdir(g.repo, g.commit, g.path)
    
    try:
        page = int(request.args.get('page'))
    except (TypeError, ValueError):
        page = 0
    
    if page:
        history_length = 30
        skip = (page-1) * 30 + 10
        if page > 7:
            previous_pages = [0, 1, 2, None] + range(page)[-3:]
        else:
            previous_pages = xrange(page)
    else:
        history_length = 10
        skip = 0
        previous_pages=None
    return render_template('history.html', page=page, history_length=history_length, skip=skip, tree=tree, previous_pages=previous_pages)

@app.route('/<path:repo>/blob/<string:commit_id>/<path:path>')
def view_blob(path):
    tree=listdir(g.repo, g.commit, g.path)
    blob=get_blob(g.repo, g.commit, g.path)
    raw_url = url_for('view_raw_blob', path=g.path)
    too_large = sum(map(len, blob.chunked)) > 100*1024
    return render_template('view_blob.html', blob=blob, raw_url=raw_url, too_large=too_large, tree=tree)


@app.route('/<path:repo>/raw/<string:commit_id>/<path:path>')
def view_raw_blob(self):
    mime, encoding = self.get_mimetype_and_encoding()
    headers = {'Content-Type': mime}
    if encoding:
        headers['Content-Encoding'] = encoding
        body = self['blob'].chunked
    if len(body) == 1 and not body[0]:
        body = []
    self.direct_response('200 yo', headers, body)


def get_mimetype_and_encoding(blob, filename):
    if guess_is_binary(blob.chunked):
        mime, encoding = mimetypes.guess_type(filename)
        if mime is None:
            mime = 'appliication/octet-stream'
        return mime, encoding
    else:
        return 'text/plain', 'utf-8'


@app.route('/<path:repo>/commit/<string:commit_id>/')
def view_commit():
    return render_template('view_commit.html')

if __name__ == '__main__':
    app.run(debug=True)
