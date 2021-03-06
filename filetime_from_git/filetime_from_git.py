#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from git import Git, Repo, InvalidGitRepositoryError
from pelican import signals, contents
from datetime import datetime
from time import mktime, altzone
from pelican.utils import strftime, set_date_tzinfo

try:
    repo = Repo(os.path.abspath('.'))
    git = Git(os.path.abspath('.'))
except InvalidGitRepositoryError as e:
    repo = None

def datetime_from_timestamp(timestamp, content):
    """
    Helper function to add timezone information to datetime,
    so that datetime is comparable to other datetime objects in recent versions
    that now also have timezone information.
    """
    return set_date_tzinfo(datetime.fromtimestamp(timestamp), tz_name=content.settings.get('TIMEZONE', None))

def filetime_from_git(content):
    if isinstance(content, contents.Static) or repo is None:
        return
    gittime = content.metadata.get('gittime', 'yes').lower()
    gittime = gittime.replace("false", "no").replace("off", "no")
    if gittime == "no":
        return
    # 1. file is not managed by git
    #    date: fs time
    # 2. file is staged, but has no commits
    #    date: fs time
    # 3. file is managed, and clean
    #    date: first commit time, update: last commit time or None
    # 4. file is managed, but dirty
    #    date: first commit time, update: fs time
    path = content.source_path
    status, stdout, stderr = git.execute(['git', 'ls-files', path, '--error-unmatch'],
            with_extended_output=True, with_exceptions=False)
    if status != 0:
        # file is not managed by git
        content.date = datetime_from_timestamp(os.stat(path).st_ctime, content)
    else:
        # file is managed by git
        commits = repo.commits(path=path)
        if len(commits) == 0:
            # never commited, but staged
            content.date = datetime_from_timestamp(os.stat(path).st_ctime, content)
        else:
            # has commited
            content.date = datetime_from_timestamp(mktime(commits[-1].committed_date) - altzone, content)

            status, stdout, stderr = git.execute(['git', 'diff', '--quiet', 'HEAD', path],
                    with_extended_output=True, with_exceptions=False)
            if status != 0:
                # file has changed
                content.modified = datetime_from_timestamp(os.stat(path).st_ctime, content)
            else:
                # file is not changed
                if len(commits) > 1:
                    content.modified = datetime_from_timestamp(mktime(commits[0].committed_date) - altzone, content)
    if not hasattr(content, 'modified'):
        content.modified = content.date
    if hasattr(content, 'date'):
        content.locale_date = strftime(content.date, content.date_format)
    if hasattr(content, 'modified'):
        content.locale_modified = strftime(content.modified, content.date_format)

def register():
    signals.content_object_init.connect(filetime_from_git)
