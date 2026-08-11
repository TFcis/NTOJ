MAX_PARSED_LIST_ITEMS = 10_000

def parse_str_to_list(s: str, *, max_items: int = MAX_PARSED_LIST_ITEMS) -> list[int]:
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
        max_items (int): Maximum number of integers to materialize.

    Returns:
        list[int]: A list of parsed integers.

    Raises:
        ValueError: If max_items is negative or the expanded result is too large.
    """

    if max_items < 0:
        raise ValueError("max_items must not be negative")

    parsed_segments: list[tuple[int, int]] = []
    parsed_items = 0
    for num in s.replace(" ", "").split(","):
        if num.isnumeric():
            try:
                value = int(num)
            except ValueError:
                continue
            left = value
            right = value
        else:
            try:
                l, r = num.split("-")
                l = int(l)
                r = int(r)
            except ValueError:
                continue

            if l > r:
                l, r = r, l
            left = l
            right = r

        segment_items = right - left + 1
        if parsed_items + segment_items > max_items:
            raise ValueError(f"parsed list exceeds the {max_items} item limit")
        parsed_segments.append((left, right))
        parsed_items += segment_items

    result = []
    for left, right in parsed_segments:
        result.extend(range(left, right + 1))

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
