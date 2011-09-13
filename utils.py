import re
import os
import stat
import time
import mimetypes
from future_builtins import map
from functools import wraps

from dulwich.objects import Commit, Blob
from pygments import highlight
from pygments.lexers import get_lexer_for_filename, get_lexer_by_name, \
                            guess_lexer, ClassNotFound
from pygments.formatters import HtmlFormatter
from flask import g



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

def subpaths(path):
    seen = []
    for part in path.split('/'):
        seen.append(part)
        yield part, '/'.join(seen)

def get_commit(repo, id):
    try:
        commit, isbranch = repo.get_branch_or_commit(id)
        if not isinstance(commit, Commit):
            raise KeyError
    except KeyError:
        g.err_msg = '"%s" has no commit "%s"' % (repo.name, id)
        abort(404)
    return commit, isbranch

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

def get_blob(repo, commit, path):
    return repo.get_tree(commit, path)
