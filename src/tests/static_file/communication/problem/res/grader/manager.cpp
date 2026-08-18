#include <algorithm>
#include <fstream>
#include <iostream>

int main(int argc, char **argv) {
    if (argc != 3) return 1;

    std::ofstream to_user(argv[2]);
    std::ifstream from_user(argv[1]);
    int target, answer;
    if (!(std::cin >> target)) return 1;
    to_user << target << std::endl;
    if (!(from_user >> answer)) return 1;

    double score = static_cast<double>(answer) / target;
    std::cout << std::clamp(score, 0.0, 1.0) << std::endl;
}
