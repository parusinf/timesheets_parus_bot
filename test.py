import unittest
from cp1251 import encode_cp1251


class TestSum(unittest.TestCase):

    def test_encode_cp1251(self):
        self.assertEqual(
            encode_cp1251('тест'),
            bytearray.fromhex('f2e5f1f2'),
            'В кодировке cp1251 "тест" должен быть "f2e5f1f2"'
        )


if __name__ == '__main__':
    unittest.main()
