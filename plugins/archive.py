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
import praxisbot

class ArchivePlugin(praxisbot.Plugin):
	"""
	Archive commands
	"""

	name = "Archive"

	def __init__(self, shell):
		super().__init__(shell)

		self.add_command("archive_pins", self.execute_archive_pins)
		self.add_command("archive_last_day", self.execute_archive_last_day)
		self.add_command("archive_all", self.execute_archive_all)

	def archive_message(self, m):
		text = "{}#{} – {} – (message: {}, author: {})\n{}".format(m.author.name,m.author.discriminator,m.timestamp,m.id,m.author.id,m.content)
		for a in m.attachments:
			text = text+"\nAttachment: {}".format(a)
		for e in m.embeds:
			text = text+"\nEmbed: {}".format(e)
		text = text+"\n\n"
		return text

	def generate_header(self, chan, title):
		text = "***********************************************************"
		text = text+"\n* Server: {} ({})".format(chan.guild.name,chan.guild.id)
		text = text+"\n* Channel: {} ({})".format(chan.name,chan.id)
		text = text+"\n* {}".format(title)
		text = text+"\n***********************************************************"
		text = text+"\n\n"
		return text

	def generate_filename(self, chan, suffix):
		fn = chan.server.name.lower().strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_")
		fn = fn+"_"+chan.name.lower().strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_")
		fn = fn+"_"+suffix+".txt"
		return fn

	@praxisbot.command
	@praxisbot.permission_admin
	async def execute_archive_all(self, scope, command, options, lines, **kwargs):
		"""
		Create a text file containing all messages.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('--channel', '-c', help='Channel to archive')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return scope

		if args.channel:
			chan = scope.shell.find_channel(args.channel, scope.server)
		else:
			chan = scope.channel

		if not chan:
			await scope.shell.print_error(scope, "Unknown channel. {}".format(args.channel))
			return

		if scope.permission < praxisbot.UserPermission.Script and not chan.permissions_for(scope.user).read_messages:
			await scope.shell.print_permission(scope, "You don't have read permission in this channel.")
			return

		messages = await scope.shell.client.pins_from(chan)
		counter = 0
		d = str(datetime.datetime.now())
		textHeader = self.generate_header(chan, "Last messages before "+d)

		b = datetime.datetime.now()
		newmessages = True
		text = ""
		while counter < 10000 and newmessages:
			newmessages = False
			async for m in scope.shell.client.logs_from(chan, limit=200, before=b):
				counter = counter+1
				text = self.archive_message(m)+text
				b = m
				newmessages = True

		f = io.BytesIO((textHeader+text).encode('UTF-8'))
		await scope.shell.client.send_file(scope.channel, f, filename=self.generate_filename(chan, d), content=str(counter)+" messages archived.")
		f.close()

	@praxisbot.command
	async def execute_archive_last_day(self, scope, command, options, lines, **kwargs):
		"""
		Create a text file containing all messages from the last 24h.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('--channel', '-c', help='Channel to archive')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return scope

		if args.channel:
			chan = scope.shell.find_channel(args.channel, scope.server)
		else:
			chan = scope.channel

		if not chan:
			await scope.shell.print_error(scope, "Unknown channel. {}".format(args.channel))
			return

		if scope.permission < praxisbot.UserPermission.Script and not chan.permissions_for(scope.user).read_messages:
			await scope.shell.print_permission(scope, "You don't have read permission in this channel.")
			return

		messages = await scope.shell.client.pins_from(chan)
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
			async for m in scope.shell.client.logs_from(chan, limit=200, before=b):
				counter = counter+1
				text = self.archive_message(m)+text
				b = m
				timecur = m.timestamp
				newmessages = True

		f = io.BytesIO((textHeader+text).encode('UTF-8'))
		await scope.shell.client.send_file(scope.channel, f, filename=self.generate_filename(chan, d), content=str(counter)+" messages archived.")
		f.close()

	@praxisbot.command
	async def execute_archive_pins(self, scope, command, options, lines, **kwargs):
		"""
		Create a text file containing all pinned messages.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		parser.add_argument('--channel', '-c', help='Channel to archive')
		args = await self.parse_options(scope, parser, options)
		if not args:
			return scope

		if args.channel:
			chan = scope.shell.find_channel(args.channel, scope.server)
		else:
			chan = scope.channel

		if not chan:
			await scope.shell.print_error(scope, "Unknown channel. {}".format(args.channel))
			return

		if scope.permission < praxisbot.UserPermission.Script and not chan.permissions_for(scope.user).read_messages:
			await scope.shell.print_permission(scope, "You don't have read permission in this channel.")
			return

		messages = await scope.shell.client.pins_from(chan)
		counter = 0
		textHeader = self.generate_header(chan, "Pinned messages")
		text = ""
		for m in messages:
			counter = counter+1
			text = self.archive_message(m)+text

		f = io.BytesIO((textHeader+text).encode('UTF-8'))
		await scope.shell.client.send_file(scope.channel, f, filename=self.generate_filename(chan, "pins"), content=str(counter)+" pinned messages archived.")
		f.close()
