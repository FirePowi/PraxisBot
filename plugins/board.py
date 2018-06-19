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

import shlex
import argparse
import re
import discord
import traceback
from io import StringIO
from plugin import Plugin
from scope import UserPermission
from scope import ExecutionScope
from scope import ExecutionBlock

class BoardPlugin(Plugin):
	"""
	Board commands
	"""

	name = "Board"

	def __init__(self, ctx, shell):
		super().__init__(ctx)
		self.boardname_regex = re.compile('[a-zA-Z0-9_-]+')

		self.ctx.dbcon.execute("CREATE TABLE IF NOT EXISTS "+self.ctx.dbprefix+"boards(id INTEGER PRIMARY KEY, name TEXT, discord_sid INTEGER, discord_cid INTEGER, discord_mid INTEGER)");

	def create_embed(self, boardname, author):
		e = discord.Embed();
		e.type = "rich"
		e.set_footer(text="Last modification by "+author.display_name+". Use `edit_board "+boardname+"` to edit this board.")
		return e

	async def execute_create_board(self, command, options, scope):
		content = options.split("\n");
		options = content[0]
		if len(content) == 1:
			content = "A fresh shared board ! All members with write permission in this channel can edit it."
		else:
			content = "\n".join(content[1:])

		parser = argparse.ArgumentParser(description='Create a new board.', prog=command)
		parser.add_argument('boardname', help='Name of the board')
		parser.add_argument('--channel', '-c', help='Channel where the board will be.')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			boardname = self.ctx.format_text(args.boardname, scope)

			if not self.boardname_regex.fullmatch(boardname):
				await self.ctx.send_message(scope.channel, "The board name must be alphanumeric")
				return scope

			chan = scope.channel
			if args.channel:
				c = self.ctx.find_channel(self.ctx.format_text(args.channel, scope), scope.server)
				if c:
					chan = c

			if not chan.permissions_for(scope.user).send_messages:
				await self.ctx.send_message(scope.channel, "You don't have write permission in this channel.")
				return scope

			with self.ctx.dbcon:
				c = self.ctx.dbcon.cursor()
				c.execute("SELECT id FROM "+self.ctx.dbprefix+"boards WHERE discord_sid = ? AND name = ?", [int(scope.server.id), str(boardname)])
				r = c.fetchone()
				if r:
					await self.ctx.send_message(scope.channel, "The board `"+boardname+"` already exists.")
					return scope

			e = self.create_embed(boardname, scope.user);

			try:
				m = await self.ctx.send_message(chan, content, e)

				with self.ctx.dbcon:
					if not self.ctx.dbcon.execute("INSERT INTO "+self.ctx.dbprefix+"boards (name, discord_sid, discord_cid, discord_mid) VALUES (?, ?, ?, ?)", [str(boardname), int(m.server.id), int(m.channel.id), int(m.id)]):
						await self.ctx.send_message(scope.channel, "The board `"+boardname+"` can't be saved.")
			except:
				print(traceback.format_exc())
				await self.ctx.send_message(scope.channel, "The board `"+boardname+"` can't be created in this channel.")

		return scope

	async def execute_delete_board(self, command, options, scope):

		parser = argparse.ArgumentParser(description='Make a board no longer editable.', prog=command)
		parser.add_argument('boardname', help='Name of the board')

		args = await self.parse_options(scope.channel, parser, options)
		if args:
			boardname = self.ctx.format_text(args.boardname, scope)

			if not self.boardname_regex.fullmatch(boardname):
				await self.ctx.send_message(scope.channel, "The board name must be alphanumeric")
				return scope

			with self.ctx.dbcon:
				c = self.ctx.dbcon.cursor()
				c.execute("SELECT id, discord_cid FROM "+self.ctx.dbprefix+"boards WHERE discord_sid = ? AND name = ?", [int(scope.server.id), str(boardname)])
				r = c.fetchone()
				if r:
					chan = self.ctx.find_channel("<#"+str(r[1])+">", scope.server)
					if chan and not chan.permissions_for(scope.user).send_messages:
						await self.ctx.send_message(scope.channel, "You don't have write permission in this channel.")
						return scope

					c.execute("DELETE FROM "+self.ctx.dbprefix+"boards WHERE id = ?", [r[0]])
					await self.ctx.send_message(scope.channel, "Board `"+boardname+"` deleted.")
					return scope

			await self.ctx.send_message(scope.channel, "Board `"+boardname+"` not found.")
		return scope

	async def execute_edit_board(self, command, options, scope):

		content = options.split("\n");
		if len(content) > 1:
			options = content[0]
			content = "\n".join(content[1:])
		else:
			await self.ctx.send_message(scope.channel, "You must write a content in the second line. Ex.: ```\n"+command+options+"\nMy message.```")
			return scope

		parser = argparse.ArgumentParser(description='Edit a board. Wirte the content of the board in the second line', prog=command)
		parser.add_argument('boardname', help='Name of the board')

		args = await self.parse_options(scope.channel, parser, options)

		if args:
			boardname = self.ctx.format_text(args.boardname, scope)

			if not self.boardname_regex.fullmatch(boardname):
				await self.ctx.send_message(scope.channel, "The board name must be alphanumeric")
				return scope

			with self.ctx.dbcon:
				c = self.ctx.dbcon.cursor()
				c.execute("SELECT discord_cid, discord_mid FROM "+self.ctx.dbprefix+"boards WHERE discord_sid = ? AND name = ?", [int(scope.server.id), str(boardname)])
				r = c.fetchone()
				if r:
					chan = self.ctx.find_channel("<#"+str(r[0])+">", scope.server)
					if not chan:
						await self.ctx.send_message(scope.channel, "The channel associated with this board is not accessible.")
						return scope

					if not chan.permissions_for(scope.user).send_messages:
						await self.ctx.send_message(scope.channel, "You don't have write permission in this channel.")
						return scope

					m = None
					try:
						m = await self.ctx.client.get_message(chan, str(r[1]))
					except:
						pass
					if not m:
						await self.ctx.send_message(scope.channel, "The message associated with this board is not accessible.")
						return scope

					e = self.create_embed(args.boardname, scope.user);
					await self.ctx.client.edit_message(m, content, embed=e)
					return scope

			await self.ctx.send_message(scope.channel, "Board `"+boardname+"` not found.")
		return scope

	async def list_commands(self, server):
		return ["create_board", "edit_board", "delete_board"]

	async def execute_command(self, shell, command, options, scope):
		if command == "create_board":
			scope.iter = scope.iter+1
			return await self.execute_create_board(command, options, scope)
		if command == "edit_board":
			scope.iter = scope.iter+1
			return await self.execute_edit_board(command, options, scope)
		if command == "delete_board":
			scope.iter = scope.iter+1
			return await self.execute_delete_board(command, options, scope)

		return scope
