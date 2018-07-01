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

class ConnectedAccount:
    """Represents a connected account.

    Attributes
    -----------
    verified : bool
        If the account is verified
    type : str
        Account type
    id : str
        Account id
    name : str
        Account nickname
    """

    __slots__ = ['verified', 'type', 'id', 'name']

    def __init__(self, **kwargs):
        self.verified = kwargs.get('verified')
        self.id = kwargs.get('id')
        self.name = kwargs.get('name')
        self.type = kwargs.get('type')

    @property
    def provider_name(self):
        if self.type == "twitter":
            return "Twitter"
        elif self.type == "steam":
            return "Steam"
        elif self.type == "twitch":
            return "Twitch"
        elif self.type == "skype":
            return "Skype"
        elif self.type == "facebook":
            return "Facebook"
        else:
            return self.type

    @property
    def url(self):
        if self.type == "twitter":
            return "https://www.twitter.com/"+str(self.name)
        elif self.type == "steam":
            return "https://steamcommunity.com/profiles/"+str(self.id)
        elif self.type == "twitch":
            return "https://www.twitch.tv/"+str(self.name)
        else:
            None



class Profile:
    """Represents a Discord user profile.

    Attributes
    -----------
    user : :class:`User`
        The user.
    connected_accounts
        An iterable of :class:`ConnectedAccount`.
    """

    __slots__ = ['user', '_connected_accounts']

    def __init__(self, **kwargs):
        self.user = User(**kwargs.get('user'))
        self._connected_accounts = []
        for ca in kwargs.get('connected_accounts', []):
            connected_account = ConnectedAccount(**ca)
            self._add_connected_account(connected_account)

    def _add_connected_account(self, ca):
        self._connected_accounts.append(ca)

    @property
    def connected_accounts(self):
        return self._connected_accounts
