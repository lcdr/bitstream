import random
import unittest

from bitstream import c_uint, ReadStream, WriteStream

class ReadStreamTest(unittest.TestCase):
	def setUp(self):
		self.locked = ReadStream(b"test")
		self.unlocked = ReadStream(b"test", unlocked=True)

	def test_read_offset(self):
		with self.assertRaises(RuntimeError):
			self.locked.read_offset
		self.assertEqual(self.unlocked.read_offset, 0)

		with self.assertRaises(RuntimeError):
			self.locked.read_offset = 1
		self.unlocked.read_offset = 1
		self.assertEqual(self.unlocked.read_offset, 1)

	def test_align_read(self):
		self.unlocked.read_offset = 5
		self.unlocked.align_read()
		self.assertEqual(self.unlocked.read_offset, 8)

	def test_skip_read(self):
		self.unlocked.skip_read(4)
		self.assertEqual(self.unlocked.read_offset, 32)

	def test_all_read(self):
		self.assertFalse(self.locked.all_read())
		self.locked.skip_read(4)
		self.assertTrue(self.locked.all_read())

	def test_read_remaining(self):
		self.assertEqual(self.locked.read_remaining(), b"test")


class WriteStreamTest(unittest.TestCase):
	def setUp(self):
		self.stream = WriteStream()

	def test_cast_multiple(self):
		bytes(self.stream)
		with self.assertRaises(RuntimeError):
			bytes(self.stream)

	def test_align_write(self):
		self.stream.write_bits(255, 5)
		self.stream.align_write()
		self.assertEqual(bytes(self.stream), b"\xf8")

class _BitStream(WriteStream, ReadStream):
	def __init__(self):
		super().__init__()
		self._unlocked = False
		self._read_offset = 0

class BitStreamTest(unittest.TestCase):
	def setUp(self):
		self.stream = _BitStream()
		shift = random.randrange(0, 8)
		if shift > 0:
			self.stream.write_bits(0xff, shift)
			self.stream.read_bits(shift)

class GeneralTest(BitStreamTest):
	def test_compressed(self):
		value = 42
		self.stream.write_compressed(c_uint(value))
		self.assertEqual(self.stream.read_compressed(c_uint), value)
		value = 1 << 16
		self.stream.write_compressed(c_uint(value))
		self.assertEqual(self.stream.read_compressed(c_uint), value)

	def test_read_bytes_too_much(self):
		with self.assertRaises(EOFError):
			self.stream.read(bytes, length=2)

	def test_read_bytes_too_much_shifted(self):
		self.stream.write_bits(0xff, 1)
		self.stream.read_bits(1)
		with self.assertRaises(EOFError):
			self.stream.read(bytes, length=1)

	def test_unaligned_bits(self):
		self.stream.align_write()
		self.stream.align_read()
		self.stream.write_bits(0xff, 7)
		self.stream.write_bits(0xff, 7)
		self.stream.read_bits(7)
		self.assertEqual(self.stream.read_bits(4), 0x0f)

class StringTest:
	STRING = None

	@classmethod
	def setUpClass(cls):
		if isinstance(cls.STRING, str):
			cls.CHAR_SIZE = 2
		else:
			cls.CHAR_SIZE = 1

	def test_write_allocated_long(self):
		with self.assertRaises(ValueError):
			self.stream.write(self.STRING, allocated_length=len(self.STRING)-2)

	def test_allocated(self):
		self.stream.write(self.STRING, allocated_length=len(self.STRING) + 10)
		value = self.stream.read(type(self.STRING), allocated_length=len(self.STRING)+10)
		self.assertEqual(value, self.STRING)

	def test_read_allocated_buffergarbage(self):
		self.stream.write(self.STRING, allocated_length=len(self.STRING)+1)
		self.stream.write(b"\xdf"*10*self.CHAR_SIZE)
		value = self.stream.read(type(self.STRING), allocated_length=len(self.STRING)+1+10)
		self.assertEqual(value, self.STRING)

	def test_read_allocated_no_terminator(self):
		self.stream.write(b"\xff"*33*self.CHAR_SIZE)
		with self.assertRaises(RuntimeError):
			self.stream.read(type(self.STRING), allocated_length=33)

	def test_variable_length(self):
		self.stream.write(self.STRING, length_type=c_uint)
		value = self.stream.read(type(self.STRING), length_type=c_uint)
		self.assertEqual(value, self.STRING)

class UnicodeStringTest(StringTest, BitStreamTest):
	STRING = "Hello world"

class ByteStringTest(StringTest, BitStreamTest):
	STRING = UnicodeStringTest.STRING.encode("latin1")
