def parse_str_to_list(s: str) -> list[int]:
    """
    Parses a string of numbers and ranges into a list of integers.

    The input string may contain comma-separated values, with optional ranges
    specified using hyphens (e.g., "1,2,4-6,10"). Whitespace is ignored.
    Invalid segments are skipped.

    Examples:
        "1, 2,  4-6" -> [1, 2, 4, 5, 6]
        "3-1,7"   -> [1, 2, 3, 7]

    Args:
        s (str): A string containing numbers and/or numeric ranges.

    Returns:
        list[int]: A list of parsed integers.
    """

    s = s.replace(" ", "").split(",")

    result = []
    for num in s:
        if num.isnumeric():
            result.append(int(num))
        else:
            try:
                l, r = num.split("-")
                l = int(l)
                r = int(r)
            except ValueError:
                continue

            if l > r:
                l, r = r, l

            result.extend(range(l, r + 1))

    return result


def merge_list_to_str(nums: list[int]) -> str:
    """
    Merges consecutive integers in a list into range format.

    For example, [3, 6, 7, 8, 9, 11, 13, 15] becomes '3,6-9,11,13,15'.

    Args:
        a (List[int]): A list of integers.

    Returns:
        str: A string with consecutive numbers merged as ranges.
    """

    if not nums:
        return ""

    nums.sort()
    result = []
    start = nums[0]
    end = nums[0]

    for n in nums[1:]:
        if n == end + 1:
            end = n
        else:
            if start == end:
                result.append(str(start))
            else:
                result.append(f"{start}-{end}")
            start = end = n

    if start == end:
        result.append(str(start))
    else:
        result.append(f"{start}-{end}")

    return ",".join(result)
