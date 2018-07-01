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
import datetime
import io
import requests
import praxisbot

class EmojiPlugin(praxisbot.Plugin):
	"""
	Emoji commands
	"""

	name = "Emoji"

	def __init__(self, shell):
		super().__init__(shell)

		self.add_command("create_emoji", self.execute_create_emoji)
		self.add_command("delete_emoji", self.execute_delete_emoji)
		self.add_command("test_emoji", self.execute_test_emoji)
		self.add_command("emojis", self.execute_emojis)

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_create_emoji(self, scope, command, options, lines, **kwargs):
		"""
		Create a custom emoji on the server.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('name', help='Name of the emoji')
		parser.add_argument('url', help='URL of the emoji')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		emoji = scope.shell.find_emoji(args.name, scope.server)
		if emoji:
			await scope.shell.print_error(scope, "An emoji with this name is already on this server: <:"+emoji.name+":"+emoji.id+">.")
			return

		#Get image
		result = requests.get(args.url, allow_redirects=True)
		if not result.ok:
			await scope.shell.print_error(scope, "Can't download image located at:`"+url+"` ("+result.status_code+").")
			return

		emoji = await scope.shell.client.create_custom_emoji(scope.server, name=args.name, image=result.content)
		await scope.shell.print_success(scope, "Emoji `:"+emoji.name+":` <:"+emoji.name+":"+emoji.id+"> created.")

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_delete_emoji(self, scope, command, options, lines, **kwargs):
		"""
		Delete a custom emoji from the server.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('name', help='Name of the emoji')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		emoji = scope.shell.find_emoji(args.name, scope.server)
		if not emoji:
			await scope.shell.print_error(scope, "Emoji `"+args.name+"` not found on this server.")
			return

		await scope.shell.client.delete_custom_emoji(emoji)
		await scope.shell.print_success(scope, "Emoji `:"+emoji.name+":` deleted.")

	@praxisbot.command
	async def execute_test_emoji(self, scope, command, options, lines, **kwargs):
		"""
		Display a custom emoji in all sizes.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('name', help='Name of the emoji')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		emoji = scope.shell.find_emoji(args.name, scope.server)
		if not emoji:
			await scope.shell.print_error(scope, "Emoji `"+args.name+"` not found on this server.")
			return

		await scope.shell.client.send_message(scope.channel, "<:"+emoji.name+":"+emoji.id+">\n**ID: **"+str(emoji.id)+"\n**Name: **"+str(emoji.name)+"\n**URL: **"+str(emoji.url)+"")

		msg = await scope.shell.client.send_message(scope.channel, "<:"+emoji.name+":"+emoji.id+">")
		await scope.shell.client.add_reaction(msg, emoji)

	@praxisbot.command
	async def execute_emojis(self, scope, command, options, lines, **kwargs):
		"""
		List of all custom emojis
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return

		stream = praxisbot.MessageStream(scope)
		await stream.send("**List of emojis**\n")
		for e in scope.server.emojis:
			await stream.send("\n - <:"+e.name+":"+e.id+"> `"+e.name+"`")

		await stream.finish()
