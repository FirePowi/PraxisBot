"""

Copyright (C) 2018 MonaIzquierda (mona.izquierda@gmail.com)

This file is part of PraxisBot.

PraxisBot is free software: you can redistribute it and/or  modify
it under the terms of the GNU Affero General Public License, version 3,
as published by the Free Software Foundation.

PraxisBot is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with PraxisBot.  If not, see <http://www.gnu.org/licenses/>.

"""

class UserPermission:
	Member=0
	Script=1
	Admin=2

class ExecutionBlock:
	def __init__(self, endname, e):
		self.endname = endname
		self.execute = e

class ExecutionScope:
	def __init__(self):
		self.iter = 0
		self.level = 0
		self.vars = {}
		self.permission = UserPermission.Member
		self.server = None
		self.user = None
		self.channel = None
		self.blocks = []
