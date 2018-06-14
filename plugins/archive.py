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
from io import StringIO
from plugin import Plugin
from scope import UserPermission
from scope import ExecutionScope
from scope import ExecutionBlock

class ArchivePlugin(Plugin):
	"""
	Archive commands
	"""

	name = "Archive"

	def __init__(self, ctx):
		super().__init__(ctx)

	def archive_message(self, m):
		text = m.author.name+"#"+m.author.discriminator+" - "+str(m.timestamp)+" - (message: "+m.id+", author: "+m.author.id+")"
		text = text+"\n"+m.content
		for a in m.attachments:
			text = text+"\nAttachment: "+str(a)
		for e in m.embeds:
			text = text+"\nEmbed: "+str(e)
		text = text+"\n\n"
		return text

	def generate_header(self, chan, title):
		text = "***********************************************************"
		text = text+"\n* Server: "+chan.server.name+" ("+chan.server.id+")"
		text = text+"\n* Channel: "+chan.name+" ("+chan.id+")"
		text = text+"\n* "+title
		text = text+"\n***********************************************************"
		text = text+"\n\n"
		return text

	def generate_filename(self, chan, suffix):
		fn = chan.server.name.lower().strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_")
		fn = fn+"_"+chan.name.lower().strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_")
		fn = fn+"_"+suffix+".txt"
		return fn

	async def execute_archive_last_day(self, command, options, scope):

		parser = argparse.ArgumentParser(description='Create a text file containing all messages from the last 24h.', prog=command)
		parser.add_argument('--channel', '-c', help='Channel to archive')

		args = await self.parse_options(scope.channel, parser, options)

		if args and args.channel:
			chan = self.ctx.find_channel(args.channel, scope.server)
		else:
			chan = scope.channel

		if chan:
			if not chan.permissions_for(scope.user).read_messages:
				await self.ctx.send_message(scope.channel, "You don't have read permission in this channel.")
				return scope

			messages = await self.ctx.client.pins_from(chan)
			counter = 0
			d = str(datetime.datetime.now())
			textHeader = self.generate_header(chan, "Last messages before "+d)

			timecur = datetime.datetime.now()
			limit = timecur-datetime.timedelta(days=1)
			b = timecur
			newmessages = True
			text = ""
			while counter < 1000 and timecur > limit and newmessages:
				newmessages = False
				async for m in self.ctx.client.logs_from(chan, limit=200, before=b):
					counter = counter+1
					text = self.archive_message(m)+text
					b = m
					timecur = m.timestamp
					newmessages = True

			f = io.StringIO(textHeader+text)
			await self.ctx.client.send_file(scope.channel, f, filename=self.generate_filename(chan, d), content=str(counter)+" messages archived.")
			f.close()
		else:
			await self.ctx.send_message(scope.channel, "Unknown channel.")

		return scope

	async def execute_archive_pins(self, command, options, scope):

		parser = argparse.ArgumentParser(description='Create a text file containing all pinned messages.', prog=command)
		parser.add_argument('--channel', '-c', help='Channel to archive')

		args = await self.parse_options(scope.channel, parser, options)

		if args and args.channel:
			chan = self.ctx.find_channel(args.channel, scope.server)
		else:
			chan = scope.channel

		if chan:
			if not chan.permissions_for(scope.user).read_messages:
				await self.ctx.send_message(scope.channel, "You don't have read permission in this channel.")
				return scope

			messages = await self.ctx.client.pins_from(chan)
			counter = 0
			textHeader = self.generate_header(chan, "Pinned messages")
			text = ""
			for m in messages:
				counter = counter+1
				text = self.archive_message(m)+text

			f = io.StringIO(textHeader+text)
			await self.ctx.client.send_file(scope.channel, f, filename=self.generate_filename(chan, "pins"), content=str(counter)+" pinned messages archived.")
			f.close()
		else:
			await self.ctx.send_message(scope.channel, "Unknown channel.")

		return scope

	async def list_commands(self, server):
		return ["archive_pins", "archive_day"]

	async def execute_command(self, shell, command, options, scope):
		if command == "archive_pins":
			scope.iter = scope.iter+1
			return await self.execute_archive_pins(command, options, scope)
		if command == "archive_last_day":
			scope.iter = scope.iter+1
			return await self.execute_archive_last_day(command, options, scope)

		return scope
