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
from pytz import timezone
from dateutil.relativedelta import relativedelta
import io
import praxisbot

class ActivityPlugin(praxisbot.Plugin):
	"""
	Activity commands
	"""

	name = "Activity"

	def __init__(self, shell):
		super().__init__(shell)

		self.add_command("activity_day", self.execute_activity_day)
		self.add_command("activity_month", self.execute_activity_month)
		self.add_command("activity_year", self.execute_activity_year)

	async def display_counters(self, scope, counters, counter_max, title, format):
		stream = praxisbot.MessageStream(scope)
		await stream.send("__**"+title+"**__")

		for counter in counters:
			text = "\nFrom "

			start_date = counter["start_date"]
			start_date = timezone('UTC').localize(start_date)
			start_date = start_date.astimezone(timezone('Europe/Paris'))
			text = text+start_date.strftime(format)

			text = text+" to "

			end_date = counter["end_date"]
			end_date = timezone('UTC').localize(end_date)
			end_date = end_date.astimezone(timezone('Europe/Paris'))
			text = text+end_date.strftime(format)

			text = text+" "

			nb_box = int(20.0*counter["counter"]/counter_max)
			nb_empty = 20-nb_box

			for i in range(0, nb_box):
				text = text+"█"
			for i in range(0, nb_empty):
				text = text+"▁"

			text = text+" "+str(counter["counter"])+" messages"

			await stream.send_monospace(text)

		await stream.finish()

	@praxisbot.command
	async def execute_activity_day(self, scope, command, options, lines, **kwargs):
		"""
		Display server activity during the last month.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return scope

		counters = []
		counter_max = 0
		for i in range(1, 25):
			start_date = datetime.datetime.utcnow() - relativedelta(hours=i)
			end_date = datetime.datetime.utcnow() - relativedelta(hours=i-1)
			counter = 0
			try:
				counter = await scope.shell.client_human.count_messages(scope.server, after=start_date, before=end_date)
			except:
				pass
			if counter > counter_max:
				counter_max = counter
			counters.append({"counter":counter, "start_date":start_date, "end_date":end_date})

		await self.display_counters(scope, counters, counter_max, "Server activity during the last 24 hours", "%H:%M")

	@praxisbot.command
	async def execute_activity_month(self, scope, command, options, lines, **kwargs):
		"""
		Display server activity during the last month.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return scope

		counters = []
		counter_max = 0
		for i in range(1, 31):
			start_date = datetime.datetime.utcnow() - relativedelta(days=i)
			end_date = datetime.datetime.utcnow() - relativedelta(days=i-1)
			counter = 0
			try:
				counter = await scope.shell.client_human.count_messages(scope.server, after=start_date, before=end_date)
			except:
				pass
			if counter > counter_max:
				counter_max = counter
			counters.append({"counter":counter, "start_date":start_date, "end_date":end_date})

		await self.display_counters(scope, counters, counter_max, "Server activity during the last 30 days", "%Y-%m-%d")

	@praxisbot.command
	async def execute_activity_year(self, scope, command, options, lines, **kwargs):
		"""
		Display server activity during the last year.
		"""

		parser = argparse.ArgumentParser(description=kwargs["description"], prog=command)
		args = await self.parse_options(scope, parser, options)
		if not args:
			return scope

		counters = []
		counter_max = 0
		for i in range(1, 13):
			start_date = datetime.datetime.utcnow() - relativedelta(months=i)
			end_date = datetime.datetime.utcnow() - relativedelta(months=i-1)
			counter = 0
			try:
				counter = await scope.shell.client_human.count_messages(scope.server, after=start_date, before=end_date)
			except:
				pass
			if counter > counter_max:
				counter_max = counter
			counters.append({"counter":counter, "start_date":start_date, "end_date":end_date})

		await self.display_counters(scope, counters, counter_max, "Server activity during the last year", "%Y-%m-%d")
