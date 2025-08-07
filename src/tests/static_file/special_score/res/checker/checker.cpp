#include <bits/stdc++.h>
using namespace std;

int main(int argc, char **argv) {
    std::ifstream user_ans_file(argv[3]);

    double score = 0;
    user_ans_file >> score;

    cout << "CF;" << score << ";" << (score >= 100 ? "AC": "PC") << endl;
    cerr << "special score test" << endl;

    return 0;
}
