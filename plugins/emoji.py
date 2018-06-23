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
import sqlite3
import requests
from io import StringIO
from plugin import Plugin
from scope import UserPermission
from scope import ExecutionScope
from scope import ExecutionBlock

class EmojiPlugin(Plugin):
	"""
	Emoji commands
	"""

	name = "Emoji"

	def __init__(self, ctx, shell):
		super().__init__(ctx)

	async def execute_create_emoji(self, command, options, scope):
		if scope.permission < UserPermission.Admin:
			await self.ctx.send_message(scope.channel, "Only admins can use this command.")
			return scope

		parser = argparse.ArgumentParser(description='Create a custom emoji on the server.', prog=command)
		parser.add_argument('name', help='Name of the emoji')
		parser.add_argument('url', help='URL of the emoji')

		args = await self.parse_options(scope.channel, parser, options)

		if not args:
			return scope

		emoji = None
		for e in scope.server.emojis:
			if e.name == args.name:
				emoji = e
				break

		if emoji:
			await self.ctx.send_message(scope.channel, "An emoji with this name is already on this server: <:"+emoji.name+":"+emoji.id+">.")
			return scope

		#Get image
		result = requests.get(args.url, allow_redirects=True)
		if not result.ok:
			await self.ctx.send_message(scope.channel, "Can't download image located at:`"+url+"` ("+result.status_code+").")
			return scope

		emoji = await self.ctx.client.create_custom_emoji(scope.server, name=args.name, image=result.content)

		return scope

	async def execute_delete_emoji(self, command, options, scope):
		if scope.permission < UserPermission.Admin:
			await self.ctx.send_message(scope.channel, "Only admins can use this command.")
			return scope

		parser = argparse.ArgumentParser(description='Delete a custom emoji from the server.', prog=command)
		parser.add_argument('name', help='Name of the emoji')

		args = await self.parse_options(scope.channel, parser, options)

		if not args:
			return scope

		emoji = None
		for e in scope.server.emojis:
			if e.name == args.name:
				emoji = e
				break

		if not emoji:
			await self.ctx.send_message(scope.channel, "Emoji `"+args.name+"` not found on this server.")
			return scope

		await self.ctx.client.delete_custom_emoji(emoji)

		return scope

	async def execute_test_emoji(self, command, options, scope):
		parser = argparse.ArgumentParser(description='Display a custom emoji.', prog=command)
		parser.add_argument('name', help='Name of the emoji')

		args = await self.parse_options(scope.channel, parser, options)

		if not args:
			return scope

		emoji = None
		for e in scope.server.emojis:
			if e.name == args.name:
				emoji = e
				break

		if not emoji:
			await self.ctx.send_message(scope.channel, "Emoji `"+args.name+"` not found on this server.")
			return scope

		await self.ctx.send_message(scope.channel, "<:"+emoji.name+":"+emoji.id+">\n**ID: **"+str(emoji.id)+"\n**Name: **"+str(emoji.name)+"\n**URL: **"+str(emoji.url)+"")

		msg = await self.ctx.send_message(scope.channel, "<:"+emoji.name+":"+emoji.id+">")
		await self.ctx.client.add_reaction(msg, emoji)

		return scope

	async def execute_emojis(self, command, options, scope):
		text = "**List of emojis**\n"

		for e in scope.server.emojis:
			if len(text) > 1000:
				await self.ctx.send_message(scope.channel, text)
				text = ""
			text = text+"\n - <:"+e.name+":"+e.id+"> `"+e.name+"`"

		await self.ctx.send_message(scope.channel, text)

		return scope

	async def list_commands(self, server):
		return ["create_emoji", "delete_emoji", "test_emoji"]

	async def execute_command(self, shell, command, options, scope):
		if command == "create_emoji":
			scope.iter = scope.iter+1
			return await self.execute_create_emoji(command, options, scope)
		elif command == "delete_emoji":
			scope.iter = scope.iter+1
			return await self.execute_delete_emoji(command, options, scope)
		elif command == "test_emoji":
			scope.iter = scope.iter+1
			return await self.execute_test_emoji(command, options, scope)
		elif command == "emojis":
			scope.iter = scope.iter+1
			return await self.execute_emojis(command, options, scope)

		return scope
