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

from subprocess import STDOUT, CalledProcessError, check_output
from sympy.utilities.misc import find_executable
from os.path import join
import tempfile
import shutil
import io
from io import BytesIO

from sympy import sympify
from sympy.parsing.sympy_parser import parse_expr
from sympy.printing.str import sstrrepr

import shlex
import argparse
import discord
import traceback
import praxisbot

class MathPlugin(praxisbot.Plugin):
	"""
	Math commands
	"""

	name = "Math"

	def __init__(self, shell):
		super().__init__(shell)

		self.add_command("latex", self.execute_latex)
		self.add_command("math", self.execute_math)
		self.add_command("chemfig", self.execute_chemfig)

	def latex_to_png(self, latex_code, stream):

		try:
			workdir = tempfile.mkdtemp()

			with io.open(join(workdir, 'texput.tex'), 'w', encoding='utf-8') as fh:
				fh.write(latex_code)

			if not find_executable('pdflatex'):
				raise RuntimeError("pdflatex program is not installed")

			if not find_executable('convert'):
				raise RuntimeError("convert program is not installed")

			try:
				check_output(['pdflatex', '-halt-on-error', '-interaction=nonstopmode', 'texput.tex', '-o', 'texput.pdf'], cwd=workdir, stderr=STDOUT)
			except CalledProcessError as e:
				raise RuntimeError(
				"'pdflatex' exited abnormally with the following output:\n%s" %
				e.output)

			try:
				check_output(['convert', '-density', '200', '-flatten', 'texput.pdf', '-quality', '90', 'texput.png'], cwd=workdir, stderr=STDOUT)
			except CalledProcessError as e:
				raise RuntimeError(
				"'convert' exited abnormally with the following output:\n%s" %
				e.output)

			with open(join(workdir, 'texput.png'), 'rb') as fh:
				stream.write(fh.read())

		finally:
			try:
				shutil.rmtree(workdir) # delete directory
			except OSError as e:
				if e.errno != 2: # code 2 - no such file or directory
					raise

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

		latex_begin = r"""
\documentclass[preview, border=4pt]{standalone}
\usepackage{amsmath}
\usepackage{amsfonts}
\begin{document}
$\displaystyle
"""

		latex_end = r"""
$
\end{document}
"""

		latex_code = latex_begin+options+"\n".join(lines)+latex_end

		stream = BytesIO()
		try:
			self.latex_to_png(latex_code, stream)
			stream.seek(0)
			await scope.shell.client.send_file(scope.channel, stream, filename="math.png")
			stream.close()
		except:
			print(traceback.format_exc())
			await scope.shell.print_error(scope, "Invalid latex expression")
			return

	@praxisbot.command
	async def execute_chemfig(self, scope, command, options, lines, **kwargs):
		"""
		Generate chimical figure.
		"""

		latex_begin = r"""
\documentclass[preview, border=4pt]{standalone}
\usepackage{amsmath}
\usepackage{amsfonts}
\usepackage{chemfig}
\begin{document}
$\displaystyle
"""

		latex_end = r"""
$
\end{document}
"""

		latex_code = latex_begin+"\\chemfig{"+options+"}"+latex_end

		stream = BytesIO()
		try:
			self.latex_to_png(latex_code, stream)
			stream.seek(0)
			await scope.shell.client.send_file(scope.channel, stream, filename="math.png")
			stream.close()
		except:
			print(traceback.format_exc())
			await scope.shell.print_error(scope, "Invalid latex expression")
			return
