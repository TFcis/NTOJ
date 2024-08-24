import unittest


def parse_list_str(s: str) -> list[int]:
    s = s.replace(' ', '').split(',')

    l = []
    for num in s:
        if num.isnumeric():
            l.append(int(num))
        elif num.find('..') != -1:
            tmp: list[str] = num.split('..')
            if len(tmp) != 2:
                continue

            i, j = tmp
            if not i.isnumeric():
                continue
            i = int(i)

            if not j.isnumeric():
                continue
            j = int(j)

            if i > j:
                i, j = j, i

            l.extend(n for n in range(i, j) if n not in l)

    return l


class TestParseMethod(unittest.TestCase):
    def test(self):
        self.assertEqual(parse_list_str('1, 2, 3, 4, 5'), [1, 2, 3, 4, 5])
        self.assertEqual(parse_list_str('1, 2, 3, 4, 5, 1..2'), [1, 2, 3, 4, 5])
        self.assertEqual(parse_list_str('1, 2, 3, 4, 5, 1..6'), [1, 2, 3, 4, 5])
        self.assertEqual(parse_list_str('1, 2, 3, 4, 5, 1..7'), [1, 2, 3, 4, 5, 6])
        self.assertEqual(parse_list_str('5..7'), [5, 6])
        self.assertEqual(parse_list_str('7..5'), [5, 6])
        self.assertEqual(parse_list_str('7.., 5'), [5])
        self.assertEqual(parse_list_str('abc, 123'), [123])
        self.assertEqual(parse_list_str('5, ...7'), [5])
        self.assertEqual(parse_list_str('fasdfa, fsadfsa, fasff, qq..ff'), [])
        self.assertEqual(parse_list_str('1.2, 3.4'), [])


if __name__ == '__main__':
    unittest.main()
