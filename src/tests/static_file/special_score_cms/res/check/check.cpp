#include <bits/stdc++.h>
using namespace std;

int main(int argc, char **argv) {
    std::ifstream user_ans_file(argv[3]);

    double score = 0;
    user_ans_file >> score;

    double final_score = 0;
    if (score >= 100.0)
        final_score = 1.0;
    else {
        final_score = score / 100.0;
    }

    cout << "CMS;" << final_score << ";" << (score >= 100 ? "AC": "PC") << endl;
    cerr << "special score (CMS) test" << endl;

    return 0;
}
