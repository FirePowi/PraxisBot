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
import discord
from sympy import preview
from sympy import sympify
from sympy.parsing.sympy_parser import parse_expr
from sympy.printing.str import sstrrepr
import praxisbot
from io import BytesIO

class MathPlugin(praxisbot.Plugin):
	"""
	Math commands
	"""

	name = "Math"

	def __init__(self, shell):
		super().__init__(shell)

		self.latex_preamble = r"""
\documentclass[17pt]{extarticle}
\pagestyle{empty}
\usepackage{amsmath}
\usepackage{amsfonts}
\usepackage{framed}
\setlength\FrameSep{1.0em}
\setlength\OuterFrameSep{\partopsep}
\begin{document}
"""

		self.add_command("latex", self.execute_latex)
		self.add_command("math", self.execute_math)

	@praxisbot.command
	async def execute_math(self, scope, command, options, lines, **kwargs):
		"""
		Evaluate math expressions.
		"""

		input = options+"\n".join(lines)

		try:
			expr = parse_expr(scope.format_text(input))
		except:
			await scope.shell.print_error(scope, "Invalid math expression.")
			return

		try:
			res = sstrrepr(expr)
			scope.vars["results"] = res
			await scope.shell.print_info(scope, "```\n"+res+"```")
		except:
			await scope.shell.print_error(scope, "Impossible to generate text from the result.")
			return

	@praxisbot.command
	async def execute_latex(self, scope, command, options, lines, **kwargs):
		"""
		Latex expressions.
		"""

		latex_code = options+"\n".join(lines)

		stream = BytesIO()
		try:
			preview("\\begin{framed}\n\\begin{equation*}\n"+latex_code+"\n\\end{equation*}\\end{framed}", output='png', viewer='BytesIO', outputbuffer=stream, preamble=self.latex_preamble)
			stream.seek(0)
			await scope.shell.client.send_file(scope.channel, stream, filename="math.png")
			stream.close()
		except:
			await scope.shell.print_error(scope, "Invalid latex expression")
			return
