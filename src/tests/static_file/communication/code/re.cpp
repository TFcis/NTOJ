#include <fstream>

int main(int argc, char **argv) {
    std::ifstream from_manager(argv[1]);
    std::ofstream to_manager(argv[2]);
    int target;
    from_manager >> target;
    return 1;
}
