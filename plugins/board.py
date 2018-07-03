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
import praxisbot
from io import StringIO

class BoardPlugin(praxisbot.Plugin):
	"""
	Board commands
	"""

	name = "Board"

	def __init__(self, shell):
		super().__init__(shell)

		self.boardname_regex = re.compile('[a-zA-Z0-9_-]+')

		self.shell.create_sql_table("boards", ["id INTEGER PRIMARY KEY", "name TEXT", "discord_sid INTEGER", "discord_cid INTEGER", "discord_mid INTEGER"])

		self.add_command("create_board", self.execute_create_board)
		self.add_command("edit_board", self.execute_edit_board)
		self.add_command("delete_board", self.execute_delete_board)
		self.add_command("show_board", self.execute_show_board)
		self.add_command("boards", self.execute_boards)

	def create_embed(self, boardname, author):
		e = discord.Embed();
		e.type = "rich"
		e.set_footer(text="Last modification by "+author.display_name+". Use `edit_board "+boardname+"` to edit this board.")
		return e

	@praxisbot.command
	async def execute_create_board(self, scope, command, options, lines, **kwargs):
		"""
		Create a new board.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('boardname', help='Name of the board')
		parser.add_argument('--channel', '-c', help='Channel where the board will be.')
		parser.add_argument('--content', help='Channel where the board will be.')
		parser.add_argument('--format', action='store_true', help='Apply PraxisBot text formating.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		boardname = scope.format_text(args.boardname)
		self.ensure_object_name("Board name", boardname)

		if args.channel:
			chan = scope.shell.find_channel(args.channel, scope.server)
		else:
			chan = scope.channel

		if not chan:
			await scope.shell.print_error(scope, "Unknown channel.")
			return

		if scope.permission < praxisbot.UserPermission.Script and not chan.permissions_for(scope.user).send_messages:
			await scope.shell.print_permission(scope, "You don't have write permission in this channel.")
			return

		boardId = scope.shell.get_sql_data("boards", ["id"], {"discord_sid": int(scope.server.id), "name": str(boardname)})
		if boardId:
			await scope.shell.print_error(scope, "The board `"+boardname+"` already exists.")
			return

		if args.content:
			content = args.content
		elif len(lines) > 0:
			content = "\n".join(lines)
		else:
			content = "A fresh shared board ! All members with write permission in this channel can edit it."

		if args.format:
			content = scope.format_text(content)

		e = self.create_embed(boardname, scope.user);
		m = await scope.shell.client.send_message(chan, content, embed=e)
		scope.shell.set_sql_data("boards", {"discord_cid": int(m.channel.id), "discord_mid": int(m.id)}, {"discord_sid": int(m.server.id), "name": str(boardname)})

	@praxisbot.command
	async def execute_delete_board(self, scope, command, options, lines, **kwargs):
		"""
		Make a board no longer editable.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('boardname', help='Name of the board')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		boardname = scope.format_text(args.boardname)
		self.ensure_object_name("Board name", boardname)

		board = scope.shell.get_sql_data("boards", ["id", "discord_cid", "discord_mid"], {"discord_sid": int(scope.server.id), "name": str(boardname)})
		if not board:
			await scope.shell.print_error(scope, "Board `"+boardname+"` not found.")
			return

		chan = scope.shell.find_channel(str(board[1]), scope.server)
		if chan and scope.permission < praxisbot.UserPermission.Script and not chan.permissions_for(scope.user).send_messages:
			await scope.shell.print_permission(scope, "You don't have write permission in this channel.")
			return

		scope.shell.delete_sql_data("boards", {"id": board[0]})

		await scope.shell.print_success(scope, "Board `"+boardname+"` deleted.")

	@praxisbot.command
	async def execute_edit_board(self, scope, command, options, lines, **kwargs):
		"""
		Edit a board. Content of the board must be written in the second line, or with the parameter --content.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('boardname', help='Name of the board')
		parser.add_argument('--content', help='Channel where the board will be.')
		parser.add_argument('--format', action='store_true', help='Apply PraxisBot text formating.')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		boardname = scope.format_text(args.boardname)
		self.ensure_object_name("Board name", boardname)

		board = scope.shell.get_sql_data("boards", ["id", "discord_cid", "discord_mid"], {"discord_sid": int(scope.server.id), "name": str(boardname)})
		if not board:
			await scope.shell.print_error(scope, "Board `"+boardname+"` not found.")
			return

		chan = scope.shell.find_channel(str(board[1]), scope.server)
		if not chan:
			await scope.shell.print_error(scope, "The channel associated with this board is not accessible.")
			return
		if scope.permission < praxisbot.UserPermission.Script and not chan.permissions_for(scope.user).send_messages:
			await scope.shell.print_permission(scope, "You don't have write permission in this channel.")
			return

		m = None
		try:
			m = await scope.shell.client.get_message(chan, str(board[2]))
		except:
			pass
		if not m:
			await scope.shell.print_error(scope, "The message associated with this board is not accessible.")
			return scope

		if args.content:
			content = args.content
		elif len(lines) > 0:
			content = "\n".join(lines)
		else:
			content = ""

		if args.format:
			content = scope.format_text(content)

		e = self.create_embed(boardname, scope.user);
		await scope.shell.client.edit_message(m, content, embed=e)

		await scope.shell.print_success(scope, "Board `"+boardname+"` edited.")

	@praxisbot.command
	async def execute_show_board(self, scope, command, options, lines, **kwargs):
		"""
		Show the source code of a board.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('boardname', help='Name of the board')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		boardname = scope.format_text(args.boardname)
		self.ensure_object_name("Board name", boardname)

		board = scope.shell.get_sql_data("boards", ["id", "discord_cid", "discord_mid"], {"discord_sid": int(scope.server.id), "name": str(boardname)})
		if not board:
			await scope.shell.print_error(scope, "Board `"+boardname+"` not found.")
			return

		chan = scope.shell.find_channel(str(board[1]), scope.server)
		if not chan:
			await scope.shell.print_error(scope, "The channel associated with this board is not accessible.")
			return
		if scope.permission < praxisbot.UserPermission.Script and not chan.permissions_for(scope.user).read_messages:
			await scope.shell.print_permission(scope, "You don't have read permission in this channel.")
			return

		m = None
		try:
			m = await scope.shell.client.get_message(chan, str(board[2]))
		except:
			pass
		if not m:
			await scope.shell.print_error(scope, "The message associated with this board is not accessible.")
			return scope

		await scope.shell.client.send_message(scope.channel, "```"+m.content+"```")

	@praxisbot.command
	async def execute_boards(self, scope, command, options, lines, **kwargs):
		"""
		List all boards.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		stream = praxisbot.MessageStream(scope)
		await stream.send("**List of boards**\n")

		with scope.shell.dbcon:
			c = scope.shell.dbcon.cursor()
			for row in c.execute("SELECT name, discord_cid FROM "+scope.shell.dbtable("boards")+" WHERE discord_sid = ? ORDER BY name", [int(scope.server.id)]):

				chan = scope.shell.find_channel(str(row[1]), scope.server)
				if not chan:
					continue
				if scope.permission < praxisbot.UserPermission.Script and not chan.permissions_for(scope.user).read_messages:
					continue
				await stream.send("\n - `"+row[0]+"` in "+chan.mention)

		await stream.finish()
