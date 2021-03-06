from __future__ import print_function, division, absolute_import
from fontTools.misc.py23 import *
from fontTools import ttLib
from fontTools.misc.textTools import safeEval
from fontTools.ttLib.tables.DefaultTable import DefaultTable
import os


class TTXParseError(Exception): pass

BUFSIZE = 0x4000


class XMLReader(object):

	def __init__(self, fileOrPath, ttFont, progress=None, quiet=False):
		if fileOrPath == '-':
			fileOrPath = sys.stdin
		if not hasattr(fileOrPath, "read"):
			self.file = open(fileOrPath, "rb")
			self._closeStream = True
		else:
			# assume readable file object
			self.file = fileOrPath
			self._closeStream = False
		self.ttFont = ttFont
		self.progress = progress
		self.quiet = quiet
		self.root = None
		self.contentStack = []
		self.stackSize = 0

	def read(self):
		if self.progress:
			self.file.seek(0, 2)
			fileSize = self.file.tell()
			self.progress.set(0, fileSize // 100 or 1)
			self.file.seek(0)
		self._parseFile(self.file)
		if self._closeStream:
			self.close()

	def close(self):
		self.file.close()

	def _parseFile(self, file):
		from xml.parsers.expat import ParserCreate
		parser = ParserCreate()
		parser.StartElementHandler = self._startElementHandler
		parser.EndElementHandler = self._endElementHandler
		parser.CharacterDataHandler = self._characterDataHandler

		pos = 0
		while True:
			chunk = file.read(BUFSIZE)
			if not chunk:
				parser.Parse(chunk, 1)
				break
			pos = pos + len(chunk)
			if self.progress:
				self.progress.set(pos // 100)
			parser.Parse(chunk, 0)

	def _startElementHandler(self, name, attrs):
		stackSize = self.stackSize
		self.stackSize = stackSize + 1
		if not stackSize:
			if name != "ttFont":
				raise TTXParseError("illegal root tag: %s" % name)
			sfntVersion = attrs.get("sfntVersion")
			if sfntVersion is not None:
				if len(sfntVersion) != 4:
					sfntVersion = safeEval('"' + sfntVersion + '"')
				self.ttFont.sfntVersion = sfntVersion
			self.contentStack.append([])
		elif stackSize == 1:
			subFile = attrs.get("src")
			if subFile is not None:
				if hasattr(self.file, 'name'):
					# if file has a name, get its parent directory
					dirname = os.path.dirname(self.file.name)
				else:
					# else fall back to using the current working directory
					dirname = os.getcwd()
				subFile = os.path.join(dirname, subFile)
				subReader = XMLReader(subFile, self.ttFont, self.progress, self.quiet)
				subReader.read()
				self.contentStack.append([])
				return
			tag = ttLib.xmlToTag(name)
			msg = "Parsing '%s' table..." % tag
			if self.progress:
				self.progress.setLabel(msg)
			elif self.ttFont.verbose:
				ttLib.debugmsg(msg)
			else:
				if not self.quiet:
					print(msg)
			if tag == "GlyphOrder":
				tableClass = ttLib.GlyphOrder
			elif "ERROR" in attrs or ('raw' in attrs and safeEval(attrs['raw'])):
				tableClass = DefaultTable
			else:
				tableClass = ttLib.getTableClass(tag)
				if tableClass is None:
					tableClass = DefaultTable
			if tag == 'loca' and tag in self.ttFont:
				# Special-case the 'loca' table as we need the
				#    original if the 'glyf' table isn't recompiled.
				self.currentTable = self.ttFont[tag]
			else:
				self.currentTable = tableClass(tag)
				self.ttFont[tag] = self.currentTable
			self.contentStack.append([])
		elif stackSize == 2:
			self.contentStack.append([])
			self.root = (name, attrs, self.contentStack[-1])
		else:
			l = []
			self.contentStack[-1].append((name, attrs, l))
			self.contentStack.append(l)

	def _characterDataHandler(self, data):
		if self.stackSize > 1:
			self.contentStack[-1].append(data)

	def _endElementHandler(self, name):
		self.stackSize = self.stackSize - 1
		del self.contentStack[-1]
		if self.stackSize == 1:
			self.root = None
		elif self.stackSize == 2:
			name, attrs, content = self.root
			self.currentTable.fromXML(name, attrs, content, self.ttFont)
			self.root = None


class ProgressPrinter(object):

	def __init__(self, title, maxval=100):
		print(title)

	def set(self, val, maxval=None):
		pass

	def increment(self, val=1):
		pass

	def setLabel(self, text):
		print(text)
