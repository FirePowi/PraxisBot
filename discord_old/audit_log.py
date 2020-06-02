# -*- coding: utf-8 -*-

"""
The MIT License (MIT)

Copyright (c) 2015-2016 Rapptz

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from .user import User

class AuditLog:
    """Represents an audit log entry.

    Attributes
    -----------
    author : str
        Author of this action
    target : str
        Targeted user by this action
    reason : str
        Reason for this action
    id : str
        Audit log entry id
    type : int
        Action type
    """

    __slots__ = ['author', 'target', 'reason', 'id', 'type']

    def __init__(self, **kwargs):
        target = None
        author = None
        for u in kwargs.get('users'):
            if kwargs.get('target_id') == u.get('id'):
                target = User(**u)
            if kwargs.get('user_id') == u.get('id'):
                author = User(**u)

        self.id = kwargs.get('id')
        self.type = kwargs.get('action_type')
        self.reason = kwargs.get('reason')
        self.target = target
        self.author = author

        if not self.reason:
            self.reason = ""
