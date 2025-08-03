#include <bits/stdc++.h>
using namespace std;

int main(int argc, char** argv) {
    ifstream test_out(argv[2]);
    ifstream user_ans(argv[3]);
	long double Answer, Output;

    test_out >> Output;
    user_ans >> Answer;

	long double Ae = abs(Answer - Output);
	long double Re = Ae / Answer;

	if (Ae <= 0.000001 || Re <= 0.000001) {
        puts("1.0");
	} else {
        puts("0.0");
	}
    return 0;
}
