import sys
import os
import re
import stat
import time
import mimetypes
from future_builtins import map
from functools import wraps

from dulwich.objects import Commit, Blob

from jinja2 import Environment, FileSystemLoader

from pygments import highlight
from pygments.lexers import get_lexer_for_filename, get_lexer_by_name, \
                            guess_lexer, ClassNotFound
from pygments.formatters import HtmlFormatter

from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash

from repo import Repo


KLAUS_ROOT = os.path.join(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(KLAUS_ROOT, 'templates')

try:
    KLAUS_VERSION = ' ' + open(os.path.join(KLAUS_ROOT, '.git/refs/heads/master')).read()[:7]
except IOError:
    KLAUS_VERSION = ''

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.debug = True
app.jinja_env.globals['KLAUS_VERSION'] = KLAUS_VERSION

app.repos = {repo.rstrip(os.sep): (os.environ.get('KLAUS_BASE_PATH', '') + repo) for repo in os.environ.get('KLAUS_REPOS', '').split()}

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
        # TODO: find correct branch here..
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


def pygmentize(code, filename=None, language=None):
    if language:
        lexer = get_lexer_by_name(language)
    else:
        try:
            lexer = get_lexer_for_filename(filename)
        except ClassNotFound:
            lexer = guess_lexer(code)
    return highlight(code, lexer, pygments_formatter)
pygments_formatter = HtmlFormatter(linenos=True)

def timesince(when, now=time.time):
    delta = now() - when
    result = []
    break_next = False
    for unit, seconds, break_immediately in [
        ('year', 365*24*60*60, False),
        ('month', 30*24*60*60, False),
        ('week', 7*24*60*60, False),
        ('day', 24*60*60, True),
        ('hour', 60*60, False),
        ('minute', 60, True),
        ('second', 1, False),
    ]:
        if delta > seconds:
            n = int(delta/seconds)
            delta -= n*seconds
            result.append((n, unit))
            if break_immediately:
                break
            if not break_next:
                break_next = True
                continue
        if break_next:
            break

    if len(result) > 1:
        n, unit = result[0]
        if unit == 'month':
            if n == 1:
                # 1 month, 3 weeks --> 7 weeks
                result = [(result[1][0] + 4, 'week')]
            else:
                # 2 months, 1 week -> 2 months
                result = result[:1]
        elif unit == 'hour' and n > 5:
            result = result[:1]

    return ', '.join('%d %s%s' % (n, unit, 's' if n != 1 else '')
                     for n, unit in result[:2])

def guess_is_binary(data):
    if isinstance(data, basestring):
        return '\0' in data
    else:
        return any(map(guess_is_binary, data))

def guess_is_image(filename):
    mime, encoding = mimetypes.guess_type(filename)
    if mime is None:
        return False
    return mime.startswith('image/')

def force_unicode(s):
    if isinstance(s, unicode):
        return s
    try:
        return s.decode('utf-8')
    except UnicodeDecodeError as exc:
        pass
    try:
        return s.decode('iso-8859-1')
    except UnicodeDecodeError:
        pass
    try:
        import chardet
        encoding = chardet.detect(s)['encoding']
        if encoding is not None:
            return s.decode(encoding)
    except (ImportError, UnicodeDecodeError):
        raise exc

def extract_author_name(email):
    match = re.match('^(.*?)<.*?>$', email)
    if match:
        return match.group(1)
    return email

app.jinja_env.filters['u'] = force_unicode
app.jinja_env.filters['timesince'] = timesince
app.jinja_env.filters['shorten_id'] = lambda id: id[:7] if len(id) in {20, 40} else id
app.jinja_env.filters['shorten_message'] = lambda msg: msg.split('\n')[0]
app.jinja_env.filters['pygmentize'] = pygmentize
app.jinja_env.filters['is_binary'] = guess_is_binary
app.jinja_env.filters['is_image'] = guess_is_image
app.jinja_env.filters['shorten_author'] = extract_author_name

def subpaths(path):
    seen = []
    for part in path.split('/'):
        seen.append(part)
        yield part, '/'.join(seen)

def get_repo(name):
    try:
        return Repo(name, app.repos[name])
    except KeyError:
        # for now just abort..
        # raise HttpError(404, 'No repository named "%s"' % name)
        abort(404)

@app.route('/')
def view_repo_list():
    repos = []
    for name in app.repos.iterkeys():
        repo = get_repo(name)
        refs = [repo[ref] for ref in repo.get_refs()]
        refs.sort(key=lambda obj:getattr(obj, 'commit_time', None), reverse=True)
        repos.append((name, refs[0].commit_time))
    if 'by-last-update' in request.args:
        repos.sort(key=lambda x: x[1], reverse=True)
    else:
        repos.sort(key=lambda x: x[0])
    return render_template("repo_list.html", repos=repos)

#class BaseRepoView(BaseView):
#    def __init__(self, env, repo, commit_id, path=None):
#        self['repo'] = repo = get_repo(repo)
#        self['commit_id'] = commit_id
#        self['commit'], isbranch = self.get_commit(repo, commit_id)
#        self['branch'] = commit_id if isbranch else 'master'
#        self['path'] = path
#        if path:
#            self['subpaths'] = list(subpaths(path))
#        self['build_url'] = self.build_url
#        super(BaseRepoView, self).__init__(env)

def get_commit(repo, id):
    try:
        commit, isbranch = repo.get_branch_or_commit(id)
        if not isinstance(commit, Commit):
            raise KeyError
    except KeyError:
        #raise HttpError(404, '"%s" has no commit "%s"' % (repo.name, id))
        abort(404)
    return commit, isbranch

#    def build_url(self, view=None, **kwargs):
#        if view is None:
#            view = self.__class__.__name__
#        default_kwargs = {
#            'repo': self['repo'].name,
#            'commit_id': self['commit_id']
#        }
#        return app.build_url(view, **dict(default_kwargs, **kwargs))

def listdir(repo, commit, path):
    dirs, files = [], []
    tree, root = get_tree(repo, commit, path)
    for entry in tree.iteritems():
        name, entry = entry.path, entry.in_path(root)
        if entry.mode & stat.S_IFDIR:
            dirs.append((name.lower(), name, entry.path))
        else:
            files.append((name.lower(), name, entry.path))
    files.sort()
    dirs.sort()
    if root:
        dirs.insert(0, (None, '..', os.path.split(root)[0]))
    return {'dirs' : dirs, 'files' : files}

def get_tree(repo, commit, path):
    root = path
    tree = repo.get_tree(commit, root)
    if isinstance(tree, Blob):
        root = os.path.split(root)[0]
        tree = repo.get_tree(commit, root)
    return tree, root

#@route('/:repo:/tree/:commit_id:/(?P<path>.*)', 'history')
@app.route('/<path:repo>/tree/<string:commit_id>/')
@app.route('/<path:repo>/tree/<string:commit_id>/<int:page>/')
@app.route('/<path:repo>/tree/<string:commit_id>/<int:page>/<path:path>')
def view_history(page=0, path=None):
    tree=listdir(g.repo, g.commit, g.path)
    
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
    return render_template('history.html', repo=g.repo, commit=g.commit, commit_id=g.commit_id, branch=g.branch, page=page, history_length=history_length, skip=skip, tree=tree)

def get_blob(repo, commit, path):
    return repo.get_tree(commit, path)

#class BaseBlobView(BaseRepoView):
#    def view(self):
#        self['blob'] = self['repo'].get_tree(self['commit'], self['path'])
#        self['directory'], self['filename'] = os.path.split(self['path'].strip('/'))

#@route('/:repo:/blob/:commit_id:/(?P<path>.*)', 'view_blob')
@app.route('/<path:repo>/blob/<string:commit_id>/<path:path>')
def view_blob(path):
    tree=listdir(g.repo, g.commit, g.path)
    blob=get_blob(g.repo, g.commit, g.path)
    raw_url = url_for('view_raw_blob', path=g.path)
    too_large = sum(map(len, blob.chunked)) > 100*1024
    return render_template('view_blob.html', blob=blob, raw_url=raw_url, too_large=too_large, tree=tree)


#@route('/:repo:/raw/:commit_id:/(?P<path>.*)', 'raw_blob')
@app.route('/<path:repo>/raw/<string:commit_id>/<path:path>')
#class RawBlob(object):
def view_raw_blob(self):
#    super(RawBlob, self).view()
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


#@route('/:repo:/commit/:commit_id:/', 'view_commit')
@app.route('/<path:repo>/commit/<string:commit_id>/')
#class CommitView(object):
def view_commit():
    return render_template('view_commit.html')


#@route('/static/(?P<path>.+)', 'static')
class StaticFilesView(object):
    def __init__(self, env, path):
        self['path'] = path
        super(StaticFilesView, self).__init__(env)

    def view(self):
        path = './static/' + self['path']
        relpath = os.path.join(KLAUS_ROOT, path)
        if os.path.isfile(relpath):
            self.direct_response(open(relpath))
        else:
            raise HttpError(404, 'Not Found')

if __name__ == '__main__':
    app.run(debug=True)
