int query(int k);

int answer() {
    long long ret{};
    long long start{0}, end{2147483647}, mid{};
    while (start <= end) {
        mid = start + (end - start) / 2;
        //std::cout << mid << '\n';
        int result = query(mid);
        if (result == -1) {
            start = mid + 1;
        } else if (result == 1) {
            end = mid - 1;
        } else {
            ret = mid;
            break;
        }
    }
    return ret;
}